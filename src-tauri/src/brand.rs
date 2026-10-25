//! What this build calls itself where people see it (tray, window titles, media controls,
//! notifications) and the id the desktop knows it by: ytminamp's, in one place, so the upstream
//! files that show a name change by one identifier each.

/// The name people see.
pub const NAME: &str = "YTMinamp (limusic)";
/// The installed `.desktop` file's name (`productName` in tauri.conf.json), and the tray and
/// media-controls (MPRIS) id: not Limusic's, so both can run side by side.
pub const ID: &str = "ytminamp";

/// The newest published ytminamp release's tag (`v1.3.0-ytminamp.6`), or `None` if there is none.
///
/// Replaces Limusic's update check, which reads Limusic's own releases and signed manifests:
/// left as it was, an upstream release would offer Limusic's download page to ytminamp, and the
/// beta channel would install Limusic over it. ytminamp's builds aren't signed for the updater,
/// so this only finds the version; the banner links to the download page. Drafts and pre-releases
/// don't count. An answer is reused for [`RELEASE_FRESH_FOR`] rather than the whole run, so a
/// session left open for days still hears of a new release; `fresh` (Check for updates) always
/// asks.
#[tauri::command]
pub async fn latest_release(fresh: Option<bool>) -> Result<Option<String>, String> {
    type Answer = Option<(std::time::Instant, Option<String>)>;
    static CACHE: std::sync::Mutex<Answer> = std::sync::Mutex::new(None);
    if !fresh.unwrap_or(false) {
        if let Some((at, tag)) = CACHE.lock().unwrap().as_ref() {
            if at.elapsed() < RELEASE_FRESH_FOR {
                return Ok(tag.clone());
            }
        }
    }
    #[derive(serde::Deserialize)]
    struct GhRelease {
        tag_name: String,
        draft: bool,
        prerelease: bool,
    }
    let releases: Vec<GhRelease> = crate::http::client()
        .get("https://api.github.com/repos/ergosteur/YTMinamp-limusic/releases?per_page=30")
        .header("User-Agent", concat!("ytminamp/", env!("CARGO_PKG_VERSION")))
        .header("Accept", "application/vnd.github+json")
        .timeout(std::time::Duration::from_secs(15))
        .send()
        .await
        .map_err(|e| e.to_string())?
        .error_for_status()
        .map_err(|e| e.to_string())?
        .json()
        .await
        .map_err(|e| e.to_string())?;
    let newest = releases
        .into_iter()
        .filter(|r| !r.draft && !r.prerelease)
        .filter_map(|r| release_key(&r.tag_name).map(|k| (k, r.tag_name)))
        .max_by_key(|(k, _)| *k)
        .map(|(_, tag)| tag);
    *CACHE.lock().unwrap() = Some((std::time::Instant::now(), newest.clone()));
    Ok(newest)
}

/// How long [`latest_release`]'s answer is reused.
const RELEASE_FRESH_FOR: std::time::Duration = std::time::Duration::from_secs(15 * 60);

/// `v1.3.0-ytminamp.6` → `(1, 3, 0, 6)`, which sorts in release order. Other tags → `None`.
fn release_key(tag: &str) -> Option<(u32, u32, u32, u32)> {
    let (version, n) = tag.trim_start_matches('v').split_once("-ytminamp.")?;
    let mut parts = version.split('.').map(|p| p.parse().ok());
    let key = (parts.next()??, parts.next()??, parts.next()??, n.parse().ok()?);
    parts.next().is_none().then_some(key)
}

#[cfg(test)]
mod tests {
    use super::release_key;

    #[test]
    fn release_tags_sort_in_release_order() {
        assert_eq!(release_key("v1.3.0-ytminamp.6"), Some((1, 3, 0, 6)));
        assert!(release_key("v1.3.0-ytminamp.10") > release_key("v1.3.0-ytminamp.9"));
        assert!(release_key("v1.3.1-ytminamp.1") > release_key("v1.3.0-ytminamp.10"));
        assert_eq!(release_key("v1.3.0"), None);
        assert_eq!(release_key("v1.3.0-rc.8"), None);
        assert_eq!(release_key("v1.3-ytminamp.1"), None);
    }
}
