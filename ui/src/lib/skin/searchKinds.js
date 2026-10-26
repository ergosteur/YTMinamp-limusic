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
	// As Limusic's search page does it: songs and videos from their own filtered searches, whose
	// rows always carry the artist and length. The unfiltered response's song rows mix in videos
	// and podcast episodes and drop one of the two; they're only the fallback. Only the search
	// asked for goes into the account's history (#203).
	const [all, songs, videos] = await Promise.all([
		api.searchAll(query, true),
		api.search(query, false).catch(() => /** @type {api.SongItem[]} */ ([])),
		api.searchVideos(query).catch(() => /** @type {api.SongItem[]} */ ([]))
	]);
	/** @param {api.SongItem} s @returns {SearchRow} */
	const song = (s) => ({ ...s, rowKind: 'song' });
	/** @type {[string, SearchRow[]][]} */
	const sections = [
		['Top result', byTopArtist(all.top).map(rowOf)],
		// Every song (Limusic's All tab stops at five); four videos, as Limusic's does, so the
		// playlists aren't buried. The Videos kind has the rest.
		['Songs', songs.length ? songs.map(song) : all.songs.map(rowOf)],
		['Albums', all.albums.map(rowOf)],
		['Artists', all.artists.map(rowOf)],
		['Videos', videos.slice(0, 4).map(song)],
		['Playlists', all.playlists.map(rowOf)]
	];
	return sections.filter(([, rows]) => rows.length).flatMap(([title, rows]) => [header(title), ...rows]);
}

/**
 * The top result's songs, their artist filled in from the artist card above them where YouTube
 * left it out: it does when the query is that artist (Limusic only fills it in once the song plays,
 * so a song queued from here would sit in the playlist with no artist).
 * @param {api.BrowseItem[]} top the card first, then its rows
 */
function byTopArtist(top) {
	const card = top[0];
	if (card?.kind !== 'artist') return top;
	const run = { text: card.title, id: card.id };
	return top.map((item) =>
		item.kind === 'song' && !item.subtitle ? { ...item, subtitle: card.title, artistRuns: [run] } : item
	);
}

/** Play `row` as a click in Limusic would, shuffled if asked. @param {SearchRow | undefined} row @param {boolean} [shuffle] */
export async function playRow(row, shuffle = false) {
	if (!row || row.rowKind === 'header') return;
	const item = row.browse;
	if (!item) return api.play(row);
	if (item.kind === 'artist') return api.startRadio('artist', item.id);
	const page = item.kind === 'album' ? await api.getAlbum(item.id) : await api.getPlaylist(item.id);
	const sourceId = 'playlistId' in page ? page.playlistId : item.id;
	const continuation = 'continuation' in page ? page.continuation : undefined;
	await playFrom({ kind: item.kind, id: item.id, title: page.title ?? item.title }, page.items, null, sourceId, shuffle || undefined, continuation);
}

/**
 * Shuffle play, as Limusic's menus and pages have it: an album's or playlist's tracks, or an
 * artist's top songs (its page's Shuffle: the whole top-songs playlist, else the few on the page),
 * in a shuffled queue. Songs have none.
 * @param {SearchRow | undefined} row
 */
export async function shuffleRow(row) {
	const item = row?.browse;
	if (!item) return;
	if (item.kind !== 'artist') return playRow(row, true);
	const artist = await api.getArtist(item.id);
	const top = artist.topSongsId ? await api.getPlaylist(artist.topSongsId) : null;
	if (top?.items.length) return playFrom(item, top.items, null, artist.topSongsId, true, top.continuation);
	if (!artist.topSongs.length) throw new Error('no songs');
	return playFrom(item, artist.topSongs, null, undefined, true);
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
