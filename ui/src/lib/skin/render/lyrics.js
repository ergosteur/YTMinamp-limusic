// The lyrics panel's canvas part: the skin's generic frame (the album art window's, titled LYRICS)
// around a plain background. The lyrics themselves are Limusic's own view laid over it in HTML
// (WinampLyricsView.svelte), in the playlist editor's font and colours.
import { drawFrame, artFrame, frameInset } from './albumArt.js';
import { isLit } from '../focus.js';

/** @typedef {import('$lib/api').SkinPayload['pledit']} PleditColours */
/** @typedef {{ x: number, y: number, w: number, h: number }} Rect */

/**
 * @param {CanvasRenderingContext2D} ctx
 * @param {Map<string, ImageBitmap>} sprites
 * @param {PleditColours} pledit
 * @param {Rect} at the whole panel, frame included
 * @param {boolean} closePressed
 */
export function drawLyrics(ctx, sprites, pledit, at, closePressed) {
	const r = lyricsViewRect(sprites, at);
	ctx.fillStyle = pledit.normalBg ?? '#000000';
	ctx.fillRect(r.x, r.y, r.w, r.h);
	drawFrame(ctx, sprites, at, closePressed, 'lyrics', isLit('lyrics'));
}

/**
 * Inside the frame of a lyrics panel at `at` (canvas px): where the HTML lyrics go.
 * @param {Map<string, ImageBitmap>} sprites @param {Rect} at
 */
export function lyricsViewRect(sprites, at) {
	const i = frameInset(artFrame(sprites));
	return { x: at.x + i.left, y: at.y + i.top, w: at.w - i.left - i.right, h: at.h - i.top - i.bottom };
}
