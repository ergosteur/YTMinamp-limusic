// The list panels: the playlist editor (Limusic's real queue) and the search panel, both drawn
// with the playlist editor's chrome, docked under the main window or floating in a window of their
// own at any size Winamp allows. Frame sprites are from pledit.bmp, text colours and font from
// pledit.txt. Coordinates: Webamp's skinSprites.ts PLEDIT table and playlist-window.css.

import { drawText } from './marquee.js';
import { isLit } from '../focus.js';
import { drawGenText, genTextWidth } from './albumArt.js';

/** Docked size: Winamp's default. */
export const PL_W = 275;
export const PL_H = 232;
/** Smallest size, and the steps it grows in (whole frame tiles, like Winamp). */
export const PL_MIN = { w: 275, h: 116 };
export const PL_STEP = { w: 25, h: 29 };
const TOP_H = 20;
const BOTTOM_H = 38;
const LEFT_W = 12;
const RIGHT_W = 20;
const TILE_H = 29;
/** Rows fit the list's 11px text (Winamp's own was 9px, too small on today's screens). */
export const ROW_H = 15;
const LIST_PAD = 3;

/** In pledit.bmp's title piece: the stripes' end caps at each side, and a plain column of
 * background (the baked-in title sits on it) to stretch under the search panel's own title. */
const TITLE_CAP = 4;
const TITLE_PLAIN_X = 5;
const TITLE_PAD = 3;

export const PLEDIT = {
	topTile: { x: 127, y: 21, w: 25, h: 20 },
	topLeft: { x: 0, y: 21, w: 25, h: 20 },
	title: { x: 26, y: 21, w: 100, h: 20 },
	topRight: { x: 153, y: 21, w: 25, h: 20 },
	leftTile: { x: 0, y: 42, w: 12, h: 29 },
	rightTile: { x: 31, y: 42, w: 20, h: 29 },
	bottomLeft: { x: 0, y: 72, w: 125, h: 38 },
	bottomRight: { x: 126, y: 72, w: 150, h: 38 },
	bottomTile: { x: 179, y: 0, w: 25, h: 38 },
	scrollHandle: { x: 52, y: 53, w: 8, h: 18 },
	scrollHandleSelected: { x: 61, y: 53, w: 8, h: 18 },
	closeSelected: { x: 52, y: 42, w: 9, h: 9 }
};

/** @typedef {{ w: number, h: number }} Size */
const DOCKED = { w: PL_W, h: PL_H };

/** The nearest size Winamp would allow: at least the minimum, in whole tiles. @param {Size} size */
export function snapPanelSize({ w, h }) {
	const steps = (/** @type {number} */ v, /** @type {number} */ min, /** @type {number} */ step) =>
		min + Math.max(0, Math.round((v - min) / step)) * step;
	return { w: steps(w, PL_MIN.w, PL_STEP.w), h: steps(h, PL_MIN.h, PL_STEP.h) };
}

/**
 * Where everything sits in a panel of `size`, relative to its top-left.
 * @param {Size} [size]
 */
export function geometry(size = DOCKED) {
	const { w, h } = size;
	const list = { x: LEFT_W, y: TOP_H + LIST_PAD, w: w - LEFT_W - RIGHT_W, h: h - TOP_H - BOTTOM_H - 2 * LIST_PAD };
	return {
		list,
		/** Scrollbar handle travel. */
		scroll: { x: w - 15, y: TOP_H, h: h - TOP_H - BOTTOM_H - PLEDIT.scrollHandle.h },
		close: { x: w - 11, y: 3, w: 9, h: 9 },
		/** The six mini transport buttons in the bottom-right (prev, play, pause, stop, next, eject). */
		transport: { x: w - 150 + 3, y: h - BOTTOM_H + 22, w: 10, h: 10 },
		/** The running-time readout above them. */
		footer: { x: w - 150 + 7, y: h - BOTTOM_H + 10 },
		/** The bottom-right corner you drag to resize a floating panel. */
		resize: { x: w - 20, y: h - 20, w: 20, h: 20 },
		/** The playlist's bottom buttons (Webamp's playlist-window.css: 22x18, 12px up). */
		buttons: {
			add: { x: 14, y: h - 30, w: 22, h: 18 },
			rem: { x: 43, y: h - 30, w: 22, h: 18 },
			sel: { x: 72, y: h - 30, w: 22, h: 18 },
			misc: { x: 101, y: h - 30, w: 22, h: 18 },
			list: { x: w - 44, y: h - 30, w: 22, h: 18 }
		}
	};
}

/** Track list area of a docked panel. */
export const LIST = geometry().list;
export const VISIBLE_ROWS = Math.floor(LIST.h / ROW_H);
/** The search panel's text box, the top of its list area (an HTML <input> sits on it). */
export const SEARCH_INPUT_H = 17;

