<script>
	// The EQ's PRESETS → Save current as preset... dialog, a small window of its own (label
	// "winamp-eqsave", see +layout.svelte and winamp.rs) in the skin's generic frame, built like the
	// Open URL one: type a name, Enter or OK saves the EQ as it is now under it (replacing a preset
	// of the same name), Esc or ✕ closes it. Presets live in winamp.json's `eqPresets`.
	import { onMount } from 'svelte';
	import { getCurrentWindow } from '@tauri-apps/api/window';
	import { emitTo, listen } from '@tauri-apps/api/event';
	import { closeWinampPanel, resizeWinampPanel } from '$lib/api';
	import { logUi } from '$lib/errlog';
	import { decodeAllSprites } from '../skin/render/spritesheet.js';
	import { artFrame, onCloseButton, drawFrame, frameInset } from '../skin/render/albumArt.js';
	import { doubleFactor, followDoubleSize, pinOneToOnePixels } from '../skin/pixels.js';
	import { loadSkin } from '../skin/skinApi.js';
	import { isLit, setActivePart } from '../skin/focus.js';
	import { flushPrefs, loadPrefs, pref, savePref } from '../skin/prefs.js';

	const WIDTH = 275;
	/** The text box and OK beside it, and the status under them: up to two lines, wrapped. */
	const BOX_H = 17;
	const OK_W = 30;
	const STATUS_LINE = 13;
	const BODY_H = BOX_H + 8 + 2 * STATUS_LINE;

	/** @type {HTMLCanvasElement} */
	let canvas;
	/** @type {HTMLInputElement} */
	let input;
	/** @type {Map<string, ImageBitmap>} */
	let sprites = new Map();
	/** @type {import('$lib/api').SkinPayload['pledit']} */
	let pledit = $state({});
	let inset = $state({ top: 20, bottom: 14, left: 11, right: 11 });
	let status = $state('Name this preset, then press Enter');
	let busy = $state(false);
	let closePressed = false;

	const close = () => closeWinampPanel('eqsave').catch((e) => console.error('close failed', e));

	function draw() {
		const ctx = canvas.getContext('2d');
		if (!ctx || sprites.size === 0) return;
		const w = WIDTH;
		const h = inset.top + BODY_H + inset.bottom;
		canvas.width = w;
		canvas.height = h;
		canvas.style.width = `${w}px`;
		canvas.style.height = `${h}px`;
		ctx.fillStyle = pledit.normalBg ?? '#000000';
		ctx.fillRect(0, 0, w, h);
		drawFrame(ctx, sprites, { x: 0, y: 0, w, h }, closePressed, 'save preset', isLit('eqsave'));
	}

	async function submit() {
		const name = input.value.trim();
		if (busy || !name) return;
		busy = true;
		try {
			// Fresh from disk: another window may have saved presets since this one opened.
			await loadPrefs();
			const eq = pref('eq', { preamp: 50, bands: Array(10).fill(50) });
			/** @type {{ name: string, preamp: number, bands: number[] }[]} */
			const presets = pref('eqPresets', []).filter((/** @type {{ name: string }} */ p) => p.name !== name);
			presets.push({ name, preamp: eq.preamp, bands: [...eq.bands] });
			presets.sort((a, b) => a.name.localeCompare(b.name));
			savePref('eqPresets', presets);
			// This window closes now: write it out instead of waiting for the batch.
			await flushPrefs();
			emitTo('winamp', 'winamp-marquee', `Saved EQ preset: ${name}`).catch(() => {});
			close();
		} catch (e) {
			status = `Couldn't save it: ${e}`;
			busy = false;
		}
	}

	function onKey(/** @type {KeyboardEvent} */ e) {
		if (e.key === 'Enter') {
			e.preventDefault();
			submit();
		} else if (e.key === 'Escape') {
			e.preventDefault();
			close();
		}
	}

	onMount(() => {
		setActivePart('eqsave');
		// The titlebar lights with focus, and this only draws when something changes.
		window.addEventListener('focus', draw);
		window.addEventListener('blur', draw);
		// The DPI fix, then double size on top, following the Winamp window's.
		const unlistenDouble = followDoubleSize(
			pinOneToOnePixels().catch((e) => logUi('error', `eq preset dialog zoom pin failed: ${e}`)),
			'eqsave'
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
					// The frame decides the height (gen.bmp's, the playlist's and the EQ's differ).
					resizeWinampPanel('eqsave', WIDTH * doubleFactor(), (inset.top + BODY_H + inset.bottom) * doubleFactor()).catch(() => {});
				})
				.catch((e) => logUi('error', `eq preset dialog skin failed: ${e}`));
		};
		reload();
		const unlistenSkin = listen('winamp-skin-changed', reload);
		requestAnimationFrame(() => input?.focus());

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
		canvas.addEventListener('mousedown', onDown);
		window.addEventListener('mousemove', onMove);
		window.addEventListener('mouseup', onUp);

		return () => {
			unlistenDouble.then((f) => f());
			window.removeEventListener('focus', draw);
			window.removeEventListener('blur', draw);
			unlistenSkin.then((f) => f());
			window.removeEventListener('mousemove', onMove);
			window.removeEventListener('mouseup', onUp);
		};
	});

	const font = $derived(`${pledit.font ? `"${pledit.font}", ` : ''}Arial, sans-serif`);
</script>

<div class="relative h-screen w-screen overflow-hidden bg-transparent">
	<canvas bind:this={canvas} class="block"></canvas>
	<input
		bind:this={input}
		class="absolute m-0 border px-1 py-0 text-[11px] leading-none outline-none"
		style:left="{inset.left + 3}px"
		style:top="{inset.top + 3}px"
		style:width="{WIDTH - inset.left - inset.right - 6 - OK_W - 4}px"
		style:height="{BOX_H}px"
		style:background={pledit.normalBg ?? '#000000'}
		style:color={pledit.normal ?? '#00ff00'}
		style:border-color={pledit.normal ?? '#00ff00'}
		style:caret-color={pledit.current ?? '#ffffff'}
		style:font-family={font}
		type="text"
		placeholder="My preset"
		spellcheck="false"
		autocomplete="off"
		disabled={busy}
		onkeydown={onKey}
	/>
	<button
		class="absolute m-0 border p-0 text-[11px] leading-none disabled:opacity-50"
		style:left="{WIDTH - inset.right - 3 - OK_W}px"
		style:top="{inset.top + 3}px"
		style:width="{OK_W}px"
		style:height="{BOX_H}px"
		style:background={pledit.normalBg ?? '#000000'}
		style:color={pledit.current ?? '#ffffff'}
		style:border-color={pledit.normal ?? '#00ff00'}
		style:font-family={font}
		type="button"
		disabled={busy}
		onclick={submit}>OK</button
	>
	<div
		class="pointer-events-none absolute overflow-hidden text-[11px]"
		style:left="{inset.left + 4}px"
		style:top="{inset.top + BOX_H + 6}px"
		style:width="{WIDTH - inset.left - inset.right - 8}px"
		style:line-height="{STATUS_LINE}px"
		style:max-height="{2 * STATUS_LINE}px"
		style:color={pledit.normal ?? '#00ff00'}
		style:font-family={font}
	>
		{status}
	</div>
</div>
