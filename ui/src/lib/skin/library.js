// Winamp mode's Media Library: Limusic's own pages (home, library, artist, album, playlist,
// search) in a window of their own (label `winamp-library`), in the skin's generic frame and
// genex.bmp's colours (MediaLibraryWindow.svelte, libraryTheme.js). Alt+L and the main menu open
// and close it; Go to artist / album and File info's links open it at that page.
import { goto } from '$app/navigation';
import { emit, emitTo, listen } from '@tauri-apps/api/event';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { WebviewWindow, getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow';
import * as api from '$lib/api';
import { auth, loadBlocked, loadLibrary, loadLibraryExtras, prefs, savedIn } from '$lib/player.svelte';
import { parseScrobbleConfig } from '$lib/scrobble';
import { doubleFactor } from './pixels.js';
import { flushPrefs, pref, savePref } from './prefs.js';

export const LIBRARY_LABEL = 'winamp-library';
/** A page for the library window to show, sent to it alone. */
const NAVIGATE_EVENT = 'winamp-library-navigate';
/** The library window, just opened, asking for the page it was opened for. */
const READY_EVENT = 'winamp-library-ready';
/** winamp.json's key for whether it's open. */
const OPEN_PREF = 'libraryOpen';
/** Its size when it first opens: Limusic's pages need room. */
export const LIBRARY_SIZE = { w: 760, h: 520 };

/** This window's page for a library window that's still opening. */
let pending = /** @type {string | null} */ (null);
let listening = false;

/**
 * Show the Media Library, at `path` (a Limusic route, '/album/MPRE…') if given, from any window.
 * @param {string} [path]
 */
export async function openLibrary(path) {
	if (getCurrentWindow().label === LIBRARY_LABEL) {
		if (path) await goto(path);
		return;
	}
	if (await WebviewWindow.getByLabel(LIBRARY_LABEL)) {
		await api.openWinampPanel('library', 0, 0); // brings it to the front
		if (path) await emitTo(LIBRARY_LABEL, NAVIGATE_EVENT, path);
		return;
	}
	if (path) {
		pending = path;
		if (!listening) {
			listening = true;
			await listen(READY_EVENT, () => {
				if (pending) emitTo(LIBRARY_LABEL, NAVIGATE_EVENT, pending).catch(() => {});
				pending = null;
			});
		}
	}
	const f = doubleFactor();
	await api.openWinampPanel('library', LIBRARY_SIZE.w * f, LIBRARY_SIZE.h * f);
}

/** Alt+L, the main menu: open the Media Library, or close it if it's open. */
export async function toggleLibrary() {
	if (await WebviewWindow.getByLabel(LIBRARY_LABEL)) await closeLibrary();
	else await openLibrary();
}

/**
 * Close the Media Library, from any window, and remember it closed. Open is remembered by the
 * window itself (`rememberLibraryOpen`), so one still open when the app quits comes back with
 * the Winamp window (skinApi.js).
 */
export async function closeLibrary() {
	savePref(OPEN_PREF, false);
	await flushPrefs();
	await api.closeWinampPanel('library');
}

/** In the library window: remember it open, and closed if the desktop closes it (Alt+F4). */
export function rememberLibraryOpen() {
	savePref(OPEN_PREF, true);
	flushPrefs().catch(() => {});
	const unlisten = getCurrentWindow().onCloseRequested(async () => {
		savePref(OPEN_PREF, false);
		await flushPrefs().catch(() => {});
	});
	return () => void unlisten.then((f) => f());
}

/** Whether the Media Library was open when the Winamp window last went: open on a first run. */
export const libraryWasOpen = () => pref(OPEN_PREF, true);

/** Whether the Media Library window is open (the main menu's tick). */
export async function libraryShown() {
	return !!(await WebviewWindow.getByLabel(LIBRARY_LABEL));
}

/** In the library window: go where the other windows ask, then say it's ready for the first. */
export async function onLibraryNavigate() {
	const unlisten = await getCurrentWebviewWindow().listen(NAVIGATE_EVENT, (e) => goto(/** @type {string} */ (e.payload)));
	await emit(READY_EVENT);
	return unlisten;
}

/**
 * In the library window: what Limusic's window loads at startup for its pages (initApp in full,
 * which the Winamp windows don't run) and reloads on a sign-in or out: the account (the home
 * greeting), the library (the sidebar's playlists) with saved albums and artists, which playlists
 * hold which tracks as last stored, blocked artists, and the settings the menus read. Not what's
 * Limusic's window's to do once: the local folder scan, the playlist crawl, the language push,
 * Listen Together.
 * @returns {() => void} stops following sign-ins
 */
export function initLibraryWindow() {
	const load = (/** @type {boolean} */ force) => {
		loadLibrary(force);
		if (auth.account?.signedIn) loadLibraryExtras(force);
		api.playlistIndex()
			.then((map) => (savedIn.map = map))
			.catch(() => {});
	};
	api.getAccount()
		.then((a) => {
			auth.account = a;
			load(false);
		})
		.catch(() => {});
	loadBlocked();
	api.getSettings()
		.then((s) => {
			prefs.musicVideos = s.music_videos === 'true';
			prefs.autoplay = s.autoplay !== 'false';
			prefs.scrobbling = parseScrobbleConfig(s.lastfm_config).enabled;
		})
		.catch(() => {});
	// initApp's own handler sets the account and empties the library; filling it again is ours,
	// after that handler has run (this one is registered first).
	const unlisten = api.onAuthChanged(() => setTimeout(() => load(true)));
	return () => void unlisten.then((f) => f());
}
