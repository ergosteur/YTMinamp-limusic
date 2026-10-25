<script>
	// A menu's Add to new playlist... dialog, a small window of its own (label "winamp-newpl", see
	// +layout.svelte and winamp.rs) in the skin's generic frame, built like Save preset: type a
	// name, pick where it goes (the YouTube Music account or this computer, the choice Limusic's New
	// playlist dialog remembers too), Enter or OK makes the playlist with the songs in it, Esc or ✕
	// closes it. The window whose menu asked does the work (skin/newPlaylist.js).
	import { onMount } from 'svelte';
	import { emit, listen } from '@tauri-apps/api/event';
	import { closeWinampPanel, getAccount, resizeWinampPanel } from '$lib/api';
	import { logUi } from '$lib/errlog';
	import { decodeAllSprites } from '../skin/render/spritesheet.js';
	import { artFrame, onCloseButton, drawFrame, frameInset } from '../skin/render/albumArt.js';
	import { doubleFactor, followDoubleSize, pinOneToOnePixels } from '../skin/pixels.js';
	import { loadSkin } from '../skin/skinApi.js';
	import { frameMouse } from '../skin/frameWindow.js';
	import { isLit, setActivePart } from '../skin/focus.js';
	import { NEWPL_DONE, NEWPL_NAME, NEWPL_TAKEN } from '../skin/newPlaylist.js';

	const WIDTH = 275;
	/** The text box and OK beside it, where it goes under them, and the status: up to two lines,
	 * wrapped. */
	const BOX_H = 17;
	const OK_W = 30;
	const STATUS_LINE = 13;
	const WHERE_Y = BOX_H + 6;
	const STATUS_Y = WHERE_Y + STATUS_LINE + 3;
	const BODY_H = STATUS_Y + 2 * STATUS_LINE + 2;
	/** NewPlaylistDialog.svelte's remembered pick, shared with it. */
	const WHERE_KEY = 'new_playlist_where';

	/** @type {HTMLCanvasElement} */
	let canvas;
	/** @type {HTMLInputElement} */
	let input;
	/** @type {Map<string, ImageBitmap>} */
	let sprites = new Map();
	/** @type {import('$lib/api').SkinPayload['pledit']} */
	let pledit = $state({});
	let inset = $state({ top: 20, bottom: 14, left: 11, right: 11 });
	const PROMPT = 'Name the new playlist, then press Enter';
	let status = $state(PROMPT);
	let local = $state(storedLocal());
	/** Signed out, only this computer will do. */
	let signedIn = $state(true);

	function storedLocal() {
		try {
			return localStorage.getItem(WHERE_KEY) === 'device';
		} catch {
			return false;
		}
	}

	/** @param {boolean} on */
	function pickLocal(on) {
		if (busy) return;
		local = on;
		try {
			localStorage.setItem(WHERE_KEY, on ? 'device' : 'account');
		} catch {
			/* a blocked store just means the choice isn't remembered */
		}
		input?.focus();
	}
	let busy = $state(false);
	let closePressed = false;

	const close = () => closeWinampPanel('newpl').catch((e) => console.error('close failed', e));

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
		drawFrame(ctx, sprites, { x: 0, y: 0, w, h }, closePressed, 'new playlist', isLit('newpl'));
	}

	/** @type {ReturnType<typeof setTimeout> | undefined} */
	let unanswered;

	function submit() {
		const name = input.value.trim();
		if (busy || !name) return;
		busy = true;
		status = 'Making the playlist...';
		emit(NEWPL_NAME, { name, local: local || !signedIn }).catch(() => {});
		// The window that asked takes it at once; one that has since closed never will.
		unanswered = setTimeout(() => {
			busy = false;
			status = 'Nothing is waiting for it any more: pick Add to new playlist... again';
		}, 2000);
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
		setActivePart('newpl');
		// The titlebar lights with focus, and this only draws when something changes.
		window.addEventListener('focus', draw);
		window.addEventListener('blur', draw);
		// The DPI fix, then double size on top, following the Winamp window's.
		const unlistenDouble = followDoubleSize(
			pinOneToOnePixels().catch((e) => logUi('error', `new playlist dialog zoom pin failed: ${e}`)),
			'newpl'
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
					resizeWinampPanel('newpl', WIDTH * doubleFactor(), (inset.top + BODY_H + inset.bottom) * doubleFactor()).catch(() => {});
				})
				.catch((e) => logUi('error', `new playlist dialog skin failed: ${e}`));
		};
		reload();
		const unlistenSkin = listen('winamp-skin-changed', reload);
		requestAnimationFrame(() => input?.focus());
		getAccount()
			.then((a) => (signedIn = a.signedIn))
			.catch(() => {});
		const unlistenTaken = listen(NEWPL_TAKEN, () => clearTimeout(unanswered));
		const unlistenDone = listen(NEWPL_DONE, (e) => {
			clearTimeout(unanswered);
			if (e.payload === null) return close();
			status = /** @type {string} */ (e.payload);
			busy = false;
		});
		// Opened again for other songs while still up: a fresh start.
		const fresh = () => {
			if (busy) return;
			status = PROMPT;
			local = storedLocal();
			input?.focus();
		};
		window.addEventListener('focus', fresh);

		const stopFrameMouse = frameMouse(canvas, {
			onClose: (e) => onCloseButton(e, WIDTH),
			inset: () => inset,
			pressed: (down) => {
				closePressed = down;
				draw();
			},
			close
		});

		return () => {
			unlistenDouble.then((f) => f());
			window.removeEventListener('focus', draw);
			window.removeEventListener('blur', draw);
			unlistenSkin.then((f) => f());
			unlistenTaken.then((f) => f());
			unlistenDone.then((f) => f());
			window.removeEventListener('focus', fresh);
			clearTimeout(unanswered);
			stopFrameMouse();
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
		placeholder="My playlist"
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
		class="absolute flex gap-3 text-[11px] whitespace-nowrap"
		style:left="{inset.left + 4}px"
		style:top="{inset.top + WHERE_Y}px"
		style:line-height="{STATUS_LINE}px"
		style:color={pledit.normal ?? '#00ff00'}
		style:font-family={font}
	>
		<span>Save on:</span>
		{@render choice(false, 'YouTube Music', !signedIn)}
		{@render choice(true, 'This computer', false)}
	</div>
	<div
		class="pointer-events-none absolute overflow-hidden text-[11px]"
		style:left="{inset.left + 4}px"
		style:top="{inset.top + STATUS_Y}px"
		style:width="{WIDTH - inset.left - inset.right - 8}px"
		style:line-height="{STATUS_LINE}px"
		style:max-height="{2 * STATUS_LINE}px"
		style:color={pledit.normal ?? '#00ff00'}
		style:font-family={font}
	>
		{status}
	</div>
</div>

{#snippet choice(/** @type {boolean} */ on, /** @type {string} */ label, /** @type {boolean} */ off)}
	{@const picked = (local || !signedIn) === on}
	<button
		class="m-0 cursor-pointer border-0 bg-transparent p-0 disabled:cursor-default disabled:opacity-50"
		style:color={picked ? (pledit.current ?? '#ffffff') : (pledit.normal ?? '#00ff00')}
		type="button"
		disabled={busy || off}
		onclick={() => pickLocal(on)}>{picked ? '\u25cf' : '\u25cb'} {label}</button
	>
{/snippet}
