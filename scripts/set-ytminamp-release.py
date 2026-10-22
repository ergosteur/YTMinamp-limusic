#!/usr/bin/env python3
"""Set ytminamp's build number N, the `.N` in the `v<Limusic version>-ytminamp.N` tags.

The app's own `version` stays Limusic's (tauri.conf.json), so N goes everywhere an installer or
the app shows a version of its own:

- the RPM's Release field: `ytminamp-1.3.0-N`, so dnf sees each build as an upgrade;
- the MSI's version: Windows Installer compares only major.minor.build (the build at most 65535),
  so N rides in the third field as patch * 1000 + N: Limusic 1.3.0 build 3 is MSI 1.3.3, Limusic
  1.3.1 build 1 is MSI 1.3.1001, and they sort in release order;
- the About box (`ui/src/lib/skin/release.js`).

The release workflows refuse a tag whose N or version doesn't match these. Start again from 1
when the Limusic version changes.

Usage: scripts/set-ytminamp-release.py N
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONF = ROOT / "src-tauri" / "tauri.conf.json"
RELEASE_JS = ROOT / "ui" / "src" / "lib" / "skin" / "release.js"


def msi_version(version: str, n: int) -> str:
    major, minor, patch = (int(p) for p in version.split("."))
    build = patch * 1000 + n
    if not (0 < n < 1000 and major <= 255 and minor <= 255 and build <= 65535):
        sys.exit(f"{version} build {n} doesn't fit an MSI version")
    return f"{major}.{minor}.{build}"


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        sys.exit(__doc__)
    n = int(sys.argv[1])
    text = CONF.read_text()
    conf = json.loads(text)
    version = conf["version"]
    msi = msi_version(version, n)

    # Edit the text rather than re-dumping the JSON, so the file keeps upstream's (Prettier's)
    # formatting. Anchored on exact text: a change upstream that moves it fails here, loudly.
    rpm = '      "rpm": {\n'
    if text.count(rpm) != 1:
        sys.exit(f"{CONF.name}: no single bundle.linux.rpm block")
    if re.search(r'"rpm": \{\n\s*"release": "[^"]*"', text):
        text = re.sub(r'("rpm": \{\n\s*"release": )"[^"]*"', rf'\g<1>"{n}"', text, count=1)
    else:
        text = text.replace(rpm, rpm + f'        "release": "{n}",\n')
    wix = re.compile(r'"wix": \{ "version": "[^"]*" \}')
    if wix.search(text):
        text = wix.sub(f'"wix": {{ "version": "{msi}" }}', text, count=1)
    else:
        linux = '    "linux": {\n'
        if text.count(linux) != 1:
            sys.exit(f"{CONF.name}: no single bundle.linux block")
        text = text.replace(linux, f'    "windows": {{\n      "wix": {{ "version": "{msi}" }}\n    }},\n' + linux)
    conf = json.loads(text)
    assert conf["bundle"]["linux"]["rpm"]["release"] == str(n)
    assert conf["bundle"]["windows"]["wix"]["version"] == msi
    CONF.write_text(text)
    RELEASE_JS.write_text(
        "// Set by scripts/set-ytminamp-release.py: this build's N in v<Limusic version>-ytminamp.N.\n"
        f"export const YTMINAMP_RELEASE = {n};\n"
    )
    print(f"v{version}-ytminamp.{n}: RPM {version}-{n}, MSI {msi}")


if __name__ == "__main__":
    main()
