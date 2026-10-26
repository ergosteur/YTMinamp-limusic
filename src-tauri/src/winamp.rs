//! Winamp skin mode: a second "miniplayer" alongside [`crate::mini`], skinned as classic Winamp
//! 2.x instead of the floating widget.
//!
//! Same pattern as `mini.rs`: it loads the same SPA as every other window — the root layout
//! branches on the window label — so there is no second bundle and no second copy of playback
//! state. Every event this app emits is global (`app.emit`), so this webview is driven by the
//! same stream as `main` and `mini`. Opening it hides the main window; coming back always goes
//! through [`crate::tray::show_main`], exactly like the mini player, so the two restore paths
//! can never disagree about what "show Limusic" means.
//!
//! The skin-loading side (parsing a `.wsz` into something the UI can draw) is unrelated to the
//! window itself and lives in the back half of this file only because both are "Winamp mode" —
//! see [`load_wsz_skin`].

use std::collections::HashMap;

use serde::Serialize;
use tauri::{AppHandle, Manager, WebviewUrl, WebviewWindowBuilder};

pub const LABEL: &str = "winamp";
/// The panels that can float in windows of their own (docked, they're drawn inside [`LABEL`]),
/// each window labelled `winamp-<panel>`; `url` is the Open URL dialog, which only ever floats.
pub const PANELS: [&str; 14] = [
    "art", "playlist", "search", "eq", "lyrics", "url", "milkdrop", "eqsave", "fileinfo", "about", "update", "library",
    "newpl", "skins",
];
/// Sent to [`LABEL`] with the panel's name when its floating window goes away, however it went.
pub const PANEL_CLOSED_EVENT: &str = "winamp-panel-closed";

/// The window label for a floating `panel`, or an error for a name that isn't one.
pub fn panel_label(panel: &str) -> Result<String, String> {
    if PANELS.contains(&panel) {
        Ok(format!("winamp-{panel}"))
    } else {
        Err(format!("no such Winamp panel: {panel}"))
    }
}

/// Whether `label` is one of the floating panel windows.
pub fn is_panel_label(label: &str) -> bool {
    label.strip_prefix("winamp-").is_some_and(|p| PANELS.contains(&p))
}

/// Whether `label` is a Winamp window, the main one or a panel's.
pub fn is_winamp_label(label: &str) -> bool {
    label == LABEL || is_panel_label(label)
}

/// Every Winamp window's label.
pub fn window_labels() -> impl Iterator<Item = String> {
    std::iter::once(LABEL.to_owned()).chain(PANELS.iter().map(|p| format!("winamp-{p}")))
}

/// Put a Winamp window back where it was last left, as the window-state plugin recorded it
/// (lib.rs). Only where windows can be placed: native Wayland lets the compositor choose. Their
/// sizes are the UI's: the skin's, the panels' remembered ones, the Media Library's default.
fn restore_place(win: &tauri::WebviewWindow) {
    use tauri_plugin_window_state::{StateFlags, WindowExt};
    if positions_known() {
        let _ = win.restore_state(StateFlags::POSITION);
    }
}

/// `main.bmp` at 1x — classic Winamp's base main-window size. The skin UI resizes the window
/// itself once it knows the loaded skin's actual size (double-size mode, shade mode); this is
/// just where it opens before any skin has been picked.
const DEFAULT: (f64, f64) = (275.0, 116.0);

/// Build (or re-show) the window, and hide the main window behind it — mirrors `mini::open`.
pub fn open(app: &AppHandle) -> Result<(), String> {
    if let Some(w) = app.get_webview_window(LABEL) {
        let _ = w.show();
        let _ = w.set_focus();
    } else {
        let (w, h) = DEFAULT;
        let win = WebviewWindowBuilder::new(app, LABEL, WebviewUrl::App("index.html".into()))
            .title(format!("{} — Winamp", crate::brand::NAME))
            .inner_size(w, h)
            .resizable(false)
            .decorations(false)
            .transparent(true)
            .shadow(false)
            .always_on_top(always_on_top(app))
            .visible(false);
        let win = crate::http::proxied(win)
            .build()
            .map_err(|e| format!("couldn't open winamp mode: {e}"))?;

        // Same WebKitGTK min-height workaround as the mini player (mini.rs) — without the view's
        // own size request, 116px would come out 200.
        #[cfg(target_os = "linux")]
        let _ = win.with_webview(|wv| {
            use gtk::prelude::WidgetExt;
            wv.inner().set_size_request(1, 1);
        });
        #[cfg(target_os = "linux")]
        crate::tune_webview_labelled(app, LABEL, false);
        restore_place(&win);
        let _ = win.show();
        let _ = win.set_focus();
    }
    if let Some(main) = app.get_webview_window("main") {
        let _ = main.hide();
        crate::tray::set_main_visible(app, false);
    }
    crate::viz::start(app);
    Ok(())
}

/// Take the window down. Callable from any thread, same as `mini::close`.
pub fn close(app: &AppHandle) {
    for panel in PANELS {
        close_panel(app, panel);
    }
    if app.get_webview_window(LABEL).is_none() {
        return;
    }
    crate::viz::stop(app);
    // A "stop after current" left on would pause the player at the end of a track with no
    // Winamp window to notice and turn it off again.
    let handle = app.clone();
    tauri::async_runtime::spawn(async move {
        let _ = stop_after_current(&handle, false).await;
    });
    let handle = app.clone();
    let _ = app.run_on_main_thread(move || {
        if let Some(w) = handle.get_webview_window(LABEL) {
            let _ = w.destroy();
        }
    });
}

/// The Winamp windows closed to the tray (✕, Alt+F4, Close to tray): the ones that were showing,
/// to show again. Empty while Winamp mode is on screen, or not open at all.
static IN_TRAY: std::sync::Mutex<Vec<String>> = std::sync::Mutex::new(Vec::new());

