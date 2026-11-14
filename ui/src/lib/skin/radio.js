// Internet radio (src-tauri/src/radio.rs): stations are queue rows whose videoId is
// `RADIO:<url>`. Opened from a playlist file (.m3u, .m3u8, .pls) or a pasted stream or playlist
// URL, and played in place of the queue, as Winamp opens a playlist.
import { invoke } from '@tauri-apps/api/core';
import { open } from '@tauri-apps/plugin-dialog';
import * as api from '$lib/api';
import { flashMarquee } from './skinApi.js';

export const STATION_PREFIX = 'RADIO:';

/** @param {string | undefined | null} id */
export const isStation = (id) => !!id && id.startsWith(STATION_PREFIX);

/** @param {api.SongItem[]} stations @param {string} name */
async function playStations(stations, name) {
	await api.playPlaylist(stations, 0, undefined, name);
	flashMarquee(stations.length > 1 ? `${name}: ${stations.length} stations` : name);
}

/** Pick a playlist file and play its stations (LIST ▸ Load, ADD). */
export async function openPlaylistFile() {
	const path = await open({
		multiple: false,
		directory: false,
		title: 'Open playlist',
		filters: [{ name: 'Playlists (*.m3u, *.m3u8, *.pls)', extensions: ['m3u', 'm3u8', 'pls'] }]
	});
	if (typeof path !== 'string') return;
	/** @type {api.SongItem[]} */
	const stations = await invoke('radio_open_file', { path });
	const name = path.split(/[\\/]/).pop()?.replace(/\.(m3u8?|pls)$/i, '') || 'Playlist';
	await playStations(stations, name);
}

/**
 * A pasted URL that isn't YouTube or Spotify: a stream plays as a station, a playlist URL as its
 * stations. False when it isn't a web URL at all.
 * @param {string} url
 */
export async function openStationUrl(url) {
	/** @type {api.SongItem[] | null} */
	const stations = await invoke('radio_open_url', { url });
	if (!stations) return false;
	await playStations(stations, stations.length === 1 ? stations[0].title : 'Internet radio');
	return true;
}
