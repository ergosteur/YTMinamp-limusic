// Winamp's menus: the main one (right-click, the titlebar's options button, the clutterbar's O)
// and the playlist's, EQ's and search results' own. Native popup menus, like the real thing,
// rather than skinned ones.
//
// On Linux the menu is a GTK one built in Rust (`winamp_popup_menu`) that pops up and returns at
// once; a pick comes back as a `winamp-menu` event. Tauri's own menu popup is modal there (muda
// spins the GTK loop until the menu says it closed), and on Wayland a menu the compositor
// dismisses can never say so: the loop never ends, Tauri stops delivering events, and the
// popup keeps the window's resource table locked. That froze the whole UI, twice.
//
// Elsewhere it's Tauri's menu API, one menu at a time and built in a single call: its `popup`
// holds the resource table while it waits for the main thread, and building a menu needs that
// table on the main thread, so overlapping the two would deadlock. A right-click while a menu is
// in flight is dropped, and the previous menu is freed before the next is built.
import { Menu } from '@tauri-apps/api/menu';
import { listen } from '@tauri-apps/api/event';
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow';
import { LogicalPosition } from '@tauri-apps/api/dpi';
import { open } from '@tauri-apps/plugin-dialog';
import * as api from '$lib/api';
import {
	addSongsToPlaylists,
	inSongLibrary,
	playback,
	ratingOf,
	setRating,
	songLibraryToken,
	toggleSongLibrary
} from '$lib/player.svelte';
import { ask } from '@tauri-apps/plugin-dialog';
import {
	lyricsOnRight,
	nextTrack,
	openSearch,
	openUrlDialog,
	pause,
	play,
	prevTrack,
	requestSearch,
	saveEq,
	seekBy,
	setArt,
	setPanelOpen,
	setRepeatMode,
	stopPlayback,
	toggleAlwaysOnTop,
	toggleDoubleSize,
	togglePanel,
	flashMarquee,
	queueResults,
	playResults,
	openEqPresetDialog,
	clearResults,
	clearSearchBox,
	searchAgain,
	sortResults,
	nowAsItem,
	showFileInfo,
	showNowFileInfo,
	placeArt,
	toggleArtCaption,
	setSearchKind,
	toggleMarqueeScroll,
	toggleMilkdropOnStart,
	playIndex,
	toggleMilkdrop,
	toggleStartInWinamp,
	toggleShuffle,
	zoomLyrics,
	ABOUT_SIZE,
	toggleStopAfterCurrent,
	stopWithFadeout
} from './skinApi.js';
import { toggleTimeRemaining, toggleVisualizer } from './input.js';
import { EQ_PRESETS } from './render/equalizer.js';
import { lyricsNow, lyricsShow, lyricsTrack, pickedLyrics, toggleLyricsShow } from './lyrics.js';
import { doubleFactor, zoomFactor } from './pixels.js';
import { thumb } from '$lib/thumb';
import { SEARCH_KINDS, isSongRow } from './searchKinds.js';
import { openInLimusic, toggleLimusic } from './navigate.js';
import { copyText } from '$lib/clipboard';
import { invertSelection, markedRows, selectAll, selectNone } from './selection.js';
import { loadPrefs, pref, savePref } from './prefs.js';
import { uiState } from './uiState.js';
import {
	clearUpcoming,
	cropToSelected,
	libraryPlaylists,
	loadPlaylist,
	removeSelected,
	reverseUpcoming,
	saveQueue,
	sortUpcoming
} from './playlistActions.js';

/**
 * Where a menu opens: the click, in window coordinates. Without a position GTK opens it "at the
 * pointer", which Wayland doesn't reveal to apps, so it landed anywhere (and parentless).
 * @typedef {{ x: number, y: number }} MenuAt
 */

/** @typedef {NonNullable<Parameters<typeof Menu.new>[0]>} MenuOptions */

const SEPARATOR = { item: /** @type {const} */ ('Separator') };

const log = (/** @type {string} */ what) => (/** @type {unknown} */ e) => console.error(`${what} failed`, e);

let busy = false;
/** @type {Menu | null} */
let last = null;
/** Whether the GTK popup is available: unknown until the first menu tries it. */
let gtkMenus = /** @type {boolean | null} */ (null);
/** What each entry of the GTK menu on screen does, by the id sent back on a pick. */
let actions = new Map();
let listening = false;

/**
 * Turn plain item descriptions into the GTK popup's entries, remembering each action by id.
 * @param {any[]} items
 * @returns {import('$lib/api').WinampMenuEntry[]}
 */
function toEntries(items) {
	return items.map((item) => {
		if (item.item === 'Separator') return { separator: true };
		/** @type {import('$lib/api').WinampMenuEntry} */
		const entry = { text: item.text };
		if (typeof item.checked === 'boolean') entry.checked = item.checked;
		if (item.enabled === false) entry.enabled = false;
		if (item.accel) entry.accel = item.accel;
		if (item.items) entry.items = toEntries(item.items);
		if (item.action) {
			// Prefixed with this window's label: every window hears every pick (the global `listen`
			// below), so a bare number from MilkDrop's menu would run the Winamp window's same-number
			// item (Next preset opened Open URL).
			const id = `${getCurrentWebviewWindow().label}:${actions.size}`;
			actions.set(id, item.action);
			entry.id = id;
		}
		return entry;
	});
}