/// Hide every Winamp window to the tray, playback going on, as Limusic's ✕ does its window.
/// False, with nothing hidden, when there's no tray to come back from (see `tray::available`).
pub fn hide_to_tray(app: &AppHandle) -> bool {
    if !crate::tray::available() || app.get_webview_window(LABEL).is_none() {
        return false;
    }
    let mut hidden = IN_TRAY.lock().unwrap_or_else(|e| e.into_inner());
    for label in window_labels() {
        if let Some(w) = app.get_webview_window(&label) {
            if w.is_visible().unwrap_or(false) && !hidden.contains(&label) {
                let _ = w.hide();
                hidden.push(label);
            }
        }
    }
    crate::viz::stop(app);
    true
}

/// Bring the Winamp windows back from the tray, if that's where they are: every way back
/// (`tray::show_main`: the tray, a second launch, the media keys' raise) asks this first, so
/// Winamp mode comes back as it went.
pub fn restore_from_tray(app: &AppHandle) -> bool {
    let labels = std::mem::take(&mut *IN_TRAY.lock().unwrap_or_else(|e| e.into_inner()));
    let Some(main) = app.get_webview_window(LABEL) else { return false };
    if labels.is_empty() {
        return false;
    }
    for label in labels.iter().filter(|l| *l != LABEL) {
        if let Some(w) = app.get_webview_window(label) {
            let _ = w.show();
        }
    }
    let _ = main.show();
    let _ = main.unminimize();
    let _ = main.set_focus();
    crate::viz::start(app);
    true
}

/// The Winamp window's ✕ and Alt+F4: to the tray when Limusic's ✕ would go there (its "close to
/// tray" setting, and a tray to come back from), otherwise quit, as Limusic's would.
pub fn close_requested(app: &AppHandle) {
    let hides = app
        .try_state::<std::sync::Arc<crate::state::AppState>>()
        .map(|s| crate::close_hides(s.db.get_setting("close_to_tray").as_deref()))
        .unwrap_or(true);
    if !(hides && hide_to_tray(app)) {
        app.exit(0);
    }
}

/// Resize the window to match a skin's actual dimensions (double-size mode, shade mode). No-op
/// if the window isn't open.
pub fn resize(app: &AppHandle, width: f64, height: f64) {
    if let Some(w) = app.get_webview_window(LABEL) {
        let _ = w.set_size(tauri::LogicalSize::new(width, height));
        keep_on_screen(&w, width, height);
    }
}

/// Whether a `width`x`height` Winamp window fits its screen's work area (double size asks before
/// growing). True when the platform can't say.
pub fn fits(app: &AppHandle, width: f64, height: f64) -> bool {
    app.get_webview_window(LABEL)
        .and_then(|w| work_area(&w))
        .map_or(true, |(_, size)| width <= size.width && height <= size.height)
}

/// How wide the Winamp window's screen is, less panels and docks, in logical px: docked panels
/// narrow to fit it (layout.js). None when the platform can't say.
pub fn work_width(app: &AppHandle) -> Option<f64> {
    app.get_webview_window(LABEL).and_then(|w| work_area(&w)).map(|(_, size)| size.width)
}

/// The window's monitor's work area (the screen minus panels and docks), in logical px.
fn work_area(w: &tauri::WebviewWindow) -> Option<(tauri::LogicalPosition<f64>, tauri::LogicalSize<f64>)> {
    let monitor = w.current_monitor().ok()??;
    let scale = monitor.scale_factor();
    let area = monitor.work_area();
    Some((area.position.to_logical(scale), area.size.to_logical(scale)))
}

/// Native Wayland gives a window no way to read or set its own position, so there's nothing to
/// correct there (GDK's choice of backend, as in lib.rs).
fn positions_known() -> bool {
    if !cfg!(target_os = "linux") {
        return true;
    }
    match std::env::var("GDK_BACKEND") {
        Ok(b) => b.split(',').next() == Some("x11"),
        Err(_) => std::env::var_os("WAYLAND_DISPLAY").is_none(),
    }
}

/// Grown past the screen's edge (double size, a panel docking below): move back inside it.
fn keep_on_screen(w: &tauri::WebviewWindow, width: f64, height: f64) {
    if !positions_known() {
        return;
    }
    let (Some((origin, size)), Ok(pos), Ok(scale)) = (work_area(w), w.outer_position(), w.scale_factor()) else {
        return;
    };
    let pos = pos.to_logical::<f64>(scale);
    // Left and top win when it's bigger than the screen: the titlebar stays reachable.
    let x = pos.x.min(origin.x + size.width - width).max(origin.x);
    let y = pos.y.min(origin.y + size.height - height).max(origin.y);
    if (x, y) != (pos.x, pos.y) {
        let _ = w.set_position(tauri::LogicalPosition::new(x, y));
    }
}

// --- floating panel windows -------------------------------------------------------------------

