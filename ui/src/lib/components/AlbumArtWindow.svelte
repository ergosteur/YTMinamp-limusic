<script>
	// The album art floating in a window of its own (window label "winamp-art", see
	// +layout.svelte and winamp.rs). The Winamp window owns whether it exists and where it docks;
	// this one just draws the cover in the skin's frame and asks that window to dock or hide it.
	import { onMount } from 'svelte';
	import { getCurrentWindow } from '@tauri-apps/api/window';
	import { emitTo, listen } from '@tauri-apps/api/event';
	import { playback } from '$lib/player.svelte';
	import { resizeWinampPanel } from '$lib/api';
	import { logUi } from '$lib/errlog';
	import { decodeAllSprites } from '../skin/render/spritesheet.js';
	import { ART_CLOSE, artFrame, artSize, drawAlbumArt } from '../skin/render/albumArt.js';
	import { startRenderLoop } from '../skin/render/loop.js';
	import { coverFor } from '../skin/art.js';
	import { pinOneToOnePixels } from '../skin/pixels.js';
	import { loadSkin } from '../skin/skinApi.js';

	/** The corner you drag to resize, like Winamp's generic windows. */
	const GRIP = 14;
	/** Smallest picture worth showing. */
	const MIN_WIDTH = 80;

	/** @type {HTMLCanvasElement} */
	let canvas;
	/** @type {Map<string, ImageBitmap>} */
	let sprites = new Map();
	let closePressed = false;

	/** Ask the Winamp window to dock the art (`dock`) or hide it (null). */
	const dockTo = (/** @type {import('../skin/uiState.js').ArtDock | null} */ dock) =>
		emitTo('winamp', 'winamp-panel-dock', { kind: 'art', dock }).catch((e) => console.error('dock request failed', e));

	onMount(() => {
		pinOneToOnePixels().catch((e) => logUi('error', `album art zoom pin failed: ${e}`));

		const reload = () =>
			loadSkin()
				.then((payload) => decodeAllSprites(payload.sprites))
				.then((decoded) => (sprites = decoded))
				.catch((e) => logUi('error', `album art skin failed: ${e}`));
		reload();
		const unlistenSkin = listen('winamp-skin-changed', reload);

		/** A press that becomes a window drag once the mouse moves (so double-clicks still land). */
		let press = /** @type {{ x: number, y: number } | null} */ (null);
		/** An in-progress resize from the corner grip: where it started, and the size then. */
		let resize = /** @type {{ x: number, y: number, w: number, h: number } | null} */ (null);
		/** The size last asked for, sent once per frame at most. */
		let pending = /** @type {{ w: number, h: number } | null} */ (null);

		const onDown = (/** @type {MouseEvent} */ e) => {
			if (e.button !== 0) return;
			const w = window.innerWidth;
			const h = window.innerHeight;
			const onClose =
				e.clientX >= w + ART_CLOSE.dx &&
				e.clientX < w + ART_CLOSE.dx + ART_CLOSE.w &&
				e.clientY >= ART_CLOSE.y &&
				e.clientY < ART_CLOSE.y + ART_CLOSE.h;
			if (onClose) {
				closePressed = true;
			} else if (e.clientX >= w - GRIP && e.clientY >= h - GRIP) {
				resize = { x: e.screenX, y: e.screenY, w, h };
			} else if (e.detail >= 2) {
				dockTo('right');
			} else {
				press = { x: e.screenX, y: e.screenY };
			}
		};
		const onMove = (/** @type {MouseEvent} */ e) => {
			if (press && Math.hypot(e.screenX - press.x, e.screenY - press.y) > 3) {
				press = null;
				getCurrentWindow().startDragging();
			}
			canvas.style.cursor = e.clientX >= window.innerWidth - GRIP && e.clientY >= window.innerHeight - GRIP ? 'nwse-resize' : '';
			if (!resize || sprites.size === 0) return;
			// The picture stays square: follow whichever way the pointer pulled further.
			const frame = artFrame(sprites);
			const byWidth = resize.w + (e.screenX - resize.x);
			const byHeight = resize.w + (e.screenY - resize.y);
			const width = Math.max(artSize(frame, { width: MIN_WIDTH }).w, Math.round(Math.max(byWidth, byHeight)));
			const size = artSize(frame, { width });
			const sendNow = pending === null;
			pending = size;
			if (sendNow) {
				requestAnimationFrame(() => {
					const next = pending;
					pending = null;
					if (next) resizeWinampPanel('art', next.w, next.h).catch(() => {});
				});
			}
		};
		const onUp = () => {
			press = null;
			resize = null;
			if (closePressed) {
				closePressed = false;
				dockTo(null);
			}
		};
		canvas.addEventListener('mousedown', onDown);
		window.addEventListener('mousemove', onMove);
		window.addEventListener('mouseup', onUp);
		canvas.title = 'Album art (double-click to dock it back; drag the corner to resize)';

		const stopLoop = startRenderLoop(() => {
			if (sprites.size === 0) return;
			const ctx = canvas.getContext('2d');
			if (!ctx) return;
			const w = window.innerWidth;
			const h = window.innerHeight;
			if (canvas.width !== w || canvas.height !== h) {
				canvas.width = w;
				canvas.height = h;
				canvas.style.width = `${w}px`;
				canvas.style.height = `${h}px`;
			}
			ctx.clearRect(0, 0, w, h);
			drawAlbumArt(ctx, sprites, coverFor(playback.now?.thumbnail), { x: 0, y: 0, w, h }, closePressed);
		});

		return () => {
			stopLoop();
			unlistenSkin.then((f) => f());
			window.removeEventListener('mousemove', onMove);
			window.removeEventListener('mouseup', onUp);
		};
	});
</script>

<div class="h-screen w-screen overflow-hidden bg-transparent">
	<canvas bind:this={canvas} class="block"></canvas>
</div>