/**
 * Rows of a panel's list, relative to the panel's top-left: the search panel's start under its
 * text box.
 * @param {'search' | 'playlist'} kind
 * @param {Size} [size]
 */
export function listRows(kind, size = DOCKED) {
	const list = geometry(size).list;
	const inset = kind === 'search' ? SEARCH_INPUT_H : 0;
	return { x: list.x, y: list.y + inset, w: list.w, rows: Math.floor((list.h - inset) / ROW_H) };
}
export const PL_TRANSPORT_ORDER = ['previous', 'play', 'pause', 'stop', 'next', 'eject'];
/** @typedef {'add' | 'rem' | 'sel' | 'misc' | 'list'} PlaylistButton */

/** "3:45" / "1:02:03" → seconds; unknown → 0. */
function seconds(duration) {
	if (!duration) return 0;
	return duration.split(':').reduce((acc, part) => acc * 60 + (Number(part) || 0), 0);
}

function clock(total) {
	const s = Math.floor(total % 60);
	const m = Math.floor(total / 60);
	return `${m}:${String(s).padStart(2, '0')}`;
}

function blit(ctx, sheet, r, dx, dy) {
	ctx.drawImage(sheet, r.x, r.y, r.w, r.h, dx, dy, r.w, r.h);
}

/** Highest valid scroll offset for `count` rows in a list showing `visible` at once. */
export function maxScroll(count, visible = VISIBLE_ROWS) {
	return Math.max(0, count - visible);
}

/** @typedef {import('$lib/api').SkinPayload['pledit']} PleditColours */
/** @typedef {{ scroll: number, selected: number | null, pressed: string | null, draggingScroll: boolean }} PanelView */

/**
 * The playlist editor.
 * @param {CanvasRenderingContext2D} ctx
 * @param {Map<string, ImageBitmap>} sprites
 * @param {PleditColours} pledit
 * @param {{ items: {title: string, artists: string, duration?: string}[], currentIndex: number }} queue
 * @param {PanelView} view
 * @param {number} oy where the panel starts in the canvas
 * @param {Size} [size]
 */
export function drawPlaylist(ctx, sprites, pledit, queue, view, oy, size = DOCKED) {
	const items = queue.items ?? [];
	// Running time ("selected/total" in Winamp; here: current track's position in the total).
	const total = items.reduce((sum, item) => sum + seconds(item.duration), 0);
	const done = items.slice(0, Math.max(0, queue.currentIndex)).reduce((sum, item) => sum + seconds(item.duration), 0);
	drawListPanel(ctx, sprites, pledit, {
		kind: 'playlist',
		items,
		current: queue.currentIndex,
		view,
		oy,
		size,
		footer: `${clock(done)}/${clock(total)}`,
		status: ''
	});
}

/**
 * The search panel: a text box (an HTML <input> over the canvas, see WinampSkin.svelte) above
 * the results.
 * @param {CanvasRenderingContext2D} ctx
 * @param {Map<string, ImageBitmap>} sprites
 * @param {PleditColours} pledit
 * @param {{ results: {title: string, artists: string, duration?: string}[], status: string } & PanelView} search
 * @param {number} oy
 * @param {Size} [size]
 */
export function drawSearch(ctx, sprites, pledit, search, oy, size = DOCKED) {
	drawListPanel(ctx, sprites, pledit, {
		kind: 'search',
		items: search.results,
		current: -1,
		view: search,
		oy,
		size,
		footer: search.results.length ? `${search.results.length} found` : '',
		status: search.status
	});
}

/**
 * @param {CanvasRenderingContext2D} ctx
 * @param {Map<string, ImageBitmap>} sprites
 * @param {PleditColours} pledit
 * @param {{ kind: 'search' | 'playlist', items: {title: string, artists: string, duration?: string}[], current: number, view: PanelView, oy: number, size: Size, footer: string, status: string }} panel
 */