/**
 * Pop up a menu from plain item descriptions: the GTK popup on Linux, else Tauri's (one
 * resource, one main-thread call), unless another is still on its way.
 * @param {() => Promise<MenuOptions>} describe
 * @param {MenuAt} at
 */
async function popup(describe, at) {
	if (busy) return;
	busy = true;
	try {
		const options = await describe();
		// The click is in CSS px; the window counts zoomed px (the DPI fix, double size).
		at = { x: at.x * zoomFactor(), y: at.y * zoomFactor() };
		if (gtkMenus !== false) {
			if (!listening) {
				// Hears every window's picks; the ids are this window's own (see toEntries).
				await listen('winamp-menu', (e) => actions.get(/** @type {string} */ (e.payload))?.());
				listening = true;
			}
			actions = new Map();
			try {
				await api.winampPopupMenu(toEntries(options.items ?? []), at.x, at.y);
				gtkMenus = true;
				return;
			} catch (e) {
				// Only "not here" moves to Tauri's menu: on Linux that one wedges on Wayland, so a
				// GTK popup that failed once is tried again next time instead.
				if (String(e).includes('not on this platform')) gtkMenus = false;
				else return console.error('winamp menu failed', e);
			}
		}
		await last?.close().catch(log('free menu'));
		last = null;
		// Tauri's items take no shortcut text (an accelerator there would register the key).
		const menu = await Menu.new(stripAccels(options));
		last = menu;
		await menu.popup(new LogicalPosition(at.x, at.y));
	} finally {
		busy = false;
	}
}

/** @param {any} options */
function stripAccels(options) {
	/** @param {any[]} items @returns {any[]} */
	const strip = (items) => items.map(({ accel, ...item }) => (item.items ? { ...item, items: strip(item.items) } : item));
	return { ...options, items: strip(options.items ?? []) };
}

/**
 * A search result's menu: the three things Limusic's own song menu leads with.
 * @param {number} index into `uiState.search.results`
 * @param {MenuAt} at
 */
export function showResultMenu(index, at) {
	return popup(async () => ({ items: await resultItems(index) }), at);
}

/**
 * Play / play next / add to queue for the selected results (or `index` if none are), the
 * right-click menu's and the search panel's ADD's.
 * @param {number | null} [index]
 */
async function resultItems(index = null) {
	const results = uiState.search.results;
	const marked = markedRows(uiState.search).filter((i) => results[i]?.rowKind !== 'header');
	const rows = marked.length ? marked : index === null ? [] : [index];
	if (!rows.length) return [{ text: 'Select some results first', enabled: false }];
	const n = rows.length > 1 ? ` (${rows.length})` : '';
	const info = results[index ?? rows[0]];
	// An artist can be played (its radio) but not queued; an album or playlist queues its tracks.
	const queueable = rows.some((i) => results[i]?.rowKind !== 'artist');
	const one = rows.length === 1 ? results[rows[0]]?.rowKind : undefined;
	const play = one === 'artist' ? 'Play radio' : one === 'album' ? 'Play album' : one === 'playlist' ? 'Play playlist' : `Play${n}`;
	return [
		{ text: play, accel: 'Enter', action: () => playResults(rows).catch(log('play')) },
		{ text: `Play next${n}`, enabled: queueable, action: () => queueResults(rows, true).catch(log('play next')) },
		{ text: `Add to queue${n}`, enabled: queueable, accel: 'Shift+Enter', action: () => queueResults(rows, false).catch(log('add to queue')) },
		SEPARATOR,
		{ text: 'View file info...', accel: 'Alt+3', enabled: !!info, action: () => info && showFileInfo(info) },
		SEPARATOR,
		rows.some((i) => isSongRow(results[i]))
			? { text: 'Rate items', items: await ratingItems(rows.map((i) => results[i]).filter(isSongRow)) }
			: { text: 'Rate items', enabled: false }
	];
}

/**
 * Rate items ▸: Like / Dislike / No rating (ticked for how the first is rated now), then Add to /
 * Remove from library and Add to existing playlist. All Limusic's own (player.svelte.ts
 * `setRating`, `toggleSongLibrary`, `addSongsToPlaylists`), so they show there too.
 * @param {import('$lib/api').SongItem[]} items
 */
