#!/usr/bin/env bash
# Build a release binary for Fedora 44 inside a rootless podman container — no Nix and no host
# toolchain needed. Output: dist/ytminamp, linked against Fedora 44's system libraries.
# Runtime needs (all in a stock Fedora 44 desktop): webkit2gtk4.1, mpv-libs, gtk3.
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
image=ytminamp-fedora-build
# `rpm`: a release RPM into dist/ (stripped, like upstream's release builds).
# Otherwise: dist/ytminamp with symbols kept, so a hang or crash can be read (eu-stack,
# coredumpctl), and the same build as dist/ytminamp-debug.x86_64.rpm, to install on any Fedora.
mode="${1:-binary}"
case "$mode" in
  binary) strip=none; bundle=(--no-bundle); rpm_as=ytminamp-debug.x86_64.rpm ;;
  rpm) strip=symbols; bundle=(--bundles rpm); rpm_as= ;;
  *) echo "usage: $0 [binary|rpm]" >&2; exit 2 ;;
esac

# The UI is already built: skip tauri.conf.json's `pnpm build` hook. No updater artifacts: the fork
# has no updater (tauri.conf.json), and they need a signing key.
config='{"build":{"beforeBuildCommand":""},"bundle":{"createUpdaterArtifacts":false}}'

podman build -t "$image" -f "$repo/packaging/fedora/Containerfile" "$repo/packaging/fedora"
mkdir -p "$repo/dist"

# Named volumes keep the cargo registry, pnpm store and target dir between runs. One target dir per
# checkout: every checkout mounts at /src, and cargo decides staleness by file times, so a shared
# one hands this checkout another one's newer build of a crate (the dev worktree's player, say).
target="ytminamp-target-$(basename "$repo")"
podman run --rm \
  -v "$repo":/src:Z \
  -v ytminamp-cargo-registry:/root/.cargo/registry \
  -v ytminamp-pnpm-store:/root/.local/share/pnpm/store \
  -v "$target":/target \
  -e CARGO_TARGET_DIR=/target \
  -e npm_config_store_dir=/root/.local/share/pnpm/store \
  -e TAURI_FRONTEND_PATH=ui \
  -e CI=true \
  -e CARGO_PROFILE_RELEASE_STRIP="$strip" \
  -e RPM_AS="$rpm_as" \
  -e TAURI_BUILD_CONFIG="$config" \
  -e YTMINAMP_SKINS="${YTMINAMP_SKINS:-}" \
  -e RUSTFLAGS="-C link-arg=-fuse-ld=mold" \
  -w /src \
  "$image" bash -euo pipefail -c '
    (cd ui && pnpm install --frozen-lockfile && pnpm build)
    # The target volume outlives builds: so clear out RPMs from earlier builds before making this one.
    rm -rf /target/release/bundle/rpm
    tauri build '"${bundle[*]}"' --config "$TAURI_BUILD_CONFIG"
    # Copy then rename: a running dist/ytminamp keeps its old inode instead of "Text file busy".
    bin=/target/release/ytminamp; [ -x "$bin" ] || bin=/target/release/limusic-app
    cp "$bin" /src/dist/.ytminamp.new && mv -f /src/dist/.ytminamp.new /src/dist/ytminamp
    # A test build: its RPM made by rpmbuild in seconds (Tauri takes minutes over the unstripped
    # binary), under a name of its own, so it never stands in for a release one.
    if [ -n "$RPM_AS" ]; then
      rpmbuild -bb --quiet --define "_topdir /tmp/rpmbuild" --define "src /src" --define "bin $bin" \
        packaging/fedora/ytminamp-debug.spec
      cp /tmp/rpmbuild/RPMS/x86_64/*.rpm "/src/dist/$RPM_AS"
    fi
    for rpm in /target/release/bundle/rpm/*.rpm; do
      [ -e "$rpm" ] || continue
      cp "$rpm" /src/dist/
    done
  '

echo "built: $repo/dist/ytminamp"
if [ -n "$rpm_as" ]; then echo "built: $repo/dist/$rpm_as"; else ls "$repo"/dist/*.rpm 2>/dev/null || true; fi
