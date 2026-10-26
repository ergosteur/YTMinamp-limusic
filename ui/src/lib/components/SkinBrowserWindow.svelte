<script>
	// The Skin Browser (label "winamp-skins", see +layout.svelte and winamp.rs; skin/skinBrowser.js):
	// Winamp's Alt+S window, in the skin's generic frame and the playlist's colours like File info.
	// A search box and group chips over the skins folder's list, each row with a thumbnail of its
	// main window, beside a preview of the picked one drawn by the real renderer. Enter, a
	// double-click or Apply switches to it; arrow keys move and the preview follows.
	import { onMount } from 'svelte';
	import { listen } from '@tauri-apps/api/event';
	import { ask, open } from '@tauri-apps/plugin-dialog';
	import * as api from '$lib/api';
	import { logUi } from '$lib/errlog';
	import { decodeAllSprites } from '../skin/render/spritesheet.js';
	import { ART_CLOSE, artFrame, drawFrame, frameInset } from '../skin/render/albumArt.js';
	import { followDoubleSize, pinOneToOnePixels } from '../skin/pixels.js';
	import { loadSkin } from '../skin/skinApi.js';
	import { frameMouse } from '../skin/frameWindow.js';
	import { isLit, setActivePart } from '../skin/focus.js';
	import { PREVIEW, drawPreview, groupOf, groupsOf, loadPreview, requestSkin, thumbnail } from '../skin/skinBrowser.js';

	const BASE = '<Base skin>';

	/** @type {HTMLCanvasElement} */
	let canvas;
	/** @type {HTMLCanvasElement | undefined} */
	let previewCanvas = $state();
	/** @type {HTMLInputElement} */
	let searchBox;
	/** @type {HTMLElement | undefined} */
	let listBox = $state();
	/** @type {Map<string, ImageBitmap>} */
	let sprites = new Map();
	/** @type {import('$lib/api').SkinPayload['pledit']} */
	let pledit = $state({});
	let inset = $state({ top: 20, bottom: 14, left: 11, right: 11 });
	let closePressed = false;
	/** The first listing picks the current skin; later ones keep the pick. */
	let firstList = true;

	/** @type {{ name: string, path: string | null, folder: string }[]} */
	let skins = $state([]);
	let current = $state(/** @type {string | null} */ (null));
	let query = $state('');
	let group = $state(/** @type {string | null} */ (null));
	let picked = $state(/** @type {string | null} */ (null));
	let status = $state('');
	/** The preview area's size, for fitting the 1x preview in it. */
	let previewW = $state(0);
	let previewH = $state(0);

	const close = () => api.closeWinampPanel('skins').catch((e) => console.error('close failed', e));
	const font = $derived(`${pledit.font ? `"${pledit.font}", ` : ''}Arial, sans-serif`);
	const groups = $derived(groupsOf(skins.filter((s) => s.path !== null)));
	/** Every word typed somewhere in the name or its folder, within the group picked. */
	const shown = $derived.by(() => {
		const words = query.toLowerCase().split(/\s+/).filter(Boolean);
		return skins.filter(
			(s) =>
				(!group || (s.path !== null && groupOf(s).toLowerCase() === group.toLowerCase())) &&
				words.every((w) => `${s.folder}/${s.name}`.toLowerCase().includes(w))
		);
	});
	const pickedSkin = $derived(skins.find((s) => s.path === picked) ?? null);
	/** The preview at 1x, or smaller to fit; never bigger (it's pixel art). */
	const previewScale = $derived(Math.min(1, previewW / PREVIEW.w || 1, previewH / PREVIEW.h || 1));

	function draw() {
		const ctx = canvas?.getContext('2d');
		if (!ctx || sprites.size === 0) return;
		const [w, h] = [window.innerWidth, window.innerHeight];
		canvas.width = w;
		canvas.height = h;
		canvas.style.width = `${w}px`;
		canvas.style.height = `${h}px`;
		ctx.fillStyle = pledit.normalBg ?? '#000000';
		ctx.fillRect(0, 0, w, h);
		drawFrame(ctx, sprites, { x: 0, y: 0, w, h }, closePressed, 'skin browser', isLit('skins'));
	}

	async function refresh() {
		const list = await api.listWszSkins();
		skins = [{ name: BASE, path: null, folder: '' }, ...list.skins.map((s) => ({ name: s.name, path: s.path, folder: s.folder }))];
		current = list.current;
		if (firstList) picked = current;
		firstList = false;
	}

	// Only the newest pick lands: arrowing quickly through the list settles on the last.
	let previews = 0;
	$effect(() => {
		const skin = pickedSkin;
		const target = previewCanvas;
		if (!target) return;
		const mine = ++previews;
		status = 'Loading…';
		loadPreview(skin?.path ?? null)
			.then(({ payload, sprites: s }) => {
				if (mine !== previews) return;
				drawPreview(target, s, payload, skin?.name ?? BASE);
				status = '';
			})
			.catch((e) => {
				if (mine === previews) status = `Couldn’t load this skin: ${e}`;
			});
	});

	/** @param {string | null} path */
	function apply(path) {
		status = 'Switching…';
		requestSkin(path).catch((e) => (status = `Couldn’t switch: ${e}`));
	}

	function random() {
		const pool = shown.filter((s) => s.path !== null && s.path !== current);
		if (!pool.length) return;
		const skin = pool[Math.floor(Math.random() * pool.length)];
		picked = skin.path;
		scrollToPicked();
		apply(skin.path);
	}

	/** As the Skins menu's Load skin…: copied into the skins folder, asking before replacing. */
	async function loadFromDisk() {
		const file = await open({ title: 'Load Winamp skin', filters: [{ name: 'Winamp skins', extensions: ['wsz', 'zip'] }] });
		if (typeof file !== 'string') return;
		const fileName = (/** @type {string} */ p) => p.split(/[\\/]/).pop()?.toLowerCase();
		// Only the top of the folder: that's where it's copied to.
		const same = skins.find((s) => s.path && !s.folder && fileName(s.path) === fileName(file) && s.path !== file);
		const replace =
			!!same &&
			(await ask(`A skin named “${same.name}” is already in the skins folder. Replace it?`, {
				title: 'Load Winamp skin',
				kind: 'warning'
			}));
		if (same && !replace) return;
		try {
			const path = await api.importWszSkin(file, replace);
			await refresh();
			picked = path;
			scrollToPicked();
			apply(path);
		} catch (e) {
			status = `Couldn’t load it: ${e}`;
		}
	}

	/** Winamp's buttons under the list and preview. @type {[string, () => unknown][]} */
	const buttons = [
		['Apply', () => pickedSkin && apply(pickedSkin.path)],
		['Random', random],
		['Load skin\u2026', loadFromDisk],
		['Open skins folder', () => api.openSkinsDir().catch((e) => (status = String(e)))]
	];

	function scrollToPicked() {
		requestAnimationFrame(() => listBox?.querySelector('[data-picked="true"]')?.scrollIntoView({ block: 'nearest' }));
	}

	/** @param {number} step */
	function move(step) {
		if (!shown.length) return;
		const at = shown.findIndex((s) => s.path === picked);
		const next = at < 0 ? 0 : Math.max(0, Math.min(shown.length - 1, at + step));
		picked = shown[next].path;
		scrollToPicked();
	}

	/** Search box keys: arrows move the list, Enter applies, Escape clears, then closes. @param {KeyboardEvent} e */
	function onSearchKey(e) {
		if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'PageDown' || e.key === 'PageUp') {
			e.preventDefault();
			move(e.key === 'ArrowDown' ? 1 : e.key === 'ArrowUp' ? -1 : e.key === 'PageDown' ? 10 : -10);
		} else if (e.key === 'Enter') {
			e.preventDefault();
			if (pickedSkin) apply(pickedSkin.path);
		} else if (e.key === 'Escape') {
			e.preventDefault();
			if (query || group) {
				query = '';
				group = null;
			} else close();
		}
	}

	/**
	 * A row's thumbnail, drawn when the row first scrolls into view.
	 * @param {HTMLImageElement} img
	 * @param {string | null} path
	 */
	function thumb(img, path) {
		const seen = new IntersectionObserver((entries) => {
			if (!entries.some((e) => e.isIntersecting)) return;
			seen.disconnect();
			thumbnail(path).then((url) => {
				if (url) img.src = url;
			});
		});
		seen.observe(img);
		return { destroy: () => seen.disconnect() };
	}

	onMount(() => {
		setActivePart('skins');
		refresh()
			.then(scrollToPicked)
			.catch((e) => (status = `Couldn’t read the skins folder: ${e}`));
		window.addEventListener('focus', draw);
		window.addEventListener('blur', draw);
		window.addEventListener('resize', draw);
		const unlistenDouble = followDoubleSize(
			pinOneToOnePixels().catch((e) => logUi('error', `skin browser zoom pin failed: ${e}`)),
			'skins'
		);
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
				})
				.catch((e) => logUi('error', `skin browser skin failed: ${e}`));
		};
		reload();
		// A switch, from here or the menu: this window wears the new skin and ticks it.
		const unlistenSkin = listen('winamp-skin-changed', () => {
			reload();
			refresh().catch(() => {});
			status = '';
		});

		const onClose = (/** @type {MouseEvent} */ e) => {
			const x = window.innerWidth + ART_CLOSE.dx;
			return e.clientX >= x && e.clientX < x + ART_CLOSE.w && e.clientY >= ART_CLOSE.y && e.clientY < ART_CLOSE.y + ART_CLOSE.h;
		};
		const stopFrameMouse = frameMouse(canvas, {
			onClose,
			inset: () => inset,
			pressed: (down) => {
				closePressed = down;
				draw();
			},
			close,
			resizable: 'skins'
		});
		// Typing anywhere goes to the search box; Alt+S closes, as it opened.
		const onKey = (/** @type {KeyboardEvent} */ e) => {
			if (e.altKey && !e.ctrlKey && !e.metaKey && e.key.toLowerCase() === 's') {
				e.preventDefault();
				close();
			} else if (e.target !== searchBox && e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
				searchBox?.focus();
			} else if (e.target !== searchBox && (e.key === 'Escape' || e.key.startsWith('Arrow') || e.key === 'Enter')) {
				onSearchKey(e);
			}
		};
		window.addEventListener('keydown', onKey);
		requestAnimationFrame(() => searchBox?.focus());
		return () => {
			unlistenDouble.then((f) => f());
			unlistenSkin.then((f) => f());
			window.removeEventListener('resize', draw);
			window.removeEventListener('focus', draw);
			window.removeEventListener('blur', draw);
			window.removeEventListener('keydown', onKey);
			stopFrameMouse();
		};
	});