async function ratingItems(items) {
	const now = items[0] ? ratingOf(items[0]) : null;
	/** @param {import('$lib/api').Rating} r */
	const rate = (r) =>
		Promise.all(items.map((item) => setRating(item, r)))
			.then(() => flashMarquee(r === 'like' ? 'Liked' : r === 'dislike' ? 'Disliked' : 'Rating cleared'))
			.catch((e) => flashMarquee(`Couldn't rate: ${e}`));
	// Library ▸ Songs takes a token YouTube mints per row, so only rows that came with one can move.
	const movable = items.filter((item) => songLibraryToken(item));
	const saved = movable.length > 0 && movable.every((item) => inSongLibrary(item));
	const library = () =>
		Promise.all(movable.map((item) => toggleSongLibrary(item)))
			.then(() => flashMarquee(saved ? 'Removed from library' : 'Added to library'))
			.catch((e) => flashMarquee(`Couldn't change the library: ${e}`));
	// Playlists songs can go into: not On Repeat or Liked Music. The cached list, like LIST's.
	const { playlists } = await libraryPlaylists();
	const targets = playlists.filter((p) => p.id !== api.ON_REPEAT_ID && p.id !== api.LIKED_MUSIC_ID);
	const addTo = (/** @type {import('$lib/api').BrowseItem} */ p) =>
		addSongsToPlaylists([p], items, 'skip')
			.then(() => flashMarquee(`Added to ${p.title}`))
			.catch((e) => flashMarquee(`Couldn't add: ${e}`));
	return [
		{ text: 'Like', checked: now === 'like', action: () => rate('like') },
		{ text: 'Dislike', checked: now === 'dislike', action: () => rate('dislike') },
		{ text: 'No rating', checked: now === 'indifferent', action: () => rate('indifferent') },
		SEPARATOR,
		movable.length
			? { text: saved ? 'Remove from library' : 'Add to library', action: library }
			: { text: 'Add to library', enabled: false },
		targets.length
			? { text: 'Add to existing playlist', items: targets.map((p) => ({ text: p.title, action: () => addTo(p) })) }
			: { text: 'Add to existing playlist', enabled: false }
	];
}

/**
 * The song title's right-click menu, real Winamp's in order, with what applies here.
 * @param {MenuAt} at
 */
export function showTitleMenu(at) {
	return popup(async () => {
		const now = nowAsItem();
		return {
			items: [
				{ text: 'View file info...', accel: 'Alt+3 or Dblclick', enabled: !!now, action: showNowFileInfo },
				check('Lyrics', uiState.lyrics.open, 'Alt+Y', () => togglePanel('lyrics')),
				SEPARATOR,
				{ text: 'Jump to file...', accel: 'J', action: requestSearch },
				SEPARATOR,
				check('Autoscroll songname', uiState.marqueeScroll, '', toggleMarqueeScroll),
				SEPARATOR,
				now ? { text: 'Rating', items: await ratingItems([now]) } : { text: 'Rating', enabled: false }
			]
		};
	}, at);
}

/**
 * The album art's right-click menu: file info, the artwork full size, the album name under it,
 * where it sits, and the track's link.
 * @param {MenuAt} at
 */
export function showArtMenu(at) {
	return popup(async () => {
		const now = nowAsItem();
		const art = uiState.art;
		const link = now ? `https://music.youtube.com/watch?v=${now.video_id}` : '';
		/** @type {[import('./uiState.js').ArtDock, string][]} */
		const docks = [
			['left', 'Left of the player'],
			['right', 'Right of the player'],
			['stack', 'Docked in the stack'],
			['float', 'Floating window']
		];
		return {
			items: [
				{ text: 'View file info...', accel: 'Alt+3', enabled: !!now, action: showNowFileInfo },
				{
					text: 'Show full-size artwork',
					enabled: !!now?.thumbnail,
					// The biggest YouTube serves: 1280x720 for a video thumbnail, any size for a cover.
					action: () => now?.thumbnail && api.openExternal(thumb(now.thumbnail, 1600) ?? now.thumbnail).catch(log('open artwork'))
				},
				SEPARATOR,
				check('Show album name', art.caption, '', toggleArtCaption),
				{
					text: 'Placement',
					items: [
						...docks.map(([dock, text]) => ({
							text: dock === 'right' && lyricsOnRight() ? 'Right of the player (lyrics are there)' : text,
							checked: art.open && art.dock === dock,
							enabled: !(dock === 'right' && lyricsOnRight()),
							action: () => placeArt(dock)
						})),
						SEPARATOR,
						{ text: 'Hide', action: () => placeArt(null) }
					]
				},
				SEPARATOR,
				{ text: 'Copy link', enabled: !!now, action: () => copyText(link).then(() => flashMarquee('Link copied'), log('copy link')) },
				{ text: 'Open in YouTube Music', enabled: !!now, action: () => api.openExternal(link).catch(log('open link')) }
			]
		};
	}, at);
}

/**
 * File info's right-click menu: its text size (the window grows with it), and the track's link.
 * @param {MenuAt} at
 * @param {{ zoom: (step: number) => void, copyLink: () => void, openInBrowser: () => void }} controls
 */
export function showFileInfoMenu(at, controls) {
	return popup(
		async () => ({
			items: [
				{ text: 'Bigger text', accel: 'Ctrl+=', action: () => controls.zoom(1) },
				{ text: 'Smaller text', accel: 'Ctrl+-', action: () => controls.zoom(-1) },
				{ text: 'Normal size', accel: 'Ctrl+0', action: () => controls.zoom(0) },
				SEPARATOR,
				{ text: 'Copy link', action: controls.copyLink },
				{ text: 'Open in browser', action: controls.openInBrowser }
			]
		}),
		at
	);
}

/**
 * The Stop button's right-click menu: the ways to stop (Ctrl+click is Stop after current too).
 * @param {MenuAt} at
 */
