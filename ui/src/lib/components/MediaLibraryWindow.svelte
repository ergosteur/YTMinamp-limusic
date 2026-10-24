<script>
	// The Media Library (label "winamp-library", see +layout.svelte, winamp.rs and skin/library.js):
	// Limusic's sidebar and pages, as they are, inside the skin's generic frame titled MEDIA
	// LIBRARY, coloured from genex.bmp if the skin has one (skin/libraryTheme.js). Not Winamp's own
	// library, on purpose: Limusic's pages, album art and all, are the library. Resized from its
	// edges, like Limusic's window, and dragged by the titlebar (skin/frameWindow.js); the frame's ✕,
	// Escape or Alt+L closes it.
	import { onMount } from 'svelte';
	import { fly } from 'svelte/transition';
	import { cubicOut } from 'svelte/easing';
	import { HugeiconsIcon } from '@hugeicons/svelte';
	import { AlertCircleIcon, CheckmarkCircle02Icon, InformationCircleIcon } from '@hugeicons/core-free-icons';
	import { listen } from '@tauri-apps/api/event';
	import { logUi } from '$lib/errlog';
	import { refreshView, ui } from '$lib/player.svelte';
	import { HELP_KEY, keyOf } from '$lib/shortcuts';
	import { win } from '$lib/win.svelte';
	import Titlebar from './Titlebar.svelte';
	import ChannelPicker from './ChannelPicker.svelte';
	import AddToPlaylist from './AddToPlaylist.svelte';
	import CommandPalette from './CommandPalette.svelte';
	import KeyboardShortcuts from './KeyboardShortcuts.svelte';
	import LinkDialog from './LinkDialog.svelte';
	import NewPlaylistDialog from './NewPlaylistDialog.svelte';
	import ShareDialog from './ShareDialog.svelte';
	import { decodeAllSprites } from '../skin/render/spritesheet.js';
	import { artFrame, drawFrame, frameInset, onCloseButton } from '../skin/render/albumArt.js';
	import { pinOneToOnePixels } from '../skin/pixels.js';
	import { loadSkin } from '../skin/skinApi.js';
	import { frameMouse } from '../skin/frameWindow.js';
	import { keyName } from '../skin/keys.js';
	import { isLit, setActivePart } from '../skin/focus.js';
	import { applyLibraryTheme } from '../skin/libraryTheme.js';
	import { closeLibrary, initLibraryWindow, onLibraryNavigate, rememberLibraryOpen } from '../skin/library.js';
	import { openLimusicSettings, toggleLimusic } from '../skin/navigate.js';

	/** @type {{ children: import('svelte').Snippet }} */
	let { children } = $props();

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

	// Limusic's titlebar as the library's toolbar, without its window buttons: the frame has its
	// own ✕, and nothing here reads this otherwise (Limusic's window, which does, sets its own).
	win.chrome = 'on';

	onMount(() => {
		setActivePart('library');
		const stopLibrary = initLibraryWindow();
		const stopRemembering = rememberLibraryOpen();
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
					applyLibraryTheme(payload);
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
			resizable: true
		});
		const onKey = (/** @type {KeyboardEvent} */ e) => {
			// Escape in a page's own dialog or box is that page's.
			if (e.key === 'Escape' && !e.defaultPrevented && e.target === document.body) close();
			// Alt+L hides it here too, as it does from the player (Limusic has no Alt+L).
			if (e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey && keyName(e) === 'l') {
				e.preventDefault();
				close();
			}
			// Limusic's own keys that the Winamp windows' shortcuts leave out (shortcuts.ts, mini):
			// F5 reloads the page, Ctrl+K the command palette, Ctrl+H the list of keys.
			if (e.defaultPrevented) return;
			const ctrl = (e.ctrlKey || e.metaKey) && !e.altKey;
			if (e.key === 'F5') refreshView();
			// The player's keys for Limusic's window and its settings, which work from here too.
			else if (e.altKey && !e.ctrlKey && !e.metaKey && keyName(e) === 'm') void toggleLimusic();
			else if (ctrl && keyOf(e) === 'p') void openLimusicSettings();
			else if (ctrl && keyOf(e) === 'k') ui.paletteOpen = !ui.paletteOpen;
			else if (ctrl && keyOf(e) === HELP_KEY.toLowerCase()) ui.shortcutsOpen = !ui.shortcutsOpen;
			else return;
			e.preventDefault();
		};
		window.addEventListener('keydown', onKey);
		return () => {
			stopLibrary();
			stopRemembering();
			unlistenNavigate.then((f) => f());
			unlistenSkin.then((f) => f());
			window.removeEventListener('focus', draw);
			window.removeEventListener('blur', draw);
			window.removeEventListener('resize', draw);
			stopFrameMouse();
			window.removeEventListener('keydown', onKey);
		};
	});
