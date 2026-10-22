// Multi-selection in the playlist and search lists, the way OS lists do it: a click selects one
// row, Ctrl+click toggles one, Shift+click selects the range from the anchor (the last plain or
// Ctrl click), Ctrl+Shift+click adds that range. `selected` stays the one row the keyboard moves
// and Enter or a double-click plays; `marked` is every highlighted row.

/** @typedef {{ selected: number | null, marked: Set<number>, anchor: number | null }} Selectable */

/**
 * A click on row `i`.
 * @param {Selectable} view @param {number} i @param {{ ctrl: boolean, shift: boolean }} keys
 */
export function clickRow(view, i, { ctrl, shift }) {
	if (shift) {
		const from = view.anchor ?? view.selected ?? i;
		const range = [];
		for (let r = Math.min(from, i); r <= Math.max(from, i); r++) range.push(r);
		view.marked = new Set(ctrl ? [...view.marked, ...range] : range);
		view.anchor = from;
	} else if (ctrl) {
		const marked = new Set(view.marked);
		if (marked.has(i)) marked.delete(i);
		else marked.add(i);
		view.marked = marked;
		view.anchor = i;
	} else {
		view.marked = new Set([i]);
		view.anchor = i;
	}
	view.selected = i;
}

/** Select just row `i` (the keyboard, a right-click outside the selection). @param {Selectable} view @param {number} i */
export function selectOnly(view, i) {
	view.marked = new Set([i]);
	view.anchor = i;
	view.selected = i;
}

/** @param {Selectable} view */
export function selectNone(view) {
	view.marked = new Set();
	view.anchor = null;
	view.selected = null;
}

/**
 * @param {Selectable} view @param {number} count rows in the list
 * @param {(i: number) => boolean} [selectable] leave out rows that aren't (a search's headers)
 */
export function selectAll(view, count, selectable = () => true) {
	view.marked = new Set(Array.from({ length: count }, (_, i) => i).filter(selectable));
}

/** @param {Selectable} view @param {number} count @param {(i: number) => boolean} [selectable] */
export function invertSelection(view, count, selectable = () => true) {
	view.marked = new Set(Array.from({ length: count }, (_, i) => i).filter((i) => selectable(i) && !view.marked.has(i)));
}

/** The selected rows, in list order. @param {Selectable} view */
export function markedRows(view) {
	return [...view.marked].sort((a, b) => a - b);
}

/** Forget rows past the end of a list that got shorter. @param {Selectable} view @param {number} count */
export function trimSelection(view, count) {
	if ([...view.marked].some((i) => i >= count)) view.marked = new Set([...view.marked].filter((i) => i < count));
	if (view.selected !== null && view.selected >= count) view.selected = null;
	if (view.anchor !== null && view.anchor >= count) view.anchor = null;
}
