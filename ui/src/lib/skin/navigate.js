// Winamp mode opening Limusic's own window: its settings (Preferences, Ctrl+P), or a page of it:
// the Winamp window sends a path, the main window goes there and comes to the front. The main
// menu's "Limusic window" shows or hides it as it is (`toggleLimusic`). Winamp mode stays
// open alongside. Shown directly rather than through `show_main`, which "Always start in Winamp
// mode" would turn into opening Winamp mode again.
import { goto } from '$app/navigation';
import { emitTo, listen } from '@tauri-apps/api/event';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { limusicWindowShown, showLimusicWindow } from '$lib/api';
import { ui } from '$lib/player.svelte';

const EVENT = 'ytminamp-navigate';
/** Sent instead of a path: open Limusic's settings (Winamp's Preferences, Ctrl+P). */
const SETTINGS = 'settings';

/** Winamp's Preferences (Ctrl+P): Limusic's settings, in its window, for now. */
export function openLimusicSettings() {
	return emitTo('main', EVENT, SETTINGS);
}

/** The main menu's "Limusic window": shown where it was, or hidden again. */
export async function toggleLimusic() {
	await showLimusicWindow(!(await limusicWindowShown()));
}

/** In the main window: go where Winamp mode asks, and come to the front. */
export function onYtminampNavigate() {
	return listen(EVENT, async (e) => {
		// Shown first, and on screen, before navigating: WebKit snapshots the page it leaves for
		// the back/forward list by painting it through GL, and a hidden window has no surface on
		// Wayland to paint with. Navigating first crashed the app (gdk_wayland_window_get_egl_surface).
		const w = getCurrentWindow();
		await w.show();
		await w.unminimize();
		await w.setFocus();
		// Animation frames don't run while the window is hidden: two of them, it's painting.
		await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
		if (e.payload === SETTINGS) ui.settingsOpen = true;
		else await goto(/** @type {string} */ (e.payload));
	});
}
