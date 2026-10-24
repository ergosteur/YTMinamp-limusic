<script>
	// The update dialog (label "winamp-update", see +layout.svelte and winamp.rs), in the skin's
	// generic frame and the playlist's colours: a newer YTMinamp build, Download (the release page:
	// builds are unsigned, so never an install in place) or Later. Opened from the update notice in
	// the main window's title, or the main menu's "Update available" (skinApi.js `watchForUpdates`).
	import { onMount } from 'svelte';
	import { listen } from '@tauri-apps/api/event';
	import { getVersion } from '@tauri-apps/api/app';
	import { getCurrentWindow } from '@tauri-apps/api/window';
	import { closeWinampPanel } from '$lib/api';
	import { logUi } from '$lib/errlog';
	import { checkForUpdatesInteractive, openDownloadPage, updateState } from '$lib/updater.svelte';
	import { decodeAllSprites } from '../skin/render/spritesheet.js';
	import { artFrame, drawFrame, frameInset, onCloseButton } from '../skin/render/albumArt.js';
	import { followDoubleSize, pinOneToOnePixels } from '../skin/pixels.js';
	import { UPDATE_SIZE, loadSkin } from '../skin/skinApi.js';
	import { isLit, setActivePart } from '../skin/focus.js';
	import { fullVersion } from '../skin/brand.js';

	const { w: WIDTH, h: HEIGHT } = UPDATE_SIZE;

	/** @type {HTMLCanvasElement} */
	let canvas;
	/** @type {Map<string, ImageBitmap>} */
	let sprites = new Map();
	/** @type {import('$lib/api').SkinPayload['pledit']} */
	let pledit = $state({});
	let inset = $state({ top: 20, bottom: 14, left: 11, right: 11 });
	let message = $state('Checking…');
	let version = $state('');
	let closePressed = false;

	const close = () => closeWinampPanel('update').catch((e) => console.error('close failed', e));
	const font = $derived(`${pledit.font ? `"${pledit.font}", ` : ''}Arial, sans-serif`);
	const newer = $derived(!!updateState.available && !updateState.available.rollback);

	function draw() {
		const ctx = canvas?.getContext('2d');
		if (!ctx || sprites.size === 0) return;
		canvas.width = WIDTH;
		canvas.height = HEIGHT;
		canvas.style.width = `${WIDTH}px`;
		canvas.style.height = `${HEIGHT}px`;
		ctx.fillStyle = pledit.normalBg ?? '#000000';
		ctx.fillRect(0, 0, WIDTH, HEIGHT);
		drawFrame(ctx, sprites, { x: 0, y: 0, w: WIDTH, h: HEIGHT }, closePressed, 'update', isLit('update'));
	}

	function download() {
		openDownloadPage();
		close();
	}

	onMount(() => {
		setActivePart('update');
		getVersion().then((v) => (version = fullVersion(v)), () => (version = '?'));
		// Limusic's own check, reading YTMinamp's releases (skin/updates.js); the answer is cached in
		// Rust, so this is the main window's answer, not another request.
		checkForUpdatesInteractive().then((r) => (message = r.message));
		window.addEventListener('focus', draw);
		window.addEventListener('blur', draw);
		const unlistenDouble = followDoubleSize(
			pinOneToOnePixels().catch((e) => logUi('error', `update zoom pin failed: ${e}`)),
			'update'
		);
		// Only the newest load lands: switch skins twice quickly and the second wins, whichever
		// finishes decoding first.
		let skinLoads = 0;
		const reload = () => {
			const mine = ++skinLoads;
			return loadSkin()
				.then(async (payload) => {
					const decoded = await decodeAllSprites(payload.sprites);
					if (mine !== skinLoads) return;
					sprites = decoded;
					pledit = payload.pledit;
					inset = frameInset(artFrame(sprites));
					draw();
				})
				.catch((e) => logUi('error', `update skin failed: ${e}`));
		};
		reload();
		const unlistenSkin = listen('winamp-skin-changed', reload);

		/** A titlebar press becomes a window drag once the mouse moves. */
		let press = /** @type {{ x: number, y: number } | null} */ (null);
		const onDown = (/** @type {MouseEvent} */ e) => {
			if (e.button !== 0) return;
			if (onCloseButton(e, WIDTH)) {
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
		const onUp = (/** @type {MouseEvent} */ e) => {
			press = null;
			if (!closePressed) return;
			closePressed = false;
			// Released off the button: no close, as in Winamp.
			if (onCloseButton(e, WIDTH)) close();
			else draw();
		};
		const onKey = (/** @type {KeyboardEvent} */ e) => {
			if (e.key === 'Escape') close();
			else if (e.key === 'Enter' && newer) download();
		};
		canvas.addEventListener('mousedown', onDown);
		window.addEventListener('mousemove', onMove);
		window.addEventListener('mouseup', onUp);
		window.addEventListener('keydown', onKey);
		return () => {
			unlistenDouble.then((f) => f());
			unlistenSkin.then((f) => f());
			window.removeEventListener('focus', draw);
			window.removeEventListener('blur', draw);
			window.removeEventListener('mousemove', onMove);
			window.removeEventListener('mouseup', onUp);
			window.removeEventListener('keydown', onKey);
		};
	});
</script>

<div class="relative h-screen w-screen overflow-hidden bg-transparent">
	<canvas bind:this={canvas} class="block"></canvas>
	<div
		class="absolute flex flex-col gap-1 text-[11px] leading-[14px]"
		style:left="{inset.left + 6}px"
		style:top="{inset.top + 6}px"
		style:right="{inset.right + 6}px"
		style:bottom="{inset.bottom + 6}px"
		style:color={pledit.normal ?? '#00ff00'}
		style:font-family={font}
	>
		<p style:color={pledit.current ?? '#ffffff'}>{message}</p>
		<p class="opacity-80">You have {version}.</p>
		<div class="mt-auto flex justify-end gap-1">
			{#snippet button(/** @type {string} */ text, /** @type {() => void} */ action)}
				<button
					type="button"
					class="border px-1.5 text-[11px] leading-[15px]"
					style:background={pledit.normalBg ?? '#000000'}
					style:color={pledit.current ?? '#ffffff'}
					style:border-color={pledit.normal ?? '#00ff00'}
					style:font-family={font}
					onclick={action}>{text}</button
				>
			{/snippet}
			{#if newer}{@render button('Download', download)}{/if}
			{@render button(newer ? 'Later' : 'OK', close)}
		</div>
	</div>
</div>
