# The test build's RPM (scripts/build-fedora.sh with no argument, as dist/ytminamp-debug.x86_64.rpm):
# the unstripped dist/ytminamp, packaged as Tauri's release RPM is (same files, desktop entry and
# dependencies) but by rpmbuild, which packs it in seconds where Tauri's bundler took eight minutes.
# Version, release, descriptions and dependencies are read from tauri.conf.json, so it follows the
# release RPM. Run in the build container:
#   rpmbuild -bb --define "src <repo>" --define "bin <binary>" ytminamp-debug.spec
%global conf %{src}/src-tauri/tauri.conf.json
%define conf_get() %(node -p "require('%{conf}').%1")

# Kept as built: no stripping, no debuginfo split, no build-id links (Tauri's RPM has none either).
%global debug_package %{nil}
%global __os_install_post %{nil}
%global _build_id_links none
%global source_date_epoch_from_changelog 0
# zstd level 3 on all cores.
%global _binary_payload w3T.zstdio

Name: ytminamp
Version: %{conf_get version}
Release: %{conf_get bundle.linux.rpm.release}
Summary: %{conf_get bundle.shortDescription}
# Cargo.toml's.
License: GPL-3.0-or-later
Requires: %{conf_get bundle.linux.rpm.depends.join()}

%description
%{conf_get bundle.longDescription}

%install
install -Dm755 %{bin} %{buildroot}%{_bindir}/ytminamp
# The desktop template, filled in as Tauri does for category Music (it has no MIME types).
sed -e '/{{[#/]if/d' -e '/{{mime_type}}/d' \
    -e 's/{{categories}}/AudioVideo;Audio;Music;/' -e 's/{{comment}}/%{summary}/' \
    -e 's/{{exec}}/ytminamp/g' -e 's/{{icon}}/ytminamp/' \
    %{src}/packaging/linux/ytminamp.desktop > ytminamp.desktop
install -Dm644 ytminamp.desktop %{buildroot}%{_datadir}/applications/ytminamp.desktop
icons=%{src}/src-tauri/icons hicolor=%{buildroot}%{_datadir}/icons/hicolor
for s in 32x32 64x64 128x128; do
  install -Dm644 $icons/$s.png $hicolor/$s/apps/ytminamp.png
done
install -Dm644 $icons/128x128@2x.png $hicolor/256x256@2/apps/ytminamp.png
install -Dm644 $icons/icon.png $hicolor/512x512/apps/ytminamp.png

%files
%{_bindir}/ytminamp
%{_datadir}/applications/ytminamp.desktop
%{_datadir}/icons/hicolor/*/apps/ytminamp.png
