<script>
	// The MilkDrop window (label "winamp-milkdrop", see +layout.svelte and winamp.rs): Butterchurn,
	// Webamp's WebGL port of MilkDrop (MIT), playing the butterchurn-presets pack. mpv plays outside
	// the webview, so there's no WebAudio to analyse: Butterchurn gets the waveform viz.rs captures
	// (`winamp-wave`, Linux), or, where there's none, a made-up one while music plays, the way the
	// analyzer falls back to test patterns. In the skin's generic frame (gen.bmp, titled MILKDROP,
	// lit while focused) like the other floating windows; fullscreen drops the frame. Drag to move,
	// the frame's corner to resize, double-click for fullscreen; N / P next / previous preset, F
	// fullscreen, right-click for the rest.
	import { onMount } from 'svelte';
	import { getCurrentWindow } from '@tauri-apps/api/window';
	import { listen } from '@tauri-apps/api/event';
	import { closeWinampPanel, resizeWinampPanel, winampStartDrag } from '$lib/api';
	import { logUi } from '$lib/errlog';
	import { playback } from '$lib/player.svelte';
	import { attachKeys } from '../skin/keys.js';
	import { loadPrefs, pref, savePref } from '../skin/prefs.js';
	import { showMilkdropMenu } from '../skin/menu.js';
	import { thumb } from '$lib/thumb';
	import { decodeAllSprites } from '../skin/render/spritesheet.js';
	import { ART_CLOSE, artFrame, drawFrame, frameInset } from '../skin/render/albumArt.js';
	import { frameMenu, onFrame } from '../skin/frameWindow.js';
	import { isLit, setActivePart } from '../skin/focus.js';
	import { pinOneToOnePixels } from '../skin/pixels.js';
	import { loadSkin } from '../skin/skinApi.js';

	/** Seconds between automatic preset changes by default (0 = never; right-click menu), and the
	 * blend into the next. */
	const AUTO_SECONDS = 20;
	const BLEND_SECONDS = 2.7;
	/** The resize grip, bottom-right: gen.bmp's corner. */
	const GRIP = 20;
	const MIN = { w: 200, h: 150 };

	/** @type {HTMLCanvasElement} the visualization (WebGL) */
	let canvas;
	/** @type {HTMLCanvasElement} the frame around it (2D) */
	let frameCanvas;
	/** @type {Map<string, ImageBitmap>} */
	let sprites = new Map();
	let inset = $state({ top: 20, bottom: 14, left: 11, right: 11 });
	let fullscreen = $state(false);
	let closePressed = false;
	/** The visualization's area, inside the frame (all of it in fullscreen). */
	const area = () =>
		fullscreen
			? { x: 0, y: 0, w: window.innerWidth, h: window.innerHeight }
			: {
					x: inset.left,
					y: inset.top,
					w: Math.max(1, window.innerWidth - inset.left - inset.right),
					h: Math.max(1, window.innerHeight - inset.top - inset.bottom)
				};
	let now = $state(0);
	let presetName = $state('');
	/** The preset browser (L, or the right-click menu): MilkDrop's own way, over the picture. */
	let browsing = $state(false);
	let filter = $state('');
	/** @type {string[]} */
	let allNames = $state([]);
	let highlighted = $state(0);
	/** @type {HTMLInputElement | undefined} */
	let filterInput = $state();
	/** @type {HTMLElement | undefined} */
	let listEl = $state();
	/** The skin's playlist colours, for the browser. @type {import('$lib/api').SkinPayload['pledit']} */
	let pledit = $state({});
	const shown = $derived(
		filter.trim() ? allNames.filter((n) => n.toLowerCase().includes(filter.trim().toLowerCase())) : allNames
	);
	/** Set in onMount: switch to the preset called `name`. @type {(name: string) => void} */
	let pick = () => {};
	let nameShownUntil = $state(0);
	/** On-screen text over the visualization: the preset's name, and the track's title and time.
	 * Each shows for a few seconds when it changes, always, or never (right-click menu).
	 * @typedef {'change' | 'always' | 'never'} OsdMode */
	let presetOsd = $state(/** @type {OsdMode} */ ('change'));
	let trackOsd = $state(/** @type {OsdMode} */ ('change'));
	let trackShownUntil = $state(0);
	/** The album art over the visualization, translucent (right-click menu; remembered). */
	let artOverlay = $state(false);
	const OSD_MS = 5000;
	/** "4:00" from seconds. @param {number} secs */
	const clock = (secs) => {
		const s = Math.max(0, Math.floor(secs || 0));
		return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
	};
	const showPreset = $derived(presetOsd === 'always' || (presetOsd === 'change' && now < nameShownUntil));
	const showTrack = $derived(
		!!playback.now && (trackOsd === 'always' || (trackOsd === 'change' && now < trackShownUntil))
	);
	let error = $state('');

	onMount(() => {
		const win = getCurrentWindow();
		/** @type {any} */
		let viz = null;
		/** @type {Record<string, unknown>} */
		let presets = {};
		/** @type {string[]} */
		let names = [];
		/** @type {number[]} */
		const history = [];
		let at = -1;
		let autoSeconds = AUTO_SECONDS;
		let nextAuto = 0;
		let raf = 0;
		let shownTrack = /** @type {string | null} */ (null);

		const wave = new Uint8Array(1024).fill(128);
		let waveAt = -Infinity;
		const unlistenWave = listen('winamp-wave', (e) => {
			wave.set(/** @type {number[]} */ (e.payload));
			waveAt = performance.now();
		});

		/** A made-up waveform for when nothing real comes: tones that drift, on a half-second beat. */
		function synthWave(/** @type {number} */ t) {
			if (!playback.now || playback.paused) return wave.fill(128);
			const beat = Math.exp(-((t % 0.5) * 6));
			const f1 = 0.02 + 0.01 * Math.sin(t * 0.3);
			const f2 = 0.11 + 0.05 * Math.sin(t * 0.17);
			for (let i = 0; i < wave.length; i++) {
				const v = 70 * beat * Math.sin(i * f1 + t * 4) + 30 * Math.sin(i * f2 - t * 7) + 12 * (Math.random() - 0.5);
				wave[i] = Math.max(0, Math.min(255, 128 + v));
			}
		}

		/** @param {number} index @param {number} blend seconds */
		function load(index, blend) {
			if (!viz || !names.length) return;
			index = ((index % names.length) + names.length) % names.length;
			viz.loadPreset(presets[names[index]], blend);
			presetName = names[index];
			nameShownUntil = performance.now() + OSD_MS;
			nextAuto = performance.now() + autoSeconds * 1000;
		}
		const random = () => Math.floor(Math.random() * names.length);
		const controls = {
			next(blend = BLEND_SECONDS) {
				if (at < history.length - 1) at++;
				else {
					history.push(random());
					at = history.length - 1;
				}
				load(history[at], blend);
			},
			previous() {
				if (at > 0) load(history[--at], 0);
			},
			hardCut: () => controls.next(0),
			/** @param {number} seconds 0 for never */
			setAutoSeconds(seconds) {
				autoSeconds = seconds;
				savePref('milkdropAutoSeconds', seconds);
				nextAuto = performance.now() + seconds * 1000;
			},
			get autoSeconds() {
				return autoSeconds;
			},
			get preset() {
				return presetName;
			},
			browse() {
				browsing = !browsing;
				if (!browsing) return;
				filter = '';
				highlighted = Math.max(0, names.indexOf(presetName));
				requestAnimationFrame(() => {
					filterInput?.focus();
					listEl?.querySelector('[data-current]')?.scrollIntoView({ block: 'center' });
				});
			},
			get presetOsd() {
				return presetOsd;
			},
			get artOverlay() {
				return artOverlay;
			},
			toggleArtOverlay() {
				artOverlay = !artOverlay;
				savePref('milkdropArtOverlay', artOverlay);
			},
			get trackOsd() {
				return trackOsd;
			},
			/** @param {OsdMode} mode */
			setPresetOsd(mode) {
				presetOsd = mode;
				savePref('milkdropPresetOsd', mode);
				if (mode === 'change') nameShownUntil = performance.now() + OSD_MS;
			},
			/** @param {OsdMode} mode */
			setTrackOsd(mode) {
				trackOsd = mode;
				savePref('milkdropTrackOsd', mode);
				if (mode === 'change') trackShownUntil = performance.now() + OSD_MS;
			},
			async toggleFullscreen() {
				// Our own state, flipped per press: asking the window right after a change can still
				// answer the old one while the compositor applies it, and a quick second press would
				// then undo the first. A resize puts it right (onResized below). This window is the
				// one resizable panel (winamp.rs), which GTK needs for fullscreen to fill the screen.
				fullscreen = !fullscreen;
				await win.setFullscreen(fullscreen);
				fit();
			},
			close: () => closeWinampPanel('milkdrop').catch((e) => console.error('close failed', e))
		};

		function fit() {
			const a = area();
			canvas.style.left = `${a.x}px`;
			canvas.style.top = `${a.y}px`;
			canvas.style.width = `${a.w}px`;
			canvas.style.height = `${a.h}px`;
			const dpr = window.devicePixelRatio || 1;
			const w = Math.max(1, Math.round(a.w * dpr));
			const h = Math.max(1, Math.round(a.h * dpr));
			if (canvas.width !== w || canvas.height !== h) {
				canvas.width = w;
				canvas.height = h;
				viz?.setRendererSize(w, h);
			}
		}

		/** What the frame was last drawn for: it's redrawn only when that changes. */
		let frameDrawn = /** @type {unknown[]} */ ([]);
		function drawFrameNow() {
			const ctx = frameCanvas.getContext('2d');
			if (!ctx) return;
			const w = window.innerWidth;
			const h = window.innerHeight;
			const drawing = [w, h, fullscreen, sprites, closePressed, isLit('milkdrop')];
			if (drawing.every((v, i) => v === frameDrawn[i])) return;
			frameDrawn = drawing;
			if (frameCanvas.width !== w || frameCanvas.height !== h) {
				frameCanvas.width = w;
				frameCanvas.height = h;
			}
			ctx.clearRect(0, 0, w, h);
			if (fullscreen || sprites.size === 0) return;
			drawFrame(ctx, sprites, { x: 0, y: 0, w, h }, closePressed, 'milkdrop', isLit('milkdrop'));
		}

		pick = (name) => {
			const index = names.indexOf(name);
			if (index < 0) return;
			history.splice(at + 1);
			history.push(index);
			at = history.length - 1;
			load(index, BLEND_SECONDS);
		};

		function frame() {
			raf = requestAnimationFrame(frame);
			const t = performance.now();
			now = t;
			drawFrameNow();
			// A new track (or the window just opened): its title and time, for a few seconds.
			const id = playback.now?.videoId ?? '';
			if (id !== shownTrack) {
				shownTrack = id;
				trackShownUntil = t + OSD_MS;
			}
			if (!viz) return;
			if (t - waveAt > 500) synthWave(t / 1000);
			if (autoSeconds > 0 && t > nextAuto) controls.next();
			try {
				viz.render({ audioLevels: { timeByteArray: wave, timeByteArrayL: wave, timeByteArrayR: wave } });
				failures = 0;
			} catch (e) {
				// A broken preset shouldn't stop the window: move on to another. Every preset failing
				// is something else (the GPU, the driver): stop rather than log it 60 times a second.
				if (++failures >= MAX_FAILURES) {
					viz = null;
					error = `MilkDrop stopped: ${MAX_FAILURES} presets in a row failed (${e})`;
					logUi('error', error);
					return;
				}
				logUi('warn', `milkdrop preset ${presetName} failed: ${e}`);
				controls.next(0);
			}
		}

		/** Presets failed in a row; and how many before giving up. */
		let failures = 0;
		const MAX_FAILURES = 10;

		// A GPU reset or a suspend can take the WebGL context away: start over once it's back,
		// instead of a black window for the rest of the session.
		const onContextLost = (/** @type {Event} */ e) => {
			e.preventDefault();
			viz = null;
		};
		const onContextRestored = () => {
			logUi('info', 'milkdrop: WebGL context restored, starting again');
			failures = 0;
			error = '';
			start();
		};
		canvas.addEventListener('webglcontextlost', onContextLost);
		canvas.addEventListener('webglcontextrestored', onContextRestored);

		const start = async () => {
			try {
				// Old webpack UMD bundles: where the export lands after CommonJS interop varies.
				const unwrap = (/** @type {any} */ m, /** @type {string} */ key) =>
					[m, m?.default, m?.default?.default].find((x) => x && typeof x[key] === 'function');
				const [bcModule, presetsModule] = await Promise.all([import('butterchurn'), import('butterchurn-presets')]);
				const butterchurn = unwrap(bcModule, 'createVisualizer');
				const pack = unwrap(presetsModule, 'getPresets');
				if (!butterchurn || !pack) throw new Error('unexpected butterchurn module shape');
				presets = pack.getPresets();
				names = Object.keys(presets);
				allNames = names;
				const dpr = window.devicePixelRatio || 1;
				const a = area();
				// No AudioContext: render() is handed the waveform (see above).
				viz = butterchurn.createVisualizer(null, canvas, {
					width: Math.round(a.w * dpr),
					height: Math.round(a.h * dpr),
					// The sizes here and in fit() are device pixels already: Butterchurn multiplies
					// by its pixelRatio, so anything but 1 renders dpr² of what the screen shows.
					pixelRatio: 1
				});
				fit();
				controls.next(0);
			} catch (e) {
				error = `MilkDrop couldn't start: ${e}`;
				logUi('error', error);
			}
		};
		start();
		raf = requestAnimationFrame(frame);
		window.addEventListener('resize', fit);

		setActivePart('milkdrop');
		pinOneToOnePixels().catch((e) => logUi('error', `milkdrop zoom pin failed: ${e}`));
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
					fit();
				})
				.catch((e) => logUi('error', `milkdrop skin failed: ${e}`));
		};
		reload();
		const unlistenSkin = listen('winamp-skin-changed', reload);

		// Window keys (Z X C V B and the rest) go to the Winamp window as everywhere; these are ours.
		const detachKeys = attachKeys();
		const onKey = (/** @type {KeyboardEvent} */ e) => {
			// The browser's filter box has its own keys (browserKey); anywhere else, Esc closes it.
			if (browsing) {
				if (e.key === 'Escape') {
					e.preventDefault();
					browsing = false;
				}
				return;
			}
			if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) return;
			const key = e.key.toLowerCase();
			if (key === 'l') controls.browse();
			else if (key === 'n') controls.next();
			else if (key === 'p') controls.previous();
			else if (key === 'f') controls.toggleFullscreen();
			else if (key === 'escape' && fullscreen) controls.toggleFullscreen();
			else return;
			e.preventDefault();
		};
		window.addEventListener('keydown', onKey);

		/** @type {{ x: number, y: number, w: number, h: number } | null} */
		let resizing = null;
		/** A press on the picture: a window drag once the pointer moves. */
		let press = /** @type {{ x: number, y: number } | null} */ (null);
		// The real state, once the window has actually changed size (see toggleFullscreen).
		const unlistenResized = win.onResized(async () => {
			const real = await win.isFullscreen();
			if (real !== fullscreen) {
				fullscreen = real;
				fit();
			}
		});
		const onClose = (/** @type {MouseEvent} */ e) => {
			const x = window.innerWidth + ART_CLOSE.dx;
			return !fullscreen && e.clientX >= x && e.clientX < x + ART_CLOSE.w && e.clientY >= ART_CLOSE.y && e.clientY < ART_CLOSE.y + ART_CLOSE.h;
		};
		const onCorner = (/** @type {MouseEvent} */ e) =>
			!fullscreen && e.clientX > window.innerWidth - GRIP && e.clientY > window.innerHeight - GRIP;
		const onDown = (/** @type {MouseEvent} */ e) => {
			if (e.button !== 0) return;
			// Clicks in the browser are its own.
			if (e.target instanceof Element && e.target.closest('.browser')) return;
			if (onClose(e)) {
				closePressed = true;
				return;
			}
			if (e.detail >= 2) {
				press = null;
				return void controls.toggleFullscreen();
			}
			if (onCorner(e)) resizing = { x: e.screenX, y: e.screenY, w: window.innerWidth, h: window.innerHeight };
			// A drag only once the pointer moves: started on the press, the compositor's window move
			// would swallow a double-click's second click, and with it the fullscreen request.
			else if (!fullscreen) press = { x: e.screenX, y: e.screenY };
		};
		/** The size the next frame sends, so a drag is one resize per frame, not per mouse move. */
		let pendingSize = /** @type {{ w: number, h: number } | null} */ (null);
		const onMove = (/** @type {MouseEvent} */ e) => {
			// Released outside the window (the drag outran it): no mouseup comes, so end it here.
			if (resizing && !(e.buttons & 1)) return onUp(e);
			// No drag from a press whose release never came (see frameWindow.js): it never ends on macOS.
			if (press && !(e.buttons & 1)) press = null;
			if (press && Math.hypot(e.screenX - press.x, e.screenY - press.y) > 3) {
				press = null;
				winampStartDrag().catch(() => {});
			}
			document.body.style.cursor = resizing || onCorner(e) ? 'nwse-resize' : '';
			if (!resizing) return;
			const w = Math.max(MIN.w, resizing.w + e.screenX - resizing.x);
			const h = Math.max(MIN.h, resizing.h + e.screenY - resizing.y);
			const sendNow = pendingSize === null;
			pendingSize = { w, h };
			if (sendNow) {
				requestAnimationFrame(() => {
					const next = pendingSize;
					pendingSize = null;
					if (next) resizeWinampPanel('milkdrop', next.w, next.h).catch(() => {});
				});
			}
		};
		const onUp = (/** @type {MouseEvent} */ e) => {
			press = null;
			if (closePressed) {
				closePressed = false;
				if (onClose(e)) controls.close();
				return;
			}
			if (!resizing) return;
			resizing = null;
			savePref('milkdropSize', { w: window.innerWidth, h: window.innerHeight });
		};
		const onMenu = (/** @type {MouseEvent} */ e) => {
			// The frame's is the player's main menu; the picture's is MilkDrop's.
			if (!fullscreen && onFrame(e.clientX, e.clientY, window.innerWidth, window.innerHeight, inset)) return frameMenu(e);
			e.preventDefault();
			showMilkdropMenu(controls, { x: e.clientX, y: e.clientY }).catch((err) => console.error('menu failed', err));
		};
		loadPrefs().then(() => {
			presetOsd = pref('milkdropPresetOsd', 'change');
			trackOsd = pref('milkdropTrackOsd', 'change');
			autoSeconds = pref('milkdropAutoSeconds', AUTO_SECONDS);
			artOverlay = pref('milkdropArtOverlay', false);
			nextAuto = performance.now() + autoSeconds * 1000;
		});
		window.addEventListener('mousedown', onDown);
		window.addEventListener('mousemove', onMove);
		window.addEventListener('mouseup', onUp);
		window.addEventListener('contextmenu', onMenu);

		return () => {
			cancelAnimationFrame(raf);
			unlistenWave.then((f) => f());
			unlistenSkin.then((f) => f());
			unlistenResized.then((f) => f());
			window.removeEventListener('mousedown', onDown);
			window.removeEventListener('contextmenu', onMenu);
			detachKeys();
			window.removeEventListener('keydown', onKey);
			window.removeEventListener('resize', fit);
			window.removeEventListener('mousemove', onMove);
			window.removeEventListener('mouseup', onUp);
		};
	});

	/** The browser's keys: ↑↓ move, Enter picks, Esc closes. @param {KeyboardEvent} e */
	function browserKey(e) {
		if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
			e.preventDefault();
			highlighted = Math.max(0, Math.min(shown.length - 1, highlighted + (e.key === 'ArrowDown' ? 1 : -1)));
			listEl?.children[highlighted]?.scrollIntoView({ block: 'nearest' });
		} else if (e.key === 'Enter') {
			e.preventDefault();
			if (shown[highlighted]) pick(shown[highlighted]);
		} else if (e.key === 'Escape') {
			e.preventDefault();
			browsing = false;
		}
		// Typing in the box isn't a Winamp shortcut.
		e.stopPropagation();
	}
