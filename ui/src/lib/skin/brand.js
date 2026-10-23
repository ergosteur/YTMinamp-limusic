// What the UI calls this build, the counterpart of src-tauri/src/brand.rs: one place, so the
// upstream components that show a name or version change by one identifier each.
import { YTMINAMP_RELEASE } from './release.js';

/** The name people see. */
export const APP_NAME = 'YTMinamp (limusic)';

/** Limusic's `version` (what `getVersion()` gives) as this build's full one: `1.3.0-ytminamp.6`. */
export const fullVersion = (/** @type {string} */ version) => `${version}-ytminamp.${YTMINAMP_RELEASE}`;
