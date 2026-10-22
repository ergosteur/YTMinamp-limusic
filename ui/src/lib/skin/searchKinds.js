// What the search panel searches for (the "Songs ▾" button in its box): songs, videos, albums,
// artists, playlists, or all of them in sections, through Limusic's own searches. Every kind comes
// back as rows the list draws like songs: a song row is a SongItem; an album, artist or playlist
// row carries its BrowseItem (`browse`) and its YouTube Music link; "All" adds header rows, which
// can't be selected or played. Playing a row does what a click on it does in Limusic, short of
// opening a page (Winamp mode has none): a song plays, an album or playlist replaces the queue, an
// artist starts its radio (playlistActions.js `openLink` does the same for pasted links).
import * as api from '$lib/api';
import { asSong } from '$lib/browse';
import { playFrom } from '$lib/player.svelte';

/** @typedef {'songs' | 'videos' | 'albums' | 'artists' | 'playlists' | 'all'} SearchKind */
/**
 * @typedef {api.SongItem & { rowKind?: 'header' | 'song' | 'album' | 'artist' | 'playlist',
 *   browse?: api.BrowseItem, link?: string }} SearchRow
 */

/** @type {[SearchKind, string][]} */
export const SEARCH_KINDS = [
	['songs', 'Songs'],
	['videos', 'Videos'],
	['albums', 'Albums'],
	['artists', 'Artists'],
	['playlists', 'Playlists'],
	['all', 'All']
];

/** The "Songs ▾" button's width, at the right end of the search box (it gives up that much). */
export const KIND_BUTTON_W = 54;

/** The button's label for `kind`. @param {SearchKind} kind */
export const kindLabel = (kind) => SEARCH_KINDS.find(([k]) => k === kind)?.[1] ?? 'Songs';

/** A YouTube Music link for an album, artist or playlist. @param {api.BrowseItem} item */
function browseLink(item) {
	if (item.kind === 'artist') return `https://music.youtube.com/channel/${item.id}`;
	// Albums and playlists are browsed as VL<playlist id> / MPRE…; the browse URL opens either.
	return `https://music.youtube.com/browse/${item.id}`;
}

/** A row for a BrowseItem: a song card becomes a playable song. @param {api.BrowseItem} item @returns {SearchRow} */
function rowOf(item) {
	if (item.kind === 'song') return { ...asSong(item), rowKind: 'song' };
	return {
		video_id: '',
		title: item.title,
		artists: item.subtitle ?? '',
		thumbnail: item.thumbnail,
		rowKind: item.kind,
		browse: item,
		link: browseLink(item)
	};
}

/** @param {string} title @returns {SearchRow} */
const header = (title) => ({ video_id: '', title, artists: '', rowKind: 'header' });

/**
 * The rows for `query`, searched as `kind`.
 * @param {SearchKind} kind @param {string} query
 * @returns {Promise<SearchRow[]>}
 */
export async function searchRows(kind, query) {
	if (kind === 'songs') return (await api.search(query, true)).map((s) => ({ ...s, rowKind: 'song' }));
	if (kind === 'videos') return (await api.searchVideos(query)).map((s) => ({ ...s, rowKind: 'song' }));
	if (kind !== 'all') return (await api.searchCards(query, kind)).map(rowOf);
	const all = await api.searchAll(query, true);
	/** @type {[string, api.BrowseItem[]][]} */
	const sections = [
		['Top result', all.top],
		['Songs', all.songs],
		['Albums', all.albums],
		['Artists', all.artists],
		['Playlists', all.playlists]
	];
	return sections.filter(([, items]) => items.length).flatMap(([title, items]) => [header(title), ...items.map(rowOf)]);
}

/** Play `row` as a click in Limusic would. @param {SearchRow | undefined} row */
export async function playRow(row) {
	if (!row || row.rowKind === 'header') return;
	const item = row.browse;
	if (!item) return api.play(row);
	if (item.kind === 'artist') return api.startRadio('artist', item.id);
	const page = item.kind === 'album' ? await api.getAlbum(item.id) : await api.getPlaylist(item.id);
	const sourceId = 'playlistId' in page ? page.playlistId : item.id;
	const continuation = 'continuation' in page ? page.continuation : undefined;
	await playFrom({ kind: item.kind, id: item.id, title: page.title ?? item.title }, page.items, null, sourceId, undefined, continuation);
}

/**
 * The songs in `rows`, for the queue: songs as they are, an album's or playlist's tracks
 * fetched, artists and headers left out (there's no queueing a radio).
 * @param {SearchRow[]} rows
 * @returns {Promise<api.SongItem[]>}
 */
export async function songsIn(rows) {
	/** @type {api.SongItem[]} */
	const out = [];
	for (const row of rows) {
		if (row.rowKind === 'header' || row.rowKind === 'artist') continue;
		const item = row.browse;
		if (!item) out.push(row);
		else if (item.kind === 'album') out.push(...(await api.getAlbum(item.id)).items);
		else if (item.kind === 'playlist') out.push(...(await api.getPlaylist(item.id)).items);
	}
	return out;
}

/** Whether `row` is a song (ratings, the library and playlists only take songs). @param {SearchRow | undefined} row */
export const isSongRow = (row) => !!row && row.rowKind !== 'header' && !row.browse;
