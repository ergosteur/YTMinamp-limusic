import { getCurrentWindow } from '@tauri-apps/api/window';
import {
	BALANCE_POS,
	CBUTTONS,
	CBUTTONS_POS,
	CLOSE_BUTTON_POS,
	CLUTTER_BUTTONS,
	CLUTTER_POS,
	EQ_TOGGLE_POS,
	MINIMIZE_BUTTON_POS,
	OPTIONS_BUTTON_POS,
	PLAYLIST_TOGGLE_POS,
	POSBAR,
	REPEAT_POS,
	SHUFFLE_POS,
	SHUFREP,
	POSBAR_POS,
	POSBAR_THUMB_TRAVEL,
	SLIDER_THUMB_SIZE,
	TIME_POS,
	TITLE_BAR_POS,
	VIS_POS,
	VOLUME_POS
} from './render/sprites.js';
import { PL_H, PL_TRANSPORT_ORDER, PL_W, ROW_H, geometry, listRows, maxScroll } from './render/playlist.js';
import {
	cycleRepeat,
	flashMarquee,
	saveEq,
	toggleAlwaysOnTop,
	toggleDoubleSize,
	focusSearch,
	nextTrack,
	playIndex,
	playResult,
	prevTrack,
	seekTo,
	setVolume,
	stopPlayback,
	togglePlayPause,
	toggleShuffle
} from './skinApi.js';
import { ART_CLOSE, artTitleHeight } from './render/albumArt.js';
import { EQ_BANDS, eqHit, eqValueAt } from './render/equalizer.js';
import { LYRICS_WHEEL_ROWS } from './render/lyrics.js';
import { savePref } from './prefs.js';
import { uiState } from './uiState.js';
import { playback } from '$lib/player.svelte';
import { closeWinamp } from '$lib/api';

const TITLEBAR_BUTTON_SIZE = { w: 9, h: 9 };
const PLAYLIST_TOGGLE_SIZE = { w: 23, h: 12 };
const PL_TITLEBAR_H = 20;
/** A docked list panel's size; floating ones come in their own. */
const DOCKED = { w: PL_W, h: PL_H };

/** @param {{x: number, y: number}} pos @param {{w: number, h: number}} size @param {number} x @param {number} y */
function hits(pos, size, x, y) {
	return x >= pos.x && x < pos.x + size.w && y >= pos.y && y < pos.y + size.h;
}

const TRANSPORT_BUTTONS = /** @type {const} */ (['previous', 'play', 'pause', 'stop', 'next', 'eject']);

/** @param {number} x @param {number} y */
function buttonAt(x, y) {
	for (const name of TRANSPORT_BUTTONS) {
		if (hits(CBUTTONS_POS[name], CBUTTONS[name], x, y)) return name;
	}
	if (hits(PLAYLIST_TOGGLE_POS, PLAYLIST_TOGGLE_SIZE, x, y)) return 'playlist';
	if (hits(EQ_TOGGLE_POS, PLAYLIST_TOGGLE_SIZE, x, y)) return 'eq';
	if (hits(SHUFFLE_POS, SHUFREP.shuffle, x, y)) return 'shuffle';
	if (hits(REPEAT_POS, SHUFREP.repeat, x, y)) return 'repeat';
	if (x >= CLUTTER_POS.x && x < CLUTTER_POS.x + CLUTTER_POS.w) {
		for (const [letter, b] of Object.entries(CLUTTER_BUTTONS)) {
			if (y >= CLUTTER_POS.y + b.y && y < CLUTTER_POS.y + b.y + b.h) return `clutter-${letter}`;
		}
	}
	return null;
}

/** The window's host (see `attachInput`), for the buttons that open or close panels. */
let current = /** @type {Host | null} */ (null);

