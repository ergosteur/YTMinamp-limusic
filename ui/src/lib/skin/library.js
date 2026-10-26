// Winamp mode's Media Library: Limusic's own pages (home, library, artist, album, playlist,
// search), floating in a window of their own (label `winamp-library`, MediaLibraryWindow.svelte)
// or docked in the Winamp window, right of the stack (WinampSkin.svelte), either way in the skin's
// generic frame and genex.bmp's colours (LibraryPages.svelte, libraryTheme.js). The Winamp window
// owns where it is, as it does for every panel (skinApi.js `setPanelOpen`): other windows ask it.
// Alt+L and the main menu open and close it; Show (artist) in Media Library and File info's links
// open it at that page, and the menus' Import from Spotify and Listen Together at that dialog.
import { goto } from '$app/navigation';
import { emit, emitTo, listen } from '@tauri-apps/api/event';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow';
import * as api from '$lib/api';
import { initImport, openImport } from '$lib/import.svelte';
import { applyLtState } from '$lib/lt.svelte';
import { auth, loadBlocked, loadLibrary, loadLibraryExtras, prefs, savedIn, ui } from '$lib/player.svelte';
import { parseScrobbleConfig } from '$lib/scrobble';
import { doubleFactor } from './pixels.js';
import { uiState } from './uiState.js';
import { setPanelOpen, togglePanel } from './skinApi.js';

export const LIBRARY_LABEL = 'winamp-library';
/** A page for the library window to show, sent to it alone. */
const NAVIGATE_EVENT = 'winamp-library-navigate';
/** The library window, just opened, asking for the page it was opened for. */
const READY_EVENT = 'winamp-library-ready';
/** Another window asking the Winamp window to show the library, at a page or not. */
const OPEN_EVENT = 'winamp-library-open';
/** A Limusic dialog for the library window to show, sent to it alone. */
const DIALOG_EVENT = 'winamp-library-dialog';
/** Its size whenever its window opens: Limusic's pages need room (shrunk to a smaller screen). */
export const LIBRARY_SIZE = { w: 760, h: 520 };

/**
 * A Limusic dialog the library shows on request: the importer (reading `link` straight away, if
 * given) or Listen Together.
 * @typedef {{ kind: 'import', link?: string } | { kind: 'listen-together' }} LibraryDialog
 */

/** Where the next library window opens (the Winamp window's, for one still opening). */
let pending = /** @type {string | null} */ (null);
/** And the dialog it opens with. */
let pendingDialog = /** @type {LibraryDialog | null} */ (null);
let listening = false;

/** The page this window shows: what a library moving between docked and floating takes along. */
export const currentPage = () => location.pathname + location.search;

/**
 * In the Winamp window: open the library's window (setPanelOpen's, floating), at the page set for
 * it (`floatLibrary`, `showLibrary`), if any.
 */
export async function openLibraryWindow() {
	if (!listening) {
		listening = true;
		await listen(READY_EVENT, () => {
			if (pending) emitTo(LIBRARY_LABEL, NAVIGATE_EVENT, pending).catch(() => {});
			if (pendingDialog) emitTo(LIBRARY_LABEL, DIALOG_EVENT, pendingDialog).catch(() => {});
			pending = null;
			pendingDialog = null;
		});
	}
	const f = doubleFactor();
	await api.openWinampPanel('library', LIBRARY_SIZE.w * f, LIBRARY_SIZE.h * f);
}

/**
 * Show the Media Library, at `path` (a Limusic route, '/album/MPRE…') if given, from any window:
 * where it is, or where it was last (floating, the first time). With `dialog`, that dialog opens
 * over it.
 * @param {string} [path]
 * @param {LibraryDialog} [dialog]
 */
export async function openLibrary(path, dialog) {
	const label = getCurrentWindow().label;
	if (label === LIBRARY_LABEL) {
		if (path) await goto(path);
		if (dialog) showDialog(dialog);
	} else if (label === 'winamp') {
		await showLibrary(path ?? null, dialog ?? null);
	} else {
		await emitTo('winamp', OPEN_EVENT, { path: path ?? null, dialog: dialog ?? null });
	}
}

