// What the playlist editor's bottom buttons do (REM, MISC, and LIST to load a playlist or save
// the queue as one) on Limusic's real queue. Only the upcoming tracks can move or go: the playing row and the ones
// before it stay put, the same rule Limusic's own queue panel follows.
import * as api from '$lib/api';
import { auth, ownedByUser, playFrom, playback } from '$lib/player.svelte';
import { parseYtLink } from '$lib/ytlink';
import { flashMarquee } from './skinApi.js';
import { uiState } from './uiState.js';
import { markedRows, selectNone } from './selection.js';

/** Remove the selected tracks that are still to come, last first so the indices stay valid. */
export async function removeSelected() {
	const rows = markedRows(uiState.pl);
	if (!rows.length) return flashMarquee('Select a track first');
	const upcoming = rows.filter((i) => i > playback.queue.currentIndex);
	if (!upcoming.length) return flashMarquee("Can't remove a played track");
	for (const i of upcoming.reverse()) await api.removeFromQueue(i);
	selectNone(uiState.pl);
	if (upcoming.length < rows.length) flashMarquee('Played tracks stay put');
	else if (upcoming.length > 1) flashMarquee(`Removed ${upcoming.length} tracks`);
}

/** Crop to selected: remove every upcoming track that isn't selected, last first. */
export async function cropToSelected() {
	const keep = uiState.pl.marked;
	if (!keep.size) return flashMarquee('Select a track first');
	const { items, currentIndex } = playback.queue;
	let removed = 0;
	for (let i = items.length - 1; i > currentIndex; i--) {
		if (keep.has(i)) continue;
		await api.removeFromQueue(i);
		removed++;
	}
	selectNone(uiState.pl);
	flashMarquee(removed ? `Removed ${removed} tracks` : 'Nothing to crop');
}

/** Remove every upcoming track, last first so the indices stay valid. */
export async function clearUpcoming() {
	const { items, currentIndex } = playback.queue;
	for (let i = items.length - 1; i > currentIndex; i--) await api.removeFromQueue(i);
	selectNone(uiState.pl);
	flashMarquee('Queue cleared');
}

/**
 * Put the upcoming tracks in a new order, one move at a time (the backend has no bulk reorder).
 * @param {(upcoming: import('$lib/api').SongItem[]) => import('$lib/api').SongItem[]} order
 */
async function reorderUpcoming(order) {
	const { items, currentIndex } = playback.queue;
	const start = currentIndex + 1;
	const working = items.slice(start);
	const wanted = order([...working]);
	for (let t = 0; t < wanted.length; t++) {
		const from = working.indexOf(wanted[t], t);
		if (from === t) continue;
		await api.moveInQueue(start + from, start + t);
		working.splice(t, 0, ...working.splice(from, 1));
	}
}

/** @param {'title' | 'artist'} key */
export function sortUpcoming(key) {
	const text = (/** @type {import('$lib/api').SongItem} */ s) => (key === 'title' ? s.title : s.artists ?? '');
	return reorderUpcoming((up) => up.sort((a, b) => text(a).localeCompare(text(b)))).then(() =>
		flashMarquee(`Sorted by ${key}`)
	);
}

export function reverseUpcoming() {
	return reorderUpcoming((up) => up.reverse()).then(() => flashMarquee('Reversed'));
}

/** The library's playlists as last fetched, or null before the first fetch has come back. */
let known = /** @type {import('$lib/api').BrowseItem[] | null} */ (null);
let fetching = /** @type {Promise<import('$lib/api').BrowseItem[]> | null} */ (null);

/**
 * Fetch the library's playlists again (one fetch at a time). The account's come from YouTube
 * Music, seconds away at worst, so menus never wait on this: they show `libraryPlaylists()`.
 */
export function refreshLibrary() {
	fetching ??= api
		.getLibrary()
		.then((items) => {
			const playlists = items.filter((item) => item.kind === 'playlist');
			known = playlists;
			// Ask now, behind the menus, which of the rest songs can go into: once the account is
			// known, or the owner-name check would vouch for none and every page would be asked.
			knowAccount().then(() => playlists.forEach((p) => vouched(p) || canAddTo(p)));
			return playlists;
		})
		.finally(() => (fetching = null));
	return fetching;
}

/** Can't take songs whatever the page says: On Repeat is built here, Liked Music by liking. */
const NEVER = (/** @type {import('$lib/api').BrowseItem} */ p) => p.id === api.ON_REPEAT_ID || p.id === api.LIKED_MUSIC_ID;

/**
 * Accepts songs without a network check: a local playlist, or the user's own by Limusic's
 * owner-name check (`ownedByUser`, the subtitle's owner against the account's name).
 * @param {import('$lib/api').BrowseItem} p
 */
const vouched = (p) => !NEVER(p) && (api.isLocalPlaylist(p.id) || ownedByUser(p));

/** Playlist id → whether its own page says songs can go in (`owned`, or `collaborative`, which
 * also covers the user's own with collaboration on: that has no edit header). Asked once a run;
 * a failure is forgotten, to be asked again. */
const addable = new Map();
let asking = 0;
/** @type {(() => void)[]} */
const asks = [];

