//! Internet radio (YTMinamp): Icecast/SHOUTcast streams as queue items, Winamp's oldest trick.
//!
//! Rides the local-files pattern (local.rs): a station is a `SongItem` whose `video_id` is
//! `RADIO:<stream or playlist url>`, intercepted in `AppState::resolve` before anything
//! YouTube-shaped runs, and handed to mpv as is. Playlist files (.m3u, .m3u8, .pls) become one
//! station per entry; a playlist *URL* (SHOUTcast's `tunein-station.m3u`, TuneIn's `Tune.ashx`)
//! stays one station and is fetched at play time, since what it points at moves.
//!
//! A station has no length and doesn't end: the hooks in state.rs keep it out of the lookahead,
//! history, scrobbling and autoplay, reconnect it when it drops, and never resume it at a
//! position. mpv's ICY `icy-title` becomes the row's title (the station name stays as its
//! artist), as Winamp shows the stream's song.

use std::collections::HashMap;
use std::path::Path;
use std::sync::Mutex;
use std::time::{Duration, Instant};

use innertube::SongItem;

use crate::orchestrator::{PlaybackData, ResolveError};

/// A station's synthetic videoId: this prefix + its URL.
pub const PREFIX: &str = "RADIO:";

/// Sent to stations: some Icecast servers refuse requests without a player-like User-Agent, and
/// mpv's headers are global, so without one a station would inherit the last YouTube client's.
const USER_AGENT: &str = "YTMinamp/1.0 (Winamp-compatible; like WACUP)";

/// The largest playlist read, from disk or the network: station lists are a few KB.
const MAX_PLAYLIST_BYTES: usize = 1 << 20;

pub fn is_station(video_id: &str) -> bool {
    video_id.starts_with(PREFIX)
}

/// The URL behind a station's videoId, or `None` when this isn't one.
pub fn station_url(video_id: &str) -> Option<&str> {
    video_id.strip_prefix(PREFIX)
}

/// Not something YouTube knows: a local file or a station. What the YouTube-only paths (autoplay,
/// ratings, lyrics, music videos) skip.
pub fn not_youtube(video_id: &str) -> bool {
    crate::local::is_local_song(video_id) || is_station(video_id)
}

fn is_http(s: &str) -> bool {
    let l = s.get(..8).unwrap_or(s).to_ascii_lowercase();
    l.starts_with("http://") || l.starts_with("https://")
}

/// A station row: the name as its title until the stream says what's playing (then the name moves
/// to `artists`, see `stream_title`).
pub fn station(name: &str, url: &str) -> SongItem {
    let name = name.trim();
    SongItem {
        video_id: format!("{PREFIX}{}", url.trim()),
        title: if name.is_empty() { url.trim().to_owned() } else { name.to_owned() },
        artists: String::new(),
        ..Default::default()
    }
}

/// The row once the stream names its song: the song as the title, the station as the artist.
/// The station's name is the title until the first song, the artist after.
pub fn retitle(item: &mut SongItem, icy_title: &str) {
    let song = icy_title.trim();
    let name = if item.artists.is_empty() { item.title.clone() } else { item.artists.clone() };
    if song.is_empty() {
        item.title = name;
        item.artists = String::new();
    } else {
        item.title = song.to_owned();
        item.artists = name;
    }
}

/// A playlist's entries as (title, location), in order: M3U/M3U8 (`#EXTINF:-1,Title` before each
/// location, or bare locations) and PLS (`FileN=` / `TitleN=`). Locations are kept as written.
pub fn parse_playlist(text: &str) -> Vec<(String, String)> {
    let text = text.trim_start_matches('\u{feff}');
    if text.lines().any(|l| l.trim().eq_ignore_ascii_case("[playlist]")) {
        return parse_pls(text);
    }
    let mut out = Vec::new();
    let mut title = String::new();
    for line in text.lines().map(str::trim) {
        if let Some(info) = line.strip_prefix("#EXTINF:") {
            title = info.split_once(',').map(|(_, t)| t.trim().to_owned()).unwrap_or_default();
        } else if line.is_empty() || line.starts_with('#') {
            continue;
        } else {
            out.push((std::mem::take(&mut title), line.to_owned()));
        }
    }
    out
}

