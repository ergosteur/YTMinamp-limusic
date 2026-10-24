//! Winamp mode's audio filters: the equalizer, and spectrum data for the analyzer and the MilkDrop
//! window, all in mpv's own filter chain.
//!
//! libmpv hands out no samples, but its audio runs through ffmpeg's filter graph, and a filter's
//! measurements reach us as frame metadata (mpv's `af-metadata/<label>` property). So the first
//! time the Winamp window opens, [`start`] appends two labelled filters to the player's chain and
//! leaves them there until the app quits, so going back and forth between Winamp mode and the full
//! window never rebuilds the chain (the one moment audio can hiccup) and the EQ keeps sounding the
//! same in both:
//!
//! - `@eq`: Winamp's ten bands (`equalizer`) and preamp (`volume`), retuned live through mpv's
//!   `af-command` as the sliders move;
//! - `@viz`: splits off a mono copy, band-passes it once per analyzer bar, merges the bands back as
//!   extra channels for `astats` to measure, and drops them again. What you hear passes through
//!   untouched. Same on every OS, and only this app's audio, no OS capture. Read only while the
//!   Winamp window is open; it costs about 7% of one core (`astats` over 21 channels).
//!
//! The 19 bands sit on the 19 bars Winamp draws (75 columns in fours, Webamp's mostly-logarithmic
//! column mapping), and each band's level is scaled to what Winamp's own FFT (Nullsoft
//! vis_classic, via Webamp) would show for it: the factors were measured against a port of that
//! FFT with pink noise and check out within a few percent on white noise. Falloff and peak hold
//! stay per frame in the UI (`render/visualizer.js`).
//!
//! MilkDrop (Butterchurn) wants a waveform; there's none to be had, so it gets one made from the
//! band levels (a tone per band), which carries the bass/mid/treble the presets react to.
//!
//! mpv filters audio before its output buffer, so the levels lead what you hear; they're held
//! back by about that buffer. No filter (a libmpv without these ffmpeg filters) just means no
//! levels, and the UI falls back to test patterns.

use std::collections::VecDeque;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use tauri::{AppHandle, Emitter, Manager};

pub const EVENT: &str = "winamp-viz";
/// The made-up waveform, for the MilkDrop window (Butterchurn): 1024 bytes, silence at 128, as
/// WebAudio's `getByteTimeDomainData` gives them.
pub const WAVE_EVENT: &str = "winamp-wave";
const MILKDROP: &str = "winamp-milkdrop";

/// Analyzer columns, before Winamp groups them into 3px bars.
pub const COLUMNS: usize = 75;
/// Each bar's centre frequency (Hz): the middle column of each group of four.
const BANDS: [f64; 19] = [
    69.0, 194.0, 325.0, 465.0, 619.0, 792.0, 992.0, 1228.0, 1516.0, 1877.0, 2340.0, 2945.0, 3750.0, 4835.0,
    6312.0, 8339.0, 11136.0, 15011.0, 20397.0,
];
/// Band amplitude (linear) → Winamp's column value, per band (see the module docs).
const SCALE: [f64; 19] = [
    89.3, 78.1, 105.2, 128.5, 146.8, 165.6, 178.8, 190.2, 201.0, 209.2, 213.7, 213.7, 219.3, 220.4, 220.2, 218.9,
    216.6, 210.3, 160.3,
];
/// The "Winamp" levels (the default): column = `FIT_A[band]` × amplitude^`FIT_P[band]`,
/// fitted per bar so that on real music our band levels show what Winamp's own FFT does. `SCALE`
/// alone matches it on noise, but music fills every band-pass at once and reads hotter: dense
/// mixes sat near the top. Fitted by matching distributions (quantiles 30-99.5%) per bar over 24
/// tracks, 1960s to now, quiet to loud, against a port of that FFT run on the same audio: drawn
/// bars now land within about a pixel of Winamp's median, where `SCALE` alone was two high and at
/// the top two to three times as often.
const FIT_A: [f64; 19] = [
    73.8, 84.7, 135.9, 198.9, 221.6, 220.5, 220.8, 210.5, 235.5, 252.0, 306.1, 310.1, 337.3, 380.9, 599.6, 508.6,
    511.5, 605.6, 3113.8,
];
const FIT_P: [f64; 19] = [
    1.110, 1.190, 1.255, 1.327, 1.312, 1.266, 1.246, 1.206, 1.212, 1.217, 1.257, 1.250, 1.266, 1.344, 1.443, 1.381,
    1.419, 1.611, 2.084,
];
/// "Linear" (the analyzer's right-click menu, winamp.json's `vizLevels`): `SCALE` as it is, what
/// builds 5 to 7 showed; reads hotter on dense mixes.
static LINEAR: AtomicBool = AtomicBool::new(false);

