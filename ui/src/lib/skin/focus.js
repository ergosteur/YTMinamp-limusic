// Which titlebar is lit. Winamp lights the active window's titlebar and dims the others'. Here the
// app window has to have focus, and in the Winamp window, where several of Winamp's windows are
// docked into one, the active one is the one last clicked (the main window to start with). A
// floating panel is its own only window (`setActivePart` with its kind when it opens).

/** @typedef {'main' | import('./layout.js').PanelKind | 'url' | 'milkdrop' | 'eqsave' | 'fileinfo'} Part */

let windowFocused = typeof document !== 'undefined' && document.hasFocus();
/** @type {Part} */
let active = 'main';
if (typeof window !== 'undefined') {
	window.addEventListener('focus', () => (windowFocused = true));
	window.addEventListener('blur', () => (windowFocused = false));
}

/** Make `part` the active window here (a click on it). @param {Part} part */
export function setActivePart(part) {
	active = part;
}

/** The window last clicked here (a key press means this app window has focus). */
export function activePart() {
	return active;
}

/** Whether `part`'s titlebar is lit. @param {Part} part */
export function isLit(part) {
	return windowFocused && active === part;
}