/// Open `panel` floating in a window of its own at `width`x`height` (or bring it back).
/// Undecorated: the skin draws its frame, and the UI resizes it itself, so no WM handles either.
/// Main thread only, like [`open`].
pub fn open_panel(app: &AppHandle, panel: &str, width: f64, height: f64) -> Result<(), String> {
    let label = panel_label(panel)?;
    if let Some(w) = app.get_webview_window(&label) {
        let _ = w.show();
        let _ = w.set_focus();
        return Ok(());
    }
    let title = match panel {
        "art" => "Album Art",
        "playlist" => "Playlist Editor",
        "url" => "Open URL",
        "eq" => "Equalizer",
        "lyrics" => "Lyrics",
        "milkdrop" => "MilkDrop",
        "eqsave" => "Save EQ Preset",
        "fileinfo" => "File Info",
        "about" => "About YTMinamp",
        "update" => "YTMinamp Update",
        "library" => "Media Library",
        "newpl" => "New Playlist",
        "skins" => "Skin Browser",
        _ => "Search",
    };
    // Not resizable (the UI sizes the window itself), except MilkDrop: GTK won't fullscreen a
    // non-resizable window to the screen, and switching resizable on just before the fullscreen
    // request races the compositor (it fullscreens at the old size, about nine times in ten).
    // The Media Library, File info and About resize too, from their frame's right and bottom
    // edges, but the UI does that itself (frameWindow.js), as the floating panels' corner does:
    // made resizable here, Tauri would add its own resize border on every side, the top included.
    let win = WebviewWindowBuilder::new(app, &label, WebviewUrl::App("index.html".into()))
        .title(title)
        .inner_size(width, height)
        .resizable(panel == "milkdrop")
        .decorations(false)
        .transparent(true)
        .shadow(false)
        .always_on_top(always_on_top(app))
        .visible(false);
    let win = crate::http::proxied(win)
        .build()
        .map_err(|e| format!("couldn't open the {title} window: {e}"))?;
    #[cfg(target_os = "linux")]
    let _ = win.with_webview(|wv| {
        use gtk::prelude::WidgetExt;
        wv.inner().set_size_request(1, 1);
    });
    #[cfg(target_os = "linux")]
    crate::tune_webview_labelled(app, &label, false);
    // tune_webview turns WebGL off everywhere; MilkDrop (Butterchurn) is WebGL, so it comes back
    // on in that window alone.
    #[cfg(target_os = "linux")]
    if panel == "milkdrop" {
        let _ = win.with_webview(|wv| {
            use webkit2gtk::{SettingsExt, WebViewExt};
            if let Some(settings) = WebViewExt::settings(&wv.inner()) {
                settings.set_enable_webgl(true);
            }
        });
    }
    // Alt+F4 or the frame's ✕ alike: the Winamp window puts its state right.
    let (handle, name) = (app.clone(), panel.to_owned());
    win.on_window_event(move |event| {
        if let tauri::WindowEvent::Destroyed = event {
            use tauri::Emitter;
            let _ = handle.emit_to(LABEL, PANEL_CLOSED_EVENT, &name);
        }
    });
    // Where it was: its size is the UI's to give (the skin's, its prefs, or the library's default).
    restore_place(&win);
    let _ = win.show();
    let _ = win.set_focus();
    fit_on_screen(&win);
    Ok(())
}

/// Shrink a floating window to its screen once it's on one. A size remembered from a bigger
/// monitor would put its resize edges or corner out of reach, and on Wayland the compositor picks
/// the monitor, so this can only be known after it's shown. Windows that fit are left alone.
fn fit_on_screen(win: &tauri::WebviewWindow) {
    /// Room left round it when it has to shrink: clear of a panel or dock along an edge, which
    /// Wayland's work area doesn't subtract.
    const MARGIN: f64 = 48.0;
    let win = win.clone();
    tauri::async_runtime::spawn(async move {
        // Until it's mapped, a window has no monitor.
        tokio::time::sleep(std::time::Duration::from_millis(300)).await;
        let (Some((_, area)), Ok(size), Ok(scale)) = (work_area(&win), win.outer_size(), win.scale_factor()) else {
            return;
        };
        let size = size.to_logical::<f64>(scale);
        if size.width <= area.width && size.height <= area.height {
            return;
        }
        let w = size.width.min(area.width - MARGIN);
        let h = size.height.min(area.height - MARGIN);
        let _ = win.set_size(tauri::LogicalSize::new(w, h));
        keep_on_screen(&win, w, h);
    });
}

/// Take `panel`'s floating window down, if it's up. Callable from any thread.
pub fn close_panel(app: &AppHandle, panel: &str) {
    let Ok(label) = panel_label(panel) else { return };
    if app.get_webview_window(&label).is_none() {
        return;
    }
    let handle = app.clone();
    let _ = app.run_on_main_thread(move || {
        if let Some(w) = handle.get_webview_window(&label) {
            let _ = w.destroy();
        }
    });
}

/// A floating panel window resizing itself.
pub fn resize_panel(app: &AppHandle, panel: &str, width: f64, height: f64) -> Result<(), String> {
    if let Some(w) = app.get_webview_window(&panel_label(panel)?) {
        let _ = w.set_size(tauri::LogicalSize::new(width, height));
    }
    Ok(())
}

// --- context menu (Linux) ---------------------------------------------------------------------

/// One entry of the skin's right-click menu, as the UI describes it. Exactly one shape applies:
/// a separator, a submenu (`items`), a check item (`checked`), or a plain item.
#[derive(serde::Deserialize)]
#[serde(rename_all = "camelCase")]
#[cfg_attr(not(target_os = "linux"), allow(dead_code))]
pub struct MenuEntry {
    #[serde(default)]
    separator: bool,
    #[serde(default)]
    text: String,
    /// Sent back in a `winamp-menu` event when the entry is picked.
    id: Option<String>,
    checked: Option<bool>,
    items: Option<Vec<MenuEntry>>,
    /// Shown greyed out when false ("No playlists in the library").
    enabled: Option<bool>,
    /// Its shortcut, shown right-aligned like Winamp's ("Ctrl+L", "Alt+E", "Z", "Left"). Only
    /// shown: the page handles the keys.
    accel: Option<String>,
}

/// "Ctrl+L" / "Alt+E" / "Z" / "Left" as GTK's accelerator syntax ("<Control>l", ...).
#[cfg(target_os = "linux")]
fn gtk_accelerator(shown: &str) -> String {
    let mut parts: Vec<&str> = shown.split('+').collect();
    let key = parts.pop().unwrap_or_default();
    let mut out = String::new();
    for m in parts {
        out.push_str(match m {
            "Ctrl" => "<Control>",
            "Alt" => "<Alt>",
            "Shift" => "<Shift>",
            _ => "",
        });
    }
    out.push_str(&if key.chars().count() == 1 { key.to_lowercase() } else { key.to_owned() });
    out
}