/// Switch between the "Winamp" and "Linear" levels.
pub fn set_linear(linear: bool) {
    LINEAR.store(linear, Ordering::Relaxed);
}

/// A distinct channel name per band, in ffmpeg's own channel order after the music's FL and FR:
/// `amerge` sorts named channels into that order, so this keeps band i on channel i + 3. Identical
/// (unnamed mono) bands work too, but make ffmpeg warn that the layouts overlap.
const BAND_CHANNELS: [&str; 19] =
    ["FC", "LFE", "BL", "BR", "FLC", "FRC", "BC", "SL", "SR", "TC", "TFL", "TFC", "TFR", "TBL", "TBC", "TBR", "DL", "DR", "WL"];
const LABEL: &str = "viz";
/// mpv's audio output buffer (its `audio-buffer` default): how far the levels run ahead.
const LEAD: Duration = Duration::from_millis(200);
const FRAME: Duration = Duration::from_millis(16);
/// No new levels for this long: nothing's playing (paused, between tracks).
const STALE: Duration = Duration::from_millis(150);
/// How often silence is resent: well inside the page's 500 ms before it calls the feed gone.
const SILENCE_HEARTBEAT: Duration = Duration::from_millis(200);
const WAVE_LEN: usize = 1024;
const WAVE_RATE: f64 = 44_100.0;

/// Winamp's EQ band frequencies (Hz).
const EQ_BANDS: [f64; 10] = [60.0, 170.0, 310.0, 600.0, 1000.0, 3000.0, 6000.0, 12000.0, 14000.0, 16000.0];
/// A slider's full travel either way, as in Winamp.
const EQ_RANGE_DB: f64 = 12.0;
/// How often the EQ is sent again: a crossfade's second deck copies the chain as first built, not
/// the live values, so it's put right within this long.
const EQ_RESEND: Duration = Duration::from_millis(500);

/// The EQ window's state, as the UI keeps it (uiState.eq, winamp.json's `eq`): sliders 0-100, 50
/// for 0 dB, 100 for +12.
#[derive(Clone, Debug, serde::Deserialize, PartialEq)]
pub struct Eq {
    pub on: bool,
    pub preamp: f64,
    pub bands: Vec<f64>,
}

impl Default for Eq {
    fn default() -> Self {
        Eq { on: true, preamp: 50.0, bands: vec![50.0; 10] }
    }
}

impl Eq {
    fn db(slider: f64) -> f64 {
        ((slider.clamp(0.0, 100.0) - 50.0) / 50.0) * EQ_RANGE_DB
    }
    /// Preamp as a linear factor (1 when off), and each band's gain in dB (0 when off).
    fn gains(&self) -> (f64, Vec<f64>) {
        if !self.on {
            return (1.0, vec![0.0; EQ_BANDS.len()]);
        }
        let bands = (0..EQ_BANDS.len()).map(|i| Self::db(self.bands.get(i).copied().unwrap_or(50.0))).collect();
        (10f64.powf(Self::db(self.preamp) / 20.0), bands)
    }
}

/// The filters went into the chain: from the first Winamp window of the session to its end.
static INSTALLED: AtomicBool = AtomicBool::new(false);
/// The Winamp window is open: the analyzer data is read and sent only then.
static ACTIVE: AtomicBool = AtomicBool::new(false);
static EQ: Mutex<Option<Eq>> = Mutex::new(None);
/// The last retune failed (nothing playing yet: mpv has no audio chain to command). Logged once
/// when it starts failing, not on every resend.
static EQ_FAILING: AtomicBool = AtomicBool::new(false);

