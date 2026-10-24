<script>
	// A Winamp panel floating in a window of its own: the playlist editor, search, the equalizer or
	// lyrics (window label "winamp-<kind>", see +layout.svelte and winamp.rs; album art has its
	// own, AlbumArtWindow.svelte). The Winamp window owns whether it exists and where it docks; this
	// one draws the panel at the window's size, resizes it from the corner (list panels in
	// Winamp's steps, lyrics freely, the EQ not at all), and asks the Winamp window to dock, hide or
	// toggle panels.
	import { onMount } from 'svelte';
	import { emitTo, listen } from '@tauri-apps/api/event';
	import { playback } from '$lib/player.svelte';
	import { resizeWinampPanel } from '$lib/api';
	import { logUi } from '$lib/errlog';
	import { decodeAllSprites } from '../skin/render/spritesheet.js';
	import {
		SEARCH_INPUT_H,
		drawPlaylist,
		drawSearch,
		geometry,
		listRows,
		snapPanelSize
	} from '../skin/render/playlist.js';
	import { startRenderLoop } from '../skin/render/loop.js';
	import { attachInput } from '../skin/input.js';
	import { setActivePart } from '../skin/focus.js';
	import { doubleFactor, followDoubleSize, pinOneToOnePixels } from '../skin/pixels.js';
	import {
		LYRICS_ZOOM_EVENT,
		SEARCH_INPUT_ID,
		fileInfoForSelection,
		flashSearch,
		followQueue,
		loadAccount,
		loadSkin,
		playIndex,
		searchKeydown,
		searchWelcome
	} from '../skin/skinApi.js';
	import { requestMainMenu, showPlaylistMenu, showLyricsMenu, showPresetsMenu, showQueueRowMenu, showSearchMenu, showTitleMenu, showVisMenu, showArtMenu, showSearchKindMenu, showResultMenu } from '../skin/menu.js';
	import { drawEqualizer } from '../skin/render/equalizer.js';
	import { drawLyrics, lyricsViewRect } from '../skin/render/lyrics.js';
	import WinampLyricsView from './WinampLyricsView.svelte';
	import { KIND_BUTTON_W, kindLabel } from '../skin/searchKinds.js';
	import { artFrame } from '../skin/render/albumArt.js';
	import { attachKeys } from '../skin/keys.js';
	import { flushPrefs, loadPrefs, pref, savePref } from '../skin/prefs.js';
	import { cropToSelected, removeSelected } from '../skin/playlistActions.js';
	import { uiState } from '../skin/uiState.js';

	/** @type {{ kind: 'playlist' | 'search' | 'eq' | 'lyrics' }} */
	let { kind } = $props();

	/** @type {HTMLCanvasElement} */
	let canvas;
	/** Only rendered for search, hence state (the binding comes and goes). */
	let searchInput = /** @type {HTMLInputElement} */ ($state());
	/** @type {Map<string, ImageBitmap>} */
	let sprites = new Map();
	/** @type {import('$lib/api').SkinPayload['pledit']} */
	let pledit = $state({});
	/** The search box's "Songs ▾" button label. */
	let kindText = $state('Songs');
	/** Where the lyrics footer goes (render/lyrics.js keeps the strip), once drawn. */
	let lyricsRect = $state(/** @type {{ x: number, y: number, w: number, h: number } | null} */ (null));
	let lyricsZoom = $state(1);

	const size = () => ({ w: window.innerWidth, h: window.innerHeight });
	/** Ask the Winamp window to dock this panel back (`'stack'`, lyrics `'right'`) or hide it (null). */
	const dockTo = (/** @type {'stack' | 'right' | null} */ dock) =>
		// Saves first: docking reloads the EQ from disk, and this window is about to close.
		flushPrefs()
			.catch((e) => console.error('saving winamp prefs failed', e))
			.then(() => emitTo('winamp', 'winamp-panel-dock', { kind, dock }))
			.catch((e) => console.error('dock request failed', e));

	const onSearchKey = (/** @type {KeyboardEvent} */ e) => searchKeydown(e, searchInput, size(), () => dockTo(null));

	onMount(() => {
		// For the search welcome's sign-in hint.
		if (kind === 'search') loadAccount();
		// This window holds just the one panel: it's the active one whenever the window has focus.
		setActivePart(kind);
		// The DPI fix, then double size on top, following the Winamp window's.
		const unlistenDouble = followDoubleSize(
			pinOneToOnePixels().catch((e) => logUi('error', `${kind} window zoom pin failed: ${e}`)),
			kind
		);
		// This window's own copy of the panel state starts open, wherever the Winamp window had it.
		({ playlist: uiState.pl, search: uiState.search, eq: uiState.eq, lyrics: uiState.lyrics })[kind].open = true;
		// The EQ's settings live in the remembered prefs, shared with the Winamp window.
		if (kind === 'eq') loadPrefs().then(() => Object.assign(uiState.eq, pref('eq', {})));
		if (kind === 'lyrics') loadPrefs().then(() => (uiState.lyrics.zoom = pref('lyricsZoom', 1)));
		if (kind === 'search') loadPrefs().then(() => (uiState.search.kind = pref('searchKind', 'songs')));
		const detachKeys = attachKeys((action) => {
			// File info for this window's own selection.
			if (action === 'fileInfo') return (fileInfoForSelection(), true);
			// Delete/Ctrl+Delete/Enter work on this playlist's own selection.
			if (kind !== 'playlist' || (action !== 'remove' && action !== 'crop' && action !== 'playSelected')) return false;
			if (action === 'remove') removeSelected().catch(() => {});
			else if (action === 'crop') cropToSelected().catch(() => {});
			else if (uiState.pl.selected !== null) playIndex(uiState.pl.selected).catch(() => {});
			return true;
		});

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
					// Lyrics' frame (gen.bmp or the EQ fallback) decides where its titlebar ends.
					uiState.art.frame = artFrame(sprites);
				})
				.catch((e) => logUi('error', `${kind} window skin failed: ${e}`));
		};
		reload();
		const unlistenSkin = listen('winamp-skin-changed', reload);
		if (kind === 'search') requestAnimationFrame(() => requestAnimationFrame(flashSearch));
		// The Winamp window's ADD/Search when this search box is the one floating.
		const unlistenFocus = listen('winamp-search-focus', () => flashSearch());
		// The lyrics' size, changed from the keyboard in any Winamp window.
		const unlistenZoom = listen(LYRICS_ZOOM_EVENT, (e) => (uiState.lyrics.zoom = /** @type {number} */ (e.payload)));

		attachInput(canvas, {
			hitTest: (x, y) => {
				const { w, h } = size();
				return x >= 0 && y >= 0 && x < w && y < h ? { kind, px: x, py: y, x: 0, y: 0, w, h } : null;
			},
			mainX: () => 0,
			showMenu: (target, at) => {
				// The frame: the main menu, which the Winamp window has.
				if (!target) return void requestMainMenu(at).catch((e) => console.error('menu request failed', e));
				const shown =
					target.kind === 'result'
						? showResultMenu(target.index, at)
						: target.kind === 'queueRow'
							? showQueueRowMenu(target.index, at)
							: target.kind === 'art'
								? showArtMenu(at)
								: target.kind === 'title'
									? showTitleMenu(at)
								: target.kind === 'vis'
									? showVisMenu(at)
						: target.kind === 'presets'
							? showPresetsMenu(at)
							: target.kind === 'lyrics'
								? showLyricsMenu(at)
								: target.kind.startsWith('search-')
									? showSearchMenu(/** @type {any} */ (target.kind), at)
								: showPlaylistMenu(/** @type {import('../skin/render/playlist.js').PlaylistButton} */ (target.kind), at);
				shown.catch((e) => console.error('menu failed', e));
			},
			closePanel: () => dockTo(null),
			popOut: () => dockTo(kind === 'lyrics' ? 'right' : 'stack'),
			moveArt: () => {},
			toggle: (which) => {
				if (which === kind) dockTo(null);
				else emitTo('winamp', 'winamp-panel-toggle', which).catch(() => {});
			}
		});

		// Resizing from the bottom-right corner, in whole frame tiles like Winamp. Captured ahead
		// of input.js, which would otherwise take the press as a click on the panel.
		/** @type {{ x: number, y: number, w: number, h: number } | null} */
		let resize = null;
		/** @type {{ w: number, h: number } | null} */
		let sent = null;
		/** The corner grip, bottom-right; none on the EQ, which is Winamp's fixed size. */
		const grip = () => {
			const { w, h } = size();
			return kind === 'eq' ? null : { x: w - 20, y: h - 20 };
		};
		/** Where a resize lands: list panels in whole frame tiles, lyrics anywhere sensible. */
		const fit = (/** @type {{ w: number, h: number }} */ s) =>
			kind === 'lyrics' ? { w: Math.max(150, s.w), h: Math.max(100, s.h) } : snapPanelSize(s);
		const onDown = (/** @type {MouseEvent} */ e) => {
			const r = grip();
			if (!r || e.button !== 0 || e.clientX < r.x || e.clientY < r.y) return;
			e.stopImmediatePropagation();
			// Page px from the window's corner (which stays put): the same unit at any zoom.
			resize = { x: e.clientX, y: e.clientY, ...size() };
		};
		const onMove = (/** @type {MouseEvent} */ e) => {
			const r = grip();
			// Released outside the window (the drag outran it): no mouseup comes, so end it here.
			if (resize && !(e.buttons & 1)) return onUp();
			canvas.style.cursor = resize || (r && e.clientX >= r.x && e.clientY >= r.y) ? 'nwse-resize' : '';
			if (!resize) return;
			const next = fit({ w: resize.w + e.clientX - resize.x, h: resize.h + e.clientY - resize.y });
			if (sent && next.w === sent.w && next.h === sent.h) return;
			sent = next;
			resizeWinampPanel(kind, next.w * doubleFactor(), next.h * doubleFactor()).catch(() => {});
			savePref(`floatSize-${kind}`, next);
		};
		const onUp = () => {
			resize = null;
			sent = null;
		};
		window.addEventListener('mousedown', onDown, { capture: true });
		window.addEventListener('mousemove', onMove);
		window.addEventListener('mouseup', onUp);

		const stopLoop = startRenderLoop(() => {
			if (sprites.size === 0) return;
			if (kind === 'search' && kindLabel(uiState.search.kind) !== kindText) kindText = kindLabel(uiState.search.kind);
			const ctx = canvas.getContext('2d');
			if (!ctx) return;
			const { w, h } = size();
			if (canvas.width !== w || canvas.height !== h) {
				canvas.width = w;
				canvas.height = h;
				canvas.style.width = `${w}px`;
				canvas.style.height = `${h}px`;
			}
			ctx.clearRect(0, 0, w, h);
			if (kind === 'playlist') {
				followQueue(listRows('playlist', { w, h }).rows);
				drawPlaylist(ctx, sprites, pledit, playback.queue, uiState.pl, 0, { w, h });
			} else if (kind === 'search') {
				drawSearch(ctx, sprites, pledit, uiState.search, 0, { w, h }, searchWelcome());
			} else if (kind === 'eq') {
				drawEqualizer(ctx, sprites, uiState.eq, 0);
			} else {
				drawLyrics(ctx, sprites, pledit, { x: 0, y: 0, w, h }, uiState.lyrics.closePressed);
				const r = lyricsViewRect(sprites, { x: 0, y: 0, w, h });
				if (!lyricsRect || r.x !== lyricsRect.x || r.y !== lyricsRect.y || r.w !== lyricsRect.w || r.h !== lyricsRect.h) lyricsRect = r;
				if (uiState.lyrics.zoom !== lyricsZoom) lyricsZoom = uiState.lyrics.zoom;
			}
		});

		return () => {
			unlistenDouble.then((f) => f());
			stopLoop();
			unlistenSkin.then((f) => f());
			unlistenFocus.then((f) => f());
			unlistenZoom.then((f) => f());
			detachKeys();
			window.removeEventListener('mousedown', onDown, { capture: true });
			window.removeEventListener('mousemove', onMove);
			window.removeEventListener('mouseup', onUp);
		};
	});

	const list = $derived(geometry().list);