export function showStopMenu(at) {
	return popup(async () => {
		const stopAfter = await api.stopAfterCurrentSet().catch(() => false);
		return {
			items: [
				{ text: 'Stop', accel: 'V', action: () => stopPlayback().catch(log('stop')) },
				{ text: 'Stop w/ fadeout', accel: 'Shift+V', action: () => stopWithFadeout().catch(log('stop with fadeout')) },
				check('Stop after current', stopAfter, 'Ctrl+V', toggleStopAfterCurrent)
			]
		};
	}, at);
}

/**
 * The analyzer's right-click menu, after Winamp's visualization one: the plug-in (MilkDrop,
 * Butterchurn, the only one here), then the main window's own analyzer modes.
 * @param {MenuAt} at
 */
export function showVisMenu(at) {
	return popup(
		async () => ({
			items: [
				{ text: 'Start/Stop plug-in', accel: 'Ctrl+Shift+K', action: toggleMilkdrop },
				{ text: 'Configure plug-in...', enabled: false },
				{ text: 'Select plug-in...', enabled: false },
				SEPARATOR,
				check('Run the plug-in on start-up', uiState.milkdropOnStart, '', toggleMilkdropOnStart),
				SEPARATOR,
				check('MilkDrop (Butterchurn)', uiState.milkdrop, '', toggleMilkdrop),
				SEPARATOR,
				check('Spectrum analyser', uiState.visMode === 'analyzer', '', () => uiState.visMode !== 'analyzer' && toggleVisualizer()),
				check('Off', uiState.visMode === 'off', '', () => uiState.visMode !== 'off' && toggleVisualizer())
			]
		}),
		at
	);
}

/**
 * A playlist row's right-click menu, in real Winamp's order (Play; Remove selected, Crop to
 * selected; View file info), with what the queue can do.
 * @param {number} index the row clicked
 * @param {MenuAt} at
 */
export function showQueueRowMenu(index, at) {
	return popup(async () => {
		const item = playback.queue.items[index];
		const marked = uiState.pl.marked.size;
		return {
			items: [
				{ text: 'Play', accel: 'Enter', action: () => playIndex(index).catch(log('play')) },
				SEPARATOR,
				{ text: marked > 1 ? `Remove selected (${marked})` : 'Remove selected', accel: 'Delete', action: () => removeSelected().catch(log('remove')) },
				{ text: 'Crop to selected', accel: 'Ctrl+Delete', action: () => cropToSelected().catch(log('crop')) },
				SEPARATOR,
				{ text: 'View file info...', accel: 'Alt+3', enabled: !!item, action: () => item && showFileInfo(item) },
				SEPARATOR,
				{ text: 'Rate items', items: await ratingItems(markedRows(uiState.pl).map((i) => playback.queue.items[i]).filter(Boolean)) }
			]
		};
	}, at);
}

/**
 * The search box's "Songs ▾" button: what to search for.
 * @param {MenuAt} at
 */
export function showSearchKindMenu(at) {
	return popup(
		async () => ({
			items: SEARCH_KINDS.map(([kind, text]) => ({
				text,
				checked: uiState.search.kind === kind,
				action: () => setSearchKind(kind)
			}))
		}),
		at
	);
}

/**
 * The search panel's bottom buttons: ADD plays or queues the selected results, REM clears, SEL
 * selects, MISC sorts the results, LIST runs a recent search again.
 * @param {'search-add' | 'search-rem' | 'search-sel' | 'search-misc' | 'search-list'} which
 * @param {MenuAt} at
 */
export function showSearchMenu(which, at) {
	const s = uiState.search;
	return popup(async () => {
		if (which === 'search-add') return { items: await resultItems() };
		if (which === 'search-rem') {
			return {
				items: [
					{ text: 'Clear results', enabled: s.results.length > 0, action: clearResults },
					{ text: 'Clear search box', action: clearSearchBox }
				]
			};
		}
		if (which === 'search-misc') {
			const some = s.results.length > 1;
			return {
				items: [
					{ text: 'Sort by title', enabled: some, action: () => sortResults('title') },
					{ text: 'Sort by artist', enabled: some, action: () => sortResults('artist') },
					{ text: 'Sort by length', enabled: some, action: () => sortResults('length') },
					{ text: 'Reverse', enabled: some, action: () => sortResults('reverse') }
				]
			};
		}
		if (which === 'search-list') {
			// Fresh from disk: a floating search window keeps its own copy.
			await loadPrefs();
			const recent = /** @type {string[]} */ (pref('searchHistory', []));
			return {
				items: recent.length
					? [
							{ text: 'Recent searches', enabled: false },
							...recent.map((q) => ({ text: q, action: () => searchAgain(q) })),
							SEPARATOR,
							{ text: 'Clear recent searches', action: () => savePref('searchHistory', []) }
						]
					: [{ text: 'No recent searches yet', enabled: false }]
			};
		}
		return {
			items: [
				{ text: 'Select all', action: () => selectAll(s, s.results.length, (i) => s.results[i]?.rowKind !== 'header') },
				{ text: 'Select none', action: () => selectNone(s) },
				{ text: 'Invert selection', action: () => invertSelection(s, s.results.length, (i) => s.results[i]?.rowKind !== 'header') }
			]
		};
	}, at);
}