/** Where the library shows (this window): open a Limusic dialog over it. @param {LibraryDialog} dialog */
function showDialog(dialog) {
	if (dialog.kind === 'import') openImport(dialog.link);
	else ui.ltOpen = true;
}

/**
 * In the Winamp window: show the library at `path`, with `dialog` over it.
 * @param {string | null} path
 * @param {LibraryDialog | null} dialog
 */
async function showLibrary(path, dialog) {
	const lib = uiState.library;
	if (lib.open && lib.dock === 'right') {
		if (path) await goto(path);
		if (dialog) showDialog(dialog);
	} else if (lib.open) {
		await api.openWinampPanel('library', 0, 0); // brings it to the front
		if (path) await emitTo(LIBRARY_LABEL, NAVIGATE_EVENT, path);
		if (dialog) await emitTo(LIBRARY_LABEL, DIALOG_EVENT, dialog);
	} else if (lib.dock === 'right') {
		setPanelOpen('library', true);
		if (path) await goto(path);
		if (dialog) showDialog(dialog);
	} else {
		pending = path;
		pendingDialog = dialog;
		setPanelOpen('library', true);
	}
}

/** In the Winamp window: float the docked library, at `path`. @param {string} path */
export function floatLibrary(path) {
	pending = path;
	setPanelOpen('library', true, 'float');
}

/** In the Winamp window: show the library wherever another window asks. */
export function onLibraryOpenRequest() {
	return listen(OPEN_EVENT, (e) => {
		const { path, dialog } = /** @type {{ path: string | null, dialog: LibraryDialog | null }} */ (e.payload);
		return showLibrary(path, dialog);
	});
}

/** Alt+L, the main menu: show the Media Library where it was last, or hide it. */
export async function toggleLibrary() {
	if (getCurrentWindow().label === 'winamp') togglePanel('library');
	else await emitTo('winamp', 'winamp-panel-toggle', 'library');
}

/** In the library window: close it (its ✕, Escape, Alt+L), through the Winamp window. */
export function closeLibrary() {
	return emitTo('winamp', 'winamp-panel-dock', { kind: 'library', dock: null });
}

/** In the library window: dock it (its titlebar's double-click), at the page it shows. */
export function dockLibrary() {
	return emitTo('winamp', 'winamp-panel-dock', { kind: 'library', dock: 'right', path: currentPage() });
}

/** Whether the Media Library is showing (the main menu's tick, in the Winamp window). */
export async function libraryShown() {
	return uiState.library.open;
}

/**
 * In the library window: go where the other windows ask, and open the dialogs they ask for, then
 * say it's ready for the first.
 */
export async function onLibraryNavigate() {
	const here = getCurrentWebviewWindow();
	const unlistenPage = await here.listen(NAVIGATE_EVENT, (e) => goto(/** @type {string} */ (e.payload)));
	const unlistenDialog = await here.listen(DIALOG_EVENT, (e) => showDialog(/** @type {LibraryDialog} */ (e.payload)));
	await emit(READY_EVENT);
	return () => {
		unlistenPage();
		unlistenDialog();
	};
}

/**
 * Wherever the library shows (its window, or the Winamp window docked): what Limusic's window
 * loads at startup for its pages (initApp in full, which the Winamp windows don't run) and
 * reloads on a sign-in or out: the account (the home
 * greeting), the library (the sidebar's playlists) with saved albums and artists, which playlists
 * hold which tracks as last stored, blocked artists, the settings the menus read, a Spotify import
 * under way and the Listen Together room (both Rust's, followed here for their dialogs). Not
 * what's Limusic's window's to do once: the local folder scan, the playlist crawl, the language
 * push.
 * @returns {() => void} stops following sign-ins
 */
export function initLibraryPages() {
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
	initImport();
	api.ltGetState().then(applyLtState).catch(() => {});
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