/**
 * Whether songs can go into `p`, from its page: two at a time, so a library's worth of saved
 * playlists doesn't land on YouTube at once.
 * @param {import('$lib/api').BrowseItem} p
 * @returns {Promise<boolean>}
 */
function canAddTo(p) {
	let answer = addable.get(p.id);
	if (!answer) {
		answer = new Promise((resolve) => {
			asks.push(() => {
				api
					.getPlaylist(p.id)
					.then((page) => resolve(page.owned || page.collaborative))
					.catch(() => {
						addable.delete(p.id);
						resolve(false);
					})
					.finally(() => {
						asking--;
						nextAsk();
					});
			});
			nextAsk();
		});
		addable.set(p.id, answer);
	}
	return answer;
}

function nextAsk() {
	while (asking < 2 && asks.length) {
		asking++;
		/** @type {() => void} */ (asks.shift())();
	}
}

/**
 * The playlists in `playlists` that accept songs: local ones and the user's own straight away, and
 * the rest (saved from someone else, or a collaborator's) as their pages say, waiting `wait` ms at
 * most for answers still coming: one that hasn't come is left out this time.
 * @param {import('$lib/api').BrowseItem[]} playlists
 * @param {number} [wait]
 */
export async function addablePlaylists(playlists, wait = 800) {
	await knowAccount();
	const candidates = playlists.filter((p) => !NEVER(p));
	const late = new Promise((resolve) => setTimeout(() => resolve(false), wait));
	const verdicts = await Promise.all(candidates.map((p) => vouched(p) || Promise.race([canAddTo(p), late])));
	return candidates.filter((_, i) => verdicts[i]);
}

/**
 * Load the account into Limusic's `auth` if this window hasn't: the Winamp windows start the way
 * the mini player does (initApp's mini path), which never asks, so its checks (signed in, and
 * `ownedByUser`'s owner name) would see nobody. Sign-ins and sign-outs after it reach every window.
 */
export async function knowAccount() {
	if (!auth.account) auth.account = await api.getAccount().catch(() => null);
}

/**
 * A playlist just made here, at the top of the menus' list before the next fetch has it.
 * @param {import('$lib/api').BrowseItem} item
 */
export function notePlaylist(item) {
	if (known) known = [item, ...known.filter((p) => p.id !== item.id)];
}

/**
 * The library's playlists for a menu, straight away: the last fetch's, refreshed behind it for
 * next time. Before any fetch has come back, the ones on this machine (SQLite, instant) and
 * `loading: true` while the account's are still on their way.
 */
export async function libraryPlaylists() {
	let failed = false;
	const refresh = refreshLibrary().catch((e) => {
		console.error('library failed', e);
		failed = true;
		return null;
	});
	if (known) return { playlists: known, loading: false };
	const local = await api.getLocalPlaylists().catch(() => []);
	// A fetch that's nearly done (the window's own, from when it opened) is worth a moment.
	const quick = await Promise.race([refresh, new Promise((r) => setTimeout(() => r(null), 150))]);
	if (quick) return { playlists: /** @type {import('$lib/api').BrowseItem[]} */ (quick), loading: false };
	// The account's didn't come (in time, or at all): this machine's, still loading only if not failed.
	return { playlists: local, loading: !failed };
}

/** Play a playlist from the library, replacing the queue, as Limusic's own page does. */
export async function loadPlaylist(/** @type {import('$lib/api').BrowseItem} */ item) {
	const page = await api.getPlaylist(item.id);
	await playFrom(item, page.items, null, item.id, undefined, page.continuation);
}

/**
 * Save the queue as a new playlist: in the YouTube Music library, or only on this machine.
 * Named for when it was saved; rename it in Limusic.
 * @param {boolean} local
 */
export async function saveQueue(local) {
	const items = playback.queue.items;
	if (!items.length) return flashMarquee('The queue is empty');
	const stamp = new Date().toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
	flashMarquee('Saving playlist...');
	const id = await api.createPlaylist(`Winamp queue ${stamp}`, local);
	if (local) await api.addToLocalPlaylist(id, items);
	else for (const item of items) await api.addToPlaylist(id, item.video_id, true);
	flashMarquee(`Saved ${items.length} tracks`);
	refreshLibrary().catch(() => {});
}

/**
 * Open a pasted YouTube / YouTube Music link (the ADD menu's Open URL). Limusic's own dialog goes
 * to the item's page; Winamp mode has no pages, so it plays: a song now (radio after it, as a
 * click in Limusic does), a playlist or album in place of the queue, an artist's radio.
 * @param {string} url
 * @returns {Promise<boolean>} false if it isn't a link Limusic can open
 */
export async function openLink(url) {
	const target = parseYtLink(url);
	if (!target) return false;
	if (target.kind === 'song') {
		await api.play(await api.song(target.id));
	} else if (target.kind === 'artist') {
		await api.startRadio('artist', target.id);
	} else {
		const page = target.kind === 'album' ? await api.getAlbum(target.id) : await api.getPlaylist(target.id);
		const source = { kind: target.kind, id: target.id, title: page.title ?? '' };
		const sourceId = 'playlistId' in page ? page.playlistId : target.id;
		const continuation = 'continuation' in page ? page.continuation : undefined;
		await playFrom(source, page.items, null, sourceId, undefined, continuation);
	}
	return true;
}