</script>

<div class="relative h-screen w-screen overflow-hidden bg-transparent">
	<canvas bind:this={canvas} class="absolute inset-0 block"></canvas>
	<div
		class="library-pages absolute flex flex-col overflow-hidden bg-background text-foreground"
		style:left="{inset.left}px"
		style:top="{inset.top}px"
		style:right="{inset.right}px"
		style:bottom="{inset.bottom}px"
	>
		<Titlebar />
		<div class="flex min-h-0 flex-1">
			{@render children()}
		</div>
	</div>
</div>

<!-- What Limusic's window has around its pages for them (+layout.svelte), less what's its window's
     alone (settings, Listen Together, the importer, the player). -->
<CommandPalette />
<ChannelPicker />
<KeyboardShortcuts />
<AddToPlaylist />
<NewPlaylistDialog />
<ShareDialog />
<LinkDialog />

<!-- Limusic's toast, as its window shows it. -->
{#if ui.toast}
	{@const toast = ui.toast}
	<div
		transition:fly={{ y: 16, duration: 220, easing: cubicOut }}
		class="fixed bottom-10 left-1/2 z-[100] flex -translate-x-1/2 items-center gap-2 rounded-lg border bg-card px-4 py-2 text-sm shadow-lg"
	>
		{#if toast.kind === 'success'}
			<HugeiconsIcon icon={CheckmarkCircle02Icon} class="h-4 w-4 shrink-0 text-primary" />
		{:else if toast.kind === 'error'}
			<HugeiconsIcon icon={AlertCircleIcon} class="h-4 w-4 shrink-0 text-destructive" />
		{:else}
			<HugeiconsIcon icon={InformationCircleIcon} class="h-4 w-4 shrink-0 text-muted-foreground" />
		{/if}
		{toast.msg}
	</div>
{/if}

<style>
	/* Limusic's sidebar, as it is, less three things that are Limusic's window's: its wordmark (the
	   frame's title says what this is), its light/dark switch (the skin decides that here, and the
	   switch would flip Limusic's own window too) and Settings (its dialog lives in Limusic's
	   window; Options ▸ Preferences opens it). By position in Sidebar.svelte. */
	.library-pages > div > :global(aside > div:first-child > span:first-child),
	.library-pages > div > :global(aside > div:first-child > div > button:last-child),
	.library-pages > div > :global(aside > nav > button) {
		display: none !important;
	}
	/* Limusic's titlebar as a toolbar: back, forward, refresh, the account, Open link, Discord and
	   Last.fm. Not the app's icon and name (the frame's title is this window's), Listen Together
	   (its dialog is Limusic's window's), theater mode, the mini player or Winamp mode. By position
	   in Titlebar.svelte: its right group's buttons are the account, link, Listen Together,
	   Discord, Last.fm, theater, mini player, Winamp. */
	.library-pages > :global(header > span:first-child),
	.library-pages > :global(header > div:first-of-type > img),
	.library-pages > :global(header > div:last-child > button:nth-of-type(3)),
	.library-pages > :global(header > div:last-child > button:nth-of-type(n + 6)) {
		display: none !important;
	}
</style>
