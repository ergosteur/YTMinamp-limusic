# Test skins

Real Winamp 2.x / XMMS skins the `skin` crate's tests parse (`crates/skin/tests/fixtures.rs`),
each released under a free licence, so they can ship in this repository. Both come from the XMMS
skin collection mirrored at <https://qmmp.ylsoftware.com/files/skins/xmms-skins/>; each archive
carries its own readme with these terms.

| File | Skin | Author | Licence |
|---|---|---|---|
| `Debian_1.0.wsz` | Debian 1.0 (2004) | Jesper Schultz | [Artistic License](https://opensource.org/licenses/artistic-license-1.0) |
| `Antares_1a.wsz` | Antarès 1a (2004) | Jérôme Villette | GPL |

The tests also use the app's built-in skin, Nullsoft's Winamp 2.91 base skin
(`src-tauri/skins/base-2.91.wsz`; see the credits in `docs/WINAMP-MODE.md`).

Add a skin here only if its own readme grants redistribution: most skins don't say, which means
all rights reserved.
