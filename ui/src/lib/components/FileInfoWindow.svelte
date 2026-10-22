<script>
	// File info (label "winamp-fileinfo", see +layout.svelte and winamp.rs): a track's cover and
	// everything Limusic knows about it, in the skin's generic frame and the playlist's colours.
	// Opened from a playlist or search row's right-click menu, or Alt+3 (Winamp's key for it). The
	// track comes through localStorage (skinApi.js `showFileInfo`), which every window shares, so an
	// open window follows a new one through the `storage` event.
	import { onMount } from 'svelte';
	import { listen } from '@tauri-apps/api/event';
	import { getCurrentWindow } from '@tauri-apps/api/window';
	import { closeWinampPanel, openExternal } from '$lib/api';
	import { copyText } from '$lib/clipboard';
	import { logUi } from '$lib/errlog';
	import { thumb } from '$lib/thumb';
	import { decodeAllSprites } from '../skin/render/spritesheet.js';
	import { ART_CLOSE, artFrame, drawFrame, frameInset } from '../skin/render/albumArt.js';
	import { pinOneToOnePixels } from '../skin/pixels.js';
	import { FILE_INFO_KEY, FILE_INFO_SIZE, loadSkin } from '../skin/skinApi.js';
	import { isLit, setActivePart } from '../skin/focus.js';

	const { w: WIDTH, h: HEIGHT } = FILE_INFO_SIZE;
	const COVER = 150;

	/** @type {HTMLCanvasElement} */
	let canvas;
	/** @type {Map<string, ImageBitmap>} */
	let sprites = new Map();
	/** @type {import('$lib/api').SkinPayload['pledit']} */
	let pledit = $state({});
	let inset = $state({ top: 20, bottom: 14, left: 11, right: 8 });
	let item = $state(/** @type {import('$lib/api').SongItem | null} */ (null));
	let note = $state('');
	let closePressed = false;

	const close = () => closeWinampPanel('fileinfo').catch((e) => console.error('close failed', e));
	// A search's album, artist or playlist row brings its own link (searchKinds.js).
	const link = $derived(item ? (/** @type {{ link?: string }} */ (item).link ?? `https://music.youtube.com/watch?v=${item.video_id}`) : '');
	const font = $derived(`${pledit.font ? `"${pledit.font}", ` : ''}Arial, sans-serif`);
	/** [label, value] rows, the empty ones left out. */
	const rows = $derived(
		item
			? /** @type {[string, string][]} */ (
					[
						['Type', ({ album: 'Album', artist: 'Artist', playlist: 'Playlist' })[/** @type {{ rowKind?: string }} */ (item).rowKind ?? ''] ?? ''],
						['Title', item.title],
						[/** @type {{ browse?: unknown }} */ (item).browse ? 'Details' : 'Artist', item.artists],
						['Album', item.album ?? ''],
						['Length', item.duration ?? ''],
						['Plays', item.play_count ?? ''],
						['Added by', item.added_by ?? ''],
						['Queued by', item.queued_by ?? ''],
						['Added', item.added_at ? new Date(item.added_at * 1000).toLocaleString() : ''],
						['Video ID', item.video_id]
					].filter(([, v]) => v)
				)
			: []
	);

	function read() {
		try {
			const raw = localStorage.getItem(FILE_INFO_KEY);
			item = raw ? JSON.parse(raw) : null;
		} catch {
			item = null;
		}
		note = '';
	}

	function draw() {
		const ctx = canvas?.getContext('2d');
		if (!ctx || sprites.size === 0) return;
		canvas.width = WIDTH;
		canvas.height = HEIGHT;
		canvas.style.width = `${WIDTH}px`;
		canvas.style.height = `${HEIGHT}px`;
		ctx.fillStyle = pledit.normalBg ?? '#000000';
		ctx.fillRect(0, 0, WIDTH, HEIGHT);
		drawFrame(ctx, sprites, { x: 0, y: 0, w: WIDTH, h: HEIGHT }, closePressed, 'file info', isLit('fileinfo'));
	}

	async function copyLink() {
		try {
			await copyText(link);
			note = 'Link copied';
		} catch (e) {
			note = `Couldn't copy: ${e}`;
		}
	}

	function openInBrowser() {
		openExternal(link).catch((e) => (note = `Couldn't open it: ${e}`));
	}

	onMount(() => {
		setActivePart('fileinfo');
		read();
		const onStorage = (/** @type {StorageEvent} */ e) => e.key === FILE_INFO_KEY && read();
		window.addEventListener('storage', onStorage);
		window.addEventListener('focus', draw);
		window.addEventListener('blur', draw);
		pinOneToOnePixels().catch((e) => logUi('error', `file info zoom pin failed: ${e}`));
		const reload = () =>
			loadSkin()
				.then(async (payload) => {
					sprites = await decodeAllSprites(payload.sprites);
					pledit = payload.pledit;
					inset = frameInset(artFrame(sprites));
					draw();
				})
				.catch((e) => logUi('error', `file info skin failed: ${e}`));
		reload();
		const unlistenSkin = listen('winamp-skin-changed', reload);

		/** A titlebar press becomes a window drag once the mouse moves. */
		let press = /** @type {{ x: number, y: number } | null} */ (null);
		const onDown = (/** @type {MouseEvent} */ e) => {
			if (e.button !== 0) return;
			const x = WIDTH + ART_CLOSE.dx;
			if (e.clientX >= x && e.clientX < x + ART_CLOSE.w && e.clientY >= ART_CLOSE.y && e.clientY < ART_CLOSE.y + ART_CLOSE.h) {
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
		const onUp = () => {
			press = null;
			if (closePressed) close();
		};
		const onKey = (/** @type {KeyboardEvent} */ e) => {
			if (e.key === 'Escape') close();
		};
		canvas.addEventListener('mousedown', onDown);
		window.addEventListener('mousemove', onMove);
		window.addEventListener('mouseup', onUp);
		window.addEventListener('keydown', onKey);
		return () => {
			unlistenSkin.then((f) => f());
			window.removeEventListener('storage', onStorage);
			window.removeEventListener('focus', draw);
			window.removeEventListener('blur', draw);
			window.removeEventListener('mousemove', onMove);
			window.removeEventListener('mouseup', onUp);
			window.removeEventListener('keydown', onKey);
		};
	});
</script>

<div class="relative h-screen w-screen overflow-hidden bg-transparent">
	<canvas bind:this={canvas} class="block"></canvas>
	{#if item}
		<div
			class="absolute flex gap-3 text-[11px] leading-[14px]"
			style:left="{inset.left + 6}px"
			style:top="{inset.top + 6}px"
			style:right="{inset.right + 6}px"
			style:bottom="{inset.bottom + 4}px"
			style:color={pledit.normal ?? '#00ff00'}
			style:font-family={font}
		>
			{#if item.thumbnail}
				<img
					src={thumb(item.thumbnail, 544) ?? item.thumbnail}
					alt=""
					class="shrink-0 object-cover"
					style:width="{COVER}px"
					style:height="{COVER}px"
				/>
			{/if}
			<div class="flex min-w-0 flex-1 flex-col">
				<table class="w-full table-fixed border-collapse">
					<tbody>
						{#each rows as [label, value] (label)}
							<tr>
								<td class="w-[62px] pr-1 align-top opacity-70">{label}</td>
								<td class="select-text break-words align-top" style:color={pledit.current ?? '#ffffff'}>{value}</td>
							</tr>
						{/each}
					</tbody>
				</table>
				<div class="mt-auto flex items-center gap-1 pt-1">
					{#snippet button(/** @type {string} */ text, /** @type {() => void} */ action)}
						<button
							type="button"
							class="border px-1.5 text-[11px] leading-[15px]"
							style:background={pledit.normalBg ?? '#000000'}
							style:color={pledit.current ?? '#ffffff'}
							style:border-color={pledit.normal ?? '#00ff00'}
							style:font-family={font}
							onclick={action}>{text}</button
						>
					{/snippet}
					{@render button('Copy link', copyLink)}
					{@render button('Open in browser', openInBrowser)}
					<span class="truncate opacity-70">{note}</span>
				</div>
			</div>
		</div>
	{/if}
</div>