/** @param {string} name */
function runButtonAction(name) {
	const log = (/** @type {string} */ what) => (/** @type {unknown} */ e) => console.error(`${what} failed`, e);
	switch (name) {
		case 'play':
		case 'pause':
			togglePlayPause().catch(log('toggle play/pause'));
			return;
		case 'stop':
			stopPlayback().catch(log('stop'));
			return;
		case 'next':
			nextTrack().catch(log('next track'));
			return;
		case 'previous':
			prevTrack().catch(log('previous track'));
			return;
		case 'eject':
			current?.toggle('search');
			return;
		case 'playlist':
			current?.toggle('playlist');
			return;
		case 'eq':
			current?.toggle('eq');
			return;
		// The clutterbar (O opens the menu where it's pressed, in attachInput).
		case 'clutter-a':
			toggleAlwaysOnTop();
			return;
		case 'clutter-i':
			current?.toggle('art');
			return;
		case 'clutter-d':
			toggleDoubleSize();
			return;
		case 'clutter-v':
			toggleVisualizer();
			return;
		case 'shuffle':
			toggleShuffle().catch(log('shuffle'));
			return;
		case 'repeat':
			cycleRepeat().catch(log('repeat'));
			return;
		default:
			return;
	}
}

/**
 * Move an EQ slider (for show: nothing filters the sound yet) and remember it.
 * @param {'preamp' | number} slider @param {number} value 0-100
 */
function setEqSlider(slider, value) {
	if (slider === 'preamp') uiState.eq.preamp = value;
	else uiState.eq.bands[slider] = value;
	saveEq();
}

/** Elapsed or remaining time in the display (click it, the menu, Ctrl+T). */
export function toggleTimeRemaining() {
	uiState.timeRemaining = !uiState.timeRemaining;
	savePref('timeRemaining', uiState.timeRemaining);
}

/** The analyzer on or off (the analyzer itself, the clutterbar's V, the menu, the shortcut). */
export function toggleVisualizer() {
	uiState.visMode = uiState.visMode === 'analyzer' ? 'off' : 'analyzer';
	savePref('visMode', uiState.visMode);
}

/** @param {HTMLCanvasElement} canvas @param {MouseEvent} event */
function canvasPoint(canvas, event) {
	const rect = canvas.getBoundingClientRect();
	const scaleX = canvas.width / rect.width;
	const scaleY = canvas.height / rect.height;
	return { x: (event.clientX - rect.left) * scaleX, y: (event.clientY - rect.top) * scaleY };
}

/** The seek thumb's centre follows the pointer. @param {number} x */
function percentFromSeekX(x) {
	const offset = x - POSBAR_POS.x - POSBAR.thumb.w / 2;
	return Math.max(0, Math.min(1, offset / POSBAR_THUMB_TRAVEL));
}

/**
 * Volume/balance are horizontal in Winamp 2: the thumb's centre follows the pointer.
 * @param {{x: number, w: number}} pos @param {number} x
 */
function percentFromHorizontalX(pos, x) {
	const travel = pos.w - SLIDER_THUMB_SIZE.w;
	const offset = x - pos.x - SLIDER_THUMB_SIZE.w / 2;
	return Math.max(0, Math.min(1, offset / travel));
}

/** @typedef {'search' | 'playlist'} ListKind */
/**
 * A menu other than the main one: a search result's, or one of the playlist's bottom buttons'.
 * @typedef {{ kind: 'result', index: number } | { kind: 'add' | 'rem' | 'sel' | 'misc' | 'list' | 'presets' }} MenuTarget
 */
/** @typedef {{ w: number, h: number }} Size */
/**
 * What's under a point: the main window or a panel, with (px, py) relative to its top-left, and
 * where it sits and how big it is in the canvas.
 * @typedef {{ kind: 'main' | import('./layout.js').PanelKind, px: number, py: number, x: number, y: number, w: number, h: number }} Hit
 */
