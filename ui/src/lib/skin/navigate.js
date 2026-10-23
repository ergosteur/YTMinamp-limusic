// Winamp mode opening a page of the full Limusic window (the playlist's + → Browse library, File
// info's artist and album): the Winamp window sends a path, the main window goes there and comes
// to the front. Media Library (Alt+L) shows or hides that window as it is (`toggleLimusic`). Winamp mode stays
// open alongside. Shown directly rather than through `show_main`, which "Always start in Winamp
// mode" would turn into opening Winamp mode again.
import { goto } from '$app/navigation';
import { emitTo, listen } from '@tauri-apps/api/event';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { limusicWindowShown, showLimusicWindow } from '$lib/api';

const EVENT = 'ytminamp-navigate';

/** In a Winamp window: show `path` (e.g. '/library') in the main window. @param {string} path */
export function openInLimusic(path) {
	return emitTo('main', EVENT, path);
}

/** Winamp's Media Library (Alt+L): Limusic's own window, shown where it was, or hidden again. */
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
		await goto(/** @type {string} */ (e.payload));
	});
}
