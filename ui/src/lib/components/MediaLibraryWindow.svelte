<script>
	// The Media Library floating (label "winamp-library", see +layout.svelte, winamp.rs and
	// skin/library.js): LibraryPages.svelte inside the skin's generic frame titled MEDIA LIBRARY.
	// Resized from its right and bottom edges and dragged by the titlebar (skin/frameWindow.js);
	// a double-click on the titlebar docks it in the Winamp window, at the page it shows; the
	// frame's ✕, Escape or Alt+L closes it.
	import { onMount } from 'svelte';
	import { listen } from '@tauri-apps/api/event';
	import { logUi } from '$lib/errlog';
	import LibraryPages from './LibraryPages.svelte';
	import { decodeAllSprites } from '../skin/render/spritesheet.js';
	import { artFrame, drawFrame, frameInset, onCloseButton } from '../skin/render/albumArt.js';
	import { pinOneToOnePixels } from '../skin/pixels.js';
	import { ui } from '$lib/player.svelte';
	import { knowSettings, loadSkin, tickerToast } from '../skin/skinApi.js';
	import { frameMouse } from '../skin/frameWindow.js';
	import { keyName } from '../skin/keys.js';
	import { isLit, setActivePart } from '../skin/focus.js';
	import { closeLibrary, dockLibrary, onLibraryNavigate } from '../skin/library.js';
	import { openLimusicSettings, toggleLimusic } from '../skin/navigate.js';

	/** @type {{ page: import('svelte').Snippet }} the route's page (+layout.svelte's `children`) */
	let { page } = $props();

	/** @type {HTMLCanvasElement} */
	let canvas;
	/** @type {Map<string, ImageBitmap>} */
	let sprites = new Map();
	let inset = $state({ top: 20, bottom: 14, left: 11, right: 11 });
	let closePressed = false;

	const close = () => closeLibrary().catch((e) => console.error('close failed', e));

	function draw() {
		const ctx = canvas?.getContext('2d');
		if (!ctx || sprites.size === 0) return;
		const w = window.innerWidth;
		const h = window.innerHeight;
		canvas.width = w;
		canvas.height = h;
		canvas.style.width = `${w}px`;
		canvas.style.height = `${h}px`;
		drawFrame(ctx, sprites, { x: 0, y: 0, w, h }, closePressed, 'media library', isLit('library'));
	}

	$effect(() => tickerToast(ui.toast));

	onMount(() => {
		knowSettings();
		setActivePart('library');
		window.addEventListener('focus', draw);
		window.addEventListener('blur', draw);
		window.addEventListener('resize', draw);
		pinOneToOnePixels().catch((e) => logUi('error', `library zoom pin failed: ${e}`));
		const unlistenNavigate = onLibraryNavigate();
		// Only the newest load lands: switch skins twice quickly and the second wins.
		let skinLoads = 0;
		const reload = () => {
			const mine = ++skinLoads;
			return loadSkin()
				.then(async (payload) => {
					const decoded = await decodeAllSprites(payload.sprites);
					if (mine !== skinLoads) return;
					sprites = decoded;
					inset = frameInset(artFrame(sprites));
					draw();
				})
				.catch((e) => logUi('error', `library skin failed: ${e}`));
		};
		reload();
		const unlistenSkin = listen('winamp-skin-changed', reload);

		const stopFrameMouse = frameMouse(canvas, {
			onClose: (e) => onCloseButton(e, window.innerWidth),
			inset: () => inset,
			pressed: (down) => {
				closePressed = down;
				draw();
			},
			close,
			resizable: 'library'
		});
		// The titlebar's double-click docks it, as every floating panel's does.
		const onDouble = (/** @type {MouseEvent} */ e) => {
			if (e.clientY < inset.top && !onCloseButton(e, window.innerWidth)) dockLibrary().catch(() => {});
		};
		canvas.addEventListener('dblclick', onDouble);
		const onKey = (/** @type {KeyboardEvent} */ e) => {
			if (e.defaultPrevented) return;
			// Escape in a page's own dialog or box is that page's.
			if (e.key === 'Escape' && e.target === document.body) return close();
			const ctrl = (e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey;
			const alt = e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey;
			// The player's keys that work from here too: Alt+L hides it, Alt+M shows Limusic's
			// window, Ctrl+P Preferences (Limusic has none of them).
			if (alt && keyName(e) === 'l') close();
			else if (alt && keyName(e) === 'm') void toggleLimusic();
			else if (ctrl && keyName(e) === 'p') void openLimusicSettings();
			else return;
			e.preventDefault();
		};
		window.addEventListener('keydown', onKey);
		return () => {
			unlistenNavigate.then((f) => f());
			unlistenSkin.then((f) => f());
			window.removeEventListener('focus', draw);
			window.removeEventListener('blur', draw);
			window.removeEventListener('resize', draw);
			stopFrameMouse();
			canvas.removeEventListener('dblclick', onDouble);
			window.removeEventListener('keydown', onKey);
		};
	});
</script>

<div class="relative h-screen w-screen overflow-hidden bg-transparent">
	<canvas bind:this={canvas} class="absolute inset-0 block"></canvas>
	<div
		class="absolute"
		style:left="{inset.left}px"
		style:top="{inset.top}px"
		style:right="{inset.right}px"
		style:bottom="{inset.bottom}px"
	>
		<LibraryPages {page} />
	</div>
</div>
