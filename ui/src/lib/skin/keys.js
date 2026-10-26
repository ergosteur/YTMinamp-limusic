// Winamp's keyboard shortcuts, in every Winamp window. Only keys Limusic's own shortcuts
// (shortcuts.ts, which run in these windows too) leave free: its Ctrl+D/F/S/R/M/Q, Ctrl+, and
// Ctrl+. and Space stay Limusic's, so double size is Ctrl+2 rather than Winamp's Ctrl+D. Nothing
// fires while typing in a text box. The Winamp window runs them all; a floating panel forwards
// them to it, bar the ones about its own selection.
import { emitTo } from '@tauri-apps/api/event';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { keyOf, typing } from '$lib/shortcuts';
import { openLimusicSettings, toggleLimusic } from './navigate.js';
import { toggleLibrary } from './library.js';
import {
	cycleRepeat,
	nextTrack,
	nudgeVolume,
	openUrlDialog,
	closeToTrayNow,
	pause,
	play,
	playIndex,
	prevTrack,
	requestSearch,
	seekBy,
	stopPlayback,
	toggleAlwaysOnTop,
	toggleDoubleSize,
	togglePanel,
	fileInfoForSelection,
	toggleMilkdrop,
	toggleShuffle,
	zoomLyrics,
	toggleStopAfterCurrent,
	stopWithFadeout
} from './skinApi.js';
import { toggleTimeRemaining } from './input.js';
import { cropToSelected, removeSelected } from './playlistActions.js';
import { uiState } from './uiState.js';
import { openSkinBrowser } from './skinBrowser.js';

/** @typedef {'previous' | 'play' | 'pause' | 'stop' | 'next' | 'back' | 'forward' | 'louder' | 'quieter'
 *   | 'shuffle' | 'repeat' | 'search' | 'url' | 'remove' | 'playSelected' | 'onTop' | 'double' | 'time'
 *   | 'playlist' | 'eq' | 'art' | 'lyrics' | 'lyricsBigger' | 'lyricsSmaller' | 'lyricsReset' | 'milkdrop' | 'fileInfo' | 'crop'
 *   | 'stopAfter' | 'stopFade' | 'library' | 'limusic' | 'searchPanel' | 'prefs' | 'tray' | 'skins'} KeyAction */

/**
 * The key, as Limusic's `keyOf` reads it, except where a modifier or the layout turns one of our
 * letters or digits into something else: Option on a Mac (Option+G is ©, Option+E a dead key),
 * AZERTY's digit row (Ctrl+2 is é). Those are read by the physical key instead.
 * @param {KeyboardEvent} e
 */
export function keyName(e) {
	const k = keyOf(e);
	if (k === 'Dead' || (k.length === 1 && k.charCodeAt(0) > 127)) {
		if (/^Key[A-Z]$/.test(e.code)) return e.code.slice(3).toLowerCase();
		if (/^Digit\d$/.test(e.code)) return e.code.slice(5);
	}
	return k.length === 1 ? k.toLowerCase() : k;
}

/**
 * The action a key press means, or null if it isn't one of ours.
 * @param {KeyboardEvent} e
 * @returns {KeyAction | null}
 */
function actionFor(e) {
	if (typing(e.target) || e.defaultPrevented) return null;
	const ctrl = e.ctrlKey || e.metaKey;
	const key = keyName(e);
	if (e.altKey && !ctrl && !e.shiftKey) {
		return /** @type {Record<string, KeyAction>} */ ({ e: 'playlist', g: 'eq', a: 'art', y: 'lyrics', k: 'searchPanel', 3: 'fileInfo', l: 'library', m: 'limusic', s: 'skins' })[key] ?? null;
	}
	// Lyrics text size, the keys Limusic zooms its own window with. Shift allowed: `+` is
	// Shift+= on many layouts. The numpad's +, - and 0 give the same keys.
	if (ctrl && !e.altKey) {
		const zoom = /** @type {Record<string, KeyAction>} */ ({ '=': 'lyricsBigger', '+': 'lyricsBigger', '-': 'lyricsSmaller', 0: 'lyricsReset' })[key];
		if (zoom) return zoom;
	}
	// Winamp's start/stop visualization plugin.
	if (ctrl && e.shiftKey && !e.altKey && key === 'k') return 'milkdrop';
	if (ctrl && !e.altKey && !e.shiftKey) {
		return (
			/** @type {Record<string, KeyAction>} */ ({
				l: 'url',
				p: 'prefs',
				a: 'onTop',
				2: 'double',
				t: 'time',
				Delete: 'crop',
				v: 'stopAfter',
				// J's, held with Ctrl: Ctrl+F is Limusic's next track.
				j: 'search',
				// Close to tray, ⌘W on macOS: away, still running. (Alt+W stays free for shade.)
				w: 'tray'
			})[key] ?? null
		);
	}
	if (e.shiftKey && !ctrl && !e.altKey && key === 'v') return 'stopFade';
	if (ctrl || e.altKey || e.shiftKey) return null;
	return (
		/** @type {Record<string, KeyAction>} */ ({
			z: 'previous',
			x: 'play',
			c: 'pause',
			v: 'stop',
			b: 'next',
			ArrowLeft: 'back',
			ArrowRight: 'forward',
			ArrowUp: 'louder',
			ArrowDown: 'quieter',
			s: 'shuffle',
			r: 'repeat',
			j: 'search',
			Delete: 'remove',
			Enter: 'playSelected'
		})[key] ?? null
	);
}

