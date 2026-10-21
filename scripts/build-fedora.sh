#!/usr/bin/env bash
# Build a release binary for Fedora 44 inside a rootless podman container — no Nix and no host
# toolchain needed. Output: dist/ytminamp, linked against Fedora 44's system libraries.
# Runtime needs (all in a stock Fedora 44 desktop): webkit2gtk4.1, mpv-libs, pulseaudio-libs, gtk3.
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
image=ytminamp-fedora-build
# `rpm`: also package an installable RPM into dist/ (stripped, like upstream's release builds).
# Otherwise: just dist/ytminamp, with symbols kept so a hang can be read with eu-stack.
mode="${1:-binary}"
case "$mode" in
  binary) strip=none; bundle=(--no-bundle) ;;
  rpm) strip=symbols; bundle=(--bundles rpm) ;;
  *) echo "usage: $0 [binary|rpm]" >&2; exit 2 ;;
esac

podman build -t "$image" -f "$repo/packaging/fedora/Containerfile" "$repo/packaging/fedora"
mkdir -p "$repo/dist"

# Named volumes keep the cargo registry, pnpm store and target dir between runs.
podman run --rm \
  -v "$repo":/src:Z \
  -v ytminamp-cargo-registry:/root/.cargo/registry \
  -v ytminamp-pnpm-store:/root/.local/share/pnpm/store \
  -v ytminamp-target:/target \
  -e CARGO_TARGET_DIR=/target \
  -e npm_config_store_dir=/root/.local/share/pnpm/store \
  -e TAURI_FRONTEND_PATH=ui \
  -e CI=true \
  -e CARGO_PROFILE_RELEASE_STRIP="$strip" \
  -e RUSTFLAGS="-C link-arg=-fuse-ld=mold" \
  -w /src \
  "$image" bash -euo pipefail -c '
    (cd ui && pnpm install --frozen-lockfile && pnpm build)
    # The UI is already built: skip tauri.conf.json'"'"'s `pnpm build` hook. No updater
    # artifacts: the fork has no updater (tauri.conf.json), and they need a signing key.
    tauri build '"${bundle[*]}"' --config "{\"build\":{\"beforeBuildCommand\":\"\"},\"bundle\":{\"createUpdaterArtifacts\":false}}"
    # Copy then rename: a running dist/ytminamp keeps its old inode instead of "Text file busy".
    bin=/target/release/ytminamp; [ -x "$bin" ] || bin=/target/release/limusic-app
    cp "$bin" /src/dist/.ytminamp.new && mv -f /src/dist/.ytminamp.new /src/dist/ytminamp
    if [ -d /target/release/bundle/rpm ]; then cp /target/release/bundle/rpm/*.rpm /src/dist/; fi
  '

echo "built: $repo/dist/ytminamp"
ls "$repo"/dist/*.rpm 2>/dev/null || true