/**
 * The playlist's bottom buttons, one short menu each. SEL selects (all, none, invert), as in
 * Winamp; LIST loads a playlist (some skins label it LOAD LIST) or saves the queue as one.
 * @param {'add' | 'rem' | 'sel' | 'misc' | 'list'} which
 * @param {MenuAt} at
 */
export function showPlaylistMenu(which, at) {
	return popup(async () => {
		if (which === 'add') {
			return {
				items: [
					{ text: 'Search YouTube Music', accel: 'Ctrl+J', action: requestSearch },
					{ text: 'Open YouTube URL…', action: openUrlDialog },
					SEPARATOR,
					// Limusic's own Library page, in the full window, for now.
					{ text: 'Browse library…', action: () => openInLimusic('/library').catch(log('browse library')) }
				]
			};
		}
		if (which === 'rem') {
			return {
				items: [
					{ text: 'Remove selected', action: () => removeSelected().catch(log('remove')) },
					{ text: 'Clear queue', action: () => clearUpcoming().catch(log('clear queue')) }
				]
			};
		}
		if (which === 'list') {
			const [load, signedIn] = await Promise.all([
				libraryItems(),
				api
					.getAccount()
					.then((a) => a.signedIn)
					.catch(() => false)
			]);
			return {
				items: [
					{ text: 'Load', items: load },
					{
						text: 'Save',
						items: [
							signedIn
								? { text: 'Queue to my YouTube Music library', action: () => saveQueue(false).catch(log('save')) }
								: { text: 'Queue to YouTube Music (sign in first)', enabled: false },
							{ text: 'Queue as a local playlist', action: () => saveQueue(true).catch(log('save')) }
						]
					}
				]
			};
		}
		if (which === 'sel') {
			const pl = uiState.pl;
			const count = playback.queue.items.length;
			return {
				items: [
					{ text: 'Select all', action: () => selectAll(pl, count) },
					{ text: 'Select none', action: () => selectNone(pl) },
					{ text: 'Invert selection', action: () => invertSelection(pl, count) }
				]
			};
		}
		if (which === 'misc') {
			return {
				items: [
					{ text: 'Sort by title', action: () => sortUpcoming('title').catch(log('sort')) },
					{ text: 'Sort by artist', action: () => sortUpcoming('artist').catch(log('sort')) },
					{ text: 'Reverse', action: () => reverseUpcoming().catch(log('reverse')) }
				]
			};
		}
		return { items: [] };
	}, at);
}

/** Library playlists to play, in Local and YouTube Music sections (LIST, and Play ▸ in the menu). */
async function libraryItems() {
	const { playlists, loading } = await libraryPlaylists();
	// On Repeat is built on this machine from its play counts, so it sits with the local ones.
	const local = (/** @type {import('$lib/api').BrowseItem} */ p) => api.isLocalPlaylist(p.id) || p.id === api.ON_REPEAT_ID;
	/** @param {string} header @param {import('$lib/api').BrowseItem[]} group */
	const section = (header, group) =>
		group.length
			? [
					{ text: header, enabled: false },
					...group.map((item) => ({ text: item.title, action: () => loadPlaylist(item).catch(log('load playlist')) }))
				]
			: [];
	const sections = [
		section('Local Playlists', playlists.filter(local)),
		// Still on its way (the first menu after opening): said the way Winamp says [Connecting].
		loading
			? [{ text: 'YouTube Music Playlists', enabled: false }, { text: '[Retrieving playlists]', enabled: false }]
			: section('YouTube Music Playlists', playlists.filter((p) => !local(p)))
	].filter((s) => s.length);
	return sections.length
		? sections.flatMap((s, i) => (i ? [SEPARATOR, ...s] : s))
		: [{ text: 'No playlists in your library', enabled: false }];
}

/** The EQ's PRESETS button: Winamp's built-in presets, and back to flat. @param {MenuAt} at */
export function showPresetsMenu(at) {
	return popup(async () => {
		// Fresh from disk: the save dialog writes them from its own window.
		await loadPrefs();
		/** @type {{ name: string, preamp: number, bands: number[] }[]} */
		const mine = pref('eqPresets', []);
		const remove = (/** @type {string} */ name) => {
			savePref('eqPresets', mine.filter((p) => p.name !== name));
			flashMarquee(`Deleted EQ preset: ${name}`);
		};
		return {
			items: [
				...mine.map((p) => ({ text: p.name, action: () => applyPreset(p.preamp, p.bands) })),
				...(mine.length ? [SEPARATOR] : []),
				{
					text: 'Winamp presets',
					items: EQ_PRESETS.map(([name, preamp, bands]) => ({ text: name, action: () => applyPreset(preamp, bands) }))
				},
				SEPARATOR,
				{ text: 'Save current as preset...', action: openEqPresetDialog },
				mine.length
					? { text: 'Delete preset', items: mine.map((p) => ({ text: p.name, action: () => remove(p.name) })) }
					: { text: 'Delete preset', enabled: false },
				SEPARATOR,
				{ text: 'Reset (flat)', action: () => applyPreset(50, Array(10).fill(50)) }
			]
		};
	}, at);
}

