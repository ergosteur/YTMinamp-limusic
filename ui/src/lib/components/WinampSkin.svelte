<script>
	// Winamp skin mode: the whole window when the window is labeled "winamp" (see +layout.svelte,
	// mirroring how MiniPlayer.svelte owns the whole window for "mini"). Driven by the same global
	// `playback` store every other window reads ($lib/player.svelte) — there is no second copy of
	// playback state, same reasoning as the mini player.
	import { onMount } from 'svelte';
	import { emitTo, listen } from '@tauri-apps/api/event';
	import { playback } from '$lib/player.svelte';
	import { logUi } from '$lib/errlog';
	import { winampAudioInfo } from '$lib/api';
	import { decodeAllSprites } from '../skin/render/spritesheet.js';
	import { pinOneToOnePixels } from '../skin/pixels.js';
	import { drawEqualizer } from '../skin/render/equalizer.js';
	import { drawLyrics } from '../skin/render/lyrics.js';
	import { lyricsNow, sungLine } from '../skin/lyrics.js';
	import { attachKeys, runKey } from '../skin/keys.js';
	import { loadPrefs, pref } from '../skin/prefs.js';
	import { applyRegionClip, drawMainWindow, sizeCanvas } from '../skin/render/mainWindow.js';
	import { artFrame, drawAlbumArt } from '../skin/render/albumArt.js';
	import { coverFor } from '../skin/art.js';
	import { LIST, SEARCH_INPUT_H, drawPlaylist, drawSearch } from '../skin/render/playlist.js';
	import { startRenderLoop } from '../skin/render/loop.js';
	import { attachInput } from '../skin/input.js';
	import { dockedLayout, hitLayout } from '../skin/layout.js';
	import {
		SEARCH_INPUT_ID,
		followQueue,
		flashMarquee,
		loadSkin,
		openSearch,
		resizeToLayout,
		restorePrefs,
		searchKeydown,
		selectSkin,
		setArt,
		setPanelOpen,
		togglePanel
	} from '../skin/skinApi.js';
	import { showMainMenu, showPlaylistMenu, showPresetsMenu, showResultMenu } from '../skin/menu.js';
	import { uiState } from '../skin/uiState.js';

	/** @type {HTMLCanvasElement} */
	let canvas;
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
	let pledit = {};
	/** The layout the canvas size/clip were last set for; null = not set yet. */
	let shapedFor = /** @type {string | null} */ (null);

	/** "Artist - Title", as the playlist shows it. */
	function nowTitle() {
		const now = playback.now;
		if (!now) return '';
		return now.artists ? `${now.artists} - ${now.title}` : now.title;
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
			return;
		}
		style.display = 'block';
		style.left = `${panel.x + LIST.x}px`;
		style.top = `${panel.y + LIST.y}px`;
		style.width = `${LIST.w}px`;
		style.height = `${SEARCH_INPUT_H - 2}px`;
		style.background = pledit.normalBg ?? '#000000';
		style.color = pledit.normal ?? '#00ff00';
		style.borderColor = pledit.normal ?? '#00ff00';
		style.caretColor = pledit.current ?? '#ffffff';
		style.fontFamily = `${pledit.font ? `"${pledit.font}", ` : ''}Arial, sans-serif`;
	}

	onMount(() => {
		let stopLoop = () => {};
		// The DPI fix first, then double size on top of it, then everything else remembered.
		const pinned = pinOneToOnePixels().catch((e) => logUi('error', `winamp zoom pin failed: ${e}`));

		/** @param {Promise<import('$lib/api').SkinPayload>} loading */
		const applySkin = (loading) =>
			loading
				.then(async (payload) => {
					const decoded = await decodeAllSprites(payload.sprites);
					if (!decoded.get('main')) throw new Error('skin has no main.bmp');
					viscolor = payload.viscolor;
					region = payload.region;
					pledit = payload.pledit;
					sprites = decoded;
					shapedFor = null; // new region.txt: reshape on the next frame
					status = '';
					// gen.bmp or the EQ fallback: the docked art's size depends on which.
					uiState.art.frame = artFrame(decoded);
					resizeToLayout();
					// Floating panel windows draw from the same skin.
					for (const kind of ['art', 'playlist', 'search', 'eq', 'lyrics', 'url']) {
						emitTo(`winamp-${kind}`, 'winamp-skin-changed').catch(() => {});
					}
				})
				.catch((e) => {
					console.error('failed to load winamp skin', e);
					logUi('error', `winamp skin failed: ${e}`);
					// A failed switch keeps the old skin; only a failed first load has nothing to show.
					if (sprites.size === 0) status = `error: ${e}`;
				});

		// Panels need the skin (album art's size depends on its frame), so they come back after it.
		applySkin(loadSkin())
			.then(() => pinned)
			.then(restorePrefs)
			.catch((e) => logUi('error', `winamp prefs failed: ${e}`));
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
						: target.kind === 'presets'
							? showPresetsMenu(at)
							: showPlaylistMenu(target.kind, at);
				shown.catch((e) => console.error('menu failed', e));
			},
			closePanel: (kind) => (kind === 'art' ? setArt(false) : setPanelOpen(kind, false)),
			// A docked panel's titlebar floats it (lyrics and the rest alike).
			// A docked panel's titlebar floats it; a double-click on docked art moves it round.
			popOut: (kind) => (kind === 'art' ? setArt(true, 'float') : setPanelOpen(kind, true, 'float')),
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
		/** @typedef {{ kind: import('../skin/layout.js').PanelKind, dock: string | null }} DockRequest */
		const unlistenDock = listen('winamp-panel-dock', (e) => {
			const { kind, dock } = /** @type {DockRequest} */ (e.payload);
			// A floating EQ saved its settings as it went: pick them up before drawing it here.
			if (kind === 'eq') loadPrefs().then(() => Object.assign(uiState.eq, pref('eq', {})));
			if (kind === 'art') {
				if (dock) setArt(true, /** @type {import('../skin/uiState.js').ArtDock} */ (dock));
				else setArt(false);
			} else if (!dock) {
				setPanelOpen(kind, false);
			} else {
				// "Dock" from a floating window: lyrics go back to the right, the rest to the stack.
				setPanelOpen(kind, true, dock === 'float' ? 'float' : kind === 'lyrics' ? 'right' : 'stack');
			}
		});
		const unlistenToggle = listen('winamp-panel-toggle', (e) =>
			togglePanel(/** @type {import('../skin/layout.js').PanelKind} */ (e.payload))
		);
		// Shortcuts pressed in a floating panel run here.
		const unlistenKey = listen('winamp-key', (e) => runKey(/** @type {import('../skin/keys.js').KeyAction} */ (e.payload)));
		const detachKeys = attachKeys();
		// A floating playlist's ADD, and the messages floating panels show in this marquee.
		const unlistenAdd = listen('winamp-search-add', () => openSearch());
		const unlistenMarquee = listen('winamp-marquee', (e) => flashMarquee(/** @type {string} */ (e.payload)));
		const unlistenClosed = listen('winamp-panel-closed', (e) => {
			const kind = /** @type {import('../skin/layout.js').PanelKind | 'url'} */ (e.payload);
			if (kind === 'url') return; // the Open URL dialog: nothing here tracks it
			const view = { art: uiState.art, playlist: uiState.pl, search: uiState.search, eq: uiState.eq, lyrics: uiState.lyrics }[kind];
			if (view.dock === 'float') view.open = false;
		});

		const unlistenViz = listen('winamp-viz', (e) => {
			uiState.vizColumns = /** @type {number[]} */ (e.payload);
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
					loading: !playback.now,
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
			const searchPanel = layout.panels.find((p) => p.kind === 'search');
			for (const panel of layout.panels) {
				if (panel.kind === 'art') {
					drawAlbumArt(ctx, sprites, coverFor(playback.now?.thumbnail), panel, uiState.art.closePressed);
					continue;
				}
				if (panel.kind === 'lyrics') {
					const state = lyricsNow();
					const sung = state.lyrics ? sungLine(state.lyrics) : -1;
					drawLyrics(ctx, sprites, pledit, state, sung, uiState.lyrics.nudge, panel, uiState.lyrics.closePressed);
					continue;
				}
				ctx.save();
				ctx.translate(panel.x, 0);
				if (panel.kind === 'search') drawSearch(ctx, sprites, pledit, uiState.search, panel.y);
				else if (panel.kind === 'eq') drawEqualizer(ctx, sprites, uiState.eq, panel.y);
				else drawPlaylist(ctx, sprites, pledit, playback.queue, uiState.pl, panel.y);
				ctx.restore();
			}
			placeSearchInput(searchPanel ?? null);
		});

		return () => {
			stopLoop();
			clearInterval(audioTimer);
			unlistenViz.then((f) => f());
			unlistenDock.then((f) => f());
			unlistenToggle.then((f) => f());
			unlistenAdd.then((f) => f());
			unlistenMarquee.then((f) => f());
			unlistenClosed.then((f) => f());
			unlistenKey.then((f) => f());
			detachKeys();
		};
	});
</script>

<div class="relative h-screen w-screen overflow-hidden bg-transparent">
	<canvas bind:this={canvas} class="block"></canvas>
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
	{#if status}
		<div class="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/60 text-[10px] text-white">
			{status}
		</div>
	{/if}
</div>