/// What a picked menu entry sends back to the window.
#[cfg_attr(not(target_os = "linux"), allow(dead_code))]
pub const MENU_EVENT: &str = "winamp-menu";

#[cfg(target_os = "linux")]
thread_local! {
    /// The menu on screen (or last on screen). Held so it outlives `popup`; replaced, and so
    /// freed, by the next one. Main thread only, like every GTK object.
    static SHOWN: std::cell::RefCell<Option<gtk::Menu>> = const { std::cell::RefCell::new(None) };
}

/// Pop up a GTK menu over window `label` at its position (x, y) and return at once; a pick
/// arrives in that window as a [`MENU_EVENT`] carrying the entry's `id`.
///
/// Not Tauri's menu API: on Linux it goes through muda, whose popup is modal. It spins
/// `gtk::main_iteration()` until the menu sends "cancel" or "selection-done", and on Wayland a
/// menu dismissed by the compositor (another window taking focus, a refused grab) can send
/// neither. The loop then never ends, and inside it Tauri can't deliver its queued messages, so
/// every event stops, while the popup command keeps the window's resource table locked. Both
/// whole-UI freezes came from that. This popup has no loop to get stuck in.
#[cfg(target_os = "linux")]
///
/// Picks go to `label`, the window asking; the menu shows over `on` if given (the Media Library's
/// frame showing the Winamp window's main menu), else over `label`.
pub fn popup_menu(
    app: &AppHandle,
    label: String,
    on: Option<String>,
    entries: Vec<MenuEntry>,
    x: f64,
    y: f64,
) -> Result<(), String> {
    let handle = app.clone();
    app.run_on_main_thread(move || {
        use gtk::prelude::*;
        let Some(win) = handle.get_webview_window(on.as_deref().unwrap_or(&label)) else { return };
        let Ok(gtk_window) = win.gtk_window() else { return };
        let Some(gdk_window) = gtk_window.window() else { return };

        let menu = build_menu(&handle, &label, &entries);
        // A parent for the popup: without one GTK can't map it as a popup on Wayland.
        menu.set_attach_widget(Some(&gtk_window));
        menu.show_all();

        // Wayland only maps a popup that grabs with a pointer device; a synthetic press stands
        // in for the click that opened it (the same trick muda uses).
        let mut event = gtk::gdk::Event::new(gtk::gdk::EventType::ButtonPress);
        event.set_device(gdk_window.display().default_seat().and_then(|s| s.pointer()).as_ref());
        // With no time, GTK takes the right button's release as a click outside and closes it.
        {
            use gtk::glib::translate::ToGlibPtr;
            let raw: *mut gtk::gdk::ffi::GdkEvent = event.to_glib_none().0;
            if !raw.is_null() {
                // SAFETY: a ButtonPress event we just created, so `button` is the live union arm.
                unsafe { (*raw).button.time = (gtk::glib::monotonic_time() / 1000) as u32 };
            }
        }
        let rect = gtk::gdk::Rectangle::new(x.round() as i32, y.round() as i32, 1, 1);
        menu.popup_at_rect(
            &gdk_window,
            &rect,
            gtk::gdk::Gravity::NorthWest,
            gtk::gdk::Gravity::NorthWest,
            Some(&event),
        );

        SHOWN.with(|shown| {
            if let Some(old) = shown.replace(Some(menu)) {
                // SAFETY: a GtkMenu we created and nothing else holds; destroying it is the
                // documented way to free a toplevel-ish widget.
                unsafe { old.destroy() };
            }
        });
    })
    .map_err(|e| e.to_string())
}

#[cfg(target_os = "linux")]
fn build_menu(app: &AppHandle, label: &str, entries: &[MenuEntry]) -> gtk::Menu {
    use gtk::prelude::*;
    use tauri::Emitter;
    let menu = gtk::Menu::new();
    for entry in entries {
        let item: gtk::MenuItem = if entry.separator {
            gtk::SeparatorMenuItem::new().upcast()
        } else if let Some(children) = &entry.items {
            let item = gtk::MenuItem::with_label(&entry.text);
            item.set_submenu(Some(&build_menu(app, label, children)));
            item
        } else if let Some(checked) = entry.checked {
            let item = gtk::CheckMenuItem::with_label(&entry.text);
            // Set before `activate` is connected, so it doesn't fire for this.
            item.set_active(checked);
            item.upcast()
        } else {
            gtk::MenuItem::with_label(&entry.text)
        };
        if entry.enabled == Some(false) {
            item.set_sensitive(false);
        }
        if let Some(accel) = &entry.accel {
            let (key, mods) = gtk::accelerator_parse(&gtk_accelerator(accel));
            if let Some(label) = item.child().and_then(|c| c.downcast::<gtk::AccelLabel>().ok()) {
                label.set_accel(key, mods);
            }
        }
        if let Some(id) = entry.id.clone() {
            let (app, label) = (app.clone(), label.to_owned());
            item.connect_activate(move |_| {
                let _ = app.emit_to(label.as_str(), MENU_EVENT, id.clone());
            });
        }
        menu.append(&item);
    }
    menu
}

// --- skin loading -----------------------------------------------------------------------------

