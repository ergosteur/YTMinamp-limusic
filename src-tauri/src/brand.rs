//! What this build calls itself where people see it (tray, window titles, media controls,
//! notifications) and the id the desktop knows it by: ytminamp's, in one place, so the upstream
//! files that show a name change by one identifier each.

/// The name people see.
pub const NAME: &str = "YTMinamp (limusic)";
/// The installed `.desktop` file's name (`productName` in tauri.conf.json), and the tray and
/// media-controls (MPRIS) id: not Limusic's, so both can run side by side.
pub const ID: &str = "ytminamp";