/**
 * The lyrics panel's menu: Limusic's romanization and translation switches, and the text size.
 * @param {MenuAt} at
 */
export function showLyricsMenu(at) {
	return popup(async () => {
		const lyrics = lyricsNow().lyrics;
		const lines = lyrics?.lines ?? [];
		const has = (/** @type {'romanized' | 'translation'} */ what) => lines.some((l) => l[what]);
		const track = lyricsTrack();
		const providers = track ? await api.lyricsProviders().catch(() => []) : [];
		/** Keep `source`'s lyrics for this song (null: back to the provider order), as Limusic's picker does. */
		const choose = (/** @type {string | null} */ source) => {
			if (!track) return;
			api
				.chooseLyricsSource({ ...track, source })
				.then((l) => {
					pickedLyrics(l, track.videoId);
					flashMarquee(l ? `Lyrics from ${l.source.replace(/^Source:\s*/, '')}` : 'No lyrics from there');
				})
				.catch((e) => flashMarquee(`Couldn't switch lyrics: ${e}`));
		};
		const offset = lyrics?.offset_ms ?? 0;
		/** Move the timing by `by` ms (0: back to none), remembered for this song. */
		const nudge = (/** @type {number} */ by) => {
			if (!track || !lyrics) return;
			const next = by === 0 ? 0 : Math.max(-15000, Math.min(15000, offset + by));
			api
				.setLyricsOffset(track.videoId, next)
				.then(() => {
					pickedLyrics({ ...lyrics, offset_ms: next }, track.videoId);
					flashMarquee(`Lyrics timing: ${next > 0 ? '+' : ''}${(next / 1000).toFixed(2)}s`);
				})
				.catch((e) => flashMarquee(`Couldn't change the timing: ${e}`));
		};
		return {
			items: [
				{
					text: has('romanized') ? 'Romanization' : 'Romanization (none for these lyrics)',
					checked: lyricsShow.romanized,
					action: () => toggleLyricsShow('romanized')
				},
				{
					text: has('translation') ? 'Translations' : 'Translations (none for these lyrics)',
					checked: lyricsShow.translated,
					action: () => toggleLyricsShow('translated')
				},
				SEPARATOR,
				{ text: 'Bigger text', accel: 'Ctrl+=', action: () => zoomLyrics(1) },
				{ text: 'Smaller text', accel: 'Ctrl+-', action: () => zoomLyrics(-1) },
				{ text: 'Normal size', accel: 'Ctrl+0', action: () => zoomLyrics(0) },
				SEPARATOR,
				track
					? {
							text: 'Lyrics source',
							items: [
								{ text: 'Automatic', checked: !!lyrics && !lyrics.pinned, action: () => choose(null) },
								SEPARATOR,
								...providers
									.filter((p) => p.on)
									.map((p) => ({
										text: p.name,
										checked: !!lyrics?.pinned && lyrics.provider === p.id,
										action: () => choose(p.id)
									}))
							]
						}
					: { text: 'Lyrics source', enabled: false },
				lyrics?.synced
					? {
							text: `Timing (${offset > 0 ? '+' : ''}${(offset / 1000).toFixed(2)}s)`,
							items: [
								{ text: 'Earlier (0.25s)', action: () => nudge(-250) },
								{ text: 'Later (0.25s)', action: () => nudge(250) },
								{ text: 'Reset', enabled: offset !== 0, action: () => nudge(0) }
							]
						}
					: { text: 'Timing', enabled: false }
			]
		};
	}, at);
}

/**
 * The MilkDrop window's menu. `controls` is the window's own (MilkdropWindow.svelte).
 * @typedef {'change' | 'always' | 'never'} OsdMode
 * @param {{ next: () => void, previous: () => void, hardCut: () => void,
 *   autoSeconds: number, setAutoSeconds: (s: number) => void, preset: string,
 *   toggleFullscreen: () => Promise<void>, close: () => void,
 *   presetOsd: OsdMode, trackOsd: OsdMode, setPresetOsd: (m: OsdMode) => void,
 *   setTrackOsd: (m: OsdMode) => void, browse: () => void, artOverlay: boolean,
 *   toggleArtOverlay: () => void }} controls
 * @param {MenuAt} at
 */
