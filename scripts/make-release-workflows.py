#!/usr/bin/env python3
"""Generate ytminamp's release workflows from upstream Limusic's.

Upstream's linux/windows/macos-release.yml carry years of hard-won platform fixes (glibc floor,
AppImage TLS repair, foreign-distro smoke tests, libmpv import lib, dylibbundler). Editing them
in place would conflict on every upstream merge, so this derives .github/workflows/ytminamp-*.yml
from them instead, changing only what has to change:

- tags are `v<version>-ytminamp.N` (the Limusic version it's built on, then ours);
- no updater: no signing key, no `.sig`, no latest.json, no beta pointer, no "Latest" dance;
- our names: bundles are `ytminamp*` (productName / mainBinaryName in tauri.conf.json);
- upstream's AppImage helper scripts run as renamed copies made at build time;
- one plain upload step attaches the installers to the release.

Re-run after an upstream merge that touches their workflows: `scripts/make-release-workflows.py`.
Every substitution must match exactly, so a change upstream that breaks an assumption here fails
loudly instead of producing a subtly wrong workflow.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def sub(text: str, old: str, new: str, count: int | None = 1) -> str:
    """Replace `old` exactly `count` times (any number if None), or stop with an error."""
    n = text.count(old)
    if (count is None and n == 0) or (count is not None and n != count):
        sys.exit(f"expected {count or 'some'} of {old!r}, found {n}")
    return text.replace(old, new)


def cut_step(text: str, name: str) -> str:
    """Drop the step called `name`, with the comment block right above it."""
    m = re.search(
        rf"((?:      #[^\n]*\n)*)      - name: {re.escape(name)}\n.*?(?=\n(?:      #[^\n]*\n)*      - (?:name|uses):|\Z)",
        text,
        re.S,
    )
    if not m:
        sys.exit(f"no step {name!r}")
    return text[: m.start()] + text[m.end() :].lstrip("\n")


def until_step(text: str, name: str) -> str:
    """Everything before the step called `name` (and the comments above it)."""
    m = re.search(rf"(?:      #[^\n]*\n)*      - name: {re.escape(name)}\n", text)
    if not m:
        sys.exit(f"no step {name!r}")
    return text[: m.start()].rstrip("\n") + "\n"


VERSION_CHECK = """      - name: Check the tag matches the app version
        shell: bash
        run: |
          VERSION="$(jq -r .version src-tauri/tauri.conf.json)"
          echo "VERSION=$VERSION" >> "$GITHUB_ENV"
          echo "PRERELEASE=false" >> "$GITHUB_ENV"
          # ytminamp tags: v<the Limusic version it's built on>-ytminamp.<our build N>, N as set by
          # scripts/set-ytminamp-release.py (RPM release, MSI version, About box).
          N="$(jq -r .bundle.linux.rpm.release src-tauri/tauri.conf.json)"
          echo "YTMINAMP_TAG=v$VERSION-ytminamp.$N" >> "$GITHUB_ENV"
          IFS=. read -r MA MI PA <<< "$VERSION"
          MSI="$(jq -r .bundle.windows.wix.version src-tauri/tauri.conf.json)"
          problem=""
          [ "${{ steps.rel.outputs.tag }}" = "v$VERSION-ytminamp.$N" ] || problem="the tag ${{ steps.rel.outputs.tag }} isn't v$VERSION-ytminamp.$N"
          [ "$MSI" = "$MA.$MI.$((PA * 1000 + N))" ] || problem="MSI version $MSI doesn't match build $N: run scripts/set-ytminamp-release.py $N"
          grep -q "YTMINAMP_RELEASE = $N;" ui/src/lib/skin/release.js || problem="ui/src/lib/skin/release.js isn't build $N: run scripts/set-ytminamp-release.py $N"
          if [ -n "$problem" ]; then
            if [ "${{ inputs.dry_run }}" = "true" ]; then
              echo "::warning::dry run: $problem"
            else
              echo "::error::$problem"
              exit 1
            fi
          fi
