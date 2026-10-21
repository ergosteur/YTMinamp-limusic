<script>
	// The ADD menu's Open YouTube URL dialog, a small window of its own (label "winamp-url", see
	// +layout.svelte and winamp.rs) in the skin's generic frame: paste a YouTube / YouTube Music
	// link, Enter plays it (playlistActions.js `openLink`), Esc or ✕ closes it.
	import { onMount } from 'svelte';
	import { getCurrentWindow } from '@tauri-apps/api/window';
	import { listen } from '@tauri-apps/api/event';
	import { closeWinampPanel, resizeWinampPanel } from '$lib/api';
	import { logUi } from '$lib/errlog';
	import { decodeAllSprites } from '../skin/render/spritesheet.js';
	import { ART_CLOSE, artFrame, drawFrame, frameInset } from '../skin/render/albumArt.js';
	import { pinOneToOnePixels } from '../skin/pixels.js';
	import { loadSkin } from '../skin/skinApi.js';
	import { openLink } from '../skin/playlistActions.js';

	const WIDTH = 275;
	/** The text box and the status line under it. */
	const BOX_H = 17;
	const BODY_H = BOX_H + 18;

	/** @type {HTMLCanvasElement} */
	let canvas;
	/** @type {HTMLInputElement} */
	let input;
	/** @type {Map<string, ImageBitmap>} */
	let sprites = new Map();
	/** @type {import('$lib/api').SkinPayload['pledit']} */
	let pledit = $state({});
	let inset = $state({ top: 20, bottom: 14, left: 11, right: 8 });
	let status = $state('Paste a YouTube or YouTube Music link, then press Enter');
	let busy = $state(false);
	let closePressed = false;

	const close = () => closeWinampPanel('url').catch((e) => console.error('close failed', e));

	function draw() {
		const ctx = canvas.getContext('2d');
		if (!ctx || sprites.size === 0) return;
		const w = WIDTH;
		const h = inset.top + BODY_H + inset.bottom;
		canvas.width = w;
		canvas.height = h;
		canvas.style.width = `${w}px`;
		canvas.style.height = `${h}px`;
		ctx.fillStyle = pledit.normalBg ?? '#000000';
		ctx.fillRect(0, 0, w, h);
		drawFrame(ctx, sprites, { x: 0, y: 0, w, h }, closePressed, 'open url');
	}

	async function submit() {
		if (busy) return;
		busy = true;
		status = 'Opening...';
		try {
			if (await openLink(input.value)) {
				close();
				return;
			}
			status = "That isn't a YouTube or YouTube Music link";
		} catch (e) {
			status = `Couldn't open it: ${e}`;
		} finally {
			busy = false;
		}
	}

	function onKey(/** @type {KeyboardEvent} */ e) {
		if (e.key === 'Enter') {
			e.preventDefault();
			submit();
		} else if (e.key === 'Escape') {
			e.preventDefault();
			close();
		}
	}

	onMount(() => {
		pinOneToOnePixels().catch((e) => logUi('error', `open url zoom pin failed: ${e}`));
		const reload = () =>
			loadSkin()
				.then(async (payload) => {
					sprites = await decodeAllSprites(payload.sprites);
					pledit = payload.pledit;
					inset = frameInset(artFrame(sprites));
					draw();
					// The frame decides the height (gen.bmp's is thicker than the EQ fallback's).
					resizeWinampPanel('url', WIDTH, inset.top + BODY_H + inset.bottom).catch(() => {});
				})
				.catch((e) => logUi('error', `open url skin failed: ${e}`));
		reload();
		const unlistenSkin = listen('winamp-skin-changed', reload);
		requestAnimationFrame(() => input?.focus());

		/** A titlebar press becomes a window drag once the mouse moves. */
		let press = /** @type {{ x: number, y: number } | null} */ (null);
		const onDown = (/** @type {MouseEvent} */ e) => {
			if (e.button !== 0) return;
			const onClose =
				e.clientX >= WIDTH + ART_CLOSE.dx &&
				e.clientX < WIDTH + ART_CLOSE.dx + ART_CLOSE.w &&
				e.clientY >= ART_CLOSE.y &&
				e.clientY < ART_CLOSE.y + ART_CLOSE.h;
			if (onClose) {
				closePressed = true;
				draw();
			} else if (e.clientY < inset.top) {
				press = { x: e.screenX, y: e.screenY };
			}
		};
		const onMove = (/** @type {MouseEvent} */ e) => {
			if (press && Math.hypot(e.screenX - press.x, e.screenY - press.y) > 3) {
				press = null;
				getCurrentWindow().startDragging();
			}
		};
		const onUp = () => {
			press = null;
			if (closePressed) close();
		};
		canvas.addEventListener('mousedown', onDown);
		window.addEventListener('mousemove', onMove);
		window.addEventListener('mouseup', onUp);

		return () => {
			unlistenSkin.then((f) => f());
			window.removeEventListener('mousemove', onMove);
			window.removeEventListener('mouseup', onUp);
		};
	});

	const font = $derived(`${pledit.font ? `"${pledit.font}", ` : ''}Arial, sans-serif`);
</script>

<div class="relative h-screen w-screen overflow-hidden bg-transparent">
	<canvas bind:this={canvas} class="block"></canvas>
	<input
		bind:this={input}
		class="absolute m-0 border px-1 py-0 text-[11px] leading-none outline-none"
		style:left="{inset.left + 3}px"
		style:top="{inset.top + 3}px"
		style:width="{WIDTH - inset.left - inset.right - 6}px"
		style:height="{BOX_H}px"
		style:background={pledit.normalBg ?? '#000000'}
		style:color={pledit.normal ?? '#00ff00'}
		style:border-color={pledit.normal ?? '#00ff00'}
		style:caret-color={pledit.current ?? '#ffffff'}
		style:font-family={font}
		type="text"
		placeholder="https://music.youtube.com/..."
		spellcheck="false"
		autocomplete="off"
		disabled={busy}
		onkeydown={onKey}
	/>
	<div
		class="pointer-events-none absolute truncate text-[11px] leading-none"
		style:left="{inset.left + 4}px"
		style:top="{inset.top + BOX_H + 7}px"
		style:width="{WIDTH - inset.left - inset.right - 8}px"
		style:color={pledit.normal ?? '#00ff00'}
		style:font-family={font}
	>
		{status}
	</div>
</div>