/// The Winamp window opened. The first time, the filters go into the player's chain (with the
/// remembered EQ) and the thread that drives them starts; they stay for the rest of the session.
/// Never fails loudly: no filters just means no EQ and no levels.
pub fn start(app: &AppHandle) {
    ACTIVE.store(true, Ordering::SeqCst);
    set_linear(crate::winamp::ui_prefs(app).get("vizLevels").and_then(|v| v.as_str()) == Some("linear"));
    if INSTALLED.swap(true, Ordering::SeqCst) {
        return;
    }
    let eq = {
        let mut eq = EQ.lock().unwrap();
        if eq.is_none() {
            *eq = crate::winamp::ui_prefs(app).get("eq").and_then(|v| serde_json::from_value(v.clone()).ok());
        }
        eq.clone().unwrap_or_default()
    };
    let state = app.state::<Arc<crate::state::AppState>>();
    if let Err(e) = state.player.set_extra_af(Some(&format!("{},{}", eq_filter(&eq), filter()))) {
        tracing::warn!(error = %e, "winamp: mpv refused the EQ/analysis filters, no EQ or spectrum");
        return;
    }
    let app = app.clone();
    let _ = std::thread::Builder::new().name("winamp-viz".into()).spawn(move || run(&app));
}

/// The Winamp window closed: stop reading the analyzer. The filters, EQ included, stay.
pub fn stop(_app: &AppHandle) {
    ACTIVE.store(false, Ordering::SeqCst);
}

/// The EQ window changed: remember it, and retune the filter if it's in.
pub fn set_eq(app: &AppHandle, eq: Eq) {
    *EQ.lock().unwrap() = Some(eq.clone());
    if INSTALLED.load(Ordering::SeqCst) {
        apply_eq(app, &eq);
    }
}

fn apply_eq(app: &AppHandle, eq: &Eq) {
    let player = &app.state::<Arc<crate::state::AppState>>().player;
    let (preamp, bands) = eq.gains();
    let mut result = player.af_command("eq", "volume", &format!("{preamp:.4}"), "volume@pre");
    for (i, g) in bands.iter().enumerate() {
        result = result.and(player.af_command("eq", "g", &format!("{g:.2}"), &format!("equalizer@b{i}")));
    }
    match result {
        Err(e) if !EQ_FAILING.swap(true, Ordering::Relaxed) => {
            tracing::debug!(error = %e, "winamp eq: retune failed (nothing playing yet?); quiet until it works again")
        }
        Err(_) => {}
        Ok(()) => EQ_FAILING.store(false, Ordering::Relaxed),
    }
}

/// The equalizer, in mpv's `af` syntax: the preamp, then a one-octave peaking filter per band.
fn eq_filter(eq: &Eq) -> String {
    let (preamp, bands) = eq.gains();
    let mut parts = vec![format!("volume@pre=volume={preamp:.4}")];
    for (i, (f, g)) in EQ_BANDS.iter().zip(bands).enumerate() {
        parts.push(format!("equalizer@b{i}=f={f}:t=o:w=1:g={g:.2}"));
    }
    format!("@eq:lavfi=[{}]", parts.join(","))
}

/// The analysis filter, in mpv's `af` syntax.
fn filter() -> String {
    let n = BANDS.len();
    let labels: String = (0..n).map(|i| format!("[b{i}]")).collect();
    let mut parts = vec![
        "aformat=channel_layouts=stereo,asplit=2[m][x]".to_string(),
        format!("[x]aformat=channel_layouts=mono,asplit={n}{labels}"),
    ];
    for (i, (f, w)) in BANDS.iter().zip(widths()).enumerate() {
        parts.push(format!("[b{i}]bandpass=f={f}:t=o:w={w:.2},pan={}|c0=c0[o{i}]", BAND_CHANNELS[i]));
    }
    let outs: String = (0..n).map(|i| format!("[o{i}]")).collect();
    // The music's layout pinned where amerge meets it, or amerge asks before it's settled (and
    // warns "No channel layout for input 1").
    parts.push("[m]aformat=channel_layouts=stereo[ms]".to_string());
    parts.push(format!(
        "[ms]{outs}amerge=inputs={},astats=metadata=1:reset=1:measure_perchannel=RMS_level:measure_overall=none,\
         pan=stereo|c0=c0|c1=c1",
        n + 1
    ));
    format!("@{LABEL}:lavfi=[{}]", parts.join(";"))
}

