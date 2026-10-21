// Winamp's keyboard shortcuts, in every Winamp window. Only keys Limusic's own shortcuts
// (shortcuts.ts, which run in these windows too) leave free: its Ctrl+D/F/S/R/M/Q, Ctrl+, and
// Ctrl+. and Space stay Limusic's, so double size is Ctrl+2 rather than Winamp's Ctrl+D. Nothing
// fires while typing in a text box. The Winamp window runs them all; a floating panel forwards
// them to it, bar the ones about its own selection.
import { emitTo } from '@tauri-apps/api/event';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { typing } from '$lib/shortcuts';
import {
	cycleRepeat,
	nextTrack,
	nudgeVolume,
	openUrlDialog,
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
	toggleShuffle,
	zoomLyrics
} from './skinApi.js';
import { toggleTimeRemaining } from './input.js';
import { removeSelected } from './playlistActions.js';
import { uiState } from './uiState.js';

/** @typedef {'previous' | 'play' | 'pause' | 'stop' | 'next' | 'back' | 'forward' | 'louder' | 'quieter'
 *   | 'shuffle' | 'repeat' | 'search' | 'url' | 'remove' | 'playSelected' | 'onTop' | 'double' | 'time'
 *   | 'playlist' | 'eq' | 'art' | 'lyrics' | 'lyricsBigger' | 'lyricsSmaller' | 'lyricsReset'} KeyAction */

/**
 * The action a key press means, or null if it isn't one of ours.
 * @param {KeyboardEvent} e
 * @returns {KeyAction | null}
 */
function actionFor(e) {
	if (typing(e.target) || e.defaultPrevented) return null;
	const ctrl = e.ctrlKey || e.metaKey;
	const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
	if (e.altKey && !ctrl && !e.shiftKey) {
		return /** @type {Record<string, KeyAction>} */ ({ e: 'playlist', g: 'eq', a: 'art', y: 'lyrics' })[key] ?? null;
	}
	// Lyrics text size, the keys Limusic zooms its own window with. Shift allowed: `+` is
	// Shift+= on many layouts. The numpad's +, - and 0 give the same keys.
	if (ctrl && !e.altKey) {
		const zoom = /** @type {Record<string, KeyAction>} */ ({ '=': 'lyricsBigger', '+': 'lyricsBigger', '-': 'lyricsSmaller', 0: 'lyricsReset' })[key];
		if (zoom) return zoom;
	}
	if (ctrl && !e.altKey && !e.shiftKey) {
		return /** @type {Record<string, KeyAction>} */ ({ l: 'url', a: 'onTop', 2: 'double', t: 'time' })[key] ?? null;
	}
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
			// Only with the lyrics showing: a size change you can't see is a confusing one.
			if (uiState.lyrics.open) zoomLyrics(action === 'lyricsBigger' ? 1 : action === 'lyricsSmaller' ? -1 : 0);
			return;
		case 'remove':
			if (uiState.pl.open) removeSelected().catch(log('remove'));
			return;
		case 'playSelected':
			if (uiState.pl.open && uiState.pl.selected !== null) playIndex(uiState.pl.selected).catch(log('play'));
			return;
	}
}

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