const log = (/** @type {string} */ what) => (/** @type {unknown} */ e) => console.error(`${what} failed`, e);

/** Do `action` (in the Winamp window). @param {KeyAction} action */
export function runKey(action) {
	switch (action) {
		case 'previous': return void prevTrack().catch(log('previous'));
		case 'play': return void play().catch(log('play'));
		case 'pause': return void pause().catch(log('pause'));
		case 'stop': return void stopPlayback().catch(log('stop'));
		case 'next': return void nextTrack().catch(log('next'));
		case 'back': return seekBy(-5);
		case 'forward': return seekBy(5);
		case 'louder': return nudgeVolume(5);
		case 'quieter': return nudgeVolume(-5);
		case 'shuffle': return void toggleShuffle().catch(log('shuffle'));
		case 'repeat': return void cycleRepeat().catch(log('repeat'));
		case 'search': return requestSearch();
		case 'url': return openUrlDialog();
		case 'onTop': return toggleAlwaysOnTop();
		case 'double': return void toggleDoubleSize();
		case 'time': return toggleTimeRemaining();
		case 'playlist':
		case 'eq':
		case 'art':
		case 'lyrics':
			return togglePanel(action);
		case 'lyricsBigger':
		case 'lyricsSmaller':
		case 'lyricsReset':
			// Only with the lyrics showing: an unseen size change is a confusing one.
			if (uiState.lyrics.open) zoomLyrics(action === 'lyricsBigger' ? 1 : action === 'lyricsSmaller' ? -1 : 0);
			return;
		case 'milkdrop':
			return toggleMilkdrop();
		case 'fileInfo':
			return fileInfoForSelection();
		case 'crop':
			if (plDocked()) cropToSelected().catch(log('crop'));
			return;
		case 'remove':
			if (plDocked()) removeSelected().catch(log('remove'));
			return;
		case 'playSelected':
			if (plDocked() && uiState.pl.selected !== null) playIndex(uiState.pl.selected).catch(log('play'));
			return;
		case 'stopAfter':
			return toggleStopAfterCurrent();
		case 'searchPanel':
			return togglePanel('search');
		case 'library':
			return void toggleLibrary().catch(log('media library'));
		case 'limusic':
			return void toggleLimusic().catch(log('limusic window'));
		case 'prefs':
			return void openLimusicSettings().catch(log('preferences'));
		case 'tray':
			return closeToTrayNow();
		case 'skins':
			return void openSkinBrowser().catch(log('skin browser'));
		case 'stopFade':
			return void stopWithFadeout().catch(log('stop with fadeout'));
	}
}

/** The playlist is in this window. Floating, its selection lives in its own window, which handles
 *  these keys itself: this one's would be left over from before it floated. */
const plDocked = () => uiState.pl.open && uiState.pl.dock !== 'float';

/**
 * Listen for the shortcuts in this window. `local` gets first go at each (a floating playlist
 * handles Delete/Enter on its own selection); the Winamp window runs the rest, and is sent them
 * from anywhere else.
 * @param {(action: KeyAction) => boolean} [local] true if it handled the action
 */
export function attachKeys(local) {
	const inWinamp = getCurrentWindow().label === 'winamp';
	const onKey = (/** @type {KeyboardEvent} */ e) => {
		const action = actionFor(e);
		if (!action) return;
		e.preventDefault();
		if (local?.(action)) return;
		if (inWinamp) runKey(action);
		else emitTo('winamp', 'winamp-key', action).catch(() => {});
	};
	window.addEventListener('keydown', onKey);
	return () => window.removeEventListener('keydown', onKey);
}
