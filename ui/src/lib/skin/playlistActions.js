// What the playlist editor's bottom buttons do (REM, MISC, LIST to load a playlist, and SEL —
// with no selection to work on here — to save the queue as one),
// on Limusic's real queue. Only the upcoming tracks can move or go: the playing row and the ones
// before it stay put, the same rule Limusic's own queue panel follows.
import * as api from '$lib/api';
import { playFrom, playback } from '$lib/player.svelte';
import { parseYtLink } from '$lib/ytlink';
import { flashMarquee } from './skinApi.js';
import { uiState } from './uiState.js';

/** Remove the selected track, if it's still to come. */
export async function removeSelected() {
	const i = uiState.pl.selected;
	if (i === null) return flashMarquee('Select a track first');
	if (i <= playback.queue.currentIndex) return flashMarquee("Can't remove a played track");
	await api.removeFromQueue(i);
	uiState.pl.selected = null;
}

/** Remove every upcoming track, last first so the indices stay valid. */
export async function clearUpcoming() {
	const { items, currentIndex } = playback.queue;
	for (let i = items.length - 1; i > currentIndex; i--) await api.removeFromQueue(i);
	uiState.pl.selected = null;
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

/** The library's playlists, for the load menu. */
export async function libraryPlaylists() {
	return (await api.getLibrary()).filter((item) => item.kind === 'playlist');
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
