# Authored native full-window proof

This subtree contains authored C/Python/Perl source and sanitized evidence, **no GUI runtime, engine, audio helper, package archive, private key, Xauthority, browser profile or raw PCM**. It is a reviewed experiment, not an installable browser mode or Store update.

The passing combined test puts unchanged Engine0.1, coherent private Debian12 Xvfb/WM/D-Bus and the existing0.15 audio helper into one pinned Ubuntu18/glibc2.27 container. Native processes run UID1000, with Chromium sandbox retained, private IPC and network disabled. Native XTest input and MIT-SHM capture run in the same container. Only original loopback pages/video are served through a private Unix relay.

[evidence/combined-result.json](evidence/combined-result.json): actual `webdriver:false`, WebGL=true,180/180 fresh inline frames at30fps,120/120 fresh fullscreen frames at30fps, no new dropped video frames, native confirmation and440Hz PCM. The [fullscreen screenshot](evidence/native-video-fullscreen.png) visibly contains the whole1280×400 video viewport; black sides are correct aspect-ratio letterboxing. [Native confirmation](evidence/native-confirm.png) and [sandbox](evidence/native-sandbox.png) are actual native screenshots. Physical MGU performance and speakers were not tested.

The separate WebGL-capable60fps capture experiment recorded345/360 changing frames (~57.5fps),20/360 dropped video frames, and≈675MiBPSS on an EPYC host. The30fps profile had no new drops and≈650MiBPSS. These are not MGU FPS promises. See the raw sanitized result files and [production plan](../docs/production-plan.md) for the real release blockers.

## Exact external inputs

Public binary/source URLs, package identities, hashes and the pinned image are in [../inputs](../inputs/). They are references only. The source archives/notices are not bundled or a completed redistribution offer.

- GUI runtime:254 manifest entries including245 runtime packages,4 optional SVG/accessibility packages,1 locale package and4 build-header packages. The optional tools are deliberately broad scratch dependencies, not a proposed production payload.
- Unmodified published Engine0.1 archive: SHA256 `0b6a73c964354214262d01f2d9bec2d0ab253cac8d27de04708912e804ef0874`; actual Chromium SHA256 `9c94b57491fcc1a4b5a013ecb8fa13a637cc9a16aebea5041899c3cb033e5a13`. Its immutable container mount is `/var/opt/mgu-browser-engine/versions/0.1.0/engine` because its ELF interpreter/RPATH use that prefix.
- Existing published0.15 `files/audio-bridge`, with its hash in external-inputs.json. It uses the separately pinned Ubuntu18 GLIBC2.27/ALSA1.1.3 test root, not a vendor SmartX binary.
- Official Node8.16.2 is needed only by the extension/new-helper tests, with its exact archive hash in the common manifest.
- Authored VP8/Opus30fps960×540 clip with440Hz tone, generated with `generate_clip.py`; no external media input is needed.
- Build/test host: unprivileged Linux x86_64, Python3.10+, C compiler compatible with the2.36 target, matching X11 headers, binutils/readelf, dpkg-deb, a local pinned Ubuntu18 Docker image, and Pillow/Numpy for screenshot/tone inspection. Fresh signed dependency resolution additionally needs Sequoia sqv and the Debian archive keyring. Nothing here installs host packages.

## Fixed-prefix historical driver versus explicit-input tools

The passing historical drivers use `/tmp/mgu-native-window-prototype` as their private runtime prefix. Their prepared ELF files have absolute private interpreter/RUNPATH/data paths; copying prepared binaries elsewhere is invalid. The driver has explicit preflight checks for required inputs and the exact engine hash, rejects an existing named container, and refuses symlink state. It recreates only its own `combined-state/profile` and ephemeral files. Use a disposable environment, never a real profile. Historical scripts refuse in-place execution inside this source-only bundle.

New utility scripts accept explicit output/input paths and keep generated files outside this tree:

```sh
# Run from a source checkout; choose a NEW/EMPTY scratch workspace.
NATIVE_SOURCE=/absolute/path/to/experiments/native-browser/native-gui-proof
NATIVE_WORK=/tmp/mgu-native-window-prototype
python3 "$NATIVE_SOURCE/scripts/fetch_pinned_debs.py" --cache /tmp/mgu-native-deb-cache --allow-download --include-devel --extract-workspace "$NATIVE_WORK"
```

