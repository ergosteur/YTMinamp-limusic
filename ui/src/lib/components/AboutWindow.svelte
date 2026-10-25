<script>
	// About (label "winamp-about", see +layout.svelte and winamp.rs): the version, who it stands
	// on, and on a second tab the licence notices (ui/static/third-party-notices.txt, shipped in
	// the app), in the skin's generic frame and the playlist's colours, like File info. WACUP's About
	// box has tabs too. Opened from the main menu's "About ytminamp…" and the main window's About
	// button.
	import { onMount } from 'svelte';
	import { listen } from '@tauri-apps/api/event';
	import { getVersion } from '@tauri-apps/api/app';
	import { closeWinampPanel, openExternal } from '$lib/api';
	import { logUi } from '$lib/errlog';
	import { decodeAllSprites } from '../skin/render/spritesheet.js';
	import { ART_CLOSE, artFrame, drawFrame, frameInset } from '../skin/render/albumArt.js';
	import { followDoubleSize, pinOneToOnePixels } from '../skin/pixels.js';
	import { flashMarquee, loadSkin, queueLlama } from '../skin/skinApi.js';
	import { frameMouse } from '../skin/frameWindow.js';
	import { isLit, setActivePart } from '../skin/focus.js';
	import { APP_NAME, fullVersion } from '../skin/brand.js';
	import { checkForUpdatesInteractive, openDownloadPage, updateState } from '$lib/updater.svelte';


	/** @type {HTMLCanvasElement} */
	let canvas;
	/** @type {Map<string, ImageBitmap>} */
	let sprites = new Map();
	/** @type {import('$lib/api').SkinPayload['pledit']} */
	let pledit = $state({});
	let inset = $state({ top: 20, bottom: 14, left: 11, right: 11 });
	let tab = $state(/** @type {'about' | 'notices'} */ ('about'));
	let version = $state('');
	let notices = $state('');
	/** Check for updates: its answer, or '' before the first check. */
	let update = $state({ checking: false, message: '', error: false });

	/** Limusic's own check (`updater.svelte.ts`), which reads YTMinamp's releases (skin/updates.js). */
	async function checkUpdates() {
		update = { checking: true, message: 'Checking\u2026', error: false };
		const { message, error } = await checkForUpdatesInteractive();
		update = { checking: false, message, error };
	}
	let closePressed = false;

	const close = () => closeWinampPanel('about').catch((e) => console.error('close failed', e));
	const font = $derived(`${pledit.font ? `"${pledit.font}", ` : ''}Arial, sans-serif`);
	/** The notices as text and links, the links opened in the browser. */
	const noticeParts = $derived(notices.split(/(https?:\/\/[^\s)]+)/));
	const cueTheLlama = () =>
		queueLlama()
			.then(() => flashMarquee('The llama is cued up'))
			.catch((e) => console.error('queueing the llama failed', e));
	const open = (/** @type {string} */ url) => openExternal(url).catch((e) => console.error('open link failed', e));

	function draw() {
		const ctx = canvas?.getContext('2d');
		if (!ctx || sprites.size === 0) return;
		// As big as the window, which opens at ABOUT_SIZE and resizes from its edges.
		const [w, h] = [window.innerWidth, window.innerHeight];
		canvas.width = w;
		canvas.height = h;
		canvas.style.width = `${w}px`;
		canvas.style.height = `${h}px`;
		ctx.fillStyle = pledit.normalBg ?? '#000000';
		ctx.fillRect(0, 0, w, h);
		drawFrame(ctx, sprites, { x: 0, y: 0, w, h }, closePressed, 'about', isLit('about'));
	}

	onMount(() => {
		setActivePart('about');
		getVersion().then((v) => (version = fullVersion(v)), () => (version = '?'));
		fetch('/third-party-notices.txt')
			.then((r) => (r.ok ? r.text() : Promise.reject(new Error(String(r.status)))))
			.then((text) => (notices = text))
			.catch((e) => (notices = `Couldn’t read the notices (${e}).`));
		window.addEventListener('focus', draw);
		window.addEventListener('blur', draw);
		window.addEventListener('resize', draw);
		// The DPI fix, then double size on top, following the Winamp window's.
		const unlistenDouble = followDoubleSize(
			pinOneToOnePixels().catch((e) => logUi('error', `about zoom pin failed: ${e}`)),
			'about'
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
				})
				.catch((e) => logUi('error', `about skin failed: ${e}`));
		};
		reload();
		const unlistenSkin = listen('winamp-skin-changed', reload);

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
			resizable: 'about'
		});
		const onKey = (/** @type {KeyboardEvent} */ e) => {
			if (e.key === 'Escape') close();
		};
		window.addEventListener('keydown', onKey);
		return () => {
			unlistenDouble.then((f) => f());
			unlistenSkin.then((f) => f());
			window.removeEventListener('resize', draw);
			window.removeEventListener('focus', draw);
			window.removeEventListener('blur', draw);
			stopFrameMouse();
			window.removeEventListener('keydown', onKey);
		};
	});
