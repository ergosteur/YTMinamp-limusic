<script>
	// The MilkDrop window (label "winamp-milkdrop", see +layout.svelte and winamp.rs): Butterchurn,
	// Webamp's WebGL port of MilkDrop (MIT), playing the butterchurn-presets pack. mpv plays outside
	// the webview, so there's no WebAudio to analyse: Butterchurn gets the waveform viz.rs captures
	// (`winamp-wave`, Linux), or, where there's none, a made-up one while music plays, the way the
	// analyzer falls back to test patterns. Drag to move, the corner to resize, double-click for
	// fullscreen; N / P next / previous preset, F fullscreen, right-click for the rest.
	import { onMount } from 'svelte';
	import { getCurrentWindow } from '@tauri-apps/api/window';
	import { listen } from '@tauri-apps/api/event';
	import { closeWinampPanel, resizeWinampPanel } from '$lib/api';
	import { logUi } from '$lib/errlog';
	import { playback } from '$lib/player.svelte';
	import { attachKeys } from '../skin/keys.js';
	import { loadPrefs, pref, savePref } from '../skin/prefs.js';
	import { showMilkdropMenu } from '../skin/menu.js';

	/** Seconds between automatic preset changes, and the blend into the next. */
	const AUTO_SECONDS = 20;
	const BLEND_SECONDS = 2.7;
	/** The resize grip, bottom-right. */
	const GRIP = 16;
	const MIN = { w: 200, h: 150 };

	/** @type {HTMLCanvasElement} */
	let canvas;
	let presetName = $state('');
	let nameShownUntil = $state(0);
	let now = $state(0);
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
		let auto = true;
		let nextAuto = 0;
		let raf = 0;

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
			nameShownUntil = performance.now() + 4000;
			nextAuto = performance.now() + AUTO_SECONDS * 1000;
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
			toggleAuto() {
				auto = !auto;
				nextAuto = performance.now() + AUTO_SECONDS * 1000;
			},
			get auto() {
				return auto;
			},
			get preset() {
				return presetName;
			},
			async toggleFullscreen() {
				await win.setFullscreen(!(await win.isFullscreen()));
			},
			close: () => closeWinampPanel('milkdrop').catch((e) => console.error('close failed', e))
		};

		function fit() {
			const dpr = window.devicePixelRatio || 1;
			const w = Math.max(1, Math.round(window.innerWidth * dpr));
			const h = Math.max(1, Math.round(window.innerHeight * dpr));
			canvas.width = w;
			canvas.height = h;
			viz?.setRendererSize(w, h);
		}

		function frame() {
			raf = requestAnimationFrame(frame);
			const t = performance.now();
			now = t;
			if (!viz) return;
			if (t - waveAt > 500) synthWave(t / 1000);
			if (auto && t > nextAuto) controls.next();
			try {
				viz.render({ audioLevels: { timeByteArray: wave, timeByteArrayL: wave, timeByteArrayR: wave } });
			} catch (e) {
				// A broken preset shouldn't stop the window: move on to another.
				logUi('warn', `milkdrop preset ${presetName} failed: ${e}`);
				controls.next(0);
			}
		}

		(async () => {
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
				const dpr = window.devicePixelRatio || 1;
				// No AudioContext: render() is handed the waveform (see above).
				viz = butterchurn.createVisualizer(null, canvas, {
					width: Math.round(window.innerWidth * dpr),
					height: Math.round(window.innerHeight * dpr),
					pixelRatio: dpr
				});
				fit();
				controls.next(0);
			} catch (e) {
				error = `MilkDrop couldn't start: ${e}`;
				logUi('error', error);
			}
		})();
		raf = requestAnimationFrame(frame);
		window.addEventListener('resize', fit);

		// Window keys (Z X C V B and the rest) go to the Winamp window as everywhere; these are ours.
		const detachKeys = attachKeys();
		const onKey = (/** @type {KeyboardEvent} */ e) => {
			if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) return;
			const key = e.key.toLowerCase();
			if (key === 'n') controls.next();
			else if (key === 'p') controls.previous();
			else if (key === 'f') controls.toggleFullscreen();
			else if (key === 'escape') win.setFullscreen(false);
			else return;
			e.preventDefault();
		};
		window.addEventListener('keydown', onKey);

		/** @type {{ x: number, y: number, w: number, h: number } | null} */
		let resizing = null;
		const onDown = (/** @type {MouseEvent} */ e) => {
			if (e.button !== 0) return;
			if (e.detail >= 2) return void controls.toggleFullscreen();
			const corner = e.clientX > window.innerWidth - GRIP && e.clientY > window.innerHeight - GRIP;
			if (corner) resizing = { x: e.screenX, y: e.screenY, w: window.innerWidth, h: window.innerHeight };
			else win.startDragging();
		};
		const onMove = (/** @type {MouseEvent} */ e) => {
			if (!resizing) return;
			const w = Math.max(MIN.w, resizing.w + e.screenX - resizing.x);
			const h = Math.max(MIN.h, resizing.h + e.screenY - resizing.y);
			resizeWinampPanel('milkdrop', w, h).catch(() => {});
		};
		const onUp = () => {
			if (!resizing) return;
			resizing = null;
			savePref('milkdropSize', { w: window.innerWidth, h: window.innerHeight });
		};
		const onMenu = (/** @type {MouseEvent} */ e) => {
			e.preventDefault();
			showMilkdropMenu(controls, { x: e.clientX, y: e.clientY }).catch((err) => console.error('menu failed', err));
		};
		loadPrefs();
		canvas.addEventListener('mousedown', onDown);
		window.addEventListener('mousemove', onMove);
		window.addEventListener('mouseup', onUp);
		canvas.addEventListener('contextmenu', onMenu);

		return () => {
			cancelAnimationFrame(raf);
			unlistenWave.then((f) => f());
			detachKeys();
			window.removeEventListener('keydown', onKey);
			window.removeEventListener('resize', fit);
			window.removeEventListener('mousemove', onMove);
			window.removeEventListener('mouseup', onUp);
		};
	});
</script>

<div class="milkdrop">
	<canvas bind:this={canvas}></canvas>
	{#if error}
		<p class="note">{error}</p>
	{:else if presetName && now < nameShownUntil}
		<p class="note">{presetName}</p>
	{/if}
	<div class="grip" title="Drag to resize"></div>
</div>

<style>
	.milkdrop {
		position: fixed;
		inset: 0;
		background: #000;
		overflow: hidden;
		cursor: default;
	}
	canvas {
		display: block;
		width: 100%;
		height: 100%;
	}
	.note {
		position: absolute;
		left: 8px;
		bottom: 6px;
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
	.grip {
		position: absolute;
		right: 0;
		bottom: 0;
		width: 16px;
		height: 16px;
		cursor: nwse-resize;
		pointer-events: none;
		background: linear-gradient(135deg, transparent 50%, rgba(255, 255, 255, 0.35) 50%);
	}
</style>
