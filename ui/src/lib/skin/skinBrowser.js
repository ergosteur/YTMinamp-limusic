// The Skin Browser (Alt+S, Skins ▸ Skin browser…; SkinBrowserWindow.svelte): Winamp's own, a list
// of the skins folder beside a preview, with a search box and groups made from the skins' names.
// The preview is the real renderer drawing the picked skin's main window, EQ and playlist from its
// own sprites (winamp.rs `preview`: loaded, not made current); each row's thumbnail is that main
// window, small, drawn once and kept. Applying goes through the Winamp window, which owns the skin.
import { emitTo } from '@tauri-apps/api/event';
import * as api from '$lib/api';
import { decodeAllSprites } from './render/spritesheet.js';
import { drawMainWindow, MAIN_H, MAIN_W } from './render/mainWindow.js';
import { drawEqualizer, EQ_H } from './render/equalizer.js';
import { drawPlaylist, PL_W } from './render/playlist.js';
import { drawAnalyzer } from './render/visualizer.js';
import { doubleFactor } from './pixels.js';

/** Its size when it opens; it resizes from its edges (frameWindow.js). */
export const SKIN_BROWSER_SIZE = { w: 600, h: 460 };
/** Sent to the Winamp window: switch to this skin (`null` = built-in), as the Skins menu does. */
export const SKIN_SELECT_EVENT = 'winamp-skin-select';
/** The preview: main window, EQ, and a playlist as short as Winamp lets one be. */
export const PREVIEW = { w: MAIN_W, h: MAIN_H + EQ_H + 116 };

/** Alt+S, the main menu: the Skin Browser's window (brought to the front if it's open). */
export function openSkinBrowser() {
	const f = doubleFactor();
	return api.openWinampPanel('skins', SKIN_BROWSER_SIZE.w * f, SKIN_BROWSER_SIZE.h * f);
}

/** Switch skins from the browser, through the Winamp window. @param {string | null} path */
export function requestSkin(path) {
	return emitTo('winamp', SKIN_SELECT_EVENT, path);
}

/**
 * A skin's group: the first word of its name ("iPod-mini-Pink" → "iPod"), as the names of a set
 * share it. @param {string} name
 */
export function groupOf(name) {
	return name.split(/[-_ .]+/)[0] || name;
}

/**
 * The groups with two skins or more, biggest first, for the chips over the list.
 * @param {{ name: string }[]} skins
 * @returns {{ group: string, count: number }[]}
 */
export function groupsOf(skins) {
	/** @type {Map<string, { group: string, count: number }>} */
	const groups = new Map();
	for (const { name } of skins) {
		const group = groupOf(name);
		const key = group.toLowerCase();
		const g = groups.get(key) ?? { group, count: 0 };
		g.count++;
		groups.set(key, g);
	}
	return [...groups.values()].filter((g) => g.count > 1).sort((a, b) => b.count - a.count || a.group.localeCompare(b.group));
}

/** A spectrum to show off the analyzer: louder in the bass, a little ripple. */
const COLUMNS = Array.from({ length: 75 }, (_, x) => Math.max(1, Math.round(13 * Math.exp(-x / 34) + 2 * Math.sin(x / 2.3) + 1)));

/**
 * The main window as it looks playing, from `sprites`, at (0, 0) of `ctx`.
 * @param {CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D} ctx
 * @param {Map<string, ImageBitmap>} sprites
 * @param {import('$lib/api').SkinPayload} payload
 * @param {string} title
 */
function drawMain(ctx, sprites, payload, title) {
	drawMainWindow(
		/** @type {CanvasRenderingContext2D} */ (ctx),
		sprites,
		{
			title,
			pledit: payload.pledit,
			kbps: 192,
			khz: 44,
			playing: true,
			positionSecs: 83,
			durationSecs: 215,
			volume: 72,
			balance: 0,
			stereo: true,
			pressedButton: null,
			draggingSeek: false,
			visMode: 'analyzer',
			viscolor: payload.viscolor,
			vizColumns: null,
			plOpen: true,
			eqOpen: true,
			artOpen: false,
			alwaysOnTop: false,
			doubleSize: false,
			timeRemaining: false,
			shuffle: false,
			repeat: 'off',
			marqueeScroll: false,
			bitmapTitle: false
		},
		0
	);
	// Lit, as the window you'd be looking at: the renderer lights it only when it has the focus.
	const titlebar = sprites.get('titlebar');
	if (titlebar) ctx.drawImage(titlebar, 27, 0, MAIN_W, 14, 0, 0, MAIN_W, 14);
	// The analyzer keeps falling peaks between calls: a few calls settle them on the spectrum.
	for (let i = 0; i < 4; i++) drawAnalyzer(/** @type {CanvasRenderingContext2D} */ (ctx), payload.viscolor, COLUMNS);
}