/// A sprite sheet, PNG-encoded and base64'd so the UI can hand it straight to `Image.src` /
/// `createImageBitmap` without a second IPC round trip per bitmap.
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SkinSprite {
    pub width: u32,
    pub height: u32,
    /// `data:image/png;base64,...`
    pub png_data_url: String,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SkinPayload {
    /// Keyed by lowercase filename without extension (`"main"`, `"cbuttons"`, ...) — same keys
    /// `skin::Skin::sprite` uses.
    pub sprites: HashMap<String, SkinSprite>,
    pub region: Option<SkinRegion>,
    /// `(r, g, b)` triples, in `viscolor.txt` order.
    pub viscolor: Vec<(u8, u8, u8)>,
    pub pledit: skin::Pledit,
    /// The Media Library's colours, from the skin's own `genex.bmp`. A skin without one leaves
    /// the library in Limusic's own theme, light or dark as [`Self::main_dark`] says.
    pub genex: Option<skin::Genex>,
    /// Whether `main.bmp` is mostly dark.
    pub main_dark: bool,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SkinRegion {
    pub normal: Vec<Vec<(i32, i32)>>,
    pub equalizer: Vec<Vec<(i32, i32)>>,
}

fn encode_png(sprite: &skin::Sprite) -> Result<String, String> {
    let mut bytes = Vec::new();
    {
        let mut encoder = png::Encoder::new(&mut bytes, sprite.width, sprite.height);
        encoder.set_color(png::ColorType::Rgba);
        encoder.set_depth(png::BitDepth::Eight);
        let mut writer = encoder.write_header().map_err(|e| e.to_string())?;
        writer.write_image_data(&sprite.rgba).map_err(|e| e.to_string())?;
    }
    Ok(format!("data:image/png;base64,{}", base64_encode(&bytes)))
}

fn base64_encode(bytes: &[u8]) -> String {
    use base64::Engine;
    base64::engine::general_purpose::STANDARD.encode(bytes)
}

/// The skin used when none is chosen, compiled in so the window works with no files on disk:
/// Nullsoft's own Winamp 2.91 base skin, the copy Webamp ships (see docs/WINAMP-MODE.md, Credits).
const DEFAULT_SKIN: &[u8] = include_bytes!("../skins/base-2.91.wsz");

/// Where skins live: `<app data>/skins`. "Load skin…" copies picked files in here, so the skin
/// menu is just a listing of this folder.
pub fn skins_dir(app: &AppHandle) -> Result<std::path::PathBuf, String> {
    let dir = app.path().app_data_dir().map_err(|e| e.to_string())?.join("skins");
    std::fs::create_dir_all(&dir).map_err(|e| format!("couldn't create {}: {e}", dir.display()))?;
    static PLACED: std::sync::Once = std::sync::Once::new();
    PLACED.call_once(|| place_bundled(app, &dir));
    Ok(dir)
}

/// The skins compiled in: the public ones (`skins/*/YTMinamp-*.wsz`), and any a build adds with `YTMINAMP_SKINS` (`ytminamp-build.rs`).
mod bundled {
    include!(concat!(env!("OUT_DIR"), "/bundled_skins.rs"));
}

/// Copy the compiled-in skins into the skins folder, as Winamp's installer drops its own into
/// `Skins\`. Each is placed once (`winamp.json`'s `bundled`: name and hash of what was written):
/// one the user deletes stays deleted, a file of theirs by the same name is left alone, and a
/// later build's newer copy replaces the old one only while that is unchanged.
fn place_bundled(app: &AppHandle, dir: &std::path::Path) {
    let placed = read_prefs(app).bundled;
    let mut now = placed.clone();
    for &(name, bytes) in bundled::BUNDLED {
        let hash = fnv1a(bytes);
        let path = dir.join(name);
        let on_disk = std::fs::read(&path).ok().map(|b| fnv1a(&b));
        let write = should_place(placed.get(name).copied(), on_disk, hash);
        if write {
            if let Err(e) = std::fs::write(&path, bytes) {
                tracing::warn!("winamp: couldn't place {}: {e}", path.display());
                continue;
            }
        }
        if write || on_disk == Some(hash) {
            now.insert(name.to_owned(), hash);
        }
    }
    if now != placed {
        let _ = update_prefs(app, |prefs| prefs.bundled = now);
    }
}

/// Whether to write a compiled-in skin (hash `new`), given the hash placed before and the one on
/// disk: when it was never placed and the name is free, or when the copy placed is still unchanged
/// and this one differs.
fn should_place(placed: Option<u64>, on_disk: Option<u64>, new: u64) -> bool {
    match (placed, on_disk) {
        (None, None) => true,
        (Some(old), Some(disk)) => disk == old && disk != new,
        _ => false,
    }
}

/// 64-bit FNV-1a: stable across builds, which `std`'s hasher doesn't promise.
fn fnv1a(bytes: &[u8]) -> u64 {
    bytes.iter().fold(0xcbf2_9ce4_8422_2325, |h, &b| (h ^ b as u64).wrapping_mul(0x100_0000_01b3))
}

/// Winamp mode's remembered state, `<app data>/winamp.json`. Kept out of limusic's settings so
/// the fork doesn't touch that struct.
#[derive(Serialize, serde::Deserialize, Default)]
struct Prefs {
    /// Absolute path of the chosen `.wsz`; `None` = the built-in skin.
    skin: Option<String>,
    /// Everything else, owned by the UI (panel placement, EQ, double size, ...): a JSON object
    /// whose top-level keys each window updates on its own (see [`merge_ui_prefs`]).
    #[serde(default)]
    ui: serde_json::Map<String, serde_json::Value>,
    /// Compiled-in skins placed in the skins folder, by file name, with the hash of what was
    /// written (see [`place_bundled`]).
    #[serde(default)]
    bundled: std::collections::BTreeMap<String, u64>,
}

/// The UI's remembered state (the `ui` object of `winamp.json`).
pub fn ui_prefs(app: &AppHandle) -> serde_json::Map<String, serde_json::Value> {
    read_prefs(app).ui
}

/// "Always start in Winamp mode" (the main menu's checkbox, winamp.json's `startInWinamp`).
pub fn start_in_winamp(app: &AppHandle) -> bool {
    ui_prefs(app).get("startInWinamp").and_then(serde_json::Value::as_bool).unwrap_or(true)
}

/// Merge `patch`'s top-level keys into the UI's remembered state. Per key, not wholesale, so
/// two windows saving different things can't undo each other.
pub fn merge_ui_prefs(
    app: &AppHandle,
    patch: serde_json::Map<String, serde_json::Value>,
) -> Result<(), String> {
    update_prefs(app, |prefs| prefs.ui.extend(patch))
}

/// Read-modify-write `winamp.json`, one writer at a time (several windows save to it).
fn update_prefs(app: &AppHandle, change: impl FnOnce(&mut Prefs)) -> Result<(), String> {
    static LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());
    let _guard = LOCK.lock().unwrap_or_else(|e| e.into_inner());
    let mut prefs = read_prefs(app);
    change(&mut prefs);
    write_prefs(app, &prefs)
}

/// Whether the Winamp windows are kept above others (the clutterbar's A).
fn always_on_top(app: &AppHandle) -> bool {
    read_prefs(app).ui.get("alwaysOnTop").and_then(|v| v.as_bool()).unwrap_or(false)
}

/// Keep every Winamp window (main and floating panels) above others, or not, and remember it.
pub fn set_always_on_top(app: &AppHandle, on: bool) -> Result<(), String> {
    let panels = PANELS.iter().map(|p| format!("winamp-{p}"));
    for label in std::iter::once(LABEL.to_owned()).chain(panels) {
        if let Some(w) = app.get_webview_window(&label) {
            let _ = w.set_always_on_top(on);
        }
    }
    merge_ui_prefs(app, serde_json::Map::from_iter([("alwaysOnTop".into(), on.into())]))
}

fn prefs_path(app: &AppHandle) -> Result<std::path::PathBuf, String> {
    Ok(app.path().app_data_dir().map_err(|e| e.to_string())?.join("winamp.json"))
}

/// The saved state, or the defaults on a first run. A file that won't parse is moved aside to
/// `winamp.json.bad` (and logged) rather than overwritten by the next save, so it can be looked at.
fn read_prefs(app: &AppHandle) -> Prefs {
    let Ok(path) = prefs_path(app) else { return Prefs::default() };
    let Ok(bytes) = std::fs::read(&path) else { return Prefs::default() };
    serde_json::from_slice(&bytes).unwrap_or_else(|e| {
        let bad = path.with_extension("json.bad");
        tracing::warn!("winamp: {} is unreadable ({e}), moved to {}", path.display(), bad.display());
        let _ = std::fs::rename(&path, &bad);
        Prefs::default()
    })
}

/// Written to a temporary file and renamed over the old one, so a crash mid-write leaves the old
/// file whole instead of half a new one.
fn write_prefs(app: &AppHandle, prefs: &Prefs) -> Result<(), String> {
    let json = serde_json::to_vec_pretty(prefs).map_err(|e| e.to_string())?;
    let path = prefs_path(app)?;
    let tmp = path.with_extension("json.tmp");
    std::fs::write(&tmp, json).map_err(|e| e.to_string())?;
    std::fs::rename(&tmp, &path).map_err(|e| e.to_string())
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SkinEntry {
    /// File name without the extension, as Winamp's skin menu shows it.
    pub name: String,
    pub path: String,
    /// The subfolder it's in, relative to the skins folder with `/` between names; `""` at the top.
    pub folder: String,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SkinList {
    pub dir: String,
    pub skins: Vec<SkinEntry>,
    /// The remembered choice; `None` = the built-in skin.
    pub current: Option<String>,
}

/// Every `.wsz`/`.zip` in [`skins_dir`] and its subfolders, sorted by name. A folder of skins can
/// be dropped in as it is (a set unzipped there, say); hidden folders are skipped, and so are
/// symlinked ones, which [`in_skins_dir`] wouldn't accept skins from.
pub fn list(app: &AppHandle) -> Result<SkinList, String> {
    let dir = skins_dir(app)?;
    let mut skins = Vec::new();
    collect_skins(&dir, "", 0, &mut skins)?;
    skins.sort_by_key(|s| s.name.to_lowercase());
    Ok(SkinList { dir: dir.to_string_lossy().into_owned(), skins, current: read_prefs(app).skin })
}

fn is_skin_file(p: &std::path::Path) -> bool {
    p.extension()
        .and_then(|x| x.to_str())
        .is_some_and(|x| x.eq_ignore_ascii_case("wsz") || x.eq_ignore_ascii_case("zip"))
}

/// The skins in `dir` (`folder` below the skins folder), and in its subfolders to a few levels.
fn collect_skins(
    dir: &std::path::Path,
    folder: &str,
    depth: usize,
    skins: &mut Vec<SkinEntry>,
) -> Result<(), String> {
    for entry in std::fs::read_dir(dir).map_err(|e| e.to_string())?.flatten() {
        let (path, Ok(kind)) = (entry.path(), entry.file_type()) else { continue };
        let name = entry.file_name().to_string_lossy().into_owned();
        if kind.is_dir() {
            if depth < 4 && !name.starts_with('.') {
                let sub = if folder.is_empty() { name } else { format!("{folder}/{name}") };
                // An unreadable subfolder just isn't listed.
                let _ = collect_skins(&path, &sub, depth + 1, skins);
            }
        } else if is_skin_file(&path) {
            skins.push(SkinEntry {
                name: path.file_stem().unwrap_or_default().to_string_lossy().into_owned(),
                path: path.to_string_lossy().into_owned(),
                folder: folder.to_owned(),
            });
        }
    }
    Ok(())
}

/// Copy a picked skin file into [`skins_dir`] and return its new path. Parsed first, so a file
/// that isn't a usable skin never lands in the menu. A skin of the same name is only replaced
/// with `replace` (the UI asks first).
pub fn import(app: &AppHandle, src: &str, replace: bool) -> Result<String, String> {
    let bytes = std::fs::read(src).map_err(|e| format!("couldn't read {src}: {e}"))?;
    skin::load(&bytes).map_err(|e| format!("not a Winamp skin: {e}"))?;
    let name = std::path::Path::new(src).file_name().ok_or("no file name")?;
    let dest = skins_dir(app)?.join(name);
    if std::path::Path::new(src) != dest {
        if dest.exists() && !replace {
            return Err(format!("{} is already in the skins folder", name.to_string_lossy()));
        }
        std::fs::write(&dest, bytes).map_err(|e| e.to_string())?;
    }
    Ok(dest.to_string_lossy().into_owned())
}

/// `path` if it's a skin file in [`skins_dir`] or a folder in it (the ones the skin menu offers),
/// else an error: the webview names the file, so it doesn't get to read others.
fn in_skins_dir(app: &AppHandle, path: &str) -> Result<(), String> {
    let path = std::fs::canonicalize(path).map_err(|e| format!("{path}: {e}"))?;
    let dir = std::fs::canonicalize(skins_dir(app)?).map_err(|e| e.to_string())?;
    if path.starts_with(&dir) && path != dir && is_skin_file(&path) {
        Ok(())
    } else {
        Err(format!("{} isn't a skin in the skins folder", path.display()))
    }
}

/// Load `path` (`None` = built-in) and remember it as the skin to open with next time. Only
/// remembered once it has parsed, so a broken pick can't stick. Only skins in [`skins_dir`].
pub async fn select(app: &AppHandle, path: Option<String>) -> Result<SkinPayload, String> {
    if let Some(path) = &path {
        in_skins_dir(app, path)?;
    }
    let payload = load(path.as_deref()).await?;
    update_prefs(app, |prefs| prefs.skin = path)?;
    Ok(payload)
}

/// Drag a Winamp window, but on macOS only while the left button is actually down: the request
/// arrives after the press that asked for it, and a window drag started once the button is up
/// never ends there (the window sticks to the cursor and other clicks stop reaching it).
pub fn start_drag(window: &tauri::WebviewWindow) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    {
        use objc2::runtime::AnyClass;
        let Some(ns_event) = AnyClass::get(c"NSEvent") else { return Ok(()) };
        // +[NSEvent pressedMouseButtons]: bit 0 is the left button.
        let held: usize = unsafe { objc2::msg_send![ns_event, pressedMouseButtons] };
        if held & 1 == 0 {
            return Ok(());
        }
    }
    window.start_dragging().map_err(|e| e.to_string())
}

/// The Skin Browser's preview: a skin from the skins folder (`None` = built-in), loaded as
/// [`select`] would, without making it the current one.
pub async fn preview(app: &AppHandle, path: Option<String>) -> Result<SkinPayload, String> {
    if let Some(path) = &path {
        in_skins_dir(app, path)?;
    }
    load(path.as_deref()).await
}

/// Load the remembered skin, falling back to the built-in one if it has gone missing or broken.
pub async fn load_current(app: &AppHandle) -> Result<SkinPayload, String> {
    if let Some(path) = read_prefs(app).skin {
        match load(Some(&path)).await {
            Ok(payload) => return Ok(payload),
            Err(e) => tracing::warn!("winamp skin {path} failed, using the built-in one: {e}"),
        }
    }
    load(None).await
}

/// Winamp's "Stop after current" (Ctrl+V): pause at the end of the playing track instead of
/// going on to the next. mpv's own `keep-open`, so nothing of the next track is heard; crossfade
/// is suspended meanwhile, since a fade starts the next track before the end. The UI notices
/// the stop (paused at the end) and turns this off again; closing Winamp mode does too.
pub async fn stop_after_current(app: &AppHandle, on: bool) -> Result<(), String> {
    let state = app.state::<std::sync::Arc<crate::state::AppState>>();
    state.player.set_keep_open(on).map_err(|e| e.to_string())?;
    STOP_AFTER.store(on, std::sync::atomic::Ordering::Relaxed);
    if on {
        state.player.set_crossfade(None);
    } else {
        state.apply_crossfade().await;
    }
    Ok(())
}

/// Media Library (Alt+L): whether Limusic's own window is up (shown and not minimized), for the
/// main menu's tick. Winamp mode's library is that window.
#[tauri::command]
pub fn limusic_window_shown(app: AppHandle) -> bool {
    app.get_webview_window("main").is_some_and(|w| {
        w.is_visible().unwrap_or(false) && !w.is_minimized().unwrap_or(false)
    })
}

/// Show Limusic's window (to the front, where it was) or hide it again; Winamp mode stays open.
/// Shown directly, not through `show_main`, which "Always start in Winamp mode" turns into opening
/// Winamp mode instead.
#[tauri::command]
pub fn show_limusic_window(app: AppHandle, show: bool) -> Result<(), String> {
    let w = app.get_webview_window("main").ok_or("Limusic's window is gone")?;
    let done = if show {
        w.show().and_then(|_| w.unminimize()).and_then(|_| w.set_focus())
    } else {
        w.hide()
    };
    done.map_err(|e| e.to_string())
}

/// The analyzer's levels, `winamp` or `linear` (what builds 5 to 7 had). The UI remembers the
/// choice (`vizLevels`); `viz::start` reads it from there too.
#[tauri::command]
pub fn set_viz_levels(levels: String) {
    crate::viz::set_linear(levels == "linear");
}

/// Whether a "stop after current" is set: every Winamp window's menus tick it from here.
static STOP_AFTER: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);

#[tauri::command]
pub async fn set_stop_after_current(app: AppHandle, on: bool) -> Result<(), String> {
    stop_after_current(&app, on).await
}

#[tauri::command]
pub fn stop_after_current_set() -> bool {
    STOP_AFTER.load(std::sync::atomic::Ordering::Relaxed)
}

/// Sheets a skin may leave out that Winamp then takes from its base skin. Not `gen`/`genex`: a skin
/// without them gets its generic windows framed in its own playlist editor's graphics instead
/// (render/albumArt.js `artFrame`), which match it better than the base skin's grey.
const FROM_BASE: &[&str] = &[
    "cbuttons", "titlebar", "shufrep", "posbar", "volume", "balance", "monoster", "playpaus",
    "numbers", "text", "pledit", "eqmain", "eq_ex", "mb", "video",
];

/// The built-in base skin, parsed once.
fn base_skin() -> Option<&'static skin::Skin> {
    static BASE: std::sync::OnceLock<Option<skin::Skin>> = std::sync::OnceLock::new();
    BASE.get_or_init(|| skin::load(DEFAULT_SKIN).ok()).as_ref()
}

