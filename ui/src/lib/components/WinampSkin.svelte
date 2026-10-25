<script>
	// Winamp skin mode: the whole window when the window is labeled "winamp" (see +layout.svelte,
	// mirroring how MiniPlayer.svelte owns the whole window for "mini"). Driven by the same global
	// `playback` store every other window reads ($lib/player.svelte) — there is no second copy of
	// playback state, same reasoning as the mini player.
	import { onMount } from 'svelte';
	import { emit, emitTo, listen } from '@tauri-apps/api/event';
	import { auth, playback, ui } from '$lib/player.svelte';
	import { logUi } from '$lib/errlog';
	import { winampAudioInfo } from '$lib/api';
	import { APP_NAME } from '../skin/brand.js';
	import { decodeAllSprites } from '../skin/render/spritesheet.js';
	import { pinOneToOnePixels } from '../skin/pixels.js';
	import { drawEqualizer } from '../skin/render/equalizer.js';
	import { drawLyrics, lyricsViewRect } from '../skin/render/lyrics.js';
	import { analyzerMoving, drawAnalyzer } from '../skin/render/visualizer.js';
	import { VIS_POS } from '../skin/render/sprites.js';
	import { analyzerColumns } from '../skin/testPattern.js';
	import WinampLyricsView from './WinampLyricsView.svelte';
	import { KIND_BUTTON_W, kindLabel } from '../skin/searchKinds.js';
	import { attachKeys, runKey } from '../skin/keys.js';
	import { loadPrefs, pref } from '../skin/prefs.js';
	import { applyRegionClip, drawMainWindow, sizeCanvas } from '../skin/render/mainWindow.js';
	import { artFrame, drawAlbumArt, drawFrame, frameInset } from '../skin/render/albumArt.js';
	import { goto } from '$app/navigation';
	import LibraryPages from './LibraryPages.svelte';
	import { currentPage, floatLibrary, onLibraryOpenRequest } from '../skin/library.js';
	import { isLit } from '../skin/focus.js';
	import { coverFor } from '../skin/art.js';
	import { LIST, SEARCH_INPUT_H, drawPlaylist, drawSearch } from '../skin/render/playlist.js';
	import { startRenderLoop } from '../skin/render/loop.js';
	import { attachInput } from '../skin/input.js';
	import { dockedLayout, hitLayout } from '../skin/layout.js';
	import {
		ART_CAPTION_EVENT,
		loadAccount,
		searchWelcome,
		LLAMA_INTRO,
		LYRICS_ZOOM_EVENT,
		setArtCaption,
		SEARCH_INPUT_ID,
		followQueue,
		followStopAfter,
		watchForUpdates,
		flashMarquee,
		loadSkin,
		openSearch,
		resizeToLayout,
		restorePrefs,
		searchKeydown,
		selectSkin,
		setArt,
		setPanelOpen,
		knowSettings,
		tickerToast,
		togglePanel
	} from '../skin/skinApi.js';
	import { onMainMenuRequest, showMainMenu, showPlaylistMenu, showLyricsMenu, showPresetsMenu, showQueueRowMenu, showSearchMenu, showTitleMenu, showVisMenu, showStopMenu, showArtMenu, showSearchKindMenu, showResultMenu } from '../skin/menu.js';
	import { uiState } from '../skin/uiState.js';
	import { refreshLibrary } from '../skin/playlistActions.js';

	/** @type {HTMLCanvasElement} */
	let canvas;
	/** The analyzer, over main.bmp's vis box: redrawn every frame on its own (see the loops). */
	/** @type {HTMLCanvasElement} */
	let vizCanvas;
	/** Where the main window starts in the canvas: art docked left pushes it right. */
	let mainX = $state(0);
	/** The search panel's text box: a real input, so typing, pasting and IME (Korean, ...) work. */
	/** @type {HTMLInputElement} */
	let searchInput;
	let status = $state('loading skin…');

	/** @type {Map<string, ImageBitmap>} */
	let sprites = new Map();
	/** @type {[number, number, number][]} */
	let viscolor = [];
	/** @type {import('$lib/api').SkinPayload['region']} */
	let region = null;
	/** @type {import('$lib/api').SkinPayload['pledit']} */
	let pledit = $state({});
	/** The search box's "Songs ▾" button: where (beside the box), and what it says. */
	let kindAt = $state(/** @type {{ x: number, y: number } | null} */ (null));
	let kindText = $state('Songs');
	/** Where the docked lyrics' HTML view goes (inside render/lyrics.js's frame), while docked. */
	/** @type {{ page: import('svelte').Snippet }} the route's page, for the docked Media Library */
	let { page } = $props();
	/** Where the docked Media Library's pages go (inside its frame), or null if it isn't docked. */
	let libraryRect = $state(/** @type {{ x: number, y: number, w: number, h: number } | null} */ (null));
	let lyricsRect = $state(/** @type {{ x: number, y: number, w: number, h: number } | null} */ (null));
	/** The lyrics' text size (uiState.lyrics.zoom), for that view. */
	let lyricsZoom = $state(1);
	/** The layout the canvas size/clip were last set for; null = not set yet. */
	let shapedFor = /** @type {string | null} */ (null);

	/** "Artist - Title", as the playlist shows it. */
	function nowTitle() {
		const now = playback.now;
		if (!now) return welcome();
		const title = now.artists ? `${now.artists} - ${now.title}` : now.title;
		// The llama intro cued (a first run, About's Cue the Llama) and not started: the welcome
		// still, the intro after it, until Play.
		const cued = now.videoId === LLAMA_INTRO.video_id && playback.paused && playback.position < 0.5;
		return cued ? `${welcome()} ${title} ***` : title;
	}

	/** With nothing playing (a first run, an empty queue): a welcome, Winamp's own line, and where
	 * to start, sign-in included until there's an account. */
	function welcome() {
		const signIn = auth.account?.signedIn ? '' : ' *** Sign in with the account button at the top of the Media Library';
		return `*** Welcome to ${APP_NAME}! It really whips the llama's ass! *** To start, search in the Search window or open the Media Library (Alt+L)${signIn} ***`;
	}

	/** Keys in the search box: see `searchKeydown`. */
	const onSearchKey = (/** @type {KeyboardEvent} */ e) =>
		searchKeydown(e, searchInput, undefined, () => setPanelOpen('search', false));

	/** What the search box was last placed for, so the per-frame call is a no-op otherwise. */
	let placedFor = /** @type {{ at: string, pledit: object | null }} */ ({ at: '', pledit: null });

	/** Keep the HTML search box on the search panel's text-box area (hidden when it's closed). */
	function placeSearchInput(/** @type {{ x: number, y: number } | null} */ panel) {
		const at = panel ? `${panel.x},${panel.y}` : '';
		if (placedFor.at === at && placedFor.pledit === pledit) return;
		placedFor = { at, pledit };
		const style = searchInput.style;
		if (!panel) {
			style.display = 'none';
			kindAt = null;
			return;
		}
		style.display = 'block';
		style.left = `${panel.x + LIST.x}px`;
		style.top = `${panel.y + LIST.y}px`;
		style.width = `${LIST.w - KIND_BUTTON_W}px`;
		style.height = `${SEARCH_INPUT_H - 2}px`;
		kindAt = { x: panel.x + LIST.x + LIST.w - KIND_BUTTON_W, y: panel.y + LIST.y };
		style.background = pledit.normalBg ?? '#000000';
		style.color = pledit.normal ?? '#00ff00';
		style.borderColor = pledit.normal ?? '#00ff00';
		style.caretColor = pledit.current ?? '#ffffff';
		style.fontFamily = `${pledit.font ? `"${pledit.font}", ` : ''}Arial, sans-serif`;
	}

	$effect(() => tickerToast(ui.toast));

	onMount(() => {
		knowSettings();
		// Whether the welcomes suggest signing in (the ticker's above, the search panel's).
		loadAccount();
		let stopLoop = () => {};
		// The DPI fix first, then double size on top of it, then everything else remembered.
		const pinned = pinOneToOnePixels().catch((e) => logUi('error', `winamp zoom pin failed: ${e}`));

		/** Only the newest skin lands: two quick picks settle on the second, whichever decodes first. */
		let skinLoads = 0;
		/** @param {Promise<import('$lib/api').SkinPayload>} loading */
		const applySkin = (loading) => {
			const mine = ++skinLoads;
			return loading
				.then(async (payload) => {
					const decoded = await decodeAllSprites(payload.sprites);
					if (mine !== skinLoads) return;
					if (!decoded.get('main')) throw new Error('skin has no main.bmp');
					viscolor = payload.viscolor;
					region = payload.region;
					pledit = payload.pledit;
					sprites = decoded;
					shapedFor = null; // new region.txt: reshape on the next frame
					status = '';
					// gen.bmp or a fallback frame: the docked art's size depends on which.
					uiState.art.frame = artFrame(decoded);
					resizeToLayout();
					// Every other Winamp window draws from the same skin. Once, to all: `listen` hears an
					// event whichever window it's sent to, so one per window reloads each of them that often.
					emit('winamp-skin-changed').catch(() => {});
				})
				.catch((e) => {
					console.error('failed to load winamp skin', e);
					logUi('error', `winamp skin failed: ${e}`);
					// A failed switch keeps the old skin; only a failed first load has nothing to show.
					if (sprites.size === 0) status = `error: ${e}`;
				});
		};

		// Panels need the skin (album art's size depends on its frame), so they come back after it.
		applySkin(loadSkin())
			.then(() => pinned)
			.then(restorePrefs)
			.catch((e) => logUi('error', `winamp prefs failed: ${e}`));
		// The menus' playlists (Play ▸, LIST), fetched now so the first right-click needn't wait.
		refreshLibrary().catch((e) => logUi('warn', `winamp library prefetch failed: ${e}`));
		/** Double-clicking docked art moves it on: right → below → left → right. */
		const NEXT_DOCK = /** @type {const} */ ({ right: 'stack', stack: 'left', left: 'right', float: 'right' });
		attachInput(canvas, {
			hitTest: hitLayout,
			mainX: () => dockedLayout().mainX,
			showMenu: (target, at) => {
				const shown = !target
					? showMainMenu((path) => applySkin(selectSkin(path)), at)
					: target.kind === 'result'
						? showResultMenu(target.index, at)
						: target.kind === 'queueRow'
							? showQueueRowMenu(target.index, at)
							: target.kind === 'art'
								? showArtMenu(at)
								: target.kind === 'title'
									? showTitleMenu(at)
								: target.kind === 'vis'
									? showVisMenu(at)
								: target.kind === 'stop'
									? showStopMenu(at)
						: target.kind === 'presets'
							? showPresetsMenu(at)
							: target.kind === 'lyrics'
								? showLyricsMenu(at)
								: target.kind.startsWith('search-')
									? showSearchMenu(/** @type {any} */ (target.kind), at)
								: showPlaylistMenu(/** @type {import('../skin/render/playlist.js').PlaylistButton} */ (target.kind), at);
				shown.catch((e) => console.error('menu failed', e));
			},
			closePanel: (kind) => (kind === 'art' ? setArt(false) : setPanelOpen(kind, false)),
			// A docked panel's titlebar floats it (lyrics and the rest alike).
			// A docked panel's titlebar floats it; a double-click on docked art moves it round.
			popOut: (kind) =>
				kind === 'art' ? setArt(true, 'float') : kind === 'library' ? floatLibrary(currentPage()) : setPanelOpen(kind, true, 'float'),
			moveArt: () => setArt(true, NEXT_DOCK[uiState.art.dock]),
			toggle: togglePanel
		});

		// kbps/kHz/channels: mpv has no event for them, and they only change per track.
		const pollAudio = () =>
			winampAudioInfo()
				.then((info) => {
					uiState.kbps = info.kbps;
					uiState.khz = info.khz;
					if (info.channels != null) uiState.stereo = info.channels >= 2;
				})
				.catch(() => {});
		pollAudio();
		const audioTimer = setInterval(pollAudio, 1000);

		// Floating panel windows (FloatingPanel.svelte): their ✕ hides the panel, a titlebar
		// double-click docks it back, their eject/playlist buttons toggle panels here, and however
		// one closes (Alt+F4 too) the panel's state follows.
		/** @typedef {{ kind: import('../skin/layout.js').PanelKind, dock: string | null, path?: string }} DockRequest */
		const unlistenDock = listen('winamp-panel-dock', (e) => {
			const { kind, dock, path } = /** @type {DockRequest} */ (e.payload);
			// A floating EQ saved its settings as it went: pick them up before drawing it here.
			if (kind === 'eq') loadPrefs().then(() => Object.assign(uiState.eq, pref('eq', {})));
			if (kind === 'art') {
				if (dock) setArt(true, /** @type {import('../skin/uiState.js').ArtDock} */ (dock));
				else setArt(false);
			} else if (!dock) {
				setPanelOpen(kind, false);
			} else {
				// "Dock" from a floating window: lyrics and the library go back to the right, the rest
				// to the stack. The library comes at the page its window showed.
				const side = kind === 'lyrics' || kind === 'library' ? 'right' : 'stack';
				setPanelOpen(kind, true, dock === 'float' ? 'float' : side);
				if (kind === 'library' && path) goto(path).catch(() => {});
			}
		});
		const unlistenToggle = listen('winamp-panel-toggle', (e) =>
			togglePanel(/** @type {import('../skin/layout.js').PanelKind} */ (e.payload))
		);
		// Go to artist / album and the like, from other windows: wherever the library is.
		const unlistenLibrary = onLibraryOpenRequest();
		// The main menu, asked for by a right-click on the Media Library's frame.
		const unlistenMainMenu = onMainMenuRequest((at) =>
			showMainMenu((path) => applySkin(selectSkin(path)), at).catch((e) => console.error('menu failed', e))
		);
		// Shortcuts pressed in a floating panel run here.
		const unlistenKey = listen('winamp-key', (e) => runKey(/** @type {import('../skin/keys.js').KeyAction} */ (e.payload)));
		// The lyrics' size, changed with Ctrl+wheel over a floating lyrics window.
		const unlistenZoom = listen(LYRICS_ZOOM_EVENT, (e) => (uiState.lyrics.zoom = /** @type {number} */ (e.payload)));
		const unlistenCaption = listen(ART_CAPTION_EVENT, (e) => setArtCaption(/** @type {boolean} */ (e.payload)));
		const detachKeys = attachKeys();
		// A newer build: in the title while paused, and first in the main menu.
		const stopUpdateWatch = watchForUpdates();
		// A floating playlist's ADD, and the messages floating panels show in this marquee.
		const unlistenAdd = listen('winamp-search-add', () => openSearch());
		// A bare string, or { text, ms } from flashMarquee in another window.
		const unlistenMarquee = listen('winamp-marquee', (e) => {
			const m = /** @type {string | { text: string, ms: number }} */ (e.payload);
			if (typeof m === 'string') flashMarquee(m);
			else flashMarquee(m.text, m.ms);
		});
		const unlistenClosed = listen('winamp-panel-closed', (e) => {
			const kind = /** @type {import('../skin/layout.js').PanelKind | 'url' | 'milkdrop' | 'eqsave' | 'fileinfo' | 'about' | 'update' | 'newpl'} */ (e.payload);
			// The Open URL, save-preset, file info, about, update and new-playlist windows: nothing
			// here tracks them.
			if (kind === 'url' || kind === 'eqsave' || kind === 'fileinfo' || kind === 'about' || kind === 'update' || kind === 'newpl') return;
			if (kind === 'milkdrop') return void (uiState.milkdrop = false);
			const view = { art: uiState.art, playlist: uiState.pl, search: uiState.search, eq: uiState.eq, lyrics: uiState.lyrics, library: uiState.library }[kind];
			if (view.dock === 'float') view.open = false;
		});

		const unlistenViz = listen('winamp-viz', (e) => {
			uiState.vizColumns = /** @type {number[]} */ (e.payload);
			uiState.vizAt = performance.now();
		});

		stopLoop = startRenderLoop((nowMs) => {
			if (sprites.size === 0) return;
			const ctx = canvas.getContext('2d');
			if (!ctx) return;
			const layout = dockedLayout();
			const shape = layout.panels.map((p) => `${p.kind}:${p.x},${p.y},${p.w},${p.h}`).join(' ');
			if (shapedFor !== shape) {
				shapedFor = shape;
				sizeCanvas(canvas, layout.width, layout.height);
				applyRegionClip(canvas, region, layout.mainX, layout.panels);
				mainX = layout.mainX;
			}
			ctx.clearRect(0, 0, canvas.width, canvas.height);
			// The main window and the stack draw at their own origin; docked left, art pushes them right.
			ctx.save();
			ctx.translate(layout.mainX, 0);
			// Merge the real playback store with the canvas-only interaction state (uiState.js)
			// into the plain shape render/mainWindow.js expects.
			drawMainWindow(
				ctx,
				sprites,
				{
					title: nowMs < uiState.marqueeMessageUntil ? uiState.marqueeMessage : nowTitle(),
					pledit,
					kbps: playback.now ? uiState.kbps : null,
					khz: playback.now ? uiState.khz : null,
					playing: !playback.paused,
					positionSecs: uiState.draggingSeek ? uiState.draggingPositionSecs : playback.position,
					durationSecs: playback.duration,
					volume: uiState.draggingVolume ? uiState.draggingVolumeValue : playback.volume,
					balance: uiState.balance,
					stereo: uiState.stereo,
					pressedButton: uiState.pressedButton,
					draggingSeek: uiState.draggingSeek,
					visMode: uiState.visMode,
					viscolor,
					// Paused: let the bars fall instead of freezing on the last frame.
					vizColumns: playback.paused ? null : uiState.vizColumns,
					plOpen: uiState.pl.open,
					eqOpen: uiState.eq.open,
					artOpen: uiState.art.open,
					alwaysOnTop: uiState.alwaysOnTop,
					doubleSize: uiState.doubleSize,
					timeRemaining: uiState.timeRemaining,
					shuffle: !!playback.queue.shuffle,
					repeat: playback.queue.repeat ?? 'off'
				},
				nowMs
			);
			ctx.restore();
			followQueue();
			followStopAfter();
			const searchPanel = layout.panels.find((p) => p.kind === 'search');
			if (kindLabel(uiState.search.kind) !== kindText) kindText = kindLabel(uiState.search.kind);
			const lyricsPanel = layout.panels.find((p) => p.kind === 'lyrics');
			const r = lyricsPanel ? lyricsViewRect(sprites, lyricsPanel) : null;
			if (r?.x !== lyricsRect?.x || r?.y !== lyricsRect?.y || r?.w !== lyricsRect?.w || r?.h !== lyricsRect?.h) lyricsRect = r;
			if (uiState.lyrics.zoom !== lyricsZoom) lyricsZoom = uiState.lyrics.zoom;
			const libraryPanel = layout.panels.find((p) => p.kind === 'library');
			const inset = frameInset(artFrame(sprites));
			const lr = libraryPanel && {
				x: libraryPanel.x + inset.left,
				y: libraryPanel.y + inset.top,
				w: libraryPanel.w - inset.left - inset.right,
				h: libraryPanel.h - inset.top - inset.bottom
			};
			if (lr?.x !== libraryRect?.x || lr?.y !== libraryRect?.y || lr?.w !== libraryRect?.w || lr?.h !== libraryRect?.h) libraryRect = lr ?? null;
			for (const panel of layout.panels) {
				if (panel.kind === 'art') {
					const caption = uiState.art.caption ? { text: playback.now?.album ?? '', pledit } : null;
					drawAlbumArt(ctx, sprites, coverFor(playback.now?.thumbnail), panel, uiState.art.closePressed, caption);
					continue;
				}
				if (panel.kind === 'lyrics') {
					drawLyrics(ctx, sprites, pledit, panel, uiState.lyrics.closePressed);
					continue;
				}
				if (panel.kind === 'library') {
					drawFrame(ctx, sprites, panel, uiState.library.closePressed, 'media library', isLit('library'));
					continue;
				}
				ctx.save();
				ctx.translate(panel.x, 0);
				if (panel.kind === 'search') drawSearch(ctx, sprites, pledit, uiState.search, panel.y, undefined, searchWelcome());
				else if (panel.kind === 'eq') drawEqualizer(ctx, sprites, uiState.eq, panel.y);
				else drawPlaylist(ctx, sprites, pledit, playback.queue, uiState.pl, panel.y);
				ctx.restore();
			}
			placeSearchInput(searchPanel ?? null);
		});
		const stopVizLoop = startRenderLoop(
			(nowMs) => {
				const on = uiState.visMode === 'analyzer' && sprites.size > 0;
				vizCanvas.style.display = on ? 'block' : 'none';
				const ctx = vizCanvas.getContext('2d');
				if (!on || !ctx) return;
				ctx.setTransform(1, 0, 0, 1, -VIS_POS.x, -VIS_POS.y);
				drawAnalyzer(ctx, viscolor, analyzerColumns(nowMs));
			},
			(nowMs) => uiState.visMode === 'analyzer' && analyzerMoving(analyzerColumns(nowMs))
		);

		return () => {
			stopLoop();
			stopVizLoop();
			clearInterval(audioTimer);
			unlistenViz.then((f) => f());
			unlistenDock.then((f) => f());
			unlistenToggle.then((f) => f());
			unlistenLibrary.then((f) => f());
			unlistenAdd.then((f) => f());
			unlistenMarquee.then((f) => f());
			unlistenClosed.then((f) => f());
			unlistenKey.then((f) => f());
			unlistenMainMenu.then((f) => f());
			unlistenZoom.then((f) => f());
			unlistenCaption.then((f) => f());
			detachKeys();
			stopUpdateWatch();
		};
	});
