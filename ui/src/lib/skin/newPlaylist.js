// A menu's "Add to new playlist...": the small naming window (NewPlaylistWindow.svelte, label
// "winamp-newpl") asks for a name, and the window whose menu asked makes the playlist and adds
// the songs, since it holds Limusic's library state. Every Winamp window hears every event
// (Tauri's global `listen`), so the asking window claims the dialog by its label and any other
// drops what it had waiting. Where it goes is the dialog's pick (the account or this machine),
// and always this machine for files on disk.
import { emit, listen } from '@tauri-apps/api/event';
import { getCurrentWindow } from '@tauri-apps/api/window';
import * as api from '$lib/api';
import { addSongsToPlaylist, auth, createLibraryPlaylist } from '$lib/player.svelte';
import { doubleFactor } from './pixels.js';
import { knowAccount, notePlaylist } from './playlistActions.js';
import { flashMarquee } from './skinApi.js';

/** The asking window's label: the others drop theirs. */
const CLAIM = 'winamp-newpl-claim';
/** From the dialog: `{ name, local }`, the name typed and whether it stays on this machine. */
export const NEWPL_NAME = 'winamp-newpl-name';
/** To the dialog: the name arrived, the playlist is on its way. */
export const NEWPL_TAKEN = 'winamp-newpl-taken';
/** To the dialog: done (null) or why not (the dialog says so and stays open). */
export const NEWPL_DONE = 'winamp-newpl-done';

/** The songs waiting for a name, fetched when it comes (an album's tracks, say). */
let waiting = /** @type {(() => Promise<api.SongItem[]>) | null} */ (null);
let busy = false;
let wired = false;

/**
 * Open the naming window for these songs.
 * @param {() => Promise<api.SongItem[]>} songs
 */
export function newPlaylistFor(songs) {
	wire();
	waiting = songs;
	emit(CLAIM, getCurrentWindow().label).catch(() => {});
	const f = doubleFactor();
	api.openWinampPanel('newpl', 275 * f, 70 * f).catch((e) => console.error('open new playlist dialog failed', e));
}

function wire() {
	if (wired) return;
	wired = true;
	const me = getCurrentWindow().label;
	listen(CLAIM, (e) => {
		if (e.payload !== me) waiting = null;
	});
	listen(NEWPL_NAME, (e) => {
		const { name, local } = /** @type {{ name: string, local: boolean }} */ (e.payload);
		if (waiting && !busy) create(name, local, waiting);
	});
}

/** @param {string} name @param {boolean} picked this machine @param {() => Promise<api.SongItem[]>} songs */
async function create(name, picked, songs) {
	busy = true;
	emit(NEWPL_TAKEN).catch(() => {});
	try {
		const items = await songs();
		await knowAccount();
		// A file on disk has no YouTube identity, so a batch holding one can only stay here.
		const local = picked || !auth.account?.signedIn || items.some((s) => api.isLocalId(s.video_id));
		const playlist = await createLibraryPlaylist(name, local);
		notePlaylist(playlist);
		waiting = null;
		// Limusic's add says how it went itself (skinApi.js tickerToast).
		if (items.length) await addSongsToPlaylist(playlist, items);
		else flashMarquee(`Made ${name}${local ? ' (on this computer)' : ''}`, 6_000);
		emit(NEWPL_DONE, null).catch(() => {});
	} catch (e) {
		emit(NEWPL_DONE, `Couldn't make it: ${e}`).catch(() => {});
	} finally {
		busy = false;
	}
}
