// The lyrics panel: the lyrics in the skin's generic frame (the album art window's, titled
// LYRICS), in the playlist editor's font and colours. Timed lyrics keep the sung line centred
// and lit; the wheel scrolls by hand until the next track.
import { drawFrame, artFrame, frameInset } from './albumArt.js';

/** At zoom 1: the playlist editor's text size. */
const LINE_H = 15;
const FONT_PX = 11;

/** @typedef {import('$lib/api').SkinPayload['pledit']} PleditColours */
/** @typedef {{ x: number, y: number, w: number, h: number }} Rect */

/** Wrapped lines, cached per lyrics and width: measuring every frame would be wasteful. */
let wrapped = { key: '', lyricsKey: '', rows: /** @type {{ text: string, line: number }[]} */ ([]) };
/** The view's scroll, in rows, easing towards where it should be. */
let shown = 0;

/**
 * Break each lyric line into rows that fit `width`, remembering which line each row came from.
 * @param {CanvasRenderingContext2D} ctx @param {import('$lib/api').LyricLine[]} lines @param {number} width
 */
function wrap(ctx, lines, width) {
	/** @type {{ text: string, line: number }[]} */
	const rows = [];
	lines.forEach((l, line) => {
		const words = l.text.split(/\s+/).filter(Boolean);
		if (!words.length) return rows.push({ text: '', line });
		let row = '';
		for (const word of words) {
			const next = row ? `${row} ${word}` : word;
			if (row && ctx.measureText(next).width > width) {
				rows.push({ text: row, line });
				row = word;
			} else row = next;
		}
		rows.push({ text: row, line });
	});
	return rows;
}

/**
 * @param {CanvasRenderingContext2D} ctx
 * @param {Map<string, ImageBitmap>} sprites
 * @param {PleditColours} pledit
 * @param {import('../lyrics.js').LyricsState} state
 * @param {number} sung the sung line, or -1
 * @param {number} nudge rows scrolled by hand
 * @param {Rect} at the whole panel, frame included
 * @param {boolean} closePressed
 * @param {number} zoom the text size, a factor of the playlist font's
 */
export function drawLyrics(ctx, sprites, pledit, state, sung, nudge, at, closePressed, zoom) {
	const lineH = LINE_H * zoom;
	const i = frameInset(artFrame(sprites));
	const inner = { x: at.x + i.left, y: at.y + i.top, w: at.w - i.left - i.right, h: at.h - i.top - i.bottom };
	ctx.save();
	ctx.fillStyle = pledit.normalBg ?? '#000000';
	ctx.fillRect(inner.x, inner.y, inner.w, inner.h);
	ctx.beginPath();
	ctx.rect(inner.x, inner.y, inner.w, inner.h);
	ctx.clip();
	ctx.font = `${Math.round(FONT_PX * zoom)}px ${pledit.font ? `"${pledit.font}", ` : ''}Arial, sans-serif`;
	ctx.textAlign = 'center';
	ctx.textBaseline = 'middle';
	const cx = inner.x + inner.w / 2;

	const message = {
		none: 'Nothing playing',
		loading: 'Looking for lyrics...',
		missing: 'No lyrics found',
		instrumental: 'Instrumental',
		ready: ''
	}[state.status];
	if (message || !state.lyrics) {
		ctx.fillStyle = pledit.normal ?? '#00ff00';
		ctx.fillText(message, cx, inner.y + inner.h / 2);
	} else {
		const lyrics = state.lyrics;
		const lyricsKey = `${lyrics.provider}|${lyrics.lines.length}|${lyrics.lines[0]?.text}`;
		const key = `${lyricsKey}|${inner.w}|${ctx.font}`;
		if (wrapped.key !== key) {
			// New lyrics start from the top; the same ones rewrapped (resized, zoomed) ease over.
			if (wrapped.lyricsKey !== lyricsKey) shown = 0;
			wrapped = { key, lyricsKey, rows: wrap(ctx, lyrics.lines, inner.w - 8) };
		}
		const rows = wrapped.rows;
		const visible = inner.h / lineH;
		// Timed: the sung line's first row in the middle. Untimed: from the top.
		const sungRow = sung >= 0 ? rows.findIndex((r) => r.line === sung) : -1;
		const max = Math.max(0, rows.length - visible);
		const target = Math.max(0, Math.min(max, (sungRow >= 0 ? sungRow - visible / 2 + 0.5 : 0) + nudge));
		shown += (target - shown) * 0.2;
		if (Math.abs(target - shown) < 0.01) shown = target;
		const first = Math.floor(shown);
		for (let r = first; r < Math.min(rows.length, first + visible + 2); r++) {
			const y = inner.y + (r - shown) * lineH + lineH / 2;
			ctx.fillStyle = (rows[r].line === sung ? pledit.current : pledit.normal) ?? '#00ff00';
			ctx.fillText(rows[r].text, cx, y);
		}
	}
	ctx.restore();
	drawFrame(ctx, sprites, at, closePressed, 'lyrics');
}

/** Rows the panel scrolls by per wheel notch. */
export const LYRICS_WHEEL_ROWS = 3;