</script>

<div class="relative h-screen w-screen overflow-hidden bg-transparent">
	<canvas bind:this={canvas} class="block"></canvas>
	<canvas
		bind:this={vizCanvas}
		class="pointer-events-none absolute"
		width={VIS_POS.w}
		height={VIS_POS.h}
		style:left="{mainX + VIS_POS.x}px"
		style:top="{VIS_POS.y}px"
		style:width="{VIS_POS.w}px"
		style:height="{VIS_POS.h}px"
		style:image-rendering="pixelated"
	></canvas>
	<input
		bind:this={searchInput}
		id={SEARCH_INPUT_ID}
		class="absolute m-0 border px-1 py-0 text-[11px] leading-none outline-none"
		style="display: none"
		type="text"
		placeholder="Search YouTube Music"
		spellcheck="false"
		autocomplete="off"
		onkeydown={onSearchKey}
	/>
	{#if kindAt}
		<button
			type="button"
			class="absolute m-0 border px-1 py-0 text-left text-[11px] leading-none outline-none"
			style:left="{kindAt.x}px"
			style:top="{kindAt.y}px"
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
	{#if libraryRect}
		<!-- At its own size in double size: Limusic's pages doubled would show next to nothing. -->
		{@const f = uiState.doubleSize ? 2 : 1}
		<div
			class="absolute"
			style:left="{libraryRect.x}px"
			style:top="{libraryRect.y}px"
			style:width="{libraryRect.w * f}px"
			style:height="{libraryRect.h * f}px"
			style:zoom={1 / f}
		>
			<LibraryPages {page} />
		</div>
	{/if}
	{#if lyricsRect}
		<WinampLyricsView rect={lyricsRect} {pledit} zoom={lyricsZoom} onmenu={(at) => showLyricsMenu(at).catch((e) => console.error('menu failed', e))} />
	{/if}
	{#if status}
		<div class="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/60 text-[10px] text-white">
			{status}
		</div>
	{/if}
</div>