/** What a preview's playlist shows. */
const SAMPLE_QUEUE = {
	items: [
		{ title: 'Llama Whippin’ Intro', artists: 'DJ Mike Llama', duration: '0:06' },
		{ title: 'Night Drive', artists: 'Copper Wire', duration: '4:12' },
		{ title: 'Slow Burn', artists: 'Lantern Hours', duration: '3:47' },
		{ title: 'Kiln', artists: 'Second Firing', duration: '5:03' },
		{ title: 'Ash & Smoke', artists: 'Afterglow', duration: '2:58' },
		{ title: 'Field Notes', artists: 'Warm Static', duration: '3:33' }
	],
	currentIndex: 1
};

/**
 * The preview: main window, EQ and a short playlist, stacked as docked, into `canvas` at 1x.
 * @param {HTMLCanvasElement} canvas
 * @param {Map<string, ImageBitmap>} sprites
 * @param {import('$lib/api').SkinPayload} payload
 * @param {string} name
 */
export function drawPreview(canvas, sprites, payload, name) {
	canvas.width = PREVIEW.w;
	canvas.height = PREVIEW.h;
	const ctx = canvas.getContext('2d');
	if (!ctx) return;
	ctx.imageSmoothingEnabled = false;
	ctx.fillStyle = '#000';
	ctx.fillRect(0, 0, PREVIEW.w, PREVIEW.h);
	drawMain(ctx, sprites, payload, `${name} - Skin preview`);
	drawEqualizer(ctx, sprites, { on: true, auto: false, preamp: 50, bands: [62, 66, 58, 50, 46, 40, 44, 52, 58, 60], dragging: null, pressed: null }, MAIN_H);
	const view = { open: true, dock: /** @type {'stack'} */ ('stack'), scroll: 0, selected: 3, marked: new Set([3]), anchor: null, pressed: null, draggingScroll: false };
	drawPlaylist(ctx, sprites, payload.pledit, SAMPLE_QUEUE, view, MAIN_H + EQ_H, { w: PL_W, h: 116 });
}

/**
 * A skin's payload and decoded sprites, the newest few kept: the browser goes back and forth.
 * @type {Map<string, Promise<{ payload: import('$lib/api').SkinPayload, sprites: Map<string, ImageBitmap> }>>}
 */
const loaded = new Map();
const KEEP = 6;

/** @param {string | null} path */
export function loadPreview(path) {
	const key = path ?? '';
	let hit = loaded.get(key);
	if (!hit) {
		hit = api.previewWszSkin(path).then(async (payload) => ({ payload, sprites: await decodeAllSprites(payload.sprites) }));
		hit.catch(() => loaded.delete(key));
		loaded.set(key, hit);
		while (loaded.size > KEEP) loaded.delete(/** @type {string} */ (loaded.keys().next().value));
	} else {
		// Most recent last, so it's the last to go.
		loaded.delete(key);
		loaded.set(key, hit);
	}
	return hit;
}

/** Thumbnails drawn so far, by path, kept for the window's life: they're small. */
const thumbs = new Map();
/** Thumbnails waiting to be drawn, two at a time, newest asked first (what's on screen). */
/** @type {{ path: string | null, done: (url: string | null) => void }[]} */
const queue = [];
let running = 0;

/**
 * A skin's main window as a small image URL (a data: PNG, a quarter size), drawn when asked and
 * kept. Rows ask as they scroll into view.
 * @param {string | null} path
 * @returns {Promise<string | null>} null for a skin that doesn't load
 */
export function thumbnail(path) {
	const key = path ?? '';
	if (thumbs.has(key)) return Promise.resolve(thumbs.get(key));
	return new Promise((done) => {
		queue.push({ path, done });
		pump();
	});
}

function pump() {
	while (running < 2 && queue.length) {
		const { path, done } = /** @type {(typeof queue)[number]} */ (queue.pop());
		const key = path ?? '';
		if (thumbs.has(key)) {
			done(thumbs.get(key));
			continue;
		}
		running++;
		api.previewWszSkin(path)
			.then(async (payload) => {
				const sprites = await decodeAllSprites(payload.sprites);
				const full = document.createElement('canvas');
				full.width = MAIN_W;
				full.height = MAIN_H;
				const ctx = full.getContext('2d');
				if (!ctx) return null;
				drawMain(ctx, sprites, payload, '');
				const small = document.createElement('canvas');
				small.width = Math.round(MAIN_W / 4);
				small.height = Math.round(MAIN_H / 4);
				const sctx = small.getContext('2d');
				if (!sctx) return null;
				sctx.imageSmoothingQuality = 'high';
				sctx.drawImage(full, 0, 0, small.width, small.height);
				for (const bitmap of sprites.values()) bitmap.close?.();
				return small.toDataURL('image/png');
			})
			.catch(() => null)
			.then((url) => {
				thumbs.set(key, url);
				done(url);
				running--;
				pump();
			});
	}
}