</script>

<div class="relative h-screen w-screen overflow-hidden bg-transparent">
	<canvas bind:this={canvas} class="block"></canvas>
	<div
		class="absolute flex flex-col gap-2 text-[11px] leading-[14px]"
		style:left="{inset.left + 6}px"
		style:top="{inset.top + 6}px"
		style:right="{inset.right + 6}px"
		style:bottom="{inset.bottom + 6}px"
		style:color={pledit.normal ?? '#00ff00'}
		style:font-family={font}
	>
		<div class="flex gap-1">
			{#each [['about', 'About'], ['notices', 'Third-party notices']] as [id, text] (id)}
				<button
					type="button"
					class="border px-1.5 text-[11px] leading-[15px]"
					style:background={tab === id ? (pledit.selectedBg ?? '#0000c6') : (pledit.normalBg ?? '#000000')}
					style:color={pledit.current ?? '#ffffff'}
					style:border-color={pledit.normal ?? '#00ff00'}
					style:font-family={font}
					onclick={() => (tab = /** @type {'about' | 'notices'} */ (id))}>{text}</button
				>
			{/each}
		</div>
		<div class="min-h-0 flex-1 select-text overflow-y-auto pr-1">
			{#if tab === 'about'}
				<p style:color={pledit.current ?? '#ffffff'}>{APP_NAME} {version}</p>
				<p class="mt-2">Limusic with a classic Winamp 2.x skin mode.</p>
				<p class="mt-2">
					Built on Limusic (SimoHypers, GPL-3.0-or-later). Skin layout, marquee and analyzer after Webamp (Jordan
					Eldredge and contributors, MIT); FFT from vis_classic (Mike Lynch, via WACUP, MIT); MilkDrop by Butterchurn
					and butterchurn-presets (Jordan Berg, MIT). The built-in skin is Nullsoft&rsquo;s Winamp 2.91 base skin.
				</p>
				<p class="mt-2">Winamp is a trademark of its owner; this is an unofficial fan project.</p>
				<p class="mt-2">
					{#each [['YTMinamp on GitHub', 'https://github.com/ergosteur/YTMinamp-limusic'], ['Limusic', 'https://github.com/SimoHypers/limusic']] as [text, url], i (url)}
						{#if i}&ensp;&middot;&ensp;{/if}<button
							type="button"
							class="cursor-pointer underline"
							style:color={pledit.current ?? '#ffffff'}
							title={url}
							onclick={() => open(url)}>{text}</button
						>
					{/each}
				</p>
				<div class="mt-3 flex flex-wrap items-center gap-2">
					{#snippet button(/** @type {string} */ text, /** @type {() => void} */ action, disabled = false)}
						<button
							type="button"
							class="border px-1.5 text-[11px] leading-[15px] disabled:opacity-50"
							style:background={pledit.normalBg ?? '#000000'}
							style:color={pledit.current ?? '#ffffff'}
							style:border-color={pledit.normal ?? '#00ff00'}
							style:font-family={font}
							{disabled}
							onclick={action}>{text}</button
						>
					{/snippet}
					{@render button('Check for updates', checkUpdates, update.checking)}
					<!-- A newer build: unsigned, so it's the release page, never an in-place install. -->
					{#if updateState.available && !updateState.available.rollback}
						{@render button('Download', openDownloadPage)}
					{/if}
					<span class:opacity-80={!update.error}>{update.message}</span>
					<!-- Winamp's welcome, again: the llama intro onto the playlist, waiting for Play. -->
					<span class="basis-full"></span>
					{@render button('Cue the Llama', cueTheLlama)}
				</div>
			{:else}
				<pre class="whitespace-pre-wrap" style:font-family={font}>{#each noticeParts as part, i (i)}{#if i % 2}<button
								type="button"
								class="cursor-pointer underline"
								style:color={pledit.current ?? '#ffffff'}
								onclick={() => open(part)}>{part}</button
							>{:else}{part}{/if}{/each}</pre>
			{/if}
		</div>
	</div>
</div>