export function showMilkdropMenu(controls, at) {
	return popup(
		async () => ({
			items: [
				{ text: controls.preset || 'Loading presets...', enabled: false },
				SEPARATOR,
				{ text: 'Browse presets...', accel: 'L', action: () => controls.browse() },
				{ text: 'Next preset', accel: 'N', action: () => controls.next() },
				{ text: 'Previous preset', accel: 'P', action: () => controls.previous() },
				{ text: 'Random preset, no blend', action: () => controls.hardCut() },
				{
					text: 'Change presets automatically',
					items: /** @type {[number, string][]} */ ([
						[0, 'Off'],
						[10, 'Every 10 seconds'],
						[20, 'Every 20 seconds'],
						[30, 'Every 30 seconds'],
						[60, 'Every minute'],
						[120, 'Every 2 minutes'],
						[300, 'Every 5 minutes']
					]).map(([seconds, text]) => ({
						text,
						checked: controls.autoSeconds === seconds,
						action: () => controls.setAutoSeconds(seconds)
					}))
				},
				SEPARATOR,
				{ text: 'Visualization Preset OSD', items: osdItems(controls.presetOsd, controls.setPresetOsd) },
				{ text: 'Track Info OSD', items: osdItems(controls.trackOsd, controls.setTrackOsd) },
				{ text: 'Album art overlay', checked: controls.artOverlay, action: () => controls.toggleArtOverlay() },
				SEPARATOR,
				{ text: 'Fullscreen', accel: 'F', action: () => controls.toggleFullscreen().catch(log('fullscreen')) },
				{ text: 'Close', accel: 'Ctrl+Shift+K', action: () => controls.close() }
			]
		}),
		at
	);
}

/**
 * When an on-screen text shows, as a submenu.
 * @param {OsdMode} current @param {(m: OsdMode) => void} set
 */
function osdItems(current, set) {
	/** @type {[OsdMode, string][]} */
	const modes = [
		['change', 'Show on change'],
		['always', 'Always show'],
		['never', 'Never show']
	];
	return modes.map(([mode, text]) => ({ text, checked: current === mode, action: () => set(mode) }));
}

/** A ticked-or-not menu item. @param {string} text @param {boolean} on @param {string} accel @param {() => unknown} action */
const check = (text, on, accel, action) => ({ text, checked: on, accel, action });

/** @param {number} preamp @param {number[]} bands */
function applyPreset(preamp, bands) {
	uiState.eq.preamp = preamp;
	uiState.eq.bands = [...bands];
	saveEq();
}

/** About ytminamp: its own window, with the licence notices on a second tab (AboutWindow.svelte). */
export function showAbout() {
	const f = doubleFactor();
	return api.openWinampPanel('about', ABOUT_SIZE.w * f, ABOUT_SIZE.h * f);
}

/**
 * Where a panel lives, as a submenu: hidden, docked, or floating in its own window.
 * @param {string} text
 * @param {'playlist' | 'search' | 'eq' | 'lyrics'} kind
 */
function placementItems(text, kind) {
	const view = /** @type {{ open: boolean, dock: string }} */ (
		{ playlist: uiState.pl, search: uiState.search, eq: uiState.eq, lyrics: uiState.lyrics }[kind]
	);
	const docked = kind === 'lyrics' ? 'right' : 'stack';
	/** @param {'stack' | 'float' | 'right'} dock */
	const show = (dock) => {
		setPanelOpen(kind, true, dock);
		if (kind === 'search' && dock === 'stack') openSearch();
	};
	return {
		text,
		items: [
			{ text: 'Hidden', checked: !view.open, action: () => setPanelOpen(kind, false) },
			{
				text: kind === 'lyrics' ? 'Right of the stack' : 'Docked in the stack',
				checked: view.open && view.dock === docked,
				action: () => show(docked)
			},
			{ text: 'Floating window', checked: view.open && view.dock === 'float', action: () => show('float') }
		]
	};
}

/**
 * Winamp's main menu (right-click, the titlebar's options button, the clutterbar's O), laid out
 * like WACUP's, with what Winamp mode actually has.
 * @param {(path: string | null) => void} switchSkin load + remember a skin (`null` = built-in)
 * @param {MenuAt} at
 */