/**
 * What the window hosting the canvas does with it: the Winamp window lays out the main window
 * and its docked panels; a floating panel window holds just one panel.
 * @typedef {{
 *   hitTest: (x: number, y: number) => Hit | null,
 *   showMenu: (target: MenuTarget | null, at: { x: number, y: number }) => void,
 *   closePanel: (kind: import('./layout.js').PanelKind) => void,
 *   popOut: (kind: import('./layout.js').PanelKind) => void,
 *   moveArt: () => void,
 *   toggle: (kind: import('./layout.js').PanelKind) => void,
 *   mainX: () => number
 * }} Host
 */

/** @param {ListKind} kind */
function panelState(kind) {
	return kind === 'search' ? uiState.search : uiState.pl;
}

/** @param {ListKind} kind */
function rowCount(kind) {
	return kind === 'search' ? uiState.search.results.length : playback.queue.items.length;
}

/** @param {ListKind} kind @param {number} row @param {Size} [size] */
export function scrollTo(kind, row, size = DOCKED) {
	panelState(kind).scroll = Math.max(0, Math.min(maxScroll(rowCount(kind), listRows(kind, size).rows), row));
}

/**
 * Panel-relative y → scroll offset, centring the handle on the pointer.
 * @param {ListKind} kind @param {number} py @param {Size} size
 */
function scrollFromHandleY(kind, py, size) {
	const scroll = geometry(size).scroll;
	const t = (py - scroll.y - 9) / scroll.h;
	const max = maxScroll(rowCount(kind), listRows(kind, size).rows);
	scrollTo(kind, Math.round(Math.max(0, Math.min(1, t)) * max), size);
}

/**
 * The list row under panel-relative (x, py), or null.
 * @param {ListKind} kind @param {number} x @param {number} py @param {Size} [size]
 */
export function rowAt(kind, x, py, size = DOCKED) {
	const area = listRows(kind, size);
	if (!hits(area, { w: area.w, h: area.rows * ROW_H }, x, py)) return null;
	const i = panelState(kind).scroll + Math.floor((py - area.y) / ROW_H);
	return i < rowCount(kind) ? i : null;
}

/** The mini transport button under panel-relative (x, py), or null. @param {number} x @param {number} py @param {Size} size */
function transportAt(x, py, size) {
	const t = geometry(size).transport;
	if (py < t.y || py >= t.y + t.h || x < t.x) return null;
	return PL_TRANSPORT_ORDER[Math.floor((x - t.x) / t.w)] ?? null;
}

/**
 * The playlist's bottom button under panel-relative (x, py), or null.
 * @param {number} x @param {number} py @param {Size} size
 * @returns {import('./render/playlist.js').PlaylistButton | null}
 */
function playlistButtonAt(x, py, size) {
	const buttons = geometry(size).buttons;
	for (const [name, r] of Object.entries(buttons)) {
		if (hits(r, r, x, py)) return /** @type {import('./render/playlist.js').PlaylistButton} */ (name);
	}
	return null;
}

const PLAYLIST_BUTTON_TIPS = {
	add: 'Search YouTube Music, or open a YouTube link',
	rem: 'Remove the selected track, or clear the queue',
	sel: 'Save the queue as a playlist',
	misc: 'Sort or reverse what plays next',
	list: 'Load a playlist from your library'
};

/** Panel-relative (px, py) is on a framed panel's (album art, lyrics) close button. @param {Hit} hit */
function onArtClose(hit) {
	return hits({ x: hit.w + ART_CLOSE.dx, y: ART_CLOSE.y }, ART_CLOSE, hit.px, hit.py);
}

const BUTTON_TIPS = /** @type {Record<string, string>} */ ({
	previous: 'Previous track',
	play: 'Play',
	pause: 'Pause',
	stop: 'Stop',
	next: 'Next track',
	eject: 'Search YouTube Music (show/hide)',
	playlist: 'Toggle playlist editor',
	eq: 'Toggle album art'
});

const REPEAT_TIPS = { off: 'Repeat: off', all: 'Repeat: all', one: 'Repeat: track' };

