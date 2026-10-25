<script>
	// File info (label "winamp-fileinfo", see +layout.svelte and winamp.rs): a track's cover and
	// everything Limusic knows about it, in the skin's generic frame and the playlist's colours.
	// Opened from a playlist or search row's right-click menu, or Alt+3 (Winamp's key for it). The
	// track comes through localStorage (skinApi.js `showFileInfo`), which every window shares, so an
	// open window follows a new one through the `storage` event. A song gets a like heart and an
	// Add to / Remove from library button (Limusic's own), and its artist and album open in Limusic's
	// window (the media library, as far as Winamp mode goes). A song with a linked album gets
	// that album's page fetched for its type, year and track number. Text zooms (the right-click menu,
	// Ctrl+=/-/0, Ctrl+wheel, a pinch), the window growing with it, remembered.
	import { onMount } from 'svelte';
	import { listen } from '@tauri-apps/api/event';
	import { closeWinampPanel, getAlbum, openExternal, resizeWinampPanel } from '$lib/api';
	import { copyText } from '$lib/clipboard';
	import { logUi } from '$lib/errlog';
	import { thumb } from '$lib/thumb';
	import { decodeAllSprites } from '../skin/render/spritesheet.js';
	import { artFrame, onCloseButton, drawFrame, frameInset } from '../skin/render/albumArt.js';
	import { doubleFactor, followDoubleSize, onPinch, pinOneToOnePixels } from '../skin/pixels.js';
	import { showFileInfoMenu } from '../skin/menu.js';
	import { FILE_INFO_KEY, FILE_INFO_SIZE, loadSkin } from '../skin/skinApi.js';
	import { frameMouse } from '../skin/frameWindow.js';
	import { isLit, setActivePart } from '../skin/focus.js';
	import { inSongLibrary, ratingOf, songLibraryToken, toggleRating, toggleSongLibrary } from '$lib/player.svelte';
	import { openLibrary } from '../skin/library.js';
	import { loadPrefs, pref, savePref } from '../skin/prefs.js';

	const COVER = 150;
	/** Text sizes, as multiples of the 11px it starts at. */
	const ZOOMS = [1, 1.25, 1.5, 1.75, 2];
	let zoom = $state(1);
	/** The window's size: zoomed with the text, then whatever its edges are dragged to. */
	let size = $state({ w: FILE_INFO_SIZE.w, h: FILE_INFO_SIZE.h });
	const px = (/** @type {number} */ n) => Math.round(n * zoom);

	/**
	 * What the song's album page adds: its title, type (Album, EP, Single) and year, the song's
	 * place on it and its play count. Per album id, fetched once.
	 * @typedef {{ title?: string, kind?: string, year?: string, track?: number, total?: number, plays?: string,
	 *   library?: import('$lib/api').SongItem['library'] }} AlbumInfo
	 */
	/** @type {Map<string, Promise<import('$lib/api').AlbumPage>>} */
	const albums = new Map();
	let albumInfo = $state(/** @type {AlbumInfo} */ ({}));

	/** @type {HTMLCanvasElement} */
	let canvas;
	/** @type {Map<string, ImageBitmap>} */
	let sprites = new Map();
	/** @type {import('$lib/api').SkinPayload['pledit']} */
	let pledit = $state({});
	let inset = $state({ top: 20, bottom: 14, left: 11, right: 11 });
	let item = $state(/** @type {import('$lib/api').SongItem | null} */ (null));
	let note = $state('');
	let closePressed = false;

	const close = () => closeWinampPanel('fileinfo').catch((e) => console.error('close failed', e));
	// A search's album, artist or playlist row brings its own link (searchKinds.js).
	const link = $derived(item ? (/** @type {{ link?: string }} */ (item).link ?? `https://music.youtube.com/watch?v=${item.video_id}`) : '');
	const font = $derived(`${pledit.font ? `"${pledit.font}", ` : ''}Arial, sans-serif`);
	/** A song, not an album, artist or playlist row from a search: it can be liked and saved. */
	const song = $derived(item && !(/** @type {{ rowKind?: string }} */ (item).rowKind ?? '').match(/album|artist|playlist/) ? item : null);
	const liked = $derived(song ? ratingOf(song) === 'like' : false);
	/** The song as the library button sees it: its own row's token if it came with one (a queue
	 *  row from radio or autoplay often doesn't), else the one on its album page's row. */
	const librarySong = $derived(
		song && !song.library && albumInfo.library ? { ...song, library: albumInfo.library } : song
	);
	const saved = $derived(librarySong ? inSongLibrary(librarySong) : false);
	/** Whether the library button can do anything: YouTube has to have sent a token with the row. */
	const canSave = $derived(librarySong ? !!songLibraryToken(librarySong) : false);
	/** Where a row's value opens in Limusic's window, if anywhere. */
	const links = $derived(
		/** @type {Record<string, string>} */ ({
			...(song?.artist_id ? { Artist: `/artist/${song.artist_id}` } : {}),
			...(song?.album_id ? { Album: `/album/${song.album_id}` } : {})
		})
	);

	/** [label, value] rows, the empty ones left out. */
	const rows = $derived(
		item
			? /** @type {[string, string][]} */ (
					[
						['Type', ({ album: 'Album', artist: 'Artist', playlist: 'Playlist' })[/** @type {{ rowKind?: string }} */ (item).rowKind ?? ''] ?? ''],
						['Title', item.title],
						[/** @type {{ browse?: unknown }} */ (item).browse ? 'Details' : 'Artist', item.artists],
						['Album', item.album ?? albumInfo.title ?? ''],
						['Release', [albumInfo.kind, albumInfo.year].filter(Boolean).join(', ')],
						['Track', albumInfo.track ? `${albumInfo.track} of ${albumInfo.total}` : ''],
						['Length', item.duration ?? ''],
						['Plays', item.play_count ?? albumInfo.plays ?? ''],
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
		albumInfo = {};
		lookUpAlbum(item);
	}

	/** The song's album page, for what the row itself doesn't say. @param {import('$lib/api').SongItem | null} song */
	function lookUpAlbum(song) {
		// Album, artist and playlist rows from a search are no song on an album.
		if (!song?.album_id || /** @type {{ rowKind?: string }} */ (song).rowKind) return;
		const id = song.album_id;
		if (!albums.has(id)) albums.set(id, getAlbum(id));
		/** @type {Promise<import('$lib/api').AlbumPage>} */ (albums.get(id))
			.then((page) => {
				if (item?.video_id !== song.video_id) return; // moved on to another track
				// "Album • 2015", "EP • 2019", "Single • 2021".
				const parts = (page.subtitle ?? '').split('•').map((p) => p.trim());
				const at = page.items.findIndex((t) => t.video_id === song.video_id);
				albumInfo = {
					title: page.title,
					kind: parts[0] || undefined,
					year: parts.find((p) => /^\d{4}$/.test(p)),
					track: at >= 0 ? at + 1 : undefined,
					total: page.items.length,
					plays: at >= 0 ? page.items[at].play_count : undefined,
					library: at >= 0 ? page.items[at].library : undefined
				};
			})
			.catch((e) => {
				albums.delete(id); // try again next time
				logUi('warn', `file info: album ${id} failed: ${e}`);
			});
	}

	/** Bigger, smaller (-1), or back to normal (0). @param {number} step */
	function zoomBy(step) {
		const i = ZOOMS.indexOf(zoom);
		const next = step === 0 ? 1 : ZOOMS[Math.max(0, Math.min(ZOOMS.length - 1, i + step))];
		if (next === zoom) return;
		zoom = next;
		savePref('fileInfoZoom', zoom);
		fit();
	}

	/** The window to the zoomed size; the frame is redrawn when it gets there (`onResize`). */
	function fit() {
		const [w, h] = [FILE_INFO_SIZE.w * zoom, FILE_INFO_SIZE.h * zoom].map((n) => Math.round(n) * doubleFactor());
		resizeWinampPanel('fileinfo', w, h).catch((e) => console.error('file info resize failed', e));
	}

	/** The window resized, by `fit` or from its edges: the frame redrawn to fill it. */
	function onResize() {
		size = { w: window.innerWidth, h: window.innerHeight };
		draw();
	}

	function draw() {
		const ctx = canvas?.getContext('2d');
		if (!ctx || sprites.size === 0) return;
		const { w, h } = size;
		canvas.width = w;
		canvas.height = h;
		canvas.style.width = `${w}px`;
		canvas.style.height = `${h}px`;
		ctx.fillStyle = pledit.normalBg ?? '#000000';
		ctx.fillRect(0, 0, w, h);
		drawFrame(ctx, sprites, { x: 0, y: 0, w, h }, closePressed, 'file info', isLit('fileinfo'));
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
		window.addEventListener('resize', onResize);
		// The DPI fix, then double size on top, following the Winamp window's.
		const unlistenDouble = followDoubleSize(
			pinOneToOnePixels().catch((e) => logUi('error', `file info zoom pin failed: ${e}`)),
			'fileinfo'
		);
		loadPrefs().then(() => {
			const saved = pref('fileInfoZoom', 1);
			if (ZOOMS.includes(saved) && saved !== 1) {
				zoom = saved;
				fit();
			}
		});
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
				.catch((e) => logUi('error', `file info skin failed: ${e}`));
		};
		reload();
		const unlistenSkin = listen('winamp-skin-changed', reload);

		const stopFrameMouse = frameMouse(canvas, {
			onClose: (e) => onCloseButton(e, size.w),
			inset: () => inset,
			pressed: (down) => {
				closePressed = down;
				draw();
			},
			close,
			resizable: 'fileinfo'
		});
		const onKey = (/** @type {KeyboardEvent} */ e) => {
			if (e.key === 'Escape') return close();
			if (!(e.ctrlKey || e.metaKey) || e.altKey) return;
			// The keys Limusic and the lyrics zoom with.
			const step = /** @type {Record<string, number>} */ ({ '=': 1, '+': 1, '-': -1, '0': 0 })[e.key];
			if (step === undefined) return;
			e.preventDefault();
			zoomBy(step);
		};
		const onWheel = (/** @type {WheelEvent} */ e) => {
			if (!(e.ctrlKey || e.metaKey)) return;
			e.preventDefault();
			zoomBy(e.deltaY < 0 ? 1 : -1);
		};
		window.addEventListener('wheel', onWheel, { passive: false });
		const stopPinch = onPinch((step) => zoomBy(step));
		const onMenu = (/** @type {MouseEvent} */ e) => {
			e.preventDefault();
			showFileInfoMenu({ x: e.clientX, y: e.clientY }, { zoom: zoomBy, copyLink, openInBrowser }).catch((err) =>
				console.error('file info menu failed', err)
			);
		};
		window.addEventListener('contextmenu', onMenu);
		window.addEventListener('keydown', onKey);
		return () => {
			unlistenDouble.then((f) => f());
			unlistenSkin.then((f) => f());
			window.removeEventListener('storage', onStorage);
			window.removeEventListener('resize', onResize);
			window.removeEventListener('focus', draw);
			window.removeEventListener('blur', draw);
			stopFrameMouse();
			window.removeEventListener('keydown', onKey);
			window.removeEventListener('wheel', onWheel);
			window.removeEventListener('contextmenu', onMenu);
			stopPinch();
		};
	});