function drawListPanel(ctx, sprites, pledit, { kind, items, current, view, oy, size, footer, status }) {
	const sheet = sprites.get('pledit');
	if (!sheet) return;
	const text = sprites.get('text');
	const { w, h } = size;
	const g = geometry(size);
	const LIST = g.list;

	// Frame: top bar tiles, corners and title (the lit row, y 0, when it's the active window);
	// side tiles; bottom tiles under the two corners.
	const top = (/** @type {{ x: number, y: number, w: number, h: number }} */ r) => (isLit(kind) ? { ...r, y: 0 } : r);
	for (let x = PLEDIT.topLeft.w; x < w - PLEDIT.topRight.w; x += PLEDIT.topTile.w) {
		blit(ctx, sheet, top(PLEDIT.topTile), x, oy);
	}
	blit(ctx, sheet, top(PLEDIT.topLeft), 0, oy);
	if (kind === 'playlist') {
		blit(ctx, sheet, top(PLEDIT.title), Math.floor((w - PLEDIT.title.w) / 2), oy);
	} else {
		// pledit.bmp's title is baked-in "WINAMP PLAYLIST"; the search panel spells its own, in
		// gen.bmp's titlebar letters (text.bmp's when the skin has none) on the title piece's
		// plain middle, between its end caps.
		const label = 'search';
		const gen = sprites.get('gen');
		const textW = gen ? genTextWidth(gen, label) : 0;
		if (gen && textW) {
			const t = top(PLEDIT.title);
			const tx = Math.floor((w - textW) / 2);
			const pad = TITLE_PAD;
			ctx.drawImage(sheet, t.x + TITLE_PLAIN_X, t.y, 1, t.h, tx - pad, oy, textW + 2 * pad, t.h);
			ctx.drawImage(sheet, t.x, t.y, TITLE_CAP, t.h, tx - pad - TITLE_CAP, oy, TITLE_CAP, t.h);
			ctx.drawImage(sheet, t.x + t.w - TITLE_CAP, t.y, TITLE_CAP, t.h, tx + textW + pad, oy, TITLE_CAP, t.h);
			drawGenText(ctx, gen, label, tx, oy, isLit(kind));
		} else if (text) {
			drawText(ctx, text, label, Math.floor((w - label.length * 5) / 2), oy + 7);
		}
	}
	blit(ctx, sheet, top(PLEDIT.topRight), w - PLEDIT.topRight.w, oy);
	for (let y = TOP_H; y < h - BOTTOM_H; y += TILE_H) {
		blit(ctx, sheet, PLEDIT.leftTile, 0, oy + y);
		blit(ctx, sheet, PLEDIT.rightTile, w - RIGHT_W, oy + y);
	}
	for (let x = PLEDIT.bottomLeft.w; x < w - PLEDIT.bottomRight.w; x += PLEDIT.bottomTile.w) {
		blit(ctx, sheet, PLEDIT.bottomTile, x, oy + h - BOTTOM_H);
	}
	blit(ctx, sheet, PLEDIT.bottomLeft, 0, oy + h - BOTTOM_H);
	blit(ctx, sheet, PLEDIT.bottomRight, w - PLEDIT.bottomRight.w, oy + h - BOTTOM_H);
	if (view.pressed === 'close') blit(ctx, sheet, PLEDIT.closeSelected, g.close.x, oy + g.close.y);

	// List.
	const listTop = oy + TOP_H;
	const listH = h - TOP_H - BOTTOM_H;
	const area = listRows(kind, size);
	ctx.fillStyle = pledit.normalBg ?? '#000000';
	ctx.fillRect(LIST.x, listTop, LIST.w, listH);

	ctx.save();
	ctx.beginPath();
	ctx.rect(LIST.x, listTop, LIST.w, listH);
	ctx.clip();
	ctx.font = `11px ${pledit.font ? `"${pledit.font}", ` : ''}Arial, sans-serif`;
	ctx.textBaseline = 'middle';
	if (status) {
		ctx.fillStyle = pledit.normal ?? '#00ff00';
		ctx.textAlign = 'left';
		ctx.fillText(status, LIST.x + 2, oy + area.y + ROW_H / 2);
	}
	for (let row = 0; !status && row < area.rows + 1; row++) {
		const i = view.scroll + row;
		if (i >= items.length) break;
		const y = oy + area.y + row * ROW_H;
		if (i === view.selected) {
			ctx.fillStyle = pledit.selectedBg ?? '#0000c6';
			ctx.fillRect(LIST.x, y, LIST.w, ROW_H);
		}
		const item = items[i];
		ctx.fillStyle = (i === current ? pledit.current : pledit.normal) ?? '#00ff00';
		const duration = item.duration ?? '';
		const durationW = ctx.measureText(duration).width;
		ctx.textAlign = 'right';
		ctx.fillText(duration, LIST.x + LIST.w - 3, y + ROW_H / 2);
		ctx.textAlign = 'left';
		const label = `${i + 1}. ${item.artists ? `${item.artists} - ` : ''}${item.title}`;
		ctx.save();
		ctx.beginPath();
		ctx.rect(LIST.x, y, LIST.w - durationW - 8, ROW_H);
		ctx.clip();
		ctx.fillText(label, LIST.x + 2, y + ROW_H / 2);
		ctx.restore();
	}
	ctx.restore();

	// Scrollbar handle.
	const max = maxScroll(items.length, area.rows);
	const handleY = oy + g.scroll.y + (max === 0 ? 0 : Math.round((view.scroll / max) * g.scroll.h));
	blit(ctx, sheet, view.draggingScroll ? PLEDIT.scrollHandleSelected : PLEDIT.scrollHandle, g.scroll.x, handleY);

	if (text && footer) drawText(ctx, text, footer, g.footer.x, oy + g.footer.y);
}