</script>

<div class="milkdrop">
	<canvas class="frame" bind:this={frameCanvas}></canvas>
	<canvas class="viz" bind:this={canvas}></canvas>
	{#if artOverlay && playback.now?.thumbnail}
		{@const a = fullscreen ? { l: 0, t: 0, r: 0, b: 0 } : { l: inset.left, t: inset.top, r: inset.right, b: inset.bottom }}
		<!-- A box over the picture (the whole screen in fullscreen) for the cover to fit inside: an
		     <img> given all four sides keeps its own size instead of stretching between them. -->
		<div class="art-overlay" style:left="{a.l}px" style:top="{a.t}px" style:right="{a.r}px" style:bottom="{a.b}px">
			<img src={thumb(playback.now.thumbnail, 1200) ?? playback.now.thumbnail} alt="" />
		</div>
	{/if}
	{#if browsing}
		{@const a = fullscreen ? { l: 0, t: 0, r: 0, b: 0 } : { l: inset.left, t: inset.top, r: inset.right, b: inset.bottom }}
		<div
			class="browser"
			style:left="{a.l + 8}px"
			style:top="{a.t + 8}px"
			style:right="{a.r + 8}px"
			style:bottom="{a.b + 8}px"
			style:background={pledit.normalBg ?? '#000000'}
			style:color={pledit.normal ?? '#00ff00'}
			style:border-color={pledit.normal ?? '#00ff00'}
			style:font-family={pledit.font ? `"${pledit.font}", Arial, sans-serif` : 'Arial, sans-serif'}
		>
			<input
				bind:this={filterInput}
				bind:value={filter}
				oninput={() => (highlighted = 0)}
				onkeydown={browserKey}
				placeholder="Filter {allNames.length} presets..."
				spellcheck="false"
				autocomplete="off"
				style:color={pledit.current ?? '#ffffff'}
				style:border-color={pledit.normal ?? '#00ff00'}
			/>
			<ul bind:this={listEl} role="listbox" aria-label="Presets">
				{#each shown as name, i (name)}
					<li
						role="option"
						aria-selected={i === highlighted}
						data-current={name === presetName ? '' : undefined}
						style:background={i === highlighted ? (pledit.selectedBg ?? '#0000ff') : undefined}
						style:color={name === presetName ? (pledit.current ?? '#ffffff') : undefined}
						onmousedown={() => ((highlighted = i), pick(name))}
						ondblclick={() => (browsing = false)}
					>
						{name}
					</li>
				{/each}
			</ul>
		</div>
	{/if}
	{#if showTrack && playback.now}
		<div
			class="note"
			style:left="{(fullscreen ? 0 : inset.left) + 6}px"
			style:top="{(fullscreen ? 0 : inset.top) + 4}px"
		>
			<p>{playback.now.artists ? `${playback.now.artists} - ` : ''}{playback.now.title}</p>
			<p>
				{clock(playback.position)} / {playback.duration > 0 ? clock(playback.duration) : (playback.now.duration ?? '?')}
			</p>
		</div>
	{/if}
	{#if error || (presetName && showPreset)}
		<p
			class="note"
			style:left="{(fullscreen ? 0 : inset.left) + 6}px"
			style:bottom="{(fullscreen ? 0 : inset.bottom) + 4}px"
		>
			{error || presetName}
		</p>
	{/if}
</div>

<style>
	.milkdrop {
		position: fixed;
		inset: 0;
		background: transparent;
		overflow: hidden;
		cursor: default;
	}
	.frame {
		position: absolute;
		inset: 0;
		display: block;
	}
	.viz {
		position: absolute;
		display: block;
		background: #000;
	}
	.browser {
		position: absolute;
		display: flex;
		flex-direction: column;
		border: 1px solid;
		font-size: 11px;
		opacity: 0.92;
	}
	.browser input {
		margin: 4px;
		padding: 1px 3px;
		border: 1px solid;
		background: transparent;
		font: inherit;
		outline: none;
	}
	.browser ul {
		margin: 0;
		padding: 0 0 4px;
		list-style: none;
		overflow-y: auto;
		flex: 1;
	}
	.browser li {
		padding: 1px 6px;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		cursor: default;
	}
	/* Fitted inside the picture, whole, aspect kept, translucent; clicks go through to the window. */
	.art-overlay {
		position: absolute;
		opacity: 0.35;
		pointer-events: none;
	}
	.art-overlay img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: contain;
		object-position: center;
	}
	.note p {
		margin: 0;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.note {
		position: absolute;
		margin: 0;
		max-width: calc(100% - 32px);
		font: 11px Arial, sans-serif;
		color: #fff;
		text-shadow: 1px 1px 0 #000;
		pointer-events: none;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
</style>
