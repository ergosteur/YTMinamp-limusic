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
	import { artFrame, artSize, drawAlbumArt, frameInset, onCloseButton } from '../skin/render/albumArt.js';
	import { frameMenu, onFrame } from '../skin/frameWindow.js';
	import { setActivePart } from '../skin/focus.js';
	import { startRenderLoop } from '../skin/render/loop.js';
	import { coverFor } from '../skin/art.js';
	import { doubleFactor, followDoubleSize, pinOneToOnePixels } from '../skin/pixels.js';
	import { ART_CAPTION_EVENT, loadSkin } from '../skin/skinApi.js';
	import { loadPrefs, pref } from '../skin/prefs.js';
	import { showArtMenu } from '../skin/menu.js';
	import { uiState } from '../skin/uiState.js';
	import { attachKeys } from '../skin/keys.js';

	/** The corner you drag to resize, like Winamp's generic windows. */
	const GRIP = 14;
	/** Smallest picture worth showing. */
	const MIN_WIDTH = 80;

	/** @type {HTMLCanvasElement} */
	let canvas;
	/** @type {Map<string, ImageBitmap>} */
	let sprites = new Map();
	let closePressed = false;
	/** The playlist's colours, for the album name under the picture. @type {import('$lib/api').SkinPayload['pledit']} */
	let pledit = {};

	/** Ask the Winamp window to dock the art (`dock`) or hide it (null). */
	const dockTo = (/** @type {import('../skin/uiState.js').ArtDock | null} */ dock) =>
		emitTo('winamp', 'winamp-panel-dock', { kind: 'art', dock }).catch((e) => console.error('dock request failed', e));

	onMount(() => {
		// Winamp's keys work here too: they're run by the Winamp window (keys.js).
		const detachKeys = attachKeys();
		setActivePart('art');
		// The DPI fix, then double size on top, following the Winamp window's.
		const unlistenDouble = followDoubleSize(
			pinOneToOnePixels().catch((e) => logUi('error', `album art zoom pin failed: ${e}`)),
			'art'
		);

		// Only the newest load lands: switch skins twice quickly and the second wins, whichever
		// finishes decoding first.
		let skinLoads = 0;
		const reload = () => {
			const mine = ++skinLoads;
			return loadSkin()
				.then((payload) => {
					pledit = payload.pledit;
					return decodeAllSprites(payload.sprites);
				})
				.then((decoded) => {
					if (mine === skinLoads) sprites = decoded;
				})
				.catch((e) => logUi('error', `album art skin failed: ${e}`));
		};
		reload();
		const unlistenSkin = listen('winamp-skin-changed', reload);
		// The album name under the picture: this window grows or shrinks by its strip.
		const setCaption = (/** @type {boolean} */ on) => {
			uiState.art.caption = on;
			if (sprites.size === 0) return;
			const size = artSize(artFrame(sprites), { width: window.innerWidth }, on);
			resizeWinampPanel('art', size.w * doubleFactor(), size.h * doubleFactor()).catch(() => {});
		};
		loadPrefs().then(() => (uiState.art.caption = pref('artCaption', false)));
		const unlistenCaption = listen(ART_CAPTION_EVENT, (e) => setCaption(/** @type {boolean} */ (e.payload)));

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
			if (onCloseButton(e, w)) {
				closePressed = true;
			} else if (e.clientX >= w - GRIP && e.clientY >= h - GRIP) {
				// Page px from the window's corner (which stays put): the same unit at any zoom.
				resize = { x: e.clientX, y: e.clientY, w, h };
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
			// Released outside the window (the drag outran it): no mouseup comes, so end it here.
			if (resize && !(e.buttons & 1)) return onUp(e);
			canvas.style.cursor = e.clientX >= window.innerWidth - GRIP && e.clientY >= window.innerHeight - GRIP ? 'nwse-resize' : '';
			if (!resize || sprites.size === 0) return;
			// The picture stays square: follow whichever way the pointer pulled further.
			const frame = artFrame(sprites);
			const byWidth = resize.w + (e.clientX - resize.x);
			const byHeight = resize.w + (e.clientY - resize.y);
			const width = Math.max(artSize(frame, { width: MIN_WIDTH }).w, Math.round(Math.max(byWidth, byHeight)));
			const size = artSize(frame, { width }, uiState.art.caption);
			const sendNow = pending === null;
			pending = size;
			if (sendNow) {
				requestAnimationFrame(() => {
					const next = pending;
					pending = null;
					if (next) resizeWinampPanel('art', next.w * doubleFactor(), next.h * doubleFactor()).catch(() => {});
				});
			}
		};
		const onUp = (/** @type {MouseEvent} */ e) => {
			press = null;
			resize = null;
			if (closePressed) {
				closePressed = false;
				// Released off the button: no close, as in Winamp.
				if (onCloseButton(e, window.innerWidth)) dockTo(null);
			}
		};
		canvas.addEventListener('mousedown', onDown);
		canvas.addEventListener('contextmenu', (e) => {
			// The frame's is the player's main menu; the picture's is the art's.
			if (onFrame(e.clientX, e.clientY, window.innerWidth, window.innerHeight, frameInset(artFrame(sprites)))) return frameMenu(e);
			e.preventDefault();
			showArtMenu({ x: e.clientX, y: e.clientY }).catch((err) => console.error('menu failed', err));
		});
		window.addEventListener('mousemove', onMove);
		window.addEventListener('mouseup', onUp);
		canvas.title = 'Album art (double-click to dock it back; drag the corner to resize; right-click for more)';

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
			const caption = uiState.art.caption ? { text: playback.now?.album ?? '', pledit } : null;
			drawAlbumArt(ctx, sprites, coverFor(playback.now?.thumbnail), { x: 0, y: 0, w, h }, closePressed, caption);
		});

		return () => {
			unlistenDouble.then((f) => f());
			detachKeys();
			stopLoop();
			unlistenSkin.then((f) => f());
			unlistenCaption.then((f) => f());
			window.removeEventListener('mousemove', onMove);
			window.removeEventListener('mouseup', onUp);
		};
	});
</script>

<div class="h-screen w-screen overflow-hidden bg-transparent">
	<canvas bind:this={canvas} class="block"></canvas>
</div>