/** @param {number} secs */
function clock(secs) {
	const s = Math.max(0, Math.floor(secs));
	return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

/**
 * What the control under `hit` does, for its tooltip; '' for none.
 * @param {Hit | null} hit
 */
function tooltipAt(hit) {
	if (!hit) return '';
	if (hit.kind === 'eq') {
		const h = eqHit(hit.px, hit.py);
		if (h === 'close') return 'Close equalizer';
		if (h === 'title') return 'Equalizer: for show, it doesn\'t change the sound yet (double-click to float or dock)';
		if (h === 'on') return 'Equalizer on/off';
		if (h === 'auto') return 'Auto-load presets (for show)';
		if (h === 'presets') return "Winamp's presets";
		if (h === 'preamp') return 'Preamp';
		if (typeof h === 'number') return `${EQ_BANDS[h]} Hz`;
		return '';
	}
	if (hit.kind === 'lyrics') {
		if (onArtClose(hit)) return 'Close lyrics';
		return 'Lyrics (scroll to look around; double-click the titlebar to float or dock)';
	}
	if (hit.kind === 'art') {
		if (onArtClose(hit)) return 'Close album art';
		if (hit.py < artTitleHeight(uiState.art.frame)) return 'Double-click to float or dock';
		return 'Album art (double-click to move it round the player; right-click for where it goes)';
	}
	const x = hit.px;
	const y = hit.py;
	if (hit.kind !== 'main') {
		const kind = hit.kind;
		const size = { w: hit.w, h: hit.h };
		const close = geometry(size).close;
		if (hits(close, close, x, y)) return kind === 'search' ? 'Close search' : 'Close playlist editor';
		if (y < PL_TITLEBAR_H) return 'Double-click to float or dock';
		const i = rowAt(kind, x, y, size);
		if (i !== null) {
			// The full line: rows are clipped to the panel's width.
			const item = kind === 'search' ? uiState.search.results[i] : playback.queue.items[i];
			const tip = item ? `${item.artists ? `${item.artists} - ` : ''}${item.title}` : '';
			return kind === 'search' ? `${tip}\nDouble-click to play, right-click for more` : tip;
		}
		const button = transportAt(x, y, size);
		if (button) return BUTTON_TIPS[button] ?? '';
		const pb = kind === 'playlist' ? playlistButtonAt(x, y, size) : null;
		return pb ? PLAYLIST_BUTTON_TIPS[pb] : '';
	}
	if (hits(CLOSE_BUTTON_POS, TITLEBAR_BUTTON_SIZE, x, y)) return 'Back to Limusic';
	if (hits(OPTIONS_BUTTON_POS, TITLEBAR_BUTTON_SIZE, x, y)) return 'Main menu (skins, shuffle, repeat)';
	if (hits(MINIMIZE_BUTTON_POS, TITLEBAR_BUTTON_SIZE, x, y)) return 'Minimize';
	if (hits(VIS_POS, VIS_POS, x, y)) return 'Click to turn the visualizer on/off';
	if (hits(TIME_POS, TIME_POS, x, y)) {
		return uiState.timeRemaining ? 'Time remaining (click for elapsed)' : 'Time elapsed (click for remaining)';
	}
	const button = buttonAt(x, y);
	if (button === 'shuffle') return `Shuffle: ${playback.queue.shuffle ? 'on' : 'off'}`;
	if (button === 'repeat') return REPEAT_TIPS[playback.queue.repeat ?? 'off'];
	if (button) return BUTTON_TIPS[button] ?? '';
	if (hits(POSBAR_POS, { w: 248, h: 10 }, x, y)) {
		return playback.duration > 0 ? `Seek (${clock(playback.position)} / ${clock(playback.duration)})` : 'Seek';
	}
	if (hits(VOLUME_POS, VOLUME_POS, x, y)) return `Volume: ${playback.volume}% (drag or scroll)`;
	if (hits(BALANCE_POS, BALANCE_POS, x, y)) return 'Balance (display only)';
	return '';
}

/**
 * @param {HTMLCanvasElement} canvas
 * @param {Host} host
 */
export function attachInput(canvas, host) {
	current = host;
	/** @type {{ what: 'seek' | 'volume' | 'balance' } | { what: 'scroll', kind: ListKind, top: number, size: Size } | { what: 'eq', slider: 'preamp' | number, top: number } | null} */
	let drag = null;
	/** The panel whose close button is held down. */
	let closing = /** @type {import('./layout.js').PanelKind | null} */ (null);
	/** Where a press on something draggable started: it becomes a window drag once the mouse
	 * moves, so a double-click still arrives (a drag started on press would swallow it). */
	let press = /** @type {{ x: number, y: number } | null} */ (null);

	/**
	 * Mouse-down inside a list panel, at panel-relative (x, py).
	 * @param {ListKind} kind @param {Hit} hit @param {MouseEvent} event
	 */
	function panelDown(kind, hit, event) {
		const view = panelState(kind);
		const size = { w: hit.w, h: hit.h };
		const g = geometry(size);
		const x = hit.px;
		const py = hit.py;
		if (hits(g.close, g.close, x, py)) {
			view.pressed = 'close';
			closing = kind;
			return;
		}
		if (py < PL_TITLEBAR_H) {
			if (event.detail >= 2) host.popOut(kind);
			else press = { x: event.screenX, y: event.screenY };
			return;
		}
		const scroll = g.scroll;
		if (x >= scroll.x && x < scroll.x + 8 && py >= scroll.y && py < scroll.y + scroll.h + 18) {
			drag = { what: 'scroll', kind, top: hit.y, size };
			view.draggingScroll = true;
			scrollFromHandleY(kind, py, size);
			return;
		}
		const i = rowAt(kind, x, py, size);
		if (i !== null) {
			view.selected = i;
			if (event.detail >= 2) {
				const play = kind === 'search' ? playResult(i) : playIndex(i);
				play.catch((e) => console.error('play failed', e));
			}
			// Typing carries on in the search box after picking a row with the mouse.
			if (kind === 'search') requestAnimationFrame(focusSearch);
			return;
		}
		const button = transportAt(x, py, size);
		if (button) {
			runButtonAction(button);
			return;
		}
		const pb = kind === 'playlist' ? playlistButtonAt(x, py, size) : null;
		if (pb) {
			const r = geometry(size).buttons[pb];
			host.showMenu({ kind: pb }, { x: hit.x + r.x, y: hit.y + r.y + r.h });
		}
	}

	canvas.addEventListener('contextmenu', (event) => {
		event.preventDefault();
		const { x, y } = canvasPoint(canvas, event);
		const at = { x: event.clientX, y: event.clientY };
		const hit = host.hitTest(x, y);
		const i = hit?.kind === 'search' ? rowAt('search', hit.px, hit.py, hit) : null;
		if (i !== null) {
			uiState.search.selected = i;
			host.showMenu({ kind: 'result', index: i }, at);
		} else {
			host.showMenu(null, at);
		}
	});

	canvas.addEventListener('mousedown', (event) => {
		if (event.button !== 0) return;
		const point = canvasPoint(canvas, event);
		const hit = host.hitTest(point.x, point.y);
		if (!hit) return;
		if (hit.kind === 'art') {
			if (onArtClose(hit)) {
				uiState.art.closePressed = true;
				closing = 'art';
			} else if (event.detail >= 2) {
				// Titlebar: float/dock, like the other panels. The picture: move it round the player.
				if (hit.py < artTitleHeight(uiState.art.frame)) host.popOut('art');
				else host.moveArt();
			} else {
				// The whole window drags, not just its titlebar: it's all picture, nothing to click.
				press = { x: event.screenX, y: event.screenY };
			}
			return;
		}
		if (hit.kind === 'eq') {
			const h = eqHit(hit.px, hit.py);
			const eq = uiState.eq;
			if (h === 'close' || h === 'on' || h === 'auto' || h === 'presets') {
				eq.pressed = h;
				if (h === 'close') closing = 'eq';
				if (h === 'presets') {
					host.showMenu({ kind: 'presets' }, { x: hit.x + 217, y: hit.y + 30 });
					eq.pressed = null;
				}
			} else if (h === 'title') {
				if (event.detail >= 2) host.popOut('eq');
				else press = { x: event.screenX, y: event.screenY };
			} else if (h !== null) {
				drag = { what: 'eq', slider: h, top: hit.y };
				eq.dragging = h;
				setEqSlider(h, eqValueAt(hit.py));
			}
			return;
		}
		if (hit.kind === 'lyrics') {
			if (onArtClose(hit)) {
				uiState.lyrics.closePressed = true;
				closing = 'lyrics';
			} else if (hit.py < artTitleHeight(uiState.art.frame) && event.detail >= 2) {
				host.popOut('lyrics');
			} else {
				press = { x: event.screenX, y: event.screenY };
			}
			return;
		}
		if (hit.kind !== 'main') {
			panelDown(hit.kind, hit, event);
			return;
		}
		const x = hit.px;
		const y = hit.py;
		if (buttonAt(x, y) === 'clutter-o') {
			// Under the letter, like Winamp's.
			host.showMenu(null, { x: hit.x + CLUTTER_POS.x, y: CLUTTER_POS.y + CLUTTER_BUTTONS.o.y + CLUTTER_BUTTONS.o.h });
			return;
		}

		if (hits(CLOSE_BUTTON_POS, TITLEBAR_BUTTON_SIZE, x, y)) {
			closeWinamp().catch((e) => console.error('close winamp failed', e));
			return;
		}
		if (hits(OPTIONS_BUTTON_POS, TITLEBAR_BUTTON_SIZE, x, y)) {
			// Under the button, like Winamp's.
			host.showMenu(null, { x: hit.x + OPTIONS_BUTTON_POS.x, y: OPTIONS_BUTTON_POS.y + TITLEBAR_BUTTON_SIZE.h });
			return;
		}
		if (hits(MINIMIZE_BUTTON_POS, TITLEBAR_BUTTON_SIZE, x, y)) {
			getCurrentWindow().minimize();
			return;
		}
		if (hits(TITLE_BAR_POS, TITLE_BAR_POS, x, y)) {
			getCurrentWindow().startDragging();
			return;
		}
		if (hits(VIS_POS, VIS_POS, x, y)) {
			toggleVisualizer();
			return;
		}
		if (hits(TIME_POS, TIME_POS, x, y)) {
			toggleTimeRemaining();
			return;
		}
		const button = buttonAt(x, y);
		if (button) {
			uiState.pressedButton = button;
			return;
		}
		if (hits(POSBAR_POS, { w: 248, h: 10 }, x, y)) {
			drag = { what: 'seek' };
			uiState.draggingSeek = true;
			uiState.draggingPositionSecs = percentFromSeekX(x) * playback.duration;
			return;
		}
		if (hits(VOLUME_POS, VOLUME_POS, x, y)) {
			drag = { what: 'volume' };
			uiState.draggingVolume = true;
			uiState.draggingVolumeValue = Math.round(percentFromHorizontalX(VOLUME_POS, x) * 100);
			setVolume(uiState.draggingVolumeValue).catch((e) => console.error('set_volume failed', e));
			return;
		}
		if (hits(BALANCE_POS, BALANCE_POS, x, y)) {
			drag = { what: 'balance' };
			// Cosmetic only — see uiState.js.
			uiState.balance = Math.round(percentFromHorizontalX(BALANCE_POS, x) * 200 - 100);
		}
	});

	canvas.addEventListener(
		'wheel',
		(event) => {
			const point = canvasPoint(canvas, event);
			const hit = host.hitTest(point.x, point.y);
			if (hit?.kind === 'lyrics') {
				event.preventDefault();
				uiState.lyrics.nudge += event.deltaY > 0 ? LYRICS_WHEEL_ROWS : -LYRICS_WHEEL_ROWS;
				return;
			}
			if (hit?.kind === 'main' && hits(VOLUME_POS, VOLUME_POS, hit.px, hit.py)) {
				// The wheel on the volume slider: 5% a notch, the level shown in the title, as Winamp does.
				event.preventDefault();
				const volume = Math.max(0, Math.min(100, Math.round(playback.volume) + (event.deltaY < 0 ? 5 : -5)));
				setVolume(volume).catch((e) => console.error('set_volume failed', e));
				flashMarquee(`Volume: ${volume}%`);
				return;
			}
			if (hit?.kind !== 'search' && hit?.kind !== 'playlist') return;
			event.preventDefault();
			scrollTo(hit.kind, panelState(hit.kind).scroll + (event.deltaY > 0 ? 3 : -3), hit);
		},
		{ passive: false }
	);

	// Native tooltips: the canvas's `title`, retargeted to whatever is under the pointer.
	canvas.addEventListener('mousemove', (event) => {
		const { x, y } = canvasPoint(canvas, event);
		const tip = tooltipAt(host.hitTest(x, y));
		if (canvas.title !== tip) canvas.title = tip;
	});

	window.addEventListener('mousemove', (event) => {
		if (press && Math.hypot(event.screenX - press.x, event.screenY - press.y) > 3) {
			press = null;
			getCurrentWindow().startDragging();
		}
		if (!drag) return;
		const { x: cx, y } = canvasPoint(canvas, event);
		const x = cx - host.mainX();
		if (drag.what === 'seek') {
			uiState.draggingPositionSecs = percentFromSeekX(x) * playback.duration;
		} else if (drag.what === 'volume') {
			uiState.draggingVolumeValue = Math.round(percentFromHorizontalX(VOLUME_POS, x) * 100);
			setVolume(uiState.draggingVolumeValue).catch((e) => console.error('set_volume failed', e));
		} else if (drag.what === 'balance') {
			uiState.balance = Math.round(percentFromHorizontalX(BALANCE_POS, x) * 200 - 100);
		} else if (drag.what === 'scroll') {
			scrollFromHandleY(drag.kind, y - drag.top, drag.size);
		} else if (drag.what === 'eq') {
			setEqSlider(drag.slider, eqValueAt(y - drag.top));
		}
	});

	window.addEventListener('mouseup', () => {
		press = null;
		if (drag?.what === 'seek') {
			seekTo(uiState.draggingPositionSecs).catch((e) => console.error('seek failed', e));
			uiState.draggingSeek = false;
		} else if (drag?.what === 'volume') {
			uiState.draggingVolume = false;
		} else if (drag?.what === 'scroll') {
			panelState(drag.kind).draggingScroll = false;
		} else if (drag?.what === 'eq') {
			uiState.eq.dragging = null;
		}
		drag = null;
		const eqPressed = uiState.eq.pressed;
		if (eqPressed === 'on' || eqPressed === 'auto') {
			uiState.eq[eqPressed] = !uiState.eq[eqPressed];
			saveEq();
		}
		uiState.eq.pressed = null;

		if (uiState.pressedButton) {
			runButtonAction(uiState.pressedButton);
			uiState.pressedButton = null;
		}
		if (closing === 'art' || closing === 'lyrics') {
			uiState[closing].closePressed = false;
			host.closePanel(closing);
		} else if (closing === 'search' || closing === 'playlist') {
			panelState(closing).pressed = null;
			host.closePanel(closing);
		} else if (closing === 'eq') {
			host.closePanel('eq');
		}
		closing = null;
	});
}
