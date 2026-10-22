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
pub const PANELS: [&str; 7] = ["art", "playlist", "search", "eq", "lyrics", "url", "milkdrop"];
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
    crate::viz::stop();
    let handle = app.clone();
    let _ = app.run_on_main_thread(move || {
        if let Some(w) = handle.get_webview_window(LABEL) {
            let _ = w.destroy();
        }
    });
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
        _ => "Search",
    };
    let win = WebviewWindowBuilder::new(app, &label, WebviewUrl::App("index.html".into()))
        .title(title)
        .inner_size(width, height)
        .resizable(false)
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
    // Alt+F4 or the frame's ✕ alike: the Winamp window puts its state right.
    let (handle, name) = (app.clone(), panel.to_owned());
    win.on_window_event(move |event| {
        if let tauri::WindowEvent::Destroyed = event {
            use tauri::Emitter;
            let _ = handle.emit_to(LABEL, PANEL_CLOSED_EVENT, &name);
        }
    });
    let _ = win.show();
    let _ = win.set_focus();
    Ok(())
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
    /// Shown greyed out when false ("No playlists in your library").
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
pub fn popup_menu(
    app: &AppHandle,
    label: String,
    entries: Vec<MenuEntry>,
    x: f64,
    y: f64,
) -> Result<(), String> {
    let handle = app.clone();
    app.run_on_main_thread(move || {
        use gtk::prelude::*;
        let Some(win) = handle.get_webview_window(&label) else { return };
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
    Ok(dir)
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
}

/// The UI's remembered state (the `ui` object of `winamp.json`).
pub fn ui_prefs(app: &AppHandle) -> serde_json::Map<String, serde_json::Value> {
    read_prefs(app).ui
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

fn read_prefs(app: &AppHandle) -> Prefs {
    prefs_path(app)
        .ok()
        .and_then(|p| std::fs::read(p).ok())
        .and_then(|b| serde_json::from_slice(&b).ok())
        .unwrap_or_default()
}

fn write_prefs(app: &AppHandle, prefs: &Prefs) -> Result<(), String> {
    let json = serde_json::to_vec_pretty(prefs).map_err(|e| e.to_string())?;
    std::fs::write(prefs_path(app)?, json).map_err(|e| e.to_string())
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SkinEntry {
    /// File name without the extension, as Winamp's skin menu shows it.
    pub name: String,
    pub path: String,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SkinList {
    pub dir: String,
    pub skins: Vec<SkinEntry>,
    /// The remembered choice; `None` = the built-in skin.
    pub current: Option<String>,
}

/// Every `.wsz`/`.zip` in [`skins_dir`], sorted by name.
pub fn list(app: &AppHandle) -> Result<SkinList, String> {
    let dir = skins_dir(app)?;
    let mut skins: Vec<SkinEntry> = std::fs::read_dir(&dir)
        .map_err(|e| e.to_string())?
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| {
            p.extension()
                .and_then(|x| x.to_str())
                .is_some_and(|x| x.eq_ignore_ascii_case("wsz") || x.eq_ignore_ascii_case("zip"))
        })
        .map(|p| SkinEntry {
            name: p.file_stem().unwrap_or_default().to_string_lossy().into_owned(),
            path: p.to_string_lossy().into_owned(),
        })
        .collect();
    skins.sort_by_key(|s| s.name.to_lowercase());
    Ok(SkinList { dir: dir.to_string_lossy().into_owned(), skins, current: read_prefs(app).skin })
}

/// Copy a picked skin file into [`skins_dir`] and return its new path. Parsed first, so a file
/// that isn't a usable skin never lands in the menu.
pub fn import(app: &AppHandle, src: &str) -> Result<String, String> {
    let bytes = std::fs::read(src).map_err(|e| format!("couldn't read {src}: {e}"))?;
    skin::load(&bytes).map_err(|e| format!("not a Winamp skin: {e}"))?;
    let name = std::path::Path::new(src).file_name().ok_or("no file name")?;
    let dest = skins_dir(app)?.join(name);
    if std::path::Path::new(src) != dest {
        std::fs::write(&dest, bytes).map_err(|e| e.to_string())?;
    }
    Ok(dest.to_string_lossy().into_owned())
}

/// Load `path` (`None` = built-in) and remember it as the skin to open with next time. Only
/// remembered once it has parsed, so a broken pick can't stick.
pub async fn select(app: &AppHandle, path: Option<String>) -> Result<SkinPayload, String> {
    let payload = load(path.as_deref()).await?;
    update_prefs(app, |prefs| prefs.skin = path)?;
    Ok(payload)
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

/// Parse a `.wsz` at `path` (or the built-in default) and hand back every sprite sheet
/// (PNG-encoded) plus the window shape/colors/playlist styling the UI needs to draw it.
async fn load(path: Option<&str>) -> Result<SkinPayload, String> {
    let bytes = match path {
        Some(path) => std::fs::read(path).map_err(|e| format!("couldn't read {path}: {e}"))?,
        None => DEFAULT_SKIN.to_vec(),
    };
    let parsed = skin::load(&bytes).map_err(|e| e.to_string())?;

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
    })
}