/// Each band's width in octaves: halfway to its neighbours either side, at least a third.
fn widths() -> Vec<f64> {
    (0..BANDS.len())
        .map(|i| {
            let lo = if i > 0 { BANDS[i - 1] } else { BANDS[0] / 2.0 };
            let hi = BANDS.get(i + 1).copied().unwrap_or((BANDS[i] * 1.3).min(22_000.0));
            ((hi / lo).log2() / 2.0).max(0.3)
        })
        .collect()
}

/// Band levels (dBFS, None for silence) from `af-metadata/viz`: channels 1 and 2 are the music,
/// 3.. the bands.
fn levels(metadata: &str) -> Option<Vec<Option<f64>>> {
    let map: serde_json::Map<String, serde_json::Value> = serde_json::from_str(metadata).ok()?;
    let band = |i: usize| {
        let v = map.get(&format!("lavfi.astats.{}.RMS_level", i + 3))?;
        v.as_str()?.parse::<f64>().ok().filter(|db| db.is_finite())
    };
    map.contains_key("lavfi.astats.3.RMS_level").then(|| (0..BANDS.len()).map(band).collect())
}

/// Band levels → the 75 columns Winamp draws, each bar's four columns alike.
fn columns(levels: &[Option<f64>]) -> Vec<f32> {
    let linear = LINEAR.load(Ordering::Relaxed);
    (0..COLUMNS)
        .map(|x| {
            let band = x / 4;
            levels[band].map_or(0.0, |db| {
                let amp = 10f64.powf(db / 20.0);
                let v = if linear { SCALE[band] * amp } else { FIT_A[band] * amp.powf(FIT_P[band]) };
                v as f32
            })
        })
        .collect()
}

/// A waveform with a tone per band at the band's level, its phases carried on between frames so
/// the shape keeps moving.
fn wave(levels: &[Option<f64>], phases: &mut [f64], elapsed: f64) -> Vec<u8> {
    let amps: Vec<f64> = levels.iter().map(|l| l.map_or(0.0, |db| 10f64.powf(db / 20.0))).collect();
    let out = (0..WAVE_LEN)
        .map(|n| {
            let t = n as f64 / WAVE_RATE;
            let s: f64 = BANDS
                .iter()
                .zip(&amps)
                .zip(phases.iter())
                .map(|((f, a), p)| a * (p + std::f64::consts::TAU * f * t).sin())
                .sum();
            // Bands at -20 dB sum to about full scale; quieter music gets a smaller wave.
            (128.0 + (s * 1.5).clamp(-1.0, 1.0) * 127.0) as u8
        })
        .collect();
    for (p, f) in phases.iter_mut().zip(BANDS) {
        *p = (*p + std::f64::consts::TAU * f * elapsed) % std::f64::consts::TAU;
    }
    out
}

