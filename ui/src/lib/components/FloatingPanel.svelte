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
	import { pinOneToOnePixels } from '../skin/pixels.js';
	import { SEARCH_INPUT_ID, flashSearch, followQueue, loadSkin, playIndex, searchKeydown } from '../skin/skinApi.js';
	import { showPlaylistMenu, showPresetsMenu, showResultMenu } from '../skin/menu.js';
	import { drawEqualizer } from '../skin/render/equalizer.js';
	import { drawLyrics } from '../skin/render/lyrics.js';
	import { artFrame } from '../skin/render/albumArt.js';
	import { lyricsNow, sungLine } from '../skin/lyrics.js';
	import { attachKeys } from '../skin/keys.js';
	import { loadPrefs, pref, savePref } from '../skin/prefs.js';
	import { removeSelected } from '../skin/playlistActions.js';
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

	const size = () => ({ w: window.innerWidth, h: window.innerHeight });
	/** Ask the Winamp window to dock this panel back (`'stack'`, lyrics `'right'`) or hide it (null). */
	const dockTo = (/** @type {'stack' | 'right' | null} */ dock) =>
		emitTo('winamp', 'winamp-panel-dock', { kind, dock }).catch((e) => console.error('dock request failed', e));

	const onSearchKey = (/** @type {KeyboardEvent} */ e) => searchKeydown(e, searchInput, size(), () => dockTo(null));

	onMount(() => {
		pinOneToOnePixels().catch((e) => logUi('error', `${kind} window zoom pin failed: ${e}`));
		// This window's own copy of the panel state starts open, wherever the Winamp window had it.
		({ playlist: uiState.pl, search: uiState.search, eq: uiState.eq, lyrics: uiState.lyrics })[kind].open = true;
		// The EQ's settings live in the remembered prefs, shared with the Winamp window.
		if (kind === 'eq') loadPrefs().then(() => Object.assign(uiState.eq, pref('eq', {})));
		const detachKeys = attachKeys((action) => {
			// Delete/Enter work on this playlist's own selection.
			if (kind !== 'playlist' || (action !== 'remove' && action !== 'playSelected')) return false;
			if (action === 'remove') removeSelected().catch(() => {});
			else if (uiState.pl.selected !== null) playIndex(uiState.pl.selected).catch(() => {});
			return true;
		});

		const reload = () =>
			loadSkin()
				.then(async (payload) => {
					sprites = await decodeAllSprites(payload.sprites);
					pledit = payload.pledit;
					// Lyrics' frame (gen.bmp or the EQ fallback) decides where its titlebar ends.
					uiState.art.frame = artFrame(sprites);
				})
				.catch((e) => logUi('error', `${kind} window skin failed: ${e}`));
		reload();
		const unlistenSkin = listen('winamp-skin-changed', reload);
		if (kind === 'search') requestAnimationFrame(() => requestAnimationFrame(flashSearch));
		// The Winamp window's ADD/Search when this search box is the one floating.
		const unlistenFocus = listen('winamp-search-focus', () => flashSearch());

		attachInput(canvas, {
			hitTest: (x, y) => {
				const { w, h } = size();
				return x >= 0 && y >= 0 && x < w && y < h ? { kind, px: x, py: y, x: 0, y: 0, w, h } : null;
			},
			mainX: () => 0,
			showMenu: (target, at) => {
				if (!target) return;
				const shown =
					target.kind === 'result'
						? showResultMenu(target.index, at)
						: target.kind === 'presets'
							? showPresetsMenu(at)
							: showPlaylistMenu(target.kind, at);
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
			resize = { x: e.screenX, y: e.screenY, ...size() };
		};
		const onMove = (/** @type {MouseEvent} */ e) => {
			const r = grip();
			canvas.style.cursor = resize || (r && e.clientX >= r.x && e.clientY >= r.y) ? 'nwse-resize' : '';
			if (!resize) return;
			const next = fit({ w: resize.w + e.screenX - resize.x, h: resize.h + e.screenY - resize.y });
			if (sent && next.w === sent.w && next.h === sent.h) return;
			sent = next;
			resizeWinampPanel(kind, next.w, next.h).catch(() => {});
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
				drawSearch(ctx, sprites, pledit, uiState.search, 0, { w, h });
			} else if (kind === 'eq') {
				drawEqualizer(ctx, sprites, uiState.eq, 0);
			} else {
				const state = lyricsNow();
				const sung = state.lyrics ? sungLine(state.lyrics) : -1;
				drawLyrics(ctx, sprites, pledit, state, sung, uiState.lyrics.nudge, { x: 0, y: 0, w, h }, uiState.lyrics.closePressed);
			}
		});

		return () => {
			stopLoop();
			unlistenSkin.then((f) => f());
			unlistenFocus.then((f) => f());
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
			style:width="calc(100vw - {list.x + 20}px)"
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
	{/if}
</div>
