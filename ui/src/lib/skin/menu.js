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
import { LogicalPosition } from '@tauri-apps/api/dpi';
import { open } from '@tauri-apps/plugin-dialog';
import * as api from '$lib/api';
import { playback } from '$lib/player.svelte';
import { message } from '@tauri-apps/plugin-dialog';
import { getVersion } from '@tauri-apps/api/app';
import {
	lyricsOnRight,
	nextTrack,
	openSearch,
	openUrlDialog,
	pause,
	play,
	playResult,
	prevTrack,
	queueResult,
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
	toggleMilkdrop,
	toggleShuffle,
	zoomLyrics
} from './skinApi.js';
import { toggleTimeRemaining, toggleVisualizer } from './input.js';
import { EQ_PRESETS } from './render/equalizer.js';
import { lyricsNow, lyricsShow, toggleLyricsShow } from './lyrics.js';
import { zoomFactor } from './pixels.js';
import { YTMINAMP_RELEASE } from './release.js';
import { uiState } from './uiState.js';
import {
	clearUpcoming,
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
			const id = String(actions.size);
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
				listening = true;
				await listen('winamp-menu', (e) => actions.get(/** @type {string} */ (e.payload))?.());
			}
			actions = new Map();
			try {
				await api.winampPopupMenu(toEntries(options.items ?? []), at.x, at.y);
				gtkMenus = true;
				return;
			} catch {
				gtkMenus = false;
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
	return popup(
		async () => ({
			items: [
				{ text: 'Play', action: () => playResult(index).catch(log('play')) },
				{ text: 'Play next', action: () => queueResult(index, true).catch(log('play next')) },
				{ text: 'Add to queue', action: () => queueResult(index, false).catch(log('add to queue')) }
			]
		}),
		at
	);
}

/**
 * The playlist's bottom buttons, one short menu each. LIST
 * loads a playlist (some skins label it LOAD LIST); SEL, which has no selection to work on here,
 * saves the queue as one.
 * @param {'add' | 'rem' | 'sel' | 'misc' | 'list'} which
 * @param {MenuAt} at
 */
export function showPlaylistMenu(which, at) {
	return popup(async () => {
		if (which === 'add') {
			return {
				items: [
					{ text: 'Search YouTube Music', action: requestSearch },
					{ text: 'Open YouTube URL…', action: openUrlDialog }
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
			return { items: [...(await libraryItems()), SEPARATOR, { text: 'Saving the queue as a playlist is under SEL', enabled: false }] };
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
		const signedIn = await api
			.getAccount()
			.then((a) => a.signedIn)
			.catch(() => false);
		return {
			items: [
				signedIn
					? { text: 'Save queue to my YouTube Music library', action: () => saveQueue(false).catch(log('save')) }
					: { text: 'Save queue to YouTube Music (sign in first)', enabled: false },
				{ text: 'Save queue as a local playlist', action: () => saveQueue(true).catch(log('save')) }
			]
		};
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
	return popup(
		async () => ({
			items: [
				...EQ_PRESETS.map(([name, preamp, bands]) => ({ text: name, action: () => applyPreset(preamp, bands) })),
				SEPARATOR,
				{ text: 'Reset (flat)', action: () => applyPreset(50, Array(10).fill(50)) }
			]
		}),
		at
	);
}

/**
 * The lyrics panel's menu: Limusic's romanization and translation switches, and the text size.
 * @param {MenuAt} at
 */
export function showLyricsMenu(at) {
	return popup(async () => {
		const lines = lyricsNow().lyrics?.lines ?? [];
		const has = (/** @type {'romanized' | 'translation'} */ what) => lines.some((l) => l[what]);
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
				{ text: 'Normal size', accel: 'Ctrl+0', action: () => zoomLyrics(0) }
			]
		};
	}, at);
}

/**
 * The MilkDrop window's menu. `controls` is the window's own (MilkdropWindow.svelte).
 * @param {{ next: () => void, previous: () => void, hardCut: () => void, toggleAuto: () => void,
 *   auto: boolean, preset: string, toggleFullscreen: () => Promise<void>, close: () => void }} controls
 * @param {MenuAt} at
 */
export function showMilkdropMenu(controls, at) {
	return popup(
		async () => ({
			items: [
				{ text: controls.preset || 'Loading presets...', enabled: false },
				SEPARATOR,
				{ text: 'Next preset', accel: 'N', action: () => controls.next() },
				{ text: 'Previous preset', accel: 'P', action: () => controls.previous() },
				{ text: 'Random preset, no blend', action: () => controls.hardCut() },
				{ text: 'Change presets automatically', checked: controls.auto, action: () => controls.toggleAuto() },
				SEPARATOR,
				{ text: 'Fullscreen', accel: 'F', action: () => controls.toggleFullscreen().catch(log('fullscreen')) },
				{ text: 'Close', accel: 'Ctrl+Shift+K', action: () => controls.close() }
			]
		}),
		at
	);
}

/** @param {number} preamp @param {number[]} bands */
function applyPreset(preamp, bands) {
	uiState.eq.preamp = preamp;
	uiState.eq.bands = [...bands];
	saveEq();
}

/** About ytminamp: the version and who it stands on. */
async function showAbout() {
	const version = await getVersion().catch(() => '?');
	await message(
		`YTMinamp (limusic) ${version} (ytminamp.${YTMINAMP_RELEASE})\n\n` +
			'Limusic with a classic Winamp 2.x skin mode.\n\n' +
			'Built on Limusic (SimoHypers, GPL-3.0-or-later). Skin layout, marquee and analyzer after ' +
			'Webamp (Jordan Eldredge and contributors, MIT); FFT from vis_classic (Mike Lynch, via ' +
			'WACUP, MIT). The built-in skin is Nullsoft\u2019s Winamp 2.91 base skin. Winamp is a ' +
			'trademark of its owner; this is an unofficial fan project.\n\n' +
			'Full credits: docs/WINAMP-MODE.md',
		{ title: 'About YTMinamp', kind: 'info' }
	);
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
		const [list, library] = await Promise.all([
			api.listWszSkins().catch((e) => {
				log('list skins')(e);
				return { dir: '', skins: [], current: null };
			}),
			libraryItems()
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
		/** @param {string} text @param {boolean} on @param {string} accel @param {() => unknown} action */
		const check = (text, on, accel, action) => ({ text, checked: on, accel, action });
		return {
			items: [
				{ text: 'About ytminamp…', action: () => showAbout().catch(log('about')) },
				SEPARATOR,
				{
					text: 'Play',
					items: [
						{ text: 'URL…', accel: 'Ctrl+L', action: openUrlDialog },
						{ text: 'Search…', accel: 'J', action: requestSearch },
						{ text: 'Playlist from Library', items: library }
					]
				},
				SEPARATOR,
				check('Playlist Editor', uiState.pl.open, 'Alt+E', () => togglePanel('playlist')),
				check('Search', uiState.search.open, '', () => togglePanel('search')),
				check('Equaliser', uiState.eq.open, 'Alt+G', () => togglePanel('eq')),
				check('Album Art', art.open, 'Alt+A', () => togglePanel('art')),
				check('Lyrics', uiState.lyrics.open, 'Alt+Y', () => togglePanel('lyrics')),
				SEPARATOR,
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
								api.importWszSkin(picked).then(switchSkin, log('import skin'));
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
