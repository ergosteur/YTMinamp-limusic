// Where everything sits in the one window. Winamp stacks its windows under the main one: the
// equalizer, then the playlist editor, with the search panel (opened by eject) just above it,
// then album art and lyrics if they're docked rather than floating; each 275 wide. Any of them can float in a window of its own instead, which leaves it
// out of this one. Album art can instead sit beside the main window, at its height, on
// either side (docked left, everything else shifts right by its width), or float in a window of
// its own, which leaves it out of this one.
import { MAIN_H, MAIN_W } from './render/mainWindow.js';
import { PL_H } from './render/playlist.js';
import { artSize } from './render/albumArt.js';
import { EQ_H } from './render/equalizer.js';
import { uiState } from './uiState.js';

/** @typedef {'search' | 'playlist' | 'art' | 'eq' | 'lyrics'} PanelKind */

/** Docked lyrics: as wide as the stack until dragged wider or narrower (input.js), and as tall
 * as Winamp's classic main + EQ + playlist. */
export const LYRICS_W = MAIN_W;
export const LYRICS_MIN_W = 150;
export const LYRICS_MAX_W = 1200;
const CLASSIC_STACK_H = MAIN_H + EQ_H + PL_H;
/** @typedef {{ kind: PanelKind, x: number, y: number, w: number, h: number }} Placed */

/**
 * @returns {{ mainX: number, width: number, height: number, panels: Placed[] }} `panels` are the
 *   docked panels in canvas coordinates, side-docked album art included.
 */
export function dockedLayout() {
	const art = uiState.art;
	const side = art.open && (art.dock === 'left' || art.dock === 'right');
	const beside = artSize(art.frame, { height: MAIN_H }, art.caption);
	const mainX = side && art.dock === 'left' ? beside.w : 0;

	/** @type {Placed[]} */
	const panels = [];
	if (side) {
		panels.push({ kind: 'art', x: art.dock === 'left' ? 0 : MAIN_W, y: 0, w: beside.w, h: beside.h });
	}
	let y = MAIN_H;
	/** @param {PanelKind} kind @param {number} h */
	const stack = (kind, h) => {
		panels.push({ kind, x: mainX, y, w: MAIN_W, h });
		y += h;
	};
	// Winamp's own order (main, EQ, playlist), search just above the playlist it looks like, and
	// the newer windows below them.
	if (uiState.eq.open && uiState.eq.dock === 'stack') stack('eq', EQ_H);
	if (uiState.search.open && uiState.search.dock === 'stack') stack('search', PL_H);
	if (uiState.pl.open && uiState.pl.dock === 'stack') stack('playlist', PL_H);
	if (art.open && art.dock === 'stack') stack('art', artSize(art.frame, { width: MAIN_W }, art.caption).h);

	// Lyrics docked: to the right of the whole stack, at least as tall as the classic one (main,
	// EQ, playlist). Album art can't take that side then (skinApi.js keeps the two apart).
	const lyricsRight = uiState.lyrics.open && uiState.lyrics.dock === 'right';
	if (lyricsRight) {
		panels.push({ kind: 'lyrics', x: mainX + MAIN_W, y: 0, w: uiState.lyrics.width, h: Math.max(CLASSIC_STACK_H, y) });
	}
	const width = mainX + MAIN_W + (side && art.dock === 'right' ? beside.w : 0) + (lyricsRight ? uiState.lyrics.width : 0);
	const height = lyricsRight ? Math.max(CLASSIC_STACK_H, y) : y;
	return { mainX, width, height, panels };
}

/**
 * What's under canvas (x, y): a docked panel with (px, py) relative to its top-left, the main
 * window with (px, py) relative to its own, or null (empty corner of the window).
 * @param {number} x @param {number} y
 * @returns {import('./input.js').Hit | null}
 */
export function hitLayout(x, y) {
	const layout = dockedLayout();
	for (const p of layout.panels) {
		if (x >= p.x && x < p.x + p.w && y >= p.y && y < p.y + p.h) {
			return { kind: p.kind, px: x - p.x, py: y - p.y, x: p.x, y: p.y, w: p.w, h: p.h };
		}
	}
	if (x >= layout.mainX && x < layout.mainX + MAIN_W && y < MAIN_H) {
		return { kind: 'main', px: x - layout.mainX, py: y, x: layout.mainX, y: 0, w: MAIN_W, h: MAIN_H };
	}
	return null;
}