/// Fill the sheets `skin` lacks from the built-in base skin, as Winamp does, so a skin without,
/// say, `cbuttons.bmp` shows the base buttons rather than none. `numbers` is filled even beside
/// a skin's own `nums_ex`, which the UI prefers anyway.
fn fill_from_base(skin: &mut skin::Skin) {
    let Some(base) = base_skin() else { return };
    for name in FROM_BASE {
        if let (false, Some(sprite)) = (skin.sprites.contains_key(*name), base.sprite(name)) {
            skin.sprites.insert((*name).to_owned(), sprite.clone());
        }
    }
}

/// Parse a `.wsz` at `path` (or the built-in default) and hand back every sprite sheet
/// (PNG-encoded) plus the window shape/colors/playlist styling the UI needs to draw it, with
/// any sheet it lacks taken from the base skin.
async fn load(path: Option<&str>) -> Result<SkinPayload, String> {
    let bytes = match path {
        Some(path) => std::fs::read(path).map_err(|e| format!("couldn't read {path}: {e}"))?,
        None => DEFAULT_SKIN.to_vec(),
    };
    let mut parsed = skin::load(&bytes).map_err(|e| e.to_string())?;
    fill_from_base(&mut parsed);

    let genex = parsed.sprite("genex").and_then(skin::genex_colors);
    let main_dark = parsed.sprite("main").is_some_and(|m| mean_luma(m) < 0.5);
    let mut sprites = HashMap::new();
    for (name, sprite) in &parsed.sprites {
        let png_data_url = encode_png(sprite)?;
        sprites.insert(name.clone(), SkinSprite { width: sprite.width, height: sprite.height, png_data_url });
    }

    Ok(SkinPayload {
        sprites,
        region: parsed.region.map(|r| SkinRegion { normal: r.normal, equalizer: r.equalizer }),
        viscolor: parsed.viscolor,
        pledit: parsed.pledit,
        genex,
        main_dark,
    })
}