</script>

<div class="relative h-screen w-screen overflow-hidden bg-transparent">
	<canvas bind:this={canvas} class="block"></canvas>
	{#if item}
		<div
			class="absolute flex gap-3"
			style:font-size="{px(11)}px"
			style:line-height="{px(14)}px"
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
					style:width="{px(COVER)}px"
					style:height="{px(COVER)}px"
				/>
			{/if}
			<div class="flex min-w-0 flex-1 flex-col">
				<div class="min-h-0 flex-1 overflow-y-auto">
				<table class="w-full table-fixed border-collapse">
					<tbody>
						{#each rows as [label, value] (label)}
							<tr>
								<td class="pr-1 align-top opacity-70" style:width="{px(62)}px">{label}</td>
								<td class="select-text break-words align-top" style:color={pledit.current ?? '#ffffff'}>
									{#if links[label]}
										<button
											type="button"
											class="cursor-pointer text-left hover:underline"
											title="Open in Limusic"
											onclick={() => openLibrary(links[label]).catch((e) => (note = `Couldn't open it: ${e}`))}
											>{value}</button
										>
									{:else}{value}{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
				</div>
				{#snippet button(/** @type {string} */ text, /** @type {() => void} */ action)}
					<button
						type="button"
						class="border px-1.5"
						style:font-size="{px(11)}px"
						style:line-height="{px(15)}px"
						style:background={pledit.normalBg ?? '#000000'}
						style:color={pledit.current ?? '#ffffff'}
						style:border-color={pledit.normal ?? '#00ff00'}
						style:font-family={font}
						onclick={action}>{text}</button
					>
				{/snippet}
				{#if song}
					<div class="flex flex-wrap items-center gap-1 pt-1">
						<button
							type="button"
							class="shrink-0 cursor-pointer"
							title={liked ? 'Liked (click to unlike)' : 'Like'}
							aria-label={liked ? 'Unlike' : 'Like'}
							onclick={() => toggleRating(song, 'like')}
						>
							<svg viewBox="0 0 24 24" style:width="{px(14)}px" style:height="{px(14)}px">
								<path
									d="M12 21s-7.5-4.6-9.6-9.2C1 8.6 3 5 6.5 5c2 0 3.7 1.1 4.5 2.7h2C13.8 6.1 15.5 5 17.5 5 21 5 23 8.6 21.6 11.8 19.5 16.4 12 21 12 21z"
									fill={liked ? (pledit.current ?? '#ffffff') : 'none'}
									stroke={pledit.current ?? '#ffffff'}
									stroke-width="2"
									stroke-linejoin="round"
								/>
							</svg>
						</button>
						<!-- Without a token, nothing: YouTube leaves the option out for a song that's already in
						     one of the user's playlists (its own apps too), so "not in library" would often be wrong. -->
						{#if canSave}
							{#if saved}<span class="shrink-0 opacity-70">In library</span>{/if}
							{@render button(saved ? 'Remove from library' : 'Add to library', () => librarySong && toggleSongLibrary(librarySong))}
						{/if}
					</div>
				{/if}
				<div class="flex flex-wrap items-center gap-1 pt-1">
					{@render button('Copy link', copyLink)}
					{@render button('Open in browser', openInBrowser)}
					<span class="truncate opacity-70">{note}</span>
				</div>
			</div>
		</div>
	{/if}
</div>
