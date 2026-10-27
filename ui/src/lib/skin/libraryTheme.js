// The Media Library window's colours: Limusic's theme tokens (routes/layout.css) set from the
// skin's genex.bmp palette. Lists and pages in the item colours, the sidebar in the window's,
// square corners, each text colour nudged until it reads (contrast.js). A skin without genex.bmp
// leaves Limusic's own default theme, dark when the skin's main window is. Set on that window's
// root alone, so Limusic's own window keeps its theme.
import { luminance, mixHex, readable } from './contrast.js';

/** Text, and the selection colour (active links, the sidebar's current page). */
const TEXT = 4.5;
const LARGE = 3;

/**
 * The tokens for `g`.
 * @param {import('$lib/api').SkinGenex} g
 * @returns {Record<string, string>}
 */
export function libraryTokens(g) {
	const fg = readable(g.itemFg, [g.itemBg], TEXT);
	const muted = mixHex(fg, 0.1, g.itemBg);
	// The pages' and the sidebar's own: one colour can't read on both when one is light and the
	// other dark (an LCD-green list in a black body), and black, the fallback, then fails the pages.
	const primary = readable(g.selection, [g.itemBg], LARGE);
	const sidebarPrimary = readable(g.selection, [g.windowBg], LARGE);
	const accent = mixHex(g.selection, 0.6, g.itemBg);
	const sidebarFg = readable(g.windowText, [g.windowBg], TEXT);
	const headerText = readable(g.headerText, [g.headerBg], TEXT);
	return {
		'--background': g.itemBg,
		'--foreground': fg,
		'--card': mixHex(fg, 0.06, g.itemBg),
		'--card-foreground': fg,
		'--popover': g.windowBg,
		'--popover-foreground': sidebarFg,
		'--primary': primary,
		'--primary-foreground': readable(g.itemFg, [primary], TEXT),
		'--secondary': g.headerBg,
		'--secondary-foreground': headerText,
		'--muted': muted,
		'--muted-foreground': readable(mixHex(fg, 0.65, g.itemBg), [g.itemBg, muted], LARGE),
		'--accent': accent,
		'--accent-foreground': readable(fg, [accent], TEXT),
		'--border': g.divider,
		'--input': g.divider,
		'--ring': primary,
		'--sidebar': g.windowBg,
		'--sidebar-foreground': sidebarFg,
		'--sidebar-primary': sidebarPrimary,
		'--sidebar-primary-foreground': readable(g.itemFg, [sidebarPrimary], TEXT),
		'--sidebar-accent': g.headerBg,
		'--sidebar-accent-foreground': headerText,
		'--sidebar-border': g.divider,
		'--sidebar-ring': sidebarPrimary,
		'--radius': '0rem'
	};
}

/** The tokens last set, to take off again for a skin without genex.bmp. */
let applied = /** @type {string[]} */ ([]);

/**
 * Put the skin's tokens on this window's root, or take them off for Limusic's own, and Limusic's
 * dark styles on when the lists (or, without genex.bmp, the main window) are dark.
 * @param {import('$lib/api').SkinPayload} skin
 */
export function applyLibraryTheme(skin) {
	const root = document.documentElement;
	for (const name of applied) root.style.removeProperty(name);
	const tokens = skin.genex ? libraryTokens(skin.genex) : {};
	for (const [name, value] of Object.entries(tokens)) root.style.setProperty(name, value);
	applied = Object.keys(tokens);
	root.classList.toggle('dark', skin.genex ? luminance(skin.genex.itemBg) < 0.18 : skin.mainDark);
}
