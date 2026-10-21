#!/usr/bin/env bash
# Build a release binary for Fedora 44 inside a rootless podman container — no Nix and no host
# toolchain needed. Output: dist/ytminamp, linked against Fedora 44's system libraries.
# Runtime needs (all in a stock Fedora 44 desktop): webkit2gtk4.1, mpv-libs, pulseaudio-libs, gtk3.
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
image=ytminamp-fedora-build

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
  -e CARGO_PROFILE_RELEASE_STRIP=none \
  -e RUSTFLAGS="-C link-arg=-fuse-ld=mold" \
  -w /src \
  "$image" bash -euo pipefail -c '
    (cd ui && pnpm install --frozen-lockfile && pnpm build)
    # The UI is already built; skip tauri.conf.json'"'"'s `pnpm build` hook.
    tauri build --no-bundle --config "{\"build\":{\"beforeBuildCommand\":\"\"}}"
    # Copy then rename: a running dist/ytminamp keeps its old inode instead of "Text file busy".
    cp /target/release/limusic-app /src/dist/.ytminamp.new && mv -f /src/dist/.ytminamp.new /src/dist/ytminamp
  '

echo "built: $repo/dist/ytminamp"
