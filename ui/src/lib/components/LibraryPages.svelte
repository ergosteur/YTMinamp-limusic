<script>
	// The Media Library's inside, wherever it shows: its own window (MediaLibraryWindow.svelte) or
	// docked in the Winamp window (WinampSkin.svelte). Limusic's titlebar as a toolbar, its sidebar
	// and pages, as they are, coloured from the skin's genex.bmp (skin/libraryTheme.js), with what
	// Limusic's window has around its pages for them: the data they read (skin/library.js), dialogs,
	// toasts and a few of its keys. Not Winamp's own library, on purpose: Limusic's pages, album art
	// and all, are the library.
	import { onMount } from 'svelte';
	import { afterNavigate } from '$app/navigation';
	import { fly } from 'svelte/transition';
	import { cubicOut } from 'svelte/easing';
	import { HugeiconsIcon } from '@hugeicons/svelte';
	import { AlertCircleIcon, CheckmarkCircle02Icon, InformationCircleIcon } from '@hugeicons/core-free-icons';
	import { listen } from '@tauri-apps/api/event';
	import { logUi } from '$lib/errlog';
	import { auth, refreshView, ui } from '$lib/player.svelte';
	import { HELP_KEY, keyOf } from '$lib/shortcuts';
	import { win } from '$lib/win.svelte';
	import Sidebar from './Sidebar.svelte';
	import Titlebar from './Titlebar.svelte';
	import ChannelPicker from './ChannelPicker.svelte';
	import AddToPlaylist from './AddToPlaylist.svelte';
	import CommandPalette from './CommandPalette.svelte';
	import KeyboardShortcuts from './KeyboardShortcuts.svelte';
	import LinkDialog from './LinkDialog.svelte';
	import NewPlaylistDialog from './NewPlaylistDialog.svelte';
	import ShareDialog from './ShareDialog.svelte';
	import { loadSkin } from '../skin/skinApi.js';
	import { applyLibraryTheme } from '../skin/libraryTheme.js';
	import { initLibraryPages } from '../skin/library.js';

	/** @type {{ page: import('svelte').Snippet }} the route's page (+layout.svelte's `children`) */
	let { page } = $props();

	/** @type {HTMLElement | undefined} */
	let scroller = $state();
	// A new page starts at the top, as in Limusic's window (+layout.svelte); Back keeps where the
	// browser leaves it.
	afterNavigate((nav) => {
		if (scroller && nav.to && nav.type !== 'popstate') scroller.scrollTop = 0;
	});

	// Limusic's titlebar as the library's toolbar, without its window buttons: the frame has its
	// own ✕, and nothing here reads this otherwise (Limusic's window, which does, sets its own).
	win.chrome = 'on';

	onMount(() => {
		const stopPages = initLibraryPages();
		// Only the newest load lands: switch skins twice quickly and the second wins.
		let skinLoads = 0;
		const reload = () => {
			const mine = ++skinLoads;
			return loadSkin()
				.then((payload) => mine === skinLoads && applyLibraryTheme(payload))
				.catch((e) => logUi('error', `library colours failed: ${e}`));
		};
		reload();
		const unlistenSkin = listen('winamp-skin-changed', reload);
		// Limusic's own keys that the Winamp windows' shortcuts leave out (shortcuts.ts, mini):
		// F5 reloads the page, Ctrl+K the command palette, Ctrl+H the list of keys.
		const onKey = (/** @type {KeyboardEvent} */ e) => {
			if (e.defaultPrevented) return;
			const ctrl = (e.ctrlKey || e.metaKey) && !e.altKey;
			if (e.key === 'F5') refreshView();
			else if (ctrl && keyOf(e) === 'k') ui.paletteOpen = !ui.paletteOpen;
			else if (ctrl && keyOf(e) === HELP_KEY.toLowerCase()) ui.shortcutsOpen = !ui.shortcutsOpen;
			else return;
			e.preventDefault();
		};
		window.addEventListener('keydown', onKey);
		return () => {
			stopPages();
			unlistenSkin.then((f) => f());
			window.removeEventListener('keydown', onKey);
		};
	});
</script>

<div class="library-pages flex h-full w-full flex-col overflow-hidden bg-background text-foreground">
	<Titlebar />
	<div class="flex min-h-0 flex-1">
		<Sidebar />
		<main class="min-w-0 flex-1 overflow-y-auto" bind:this={scroller}>
			{#key `${auth.epoch}:${ui.epoch}`}
				{@render page()}
			{/key}
		</main>
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
	/* The account as its picture and arrow alone: no name. Limusic shows the arrow only in a wide
	   window (lg:), so it is shown here at any width. By position in AccountMenu.svelte. */
	.library-pages > :global(header > div:last-child > button:first-of-type > span) {
		display: none !important;
	}
	.library-pages > :global(header > div:last-child > button:first-of-type > svg:last-child) {
		display: block !important;
	}
</style>