"""


def upload_step(files: str) -> str:
    return f"""
      # No updater in ytminamp (tauri.conf.json), so no latest.json, signatures or beta pointer:
      # attach the installers to the release and that's it.
      - name: Attach to the release
        if: ${{{{ !inputs.dry_run }}}}
        shell: bash
        env:
          GH_TOKEN: ${{{{ github.token }}}}
        run: |
          set -euo pipefail
          shopt -s nullglob
          FILES=({files})
          [ ${{#FILES[@]}} -gt 0 ] || {{ echo "::error::nothing to attach"; find target/release/bundle -maxdepth 2; exit 1; }}
          # Named for the whole tag (ytminamp_1.3.0-ytminamp.3_...), so one release's files can't be
          # mistaken for another's: the bundler only knows the Limusic version.
          OUT="$RUNNER_TEMP/attach"
          mkdir -p "$OUT"
          for f in "${{FILES[@]}}"; do
            name="$(basename "$f")"
            cp "$f" "$OUT/${{name/_${{VERSION}}_/_${{YTMINAMP_TAG#v}}_}}"
          done
          gh release upload "${{{{ steps.rel.outputs.tag }}}}" "$OUT"/* --repo "$GITHUB_REPOSITORY" --clobber
          ls "$OUT"
"""


def common(text: str, platform: str, source: str) -> str:
    text = re.sub(r"\Aname: [^\n]*\n", f"name: ytminamp {platform} release\n", text)
    text = (
        f"# GENERATED from upstream's {source} by scripts/make-release-workflows.py; edit that\n"
        "# script, not this file. Upstream's own notes follow, still true except where the script\n"
        "# changes things (tags, no updater signing, ytminamp names, the upload).\n#\n"
        + text
    )
    text = re.sub(
        r"      - name: Check the tag matches the app version\n.*?(?=\n(?:      #[^\n]*\n)*      - (?:name|uses):)",
        VERSION_CHECK.rstrip("\n"),
        text,
        count=1,
        flags=re.S,
    )
    text = re.sub(r"group: (\w+)-release-", r"group: ytminamp-\1-release-", text)
    # The signing key: drop it from the build step's env, and the check that insists on it.
    text = re.sub(
        r"          # Scoped to this step only[^\n]*\n          TAURI_SIGNING_PRIVATE_KEY: [^\n]*\n          TAURI_SIGNING_PRIVATE_KEY_PASSWORD: [^\n]*\n",
        "",
        text,
    )
    text = re.sub(
        r"          if \[ -z \"\$\{TAURI_SIGNING_PRIVATE_KEY:-\}\" \]; then\n[^\n]*\n            exit 1\n          fi\n",
        "",
        text,
    )
    # An env: block that held only the key (Windows') is left with just comments: YAML reads that
    # as an empty value, which Actions rejects. Drop the key, keep the comments.
    text = re.sub(r"        env:\n((?:          #[^\n]*\n)+)(?=        \w)", r"\1", text)
    live = [l for l in text.splitlines() if not l.lstrip().startswith("#")]
    if any("TAURI_SIGNING_PRIVATE_KEY" in l for l in live):
        sys.exit(f"{source}: a signing-key reference survived")
    return text


def linux() -> str:
    source = "linux-release.yml"
    t = (WORKFLOWS / source).read_text()
    t = until_step(t, "Attach the AppImage + deb, teach latest.json about Linux")
    t = common(t, "Linux", source)
    t = sub(
        t,
        """tauri build --bundles "$BUNDLES" --config '{"build":{"beforeBuildCommand":""}}'""",
        """tauri build --bundles "$BUNDLES" --config '{"build":{"beforeBuildCommand":""},"bundle":{"createUpdaterArtifacts":false}}'""",
    )
    # Upstream's AppImage helpers hard-code limusic's names: run renamed copies.
    t = sub(
        t,
        "          scripts/fix-appdir-tls.sh\n",
        "          sed -e 's/limusic\\.AppDir/ytminamp.AppDir/g' -e 's/limusic_\\*\\.AppImage/ytminamp_*.AppImage/g' \\\n"
        "            scripts/fix-appdir-tls.sh > scripts/.ytminamp-fix-appdir-tls.sh\n"
        "          bash scripts/.ytminamp-fix-appdir-tls.sh\n",
    )
    t = sub(
        t,
        '          CHECK="$PWD/scripts/appdir-foreign-check.sh"\n',
        "          sed 's#usr/bin/limusic-app#usr/bin/ytminamp#g' scripts/appdir-foreign-check.sh \\\n"
        "            > scripts/.ytminamp-appdir-foreign-check.sh\n"
        '          CHECK="$PWD/scripts/.ytminamp-appdir-foreign-check.sh"\n',
    )
    t = sub(t, "limusic.AppDir", "ytminamp.AppDir", None)
    t = sub(t, "limusic_${VERSION}_", "ytminamp_${VERSION}_", None)
    t = sub(t, "/limusic.deb", "/ytminamp.deb", None)
    t = sub(t, "dpkg -L limusic", "dpkg -L ytminamp")
    t = sub(t, "-W limusic", "-W ytminamp")
    return t + upload_step(
        "target/release/bundle/appimage/ytminamp_${VERSION}_*.AppImage"
        ' $([ "${{ steps.deb_check.outcome }}" = success ] && echo target/release/bundle/deb/ytminamp_${VERSION}_*.deb)'
    )


def windows() -> str:
    source = "windows-release.yml"
    t = (WORKFLOWS / source).read_text()
    t = until_step(t, "Attach installers + teach latest.json about Windows")
    t = common(t, "Windows", source)
    t = sub(
        t,
        """tauri build "${BUNDLES[@]}" --config '{"build":{"beforeBuildCommand":""}}'""",
        """tauri build "${BUNDLES[@]}" --config '{"build":{"beforeBuildCommand":""},"bundle":{"createUpdaterArtifacts":false}}'""",
    )
    t = sub(t, "name: limusic-dry-run-", "name: ytminamp-dry-run-")
    t = sub(t, "            target/release/bundle/nsis/*.sig\n", "")
    return t + upload_step(
        "target/release/bundle/nsis/ytminamp_${VERSION}_x64-setup.exe target/release/bundle/msi/ytminamp_${VERSION}_*.msi"
    )


def macos() -> str:
    source = "macos-release.yml"
    t = (WORKFLOWS / source).read_text()
    t = until_step(t, "Attach the DMG + teach latest.json about macOS")
    # The updater archive and its round-trip check: no updater here.
    t = cut_step(t, "Archive + sign the updater bundle")
    t = cut_step(t, "Verify the archived app still passes codesign")
    t = common(t, "macOS", source)
    t = sub(t, "limusic.app", "ytminamp.app", None)
    t = sub(t, "limusic_${VERSION}_aarch64.dmg", "ytminamp_${VERSION}_aarch64.dmg")
    t = sub(t, 'STAGE="$(mktemp -d)/Limusic"', 'STAGE="$(mktemp -d)/YTMinamp"')
    t = sub(t, '-volname "Limusic"', '-volname "YTMinamp"')
    t = sub(t, "name: limusic-macos-dry-run-", "name: ytminamp-macos-dry-run-")
    t = sub(
        t,
        "            target/release/bundle/macos/*.app.tar.gz\n            target/release/bundle/macos/*.app.tar.gz.sig\n",
        "",
    )
    return t + upload_step("target/release/bundle/dmg/ytminamp_${VERSION}_aarch64.dmg")


def main() -> None:
    for name, make in [("linux", linux), ("windows", windows), ("macos", macos)]:
        out = WORKFLOWS / f"ytminamp-{name}.yml"
        out.write_text(make())
        print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