The downloader verifies exact manifest sizes/SHA256, never silently upgrades versions, and never runs maintainer scripts. If an upstream archive has removed a pinned version it fails; obtain the exact matching archive from a verified snapshot instead of substituting another version. `fetch_bookworm.py`/`fetch_bookworm_extra.py` retain the original signed-metadata resolution logic, but resolving fresh metadata may select newer packages and does **not** reproduce this exact evidence.

Copy the authored historical preparation/proof sources (not the SOURCE_ONLY marker) into that external workspace, then prepare core, pinned add-on, MIME/icon caches, schemas and final private environment:

```sh
cp "$NATIVE_SOURCE/scripts/prepare_bookworm.py" "$NATIVE_SOURCE/scripts/prepare_bookworm_assets.py" "$NATIVE_SOURCE/scripts/prepare_bookworm_extra.py" "$NATIVE_SOURCE/scripts/combined_native_smoke.py" "$NATIVE_SOURCE/scripts/local-http-relay.pl" "$NATIVE_WORK/"
python3 "$NATIVE_WORK/prepare_bookworm.py"
python3 "$NATIVE_SOURCE/scripts/prepare_extra_pinned.py" --workspace "$NATIVE_WORK"
python3 "$NATIVE_WORK/prepare_bookworm_assets.py"
python3 "$NATIVE_WORK/prepare_bookworm_extra.py"
python3 "$NATIVE_SOURCE/scripts/finalize_runtime_env.py" --workspace "$NATIVE_WORK"
python3 "$NATIVE_SOURCE/scripts/build_test_helpers.py" --workspace "$NATIVE_WORK" --include-dir "$NATIVE_WORK/bookworm-devel/usr/include" --output-dir "$NATIVE_WORK"
python3 "$NATIVE_SOURCE/scripts/generate_clip.py" --output "$NATIVE_WORK/clip.webm"
```

Do not rebuild/patch a runtime while another fixture uses it. The build helper rejects GLIBC imports newer than2.36 and private-loader closure leaks. In this review, all254 cached public archives were verified without downloading or extracting them; both authored test helpers were rebuilt into a separate scratch directory and passed ABI/private-loader checks. The complete clean-workspace preparation recipe itself was not rerun after packaging this source bundle.

Before executing `combined_native_smoke.py`, supply these exact explicitly documented historical inputs:

- Extract **only regular engine payload files** under `$NATIVE_WORK/published-engine`; verify the archive and Chromium hashes above. Preserve the original bytes. The driver creates its own root-owned4755 sandbox-helper copy only inside the disposable container.
- Put the old-ABI test root at `/workspace/mgu-browser/.local/audio-abi-2.27/root`, with its `lib/x86_64-linux-gnu/ld-2.27.so` and pinned ALSA libraries. URLs/hashes are in `old-audio-abi-manifest.json`; extract those verified packages without running installation scripts.
- Put the exact existing helper at `/workspace/mgu-browser-audio-focus/.local/published-0.15.0-verify/runtime-unpacked/files/audio-bridge` and verify its recorded SHA256. These are fixture paths, not required production paths.

Then run `python3 "$NATIVE_WORK/combined_native_smoke.py"`. It writes generated raw state only to `$NATIVE_WORK/combined-state` and new result JSON outside this review tree. It does not perform external account operations. The container is network:none/privateIPC and read-only-binds inputs; SYS_ADMIN and fixture AppArmor-unconfined permit Chromium's own sandbox. No privileged-container or Chromium no-sandbox flag is used. The separate strict runtime-only probe requires no extra container capabilities.

The generated private runtime requires MIME/icon/schema/font/XKB, NSS/gconv/locale and WM defaults/theme configuration. Missing MIME cache originally caused an actual GTK abort, and host-path fallbacks were caught in the old-base gate; do not remove these as cosmetic assets. See [dependency-feasibility.md](../docs/dependency-feasibility.md).

## Remaining integration

This is not a replacement BrowserSession. The separate bounded helper is documented in [../native-helper](../native-helper/README.md), and the legitimate metadata/native-messaging extension in [../extension-proof](../extension-proof/README.md). Native-widget focus/keyboard/Unicode, frame/document generations, storage recovery, phone preview/staged uploads, final dependency pruning/licensing and physical MGU qualification remain explicit work.