fn run(app: &AppHandle) {
    let state = app.state::<Arc<crate::state::AppState>>();
    let silence = vec![None; BANDS.len()];
    // Readings waiting out the output buffer's lead.
    let mut queue: VecDeque<(Instant, Vec<Option<f64>>)> = VecDeque::new();
    let mut last_raw = String::new();
    let mut last_change = Instant::now();
    let mut shown = silence.clone();
    let mut phases = vec![0.0; BANDS.len()];
    let mut last_frame = Instant::now();
    let mut last_eq = Instant::now();
    let mut sent_silence = false;
    let mut last_emit = Instant::now();
    loop {
        std::thread::sleep(FRAME);
        let now = Instant::now();
        if now.duration_since(last_eq) >= EQ_RESEND {
            last_eq = now;
            if let Some(eq) = EQ.lock().unwrap().clone() {
                apply_eq(app, &eq);
            }
        }
        if !ACTIVE.load(Ordering::SeqCst) {
            queue.clear();
            last_raw.clear();
            continue;
        }
        let raw = state.player.af_metadata(LABEL).unwrap_or_default();
        if raw != last_raw {
            last_change = now;
            if let Some(l) = levels(&raw) {
                queue.push_back((now, l));
            }
            last_raw = raw;
        }
        while queue.front().is_some_and(|(at, _)| now.duration_since(*at) >= LEAD) {
            shown = queue.pop_front().unwrap().1;
        }
        // Nothing new for a while: playback stopped, so the bars drop.
        if now.duration_since(last_change) > STALE + LEAD {
            shown.clone_from(&silence);
            queue.clear();
        }
        // Silence again: the bars already fell, so a heartbeat keeps the feed fresh for the page
        // (testPattern.js), instead of sixty identical frames a second.
        let silent = shown.iter().all(Option::is_none);
        if !silent || !sent_silence || now.duration_since(last_emit) >= SILENCE_HEARTBEAT {
            let _ = app.emit_to(crate::winamp::LABEL, EVENT, columns(&shown));
            sent_silence = silent;
            last_emit = now;
        }
        if app.get_webview_window(MILKDROP).is_some() {
            let elapsed = now.duration_since(last_frame).as_secs_f64();
            let _ = app.emit_to(MILKDROP, WAVE_EVENT, wave(&shown, &mut phases, elapsed));
        }
        last_frame = now;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn filter_measures_one_channel_per_band_and_keeps_the_music_stereo() {
        let f = filter();
        assert!(f.starts_with("@viz:lavfi=["));
        assert_eq!(f.matches("bandpass=").count(), BANDS.len());
        assert!(f.contains(&format!("amerge=inputs={}", BANDS.len() + 1)));
        assert!(f.ends_with("pan=stereo|c0=c0|c1=c1]"));
        assert_eq!(f.matches("|c0=c0[o").count(), BANDS.len(), "every band gets its own channel name");
    }

    #[test]
    fn band_levels_come_from_channels_three_on() {
        let meta = r#"{"lavfi.astats.1.RMS_level":"-20.0","lavfi.astats.2.RMS_level":"-20.0","lavfi.astats.3.RMS_level":"-30.5","lavfi.astats.4.RMS_level":"-inf"}"#;
        let l = levels(meta).unwrap();
        assert_eq!(l.len(), BANDS.len());
        assert_eq!(l[0], Some(-30.5));
        assert_eq!(l[1], None, "-inf is silence");
        assert!(levels("{}").is_none());
        assert!(levels("not json").is_none());
    }

    #[test]
    fn a_band_lights_its_own_bar_only() {
        let mut l = vec![None; BANDS.len()];
        l[2] = Some(-20.0);
        let cols = columns(&l);
        assert_eq!(cols.len(), COLUMNS);
        assert!(cols[8..12].iter().all(|&c| c > 1.0));
        assert!(cols.iter().enumerate().all(|(i, &c)| (8..12).contains(&i) || c == 0.0));
    }

    #[test]
    fn winamp_levels_read_lower_than_linear_on_typical_music() {
        // A mid band at a busy mix's level: the calibrated mapping keeps it off the top.
        let mut l = vec![None; BANDS.len()];
        l[6] = Some(-15.0);
        set_linear(true);
        let linear = columns(&l)[24];
        set_linear(false);
        let winamp = columns(&l)[24];
        assert!(winamp < linear, "{winamp} vs {linear}");
        assert!(winamp > 15.0 * 0.5 && linear > 15.0, "{winamp} {linear}");
    }

    #[test]
    fn eq_sliders_map_to_plus_minus_twelve_db_and_off_is_flat() {
        let mut eq = Eq { on: true, preamp: 100.0, bands: vec![50.0; 10] };
        eq.bands[0] = 100.0;
        eq.bands[9] = 0.0;
        let (pre, bands) = eq.gains();
        assert!((pre - 10f64.powf(12.0 / 20.0)).abs() < 1e-9);
        assert_eq!((bands[0], bands[5], bands[9]), (12.0, 0.0, -12.0));
        eq.on = false;
        assert_eq!(eq.gains(), (1.0, vec![0.0; 10]));
        let f = eq_filter(&Eq::default());
        assert!(f.starts_with("@eq:lavfi=[volume@pre=volume=1.0000,equalizer@b0=f=60:t=o:w=1:g=0.00"));
        assert_eq!(f.matches("equalizer@b").count(), 10);
    }

    /// `cargo test -p limusic-app print_filters -- --ignored --nocapture`: the chain as mpv gets
    /// it, to try by hand (`mpv --af='...' file`).
    #[test]
    #[ignore]
    fn print_filters() {
        println!("{},{}", eq_filter(&Eq::default()), filter());
    }

    #[test]
    fn silence_is_a_flat_wave() {
        let mut phases = vec![0.0; BANDS.len()];
        assert!(wave(&vec![None; BANDS.len()], &mut phases, 0.016).iter().all(|&b| b == 128));
    }
}