</script>

<div class="relative h-screen w-screen overflow-hidden bg-transparent">
	<canvas bind:this={canvas} class="block"></canvas>
	{#if kind === 'search'}
		<input
			bind:this={searchInput}
			id={SEARCH_INPUT_ID}
			class="absolute m-0 border px-1 py-0 text-[11px] leading-none outline-none"
			style:left="{list.x}px"
			style:top="{list.y}px"
			style:width="calc(100vw - {list.x + 20 + KIND_BUTTON_W}px)"
			style:height="{SEARCH_INPUT_H - 2}px"
			style:background={pledit.normalBg ?? '#000000'}
			style:color={pledit.normal ?? '#00ff00'}
			style:border-color={pledit.normal ?? '#00ff00'}
			style:caret-color={pledit.current ?? '#ffffff'}
			style:font-family={`${pledit.font ? `"${pledit.font}", ` : ''}Arial, sans-serif`}
			type="text"
			placeholder="Search YouTube Music"
			spellcheck="false"
			autocomplete="off"
			onkeydown={onSearchKey}
		/>
		<button
			type="button"
			class="absolute m-0 border px-1 py-0 text-left text-[11px] leading-none outline-none"
			style:left="calc(100vw - {20 + KIND_BUTTON_W}px)"
			style:top="{list.y}px"
			style:width="{KIND_BUTTON_W}px"
			style:height="{SEARCH_INPUT_H - 2}px"
			style:background={pledit.normalBg ?? '#000000'}
			style:color={pledit.current ?? '#ffffff'}
			style:border-color={pledit.normal ?? '#00ff00'}
			style:font-family={`${pledit.font ? `"${pledit.font}", ` : ''}Arial, sans-serif`}
			title="What to search for"
			onclick={(e) => {
				const r = e.currentTarget.getBoundingClientRect();
				showSearchKindMenu({ x: r.left, y: r.bottom }).catch((err) => console.error('menu failed', err));
			}}>{kindText} ▾</button
		>
	{/if}
	{#if kind === 'lyrics' && lyricsRect}
		<WinampLyricsView rect={lyricsRect} {pledit} zoom={lyricsZoom} onmenu={(at) => showLyricsMenu(at).catch((e) => console.error('menu failed', e))} />
	{/if}
</div>
