// Where everything sits in the one window. Winamp stacks its windows under the main one: the
// equalizer, then the playlist editor, with the search panel (opened by eject) just above it,
// then album art and lyrics if they're docked rather than floating; each 275 wide. Any of them can float in a window of its own instead, which leaves it
// out of this one. Album art can instead sit beside the main window, at its height (or the main
// window's and the EQ's together, `artTall`), on either side (docked left, everything else
// shifts right by its width), or float in a window of its own, which leaves it out of this one.
import { MAIN_H, MAIN_W } from './render/mainWindow.js';
import { PL_H } from './render/playlist.js';
import { artSize } from './render/albumArt.js';
import { EQ_H } from './render/equalizer.js';
import { uiState } from './uiState.js';

/** @typedef {'search' | 'playlist' | 'art' | 'eq' | 'lyrics' | 'library'} PanelKind */

/** Docked lyrics: as wide as the stack until dragged wider or narrower (input.js), and as tall
 * as Winamp's classic main + EQ + playlist. */
export const LYRICS_W = MAIN_W;
export const LYRICS_MIN_W = 150;
export const LYRICS_MAX_W = 1200;
const CLASSIC_STACK_H = MAIN_H + EQ_H + PL_H;
/** The docked Media Library's width: dragged from its right edge, within these. */
export const LIBRARY_MIN_W = 480;
export const LIBRARY_MAX_W = 1600;
/** Docked lyrics narrow this far to fit the screen before the library gives way (dockedLayout). */
const LYRICS_FIT_MIN_W = 380;
/** @typedef {{ kind: PanelKind, x: number, y: number, w: number, h: number }} Placed */

/** Side-docked album art's two heights: the main window's, or the main window's and the EQ's. */
export const ART_SIDE_H = MAIN_H;
export const ART_TALL_H = MAIN_H + EQ_H;
/** Whether side-docked art can be the tall one: only with the EQ docked under the main window. */
export const artCanBeTall = () => uiState.eq.open && uiState.eq.dock === 'stack';
/** Side-docked album art's height, as set and as the EQ allows. */
export const artSideHeight = () => (uiState.art.tall && artCanBeTall() ? ART_TALL_H : ART_SIDE_H);

/**
 * @returns {{ mainX: number, width: number, height: number, panels: Placed[] }} `panels` are the
 *   docked panels in canvas coordinates, side-docked album art included.
 */
export function dockedLayout() {
	const art = uiState.art;
	const side = art.open && (art.dock === 'left' || art.dock === 'right');
	const beside = artSize(art.frame, { height: artSideHeight() }, art.caption);
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

	// The Media Library docked: right of the stack and exactly as tall (docking it opens search
	// and the playlist so there's room), never taller.
	const libraryRight = uiState.library.open && uiState.library.dock === 'right';
	const lyricsRight = uiState.lyrics.open && uiState.lyrics.dock === 'right';
	let libraryW = libraryRight ? uiState.library.width : 0;
	let lyricsW = lyricsRight ? uiState.lyrics.width : 0;
	// Wider than the screen: lyrics give way first, down to LYRICS_FIT_MIN_W, then the library,
	// down to its minimum. Only as shown: the widths asked for stay, for a wider screen.
	const fixed = mainX + MAIN_W + (side && art.dock === 'right' ? beside.w : 0);
	const room = uiState.workWidth ? Math.floor(uiState.workWidth / (uiState.doubleSize ? 2 : 1)) : Infinity;
	let over = fixed + libraryW + lyricsW - room;
	if (over > 0 && lyricsW > LYRICS_FIT_MIN_W) {
		const cut = Math.min(over, lyricsW - LYRICS_FIT_MIN_W);
		lyricsW -= cut;
		over -= cut;
	}
	if (over > 0 && libraryW > LIBRARY_MIN_W) libraryW -= Math.min(over, libraryW - LIBRARY_MIN_W);
	if (libraryRight) panels.push({ kind: 'library', x: mainX + MAIN_W, y: 0, w: libraryW, h: y });

	// Lyrics docked: to the right of the whole stack (and the library), at least as tall as the
	// classic one (main, EQ, playlist). Album art can't take that side then, nor beside the
	// library (skinApi.js keeps them apart).
	if (lyricsRight) {
		panels.push({ kind: 'lyrics', x: mainX + MAIN_W + libraryW, y: 0, w: lyricsW, h: Math.max(CLASSIC_STACK_H, y) });
	}
	const width = fixed + libraryW + lyricsW;
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