</script>

<div class="relative h-screen w-screen overflow-hidden bg-transparent">
	<canvas bind:this={canvas} class="block"></canvas>
	<div
		class="absolute flex flex-col gap-1.5 text-[11px] leading-[14px]"
		style:left="{inset.left + 5}px"
		style:top="{inset.top + 5}px"
		style:right="{inset.right + 5}px"
		style:bottom="{inset.bottom + 5}px"
		style:color={pledit.normal ?? '#00ff00'}
		style:font-family={font}
	>
		<!-- Search, and the count it leaves. -->
		<div class="flex items-center gap-2">
			<input
				bind:this={searchBox}
				bind:value={query}
				onkeydown={onSearchKey}
				type="text"
				placeholder="Search skins"
				spellcheck="false"
				autocomplete="off"
				class="min-w-0 flex-1 border px-1 py-0 text-[11px] leading-[16px] outline-none"
				style:background={pledit.normalBg ?? '#000000'}
				style:color={pledit.current ?? '#ffffff'}
				style:border-color={pledit.normal ?? '#00ff00'}
				style:font-family={font}
			/>
			<span class="shrink-0 opacity-80">{shown.length} of {skins.length}</span>
		</div>

		<!-- Groups, from the names: one at a time, or all. -->
		{#if groups.length}
			<div class="flex max-h-[38px] flex-wrap gap-1 overflow-y-auto">
				{#each [{ group: null, count: skins.length }, ...groups] as g (g.group ?? '')}
					<button
						type="button"
						class="border px-1 text-[10px] leading-[14px]"
						style:background={group === g.group ? (pledit.selectedBg ?? '#0000c6') : (pledit.normalBg ?? '#000000')}
						style:color={group === g.group ? (pledit.current ?? '#ffffff') : (pledit.normal ?? '#00ff00')}
						style:border-color={pledit.normal ?? '#00ff00'}
						style:font-family={font}
						onclick={() => (group = group === g.group ? null : g.group)}>{g.group ?? 'All'} <span class="opacity-70">{g.count}</span></button
					>
				{/each}
			</div>
		{/if}

		<div class="flex min-h-0 flex-1 gap-2">
			<!-- The list: thumbnail and name, the current skin ticked. -->
			<div
				bind:this={listBox}
				class="min-h-0 w-[230px] shrink-0 overflow-y-auto border"
				style:border-color={pledit.normal ?? '#00ff00'}
				role="listbox"
				aria-label="Skins"
			>
				{#each shown as skin (skin.path ?? '')}
					{@const isPicked = skin.path === picked}
					<button
						type="button"
						role="option"
						aria-selected={isPicked}
						data-picked={isPicked}
						class="flex w-full items-center gap-1.5 px-1 py-0.5 text-left"
						style:background={isPicked ? (pledit.selectedBg ?? '#0000c6') : 'transparent'}
						style:color={skin.path === current ? (pledit.current ?? '#ffffff') : (pledit.normal ?? '#00ff00')}
						style:font-family={font}
						onclick={() => (picked = skin.path)}
						ondblclick={() => apply(skin.path)}
						title={skin.folder ? `${skin.folder}/${skin.name}` : skin.name}
					>
						{#if skin.path === null}
							<span class="block h-[29px] w-[69px] shrink-0 border border-dashed opacity-50" style:border-color={pledit.normal ?? '#00ff00'}></span>
						{:else}
							<img use:thumb={skin.path} alt="" width="69" height="29" class="block h-[29px] w-[69px] shrink-0 bg-black/30" />
						{/if}
						<span class="min-w-0 flex-1 truncate">{skin.name}</span>
						{#if skin.path === current}<span class="shrink-0">✓</span>{/if}
					</button>
				{:else}
					<div class="p-2 opacity-70">No skins match.</div>
				{/each}
			</div>

			<!-- The preview, at 1x or smaller to fit, crisp. -->
			<div class="flex min-w-0 flex-1 flex-col gap-1">
				<div class="flex min-h-0 flex-1 items-start justify-center overflow-hidden" bind:clientWidth={previewW} bind:clientHeight={previewH}>
					<canvas
						bind:this={previewCanvas}
						class="block"
						style:width="{PREVIEW.w * previewScale}px"
						style:height="{PREVIEW.h * previewScale}px"
						style:image-rendering={previewScale === 1 ? 'pixelated' : 'auto'}
					></canvas>
				</div>
				<div class="truncate text-center" style:color={pledit.current ?? '#ffffff'}>
					{status || (pickedSkin ? pickedSkin.name + (pickedSkin.path === current ? ' (current)' : '') : '')}
				</div>
			</div>
		</div>

		<!-- Winamp's buttons. -->
		<div class="flex flex-wrap items-center gap-1.5">
			{#each buttons as [text, action] (text)}
				<button
					type="button"
					class="border px-2 text-[11px] leading-[16px]"
					style:background={pledit.normalBg ?? '#000000'}
					style:color={pledit.current ?? '#ffffff'}
					style:border-color={pledit.normal ?? '#00ff00'}
					style:font-family={font}
					onclick={() => action()}>{text}</button
				>
			{/each}
		</div>
	</div>
</div>