fn parse_pls(text: &str) -> Vec<(String, String)> {
    let mut files: HashMap<u32, String> = HashMap::new();
    let mut titles: HashMap<u32, String> = HashMap::new();
    for line in text.lines().map(str::trim) {
        let Some((key, value)) = line.split_once('=') else { continue };
        let key = key.trim().to_ascii_lowercase();
        let entry = |p: &str| key.strip_prefix(p).and_then(|n| n.parse::<u32>().ok());
        if let Some(n) = entry("file") {
            files.insert(n, value.trim().to_owned());
        } else if let Some(n) = entry("title") {
            titles.insert(n, value.trim().to_owned());
        }
    }
    let mut keys: Vec<u32> = files.keys().copied().collect();
    keys.sort_unstable();
    keys.into_iter()
        .map(|n| (titles.remove(&n).unwrap_or_default(), files.remove(&n).unwrap_or_default()))
        .collect()
}

/// An HLS media playlist is a stream, not a list of stations: mpv plays the URL itself.
fn is_hls(text: &str) -> bool {
    text.contains("#EXT-X-")
}

/// Whether a URL names a playlist rather than a stream, by its path's extension.
fn looks_like_playlist(url: &str) -> bool {
    let path = url.split(['?', '#']).next().unwrap_or(url).to_ascii_lowercase();
    [".m3u", ".m3u8", ".pls"].iter().any(|ext| path.ends_with(ext))
        || path.contains("tune.ashx")
        || url.to_ascii_lowercase().contains("ext=.m3u")
        || url.to_ascii_lowercase().contains("ext=.pls")
}

/// The stations in a playlist file on disk. Entries that aren't web streams (local paths) are
/// skipped for now: the files in a playlist would need the local library's tags.
pub fn stations_from_file(path: &Path) -> Result<Vec<SongItem>, String> {
    let bytes = std::fs::read(path).map_err(|e| format!("could not read {}: {e}", path.display()))?;
    if bytes.len() > MAX_PLAYLIST_BYTES {
        return Err(format!("{} is too large for a playlist", path.display()));
    }
    let text = String::from_utf8_lossy(&bytes);
    let stations: Vec<SongItem> = parse_playlist(&text)
        .into_iter()
        .filter(|(_, loc)| is_http(loc))
        .map(|(title, loc)| station(&title, &loc))
        .collect();
    if stations.is_empty() {
        return Err(format!("no internet radio streams in {}", path.display()));
    }
    Ok(stations)
}

/// The station(s) behind a URL someone typed or pasted: a stream is one station; a playlist URL
/// is opened and becomes its stations. `None` when it isn't a web URL at all.
pub async fn stations_from_url(url: &str) -> Option<Result<Vec<SongItem>, String>> {
    let url = url.trim();
    if !is_http(url) {
        return None;
    }
    if !looks_like_playlist(url) {
        return Some(Ok(vec![station("", url)]));
    }
    Some(match fetch_text(url).await {
        Ok(text) if is_hls(&text) => Ok(vec![station("", url)]),
        Ok(text) => {
            let stations: Vec<SongItem> = parse_playlist(&text)
                .into_iter()
                .filter(|(_, loc)| is_http(loc))
                .map(|(title, loc)| station(&title, &loc))
                .collect();
            if stations.is_empty() {
                Err(format!("no streams in {url}"))
            } else {
                Ok(stations)
            }
        }
        Err(e) => Err(e),
    })
}

async fn fetch_text(url: &str) -> Result<String, String> {
    let resp = crate::http::client()
        .get(url)
        .header(reqwest::header::USER_AGENT, USER_AGENT)
        .timeout(Duration::from_secs(15))
        .send()
        .await
        .and_then(reqwest::Response::error_for_status)
        .map_err(|e| format!("could not open {url}: {e}"))?;
    if resp.content_length().is_some_and(|n| n as usize > MAX_PLAYLIST_BYTES) {
        return Err(format!("{url} is too large for a playlist"));
    }
    // A stream mislabelled as a playlist would never end: read a bounded amount.
    let mut body = Vec::new();
    let mut resp = resp;
    while let Some(chunk) = resp.chunk().await.map_err(|e| format!("could not read {url}: {e}"))? {
        body.extend_from_slice(&chunk);
        if body.len() > MAX_PLAYLIST_BYTES {
            return Err(format!("{url} is not a playlist"));
        }
    }
    Ok(String::from_utf8_lossy(&body).into_owned())
}

/// Everything the player needs for a station: its stream URL (a playlist URL is opened for its
/// first stream) and a User-Agent of its own.
pub async fn playback_data(video_id: &str, url: &str) -> Result<PlaybackData, ResolveError> {
    let mut stream = url.to_owned();
    if looks_like_playlist(url) {
        let text = fetch_text(url).await.map_err(ResolveError::AllClientsFailed)?;
        if !is_hls(&text) {
            stream = parse_playlist(&text)
                .into_iter()
                .map(|(_, loc)| loc)
                .find(|loc| is_http(loc))
                .ok_or_else(|| ResolveError::AllClientsFailed(format!("no streams in {url}")))?;
        }
    }
    Ok(PlaybackData {
        video_id: video_id.to_owned(),
        stream_url: stream,
        itag: 0,
        headers: HashMap::from([("User-Agent".to_owned(), USER_AGENT.to_owned())]),
        // Never cached (state.rs returns before the stream cache, as for local files).
        expires_in_seconds: i64::MAX / 2,
        loudness_db: None,
        playback_ping: None,
        title: None,
        artists: None,
        duration: None,
        is_video: Some(false),
        thumbnail: None,
        stream_client: "radio".to_owned(),
    })
}