/// `image`'s mean brightness, 0 (black) to 1 (white), by Rec. 601 luma.
fn mean_luma(image: &skin::Sprite) -> f64 {
    let pixels = image.rgba.chunks_exact(4);
    let count = pixels.len().max(1) as f64;
    let sum: f64 = pixels.map(|p| 0.299 * p[0] as f64 + 0.587 * p[1] as f64 + 0.114 * p[2] as f64).sum();
    sum / count / 255.0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn missing_sheets_come_from_the_base_skin_but_gen_does_not() {
        let mut skin = skin::load(DEFAULT_SKIN).unwrap();
        skin.sprites.remove("cbuttons");
        skin.sprites.remove("gen");
        fill_from_base(&mut skin);
        assert!(skin.sprite("cbuttons").is_some());
        assert!(skin.sprite("gen").is_none());
    }

    #[test]
    fn every_filled_sheet_is_in_the_base_skin() {
        let base = skin::load(DEFAULT_SKIN).unwrap();
        for name in FROM_BASE {
            assert!(base.sprite(name).is_some(), "{name}");
        }
    }

    #[test]
    fn bundled_skins_are_placed_once_and_updated_only_while_untouched() {
        assert!(should_place(None, None, 1)); // new
        assert!(!should_place(None, Some(2), 1)); // the user's own file of that name
        assert!(!should_place(Some(1), None, 1)); // deleted by the user
        assert!(should_place(Some(1), Some(1), 2)); // a newer build's copy
        assert!(!should_place(Some(1), Some(3), 2)); // changed by the user
        assert!(!should_place(Some(1), Some(1), 1)); // already there
    }

    #[test]
    fn skins_are_found_in_subfolders_but_not_hidden_ones() {
        let root = std::env::temp_dir().join(format!("ytminamp-skins-test-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        for dir in ["ARTMS/Light", ".hidden", "Empty"] {
            std::fs::create_dir_all(root.join(dir)).unwrap();
        }
        for file in ["Top.wsz", "ARTMS/ARTMS.wsz", "ARTMS/Light/ARTMS-Light.WSZ", ".hidden/No.wsz"] {
            std::fs::write(root.join(file), b"").unwrap();
        }
        std::fs::write(root.join("ARTMS/readme.txt"), b"").unwrap();
        let mut skins = Vec::new();
        collect_skins(&root, "", 0, &mut skins).unwrap();
        let mut found: Vec<_> = skins.iter().map(|s| (s.folder.as_str(), s.name.as_str())).collect();
        found.sort();
        assert_eq!(found, [("", "Top"), ("ARTMS", "ARTMS"), ("ARTMS/Light", "ARTMS-Light")]);
        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn the_skins_always_shipped_are_compiled_in_and_parse() {
        for name in ["YTMinamp-Ember.wsz", "YTMinamp-Frutiger-Aero.wsz"] {
            let (_, bytes) = bundled::BUNDLED.iter().find(|(n, _)| *n == name).unwrap();
            skin::load(bytes).unwrap();
        }
    }
}