export function showMainMenu(switchSkin, at) {
	return popup(async () => {
		const [list, library, stopAfter, limusicShown] = await Promise.all([
			api.listWszSkins().catch((e) => {
				log('list skins')(e);
				return { dir: '', skins: [], current: null };
			}),
			libraryItems(),
			api.stopAfterCurrentSet().catch(() => false),
			api.limusicWindowShown().catch(() => false)
		]);
		const repeat = playback.queue.repeat ?? 'off';
		const art = uiState.art;
		/** @type {[import('./uiState.js').ArtDock, string][]} */
		const artDocks = [
			['left', 'Left of the player'],
			['right', 'Right of the player'],
			['stack', 'Docked in the stack'],
			['float', 'Floating window']
		];
		/** @type {['off' | 'all' | 'one', string][]} */
		const repeatModes = [
			['off', 'Off'],
			['all', 'All'],
			['one', 'Track']
		];
		return {
			items: [
				{ text: 'About ytminamp…', action: () => showAbout().catch(log('about')) },
				SEPARATOR,
				{
					text: 'Play',
					items: [
						{ text: 'URL…', accel: 'Ctrl+L', action: openUrlDialog },
						{ text: 'Search…', accel: 'Ctrl+J', action: requestSearch },
						{ text: 'Playlist from Library', items: library }
					]
				},
				// WACUP's: what's playing (Alt+3 picks the selected row instead when a list is active).
				{ text: 'View file info...', accel: 'Alt+3', enabled: !!playback.now, action: showNowFileInfo },
				SEPARATOR,
				// Limusic's own window is the library: its pages, search, playlists.
				check('Media Library (Limusic window)', limusicShown, 'Alt+L', () => toggleLimusic().catch(log('media library'))),
				check('Playlist Editor', uiState.pl.open, 'Alt+E', () => togglePanel('playlist')),
				check('Search', uiState.search.open, 'Alt+K', () => togglePanel('search')),
				check('Equaliser', uiState.eq.open, 'Alt+G', () => togglePanel('eq')),
				check('Album Art', art.open, 'Alt+A', () => togglePanel('art')),
				check('Lyrics', uiState.lyrics.open, 'Alt+Y', () => togglePanel('lyrics')),
				SEPARATOR,
				check('Always start in Winamp mode', uiState.startInWinamp, '', toggleStartInWinamp),
				{
					text: 'Options',
					items: [
						check('Always on top', uiState.alwaysOnTop, 'Ctrl+A', toggleAlwaysOnTop),
						check('Double size', uiState.doubleSize, 'Ctrl+2', () => toggleDoubleSize()),
						check('Time remaining', uiState.timeRemaining, 'Ctrl+T', toggleTimeRemaining)
					]
				},
				{
					text: 'Playback',
					items: [
						{ text: 'Previous', accel: 'Z', action: () => prevTrack().catch(log('previous')) },
						{ text: 'Play', accel: 'X', action: () => play().catch(log('play')) },
						{ text: 'Pause', accel: 'C', action: () => pause().catch(log('pause')) },
						{ text: 'Stop', accel: 'V', action: () => stopPlayback().catch(log('stop')) },
						{ text: 'Next', accel: 'B', action: () => nextTrack().catch(log('next')) },
						SEPARATOR,
						{ text: 'Stop w/ fadeout', accel: 'Shift+V', action: () => stopWithFadeout().catch(log('stop with fadeout')) },
						check('Stop after current', stopAfter, 'Ctrl+V', toggleStopAfterCurrent),
						SEPARATOR,
						{ text: 'Back 5 seconds', accel: 'Left', action: () => seekBy(-5) },
						{ text: 'Fwd 5 seconds', accel: 'Right', action: () => seekBy(5) },
						SEPARATOR,
						check('Shuffle', !!playback.queue.shuffle, 'S', () => toggleShuffle().catch(log('shuffle'))),
						{
							text: 'Repeat',
							items: repeatModes.map(([mode, text]) => ({
								text,
								checked: repeat === mode,
								action: () => setRepeatMode(mode).catch(log('repeat'))
							}))
						}
					]
				},
				{
					text: 'Visualisation',
					items: [
						check('Spectrum analyser', uiState.visMode === 'analyzer', '', () => uiState.visMode !== 'analyzer' && toggleVisualizer()),
						check('Off', uiState.visMode === 'off', '', () => uiState.visMode !== 'off' && toggleVisualizer()),
						SEPARATOR,
						check('MilkDrop window', uiState.milkdrop, 'Ctrl+Shift+K', toggleMilkdrop)
					]
				},
				{
					text: 'Skins',
					items: [
						{ text: '<Base skin>', checked: list.current === null, action: () => switchSkin(null) },
						...list.skins.map((s) => ({ text: s.name, checked: list.current === s.path, action: () => switchSkin(s.path) })),
						SEPARATOR,
						{
							text: 'Load skin…',
							action: async () => {
								const picked = await open({
									title: 'Load Winamp skin',
									filters: [{ name: 'Winamp skins', extensions: ['wsz', 'zip'] }]
								});
								if (typeof picked !== 'string') return;
								// Same file name as one already in the folder (and not that very file): ask.
								const fileName = (/** @type {string} */ p) => p.split(/[\\/]/).pop()?.toLowerCase();
								const same = list.skins.find((s) => fileName(s.path) === fileName(picked) && s.path !== picked);
								const replace =
									!!same &&
									(await ask(`A skin named \u201c${same.name}\u201d is already in the skins folder. Replace it?`, {
										title: 'Load Winamp skin',
										kind: 'warning'
									}));
								if (same && !replace) return;
								api.importWszSkin(picked, replace).then(switchSkin, log('import skin'));
							}
						},
						{ text: 'Open skins folder', action: () => api.openSkinsDir().catch(log('open skins folder')) }
					]
				},
				{
					text: 'Window Settings',
					items: [
						placementItems('Playlist editor', 'playlist'),
						placementItems('Search', 'search'),
						placementItems('Equaliser', 'eq'),
						{
							text: 'Album art',
							items: [
								{ text: 'Hidden', checked: !art.open, action: () => setArt(false) },
								...artDocks.map(([dock, text]) => ({
									text: dock === 'right' && lyricsOnRight() ? 'Right of the player (lyrics are there)' : text,
									checked: art.open && art.dock === dock,
									enabled: !(dock === 'right' && lyricsOnRight()),
									action: () => setArt(true, dock)
								}))
							]
						},
						placementItems('Lyrics', 'lyrics')
					]
				},
				SEPARATOR,
				{ text: 'Back to Limusic', action: () => api.closeWinamp().catch(log('close winamp')) },
				{ text: 'Exit', accel: 'Alt+F4', action: () => api.quitApp().catch(log('quit')) }
			]
		};
	}, at);
}