/// Reconnects: a dropped station is reopened rather than skipped, but one that keeps dropping
/// (gone, or the network is) stops after a few tries a minute, as Winamp gives up on a dead one.
pub struct Reconnects(Mutex<Vec<Instant>>);

const RECONNECTS_PER_MINUTE: usize = 5;

impl Reconnects {
    pub const fn new() -> Self {
        Self(Mutex::new(Vec::new()))
    }

    /// Whether another reconnect is allowed now (and count it).
    pub fn allow(&self) -> bool {
        let mut tries = self.0.lock().unwrap();
        let now = Instant::now();
        tries.retain(|t| now.duration_since(*t) < Duration::from_secs(60));
        if tries.len() >= RECONNECTS_PER_MINUTE {
            return false;
        }
        tries.push(now);
        true
    }
}

pub static RECONNECTS: Reconnects = Reconnects::new();

/// How long to wait before reopening a dropped station.
pub const RECONNECT_DELAY: Duration = Duration::from_secs(2);

/// Tauri: the stations in a playlist file the user picked (.m3u, .m3u8, .pls).
#[tauri::command]
pub async fn radio_open_file(path: String) -> Result<Vec<SongItem>, String> {
    tauri::async_runtime::spawn_blocking(move || stations_from_file(Path::new(&path)))
        .await
        .map_err(|e| e.to_string())?
}

/// Tauri: the station(s) behind a typed URL; `None` when it isn't a web URL.
#[tauri::command]
pub async fn radio_open_url(url: String) -> Result<Option<Vec<SongItem>>, String> {
    stations_from_url(&url).await.transpose()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn m3u_entries_keep_their_titles() {
        let text = "\u{feff}#EXTM3U\n#EXTINF:-1,CFNY FM Toronto 102.1 The Edge\nhttp://live.leanstream.co/CFNYFM-MP3\n\nhttp://bare.example/stream\n";
        assert_eq!(
            parse_playlist(text),
            vec![
                ("CFNY FM Toronto 102.1 The Edge".into(), "http://live.leanstream.co/CFNYFM-MP3".into()),
                (String::new(), "http://bare.example/stream".into()),
            ]
        );
    }

    #[test]
    fn pls_entries_come_in_number_order() {
        let text = "[playlist]\nNumberOfEntries=2\nFile2=http://b/\nTitle2=B\nFile1=http://a/\nTitle1=A\nVersion=2\n";
        assert_eq!(parse_playlist(text), vec![("A".into(), "http://a/".into()), ("B".into(), "http://b/".into())]);
    }

    #[test]
    fn playlist_urls_are_told_from_streams() {
        assert!(looks_like_playlist("https://directory.shoutcast.com/sbin/tunein-station.m3u?id=1"));
        assert!(looks_like_playlist("http://opml.radiotime.com/Tune.ashx?id=s2915&partnerId=RadioTime&ext=.m3u"));
        assert!(looks_like_playlist("http://x/list.PLS"));
        assert!(!looks_like_playlist("http://live.leanstream.co/CFNYFM-MP3"));
        assert!(!looks_like_playlist("https://streaming.nrjaudio.fm/ou5k6tirv93h"));
    }

    #[test]
    fn a_station_row_takes_the_song_and_keeps_its_name() {
        let mut row = station("CFNY 102.1", "http://s/");
        assert_eq!((row.title.as_str(), row.artists.as_str()), ("CFNY 102.1", ""));
        retitle(&mut row, "Artist - Song");
        assert_eq!((row.title.as_str(), row.artists.as_str()), ("Artist - Song", "CFNY 102.1"));
        retitle(&mut row, "Other - Tune");
        assert_eq!(row.artists, "CFNY 102.1");
        retitle(&mut row, "");
        assert_eq!((row.title.as_str(), row.artists.as_str()), ("CFNY 102.1", ""));
    }

    #[test]
    fn reconnects_stop_after_a_few_a_minute() {
        let r = Reconnects::new();
        assert!((0..RECONNECTS_PER_MINUTE).all(|_| r.allow()));
        assert!(!r.allow());
    }
}
