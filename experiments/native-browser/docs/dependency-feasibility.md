# Native full-window Chromium: dependency feasibility

Measured 2026-11-08 on the prototype host. This audit only reads host and already-extracted engine files. No system packages were installed and no production files were changed. The native GUI and performance proof belongs to `prototype.py` / `results.json`; this document qualifies packaging, not MGU hardware performance.

## Finding

The architecture is feasible to continue prototyping, but **copying the working host Xorg/GTK/xfwm4 binaries into the existing package will not work**. They require GLIBC 2.38. The published Chromium Engine 0.1.0 carries its own Debian 12 GLIBC 2.36; the firmware baseline is GLIBC 2.27. A coherent additional native GUI runtime must therefore be built or packaged and tested. Existing engine provenance does not cover those extra components.

## Concrete compatibility evidence

`readelf --version-info` / `--dyn-syms --wide` and the published private loader produced the following results. Full output is in `dependency-audit.json`; binary/source package versions are in `dependency-packages.tsv`.

| Component on this host | Version / evidence | Consequence |
| --- | --- | --- |
| Xorg `/usr/lib/xorg/Xorg` | xorg-server `2:21.1.16-1.3+deb13u4`; requires GLIBC_2.38 (`__isoc23_sscanf`, `strlcpy`, `strlcat`, etc.) | Does not load against published engine GLIBC 2.36 or firmware 2.27. |
| Dummy driver `dummy_drv.so` | `1:0.4.0-1`; highest GLIBC need 2.4; server log reports Xorg video ABI **25.2** | Low libc minimum does not make it compatible with an arbitrary older Xorg. Server and module ABI must match; an Ubuntu18-era server/ABI cannot be substituted blindly. |
| xfwm4 | `4.20.0-1`; requires GLIBC_2.38 | Cannot reuse this binary with current engine runtime. Its GTK/Xfce dependency closure is substantial. |
| GTK3/GDK on host | GTK `3.24.49-3`; GLIBC_2.38 in both libc and libm | Host native chooser cannot be qualified for the package by adding only libgtk.so. |
| xkbcomp / xauth | Both require GLIBC_2.38 here | Auxiliary executables also need coherent packaging/rebuilds. |
| libXtst6 | `2:1.2.5-1`; GLIBC need 2.4 | Published engine lacks the file. Its loader successfully resolves this host library exclusively to existing engine X11/Xext/xcb/libc dependencies, with no version errors. Actual XTest functionality still belongs to the running prototype. |
| Published engine | Debian Chromium `156.0.8078.79-1~deb12u1`; private libc defines up to GLIBC_2.36 | Existing native client runtime is a useful base, but not a complete desktop stack. |

Actual check, not an inference:

```text
published-engine/lib/ld-linux-x86-64.so.2 --library-path published-engine/lib --list /usr/lib/xorg/Xorg
...libc.so.6: version `GLIBC_2.38' not found (required by /usr/lib/xorg/Xorg)
```

The private-loader `--list` command returned status 0 even while emitting these version errors. Checking its exit status alone would give a false pass. GTK/GDK, libpciaccess, Xfont2, xshmfence, audit, fontenc and cap-ng also emit GLIBC_2.38 errors when host dependencies leak into that check.

The host Xorg closure has 28 resolved library SONAMEs; **9 are absent** from the engine set (unwind, xcvt, pciaccess, Xfont2, xshmfence, audit, bz2, fontenc, cap-ng). The xfwm4 closure has 74, of which **26 are absent**, including GTK/GDK, Xfce libraries, ICE/SM, Xcursor, PangoCairo/PangoFT2 and GdkPixbuf. These counts are host-specific transitive SONAME comparisons, not a proposed minimal bundle.

## Practical runtime choices

1. **Coherent Debian12 native GUI add-on matching the existing private GLIBC2.36.** Obtain Xvfb or Xorg plus its matching modules, GTK3 chooser and a small window manager from a single qualified sysroot; include complete non-ELF assets. This is the shortest next reproducible compatibility experiment. Current host Debian13 binaries cannot be mixed in. No such add-on was assembled or tested in this audit.
2. **Build current Xvfb/Xorg and a minimal window manager against an older supported sysroot.** A server using only virtual framebuffer facilities can avoid dependencies on hardware modesetting, VT, DRM, udev and input-device probing. Build options, bundled library security maintenance and MGU kernel behavior still require evidence. Xvfb is absent on this host, so its capture/resize/extension behavior has not been demonstrated here.
3. **Use a second, coherent newer private loader/libc stack** for server/WM/GTK, separate from engine clients. X11 protocol permits server/client processes with different libc versions. This increases bundle size and maintenance; the newer libc's minimum kernel and syscalls must be qualified on the MGU. Do not point arbitrary host GTK libraries at the engine's older loader.
4. **Old Ubuntu18-era Xorg/Xvfb** could meet the firmware libc ABI, but reintroduces an old security baseline, matching driver constraints and maintenance work. It is not accepted merely because it starts. Prefer a maintained source build / coherent current runtime over an unreviewed historical binary snapshot.

Do not replace firmware libc or globally set LD_LIBRARY_PATH. Use per-process loader/library paths and immutable, pinned, versioned GUI runtime files. Packaging tests must fail if any dependency resolves from the build host or `/usr/lib` on the MGU unexpectedly.

## Assets and kernel requirements beyond ldd

- Native X11 client capture/input needs X11, Xext/MIT-SHM and Xtst; optional XDamage/XFixes can reduce idle work. Check extension presence and supported image masks, stride, depth and byte order at runtime. Existing prototype uses 24-bit root / 32-bit BGRX storage.
- The present XShm path uses System V `shmget`/`shmat`/`shmctl` and requires `CONFIG_SYSVIPC`, adequate SHMMAX/SHMALL limits and the **same IPC namespace** for server and capture helper. Mark segments IPC_RMID after attach and detach on cleanup. A bounded XGetImage fallback is possible but is not performance-qualified here.
- Ship a coherent XKB rules/symbols/keycodes/compat/types tree and xkbcomp where the server requires it. Host `/usr/share/X11/xkb` is 3,591,687 bytes; keymap assumptions must not leak from the host. Native text beyond simple ASCII requires a deliberate keyboard/compose/clipboard design, not per-character US-layout assumptions.
- Fonts/fontconfig configuration and cache directories, locale/UTF-8 behavior, GTK settings/GSettings schemas, GdkPixbuf loader modules plus regenerated loader cache, icons and selected WM theme are runtime inputs. Host GdkPixbuf loader directory is ~600kB; Xfwm default theme ~53kB. Do not ship build-host absolute loader-cache paths.
- Authenticated Unix X socket, private 0700 runtime directory /0600 MIT cookie, `-nolisten tcp`, no `-ac`, no inherited public DISPLAY, no shared Xauthority. Any client with that cookie can observe/inject into the whole private session; isolate profile secrets and untrusted file access accordingly.
- Supervise X server, WM, D-Bus if required, capture and Chromium as one owned lifecycle; crash cleanup must remove auth/socket/IPC resources and not leave privileged or public servers. Current prototype does not establish production watchdog/recovery behavior.
- The engine libc ELF ABI note says Linux **3.2.0**. This is only the libc note; it does not prove that the full Chromium sandbox, GUI stack, GPU driver, seccomp or all runtime code paths support a particular MGU kernel. Namespace/seccomp/userns/setuid-sandbox policy must remain enabled and be tested on-device. The native GUI may not require GPU device access when software rendering is selected, but hardware video acceleration is unproven.

## Redistribution evidence and open work

Relevant host copyright files were copied unchanged for local review into `native-copyright-evidence/`; SHA256/source paths are in `native-copyright-evidence.json`. The source package names and exact versions are in `dependency-packages.tsv`.

| Pieces | Evidence from installed Debian copyright files | Packaging requirement still to complete |
| --- | --- | --- |
| Xorg, dummy, X11/Xext/Xtst, xauth | Predominantly MIT/X11 / historical permissive forms, sometimes specific notice/advertising clauses | Preserve the complete applicable notices for the exact shipped files, including all legacy contributors. |
| xfwm4 | Source-file groups marked GPL, GPL-2+ and LGPL | Provide applicable license text, exact corresponding source/patches/build material or compliant source offer. Separate-process distribution does not by itself make the browser program GPL. A different minimal WM changes the inventory and must be audited separately. |
| GTK/GDK/GdkPixbuf/GLib and related libraries | Mostly LGPL-covered runtime code, with per-file exceptions and additional asset/tool licenses | Verify which files are shipped, preserve notices, supply corresponding source/modifications as required and preserve users' ability to replace/relink covered dynamic libraries. Do not label an entire source package using only its first license tag. |
| D-Bus | Copyright file says effective majority `GPL-2+ or AFL-2.1`, some utilities GPL-2+ only | Inventory exact daemon/helper files and select/apply permitted licenses with required notices/source obligations. Existing libdbus notice is not automatically sufficient for new executables. |
| XKB/fonts/themes | XKB contains multiple historical permissive forms; font/theme files have their own notices | Include actual chosen data-file licenses; existing DejaVu engine notice covers only the fonts already shipped. |
| Chromium / codecs / optional graphics | Published engine already has a detailed Debian package provenance and copyright set | Preserve it; re-audit any newly added native GUI, Mesa/GLX/ANGLE/SwiftShader or media binaries. Native window support does not grant Widevine/CDM, proprietary service, codec patent or trademark rights. No such provisioning is included. |

This is an engineering inventory, not a completed legal clearance. A release needs a full recursive manifest of the **actual** new runtime, hashes, binary/source versions, licenses/notices, source availability and reproducible builds, followed by exact-package loading and on-device tests. Current host GUI success cannot establish those facts.

## Follow-up: coherent Debian12 runtime fetched and started

The parent subsequently authorized assembling a complete scratch runtime. `fetch_bookworm.py` now downloads Debian bookworm, bookworm-updates and bookworm-security **signed InRelease** files, verifies them with Sequoia `sqv` against the installed Debian archive keyring, checks Release expiration, verifies Packages.xz and Sources.xz against the signed SHA256 fields, and verifies every `.deb` against its authenticated Packages SHA256/size. No package manager installation, maintainer scripts, alternatives or triggers run. Files are extracted only beneath this prototype directory; setuid/setgid bits are stripped.

- `bookworm-manifest.json`: 245 recursive Depends/Pre-Depends packages, 133.35MiB downloaded, approximately543MiB extracted. This is deliberately broad; dependencies pull in unused system utilities, Mesa drivers and other assets. It is **not** a proposed optimized production bundle.
- Xvfb and xserver-common `2:21.1.7-3+deb12u13` come from bookworm-security; xfwm4 is4.18.0-1, GTK is3.24.38-2~deb12u3, private libc2.36-9+deb12u14. Every selected package has its source package/version and exact authenticated source archive URLs/SHA256/size recorded. Those source archives are recorded, not yet downloaded or published.
- `bookworm-loader-closure.json` verifies Xvfb, xfwm4, xkbcomp, xauth, D-Bus, GTK3 and libXtst resolve through the private bookworm loader with **no host-library paths and no version errors**.
- `prepare_bookworm.py` updates876 dynamic ELF files to a private interpreter/RUNPATH. Original signed `.debs` remain unchanged; original/runtime hashes and transformations are in `bookworm-runtime-patches.json`. GTK schemas and private GdkPixbuf loader cache are generated; fontconfig, D-Bus service/config and GTK/XKB environment paths are explicit.
- Xvfb embeds `/usr/bin/xkbcomp`. A tiny **prototype-only** preload (`xkb_private_path.c/.so`, GLIBC need2.34) sets its exported `XkbBinDirectory` from the explicit private environment. The server receives it via the loader `--preload` flag so it does not leak into Chrome. A production server build should configure the intended immutable prefix directly instead of needing this runtime shim.
- `bookworm_stack_smoke.py` starts private authenticated Xvfb1280×400, a private D-Bus session and the private xfwm4, then cleans all owned process groups/auth files. Actual result in `bookworm-stack-smoke.json`: **success:true**, MIT-SHM/XTEST/DAMAGE/RANDR available,1280×400 root, strace proves the **private xkbcomp** executed; `/proc` maps for the native server/WM/D-Bus/service processes show **zero host shared-library leaks**. Host strace is external test instrumentation only. This proves this host can run the coherent private stack; it does not prove MGU hardware/kernel compatibility or exact-engine browser integration.
- xfwm4 prints an AT-SPI accessibility-bus warning because the optional at-spi2-core daemon/service was not included. It continues running. Native keyboard events/capture do not depend on it; future native accessibility/focus-role integration needs that component and its own tests. Do not silence the warning by pretending accessibility works.

Use `bookworm-env.json` for private GTK/schema/pixbuf/fonts/XKB paths. No global LD_LIBRARY_PATH is required for the patched native binaries. The unchanged exact Chromium engine uses its own DT_RPATH first; a **Chrome-process-only** LD_LIBRARY_PATH with the private bookworm directories can supply missing GTK3 without replacing its RPATH-resolved engine libraries. That actual mixed same-Debian12 integration is for the parent prototype test to qualify. No production files were changed.

### Native GTK assets: reproduced failure and fix

The first exact-engine/native-GUI integration run reached authored video playback with webdriver:false, but subsequently **aborted in GTK** when a native chooser needed `Adwaita/16x16/status/image-missing.png`: GdkPixbuf reported an unrecognized image format. This was a real missing-runtime-assets bug, not just a cosmetic warning.

Package extraction does not run shared-mime-info's maintainer trigger, so the MIME XML files existed but **mime.cache was absent**. The private `gdk-pixbuf-thumbnailer` reproduced exactly the same PNG failure with the original environment (exit1). Running the private `update-mime-database` on a copied private MIME tree fixed that same command (exit0, actual1186-byte PNG output). The PNG loader is built into GdkPixbuf; its absence from the external module list was not the cause.

`prepare_bookworm_assets.py` creates a separate `bookworm-assets-candidate/share` tree with compiled MIME database and private Adwaita/hicolor icon caches. It never edits a running core runtime. `bookworm-assets-proof.json` records before/after. Apply **bookworm-assets-env.json after bookworm-env.json**; its XDG_DATA_DIRS puts the generated assets first. The parent must rerun the complete native chooser/file selection flow with that overlay before calling exact-engine GUI integration successful.

### Optional SVG/accessibility add-on

`fetch_bookworm_extra.py` uses the same signed metadata and hash chain to fetch four additional packages into a separate `bookworm-extra`: librsvg2-2, librsvg2-common, at-spi2-core and gsettings-desktop-schemas (3.19MiB compressed /26.4MiB extracted). `bookworm-extra-manifest.json` records exact binaries and source archive URLs/hashes; `bookworm-extra-patches.json` records private interpreter/RUNPATH changes.

`prepare_bookworm_extra.py` produces a merged private GdkPixbuf cache including the SVG module and merged GSettings schemas. The private thumbnailer demonstrably renders an actual Adwaita symbolic SVG (`bookworm-extra-proof.json`: success:true,417-byte PNG output). Apply **bookworm-extra-env.json last**, after the core and MIME-assets overlays. This improves normal GTK symbolic-icon support without loading host modules.

The default AT-SPI bus launcher still embeds `/usr/bin/dbus-daemon` and its default configuration path, so automatically starting it is **not yet qualified** as a private runtime. A possible prototype path is to launch the already-private D-Bus daemon with `bookworm-extra-accessibility.conf` and set AT_SPI_BUS_ADDRESS explicitly; libatspi supports that environment variable. Private registry service paths are prepared, but no native Chromium accessibility tree/focus-role proof is claimed here. The captured full-window/browser input prototype can proceed without this optional facility.

## Final qualification: whole private runtime inside Ubuntu18 / GLIBC2.27

`ubuntu18_runtime_probe.py` now starts the **actual Xvfb, xfwm4, private D-Bus and activated xfconfd inside** the pinned Ubuntu18 image `ubuntu@sha256:152dc042452c496007f07ca9127571cb9c29697f42acbfad72324b2bb2e43c98`. This goes beyond running Chrome alone in an old container while Xorg/WM stay on the new host.

The successful result is in `ubuntu18-runtime-result.json`, with command/config and container inspection retained alongside it. The image's own `getconf GNU_LIBC_VERSION` reports **glibc2.27**. The native graphics payload uses the bundled private GLIBC2.36 and authenticated Debian12 libraries. The whole core runtime is mounted read-only; separate test state is writable. Network is `none`, IPC is private with64MiB `/dev/shm`; **no host X socket, no host IPC, no extra capabilities and no AppArmor override** are used. OS bootstrap/logging helpers use the old image's ordinary utilities; they are not mistaken for native graphics payload processes.

| Actual assertion | Result |
| --- | --- |
| Live private Xvfb, xfwm4, D-Bus, xfconfd | All four run as UID1000; native WM EWMH owner verified and process remains alive through the test. |
| Native input through XTest | 4 key presses/releases: Tab, Shift+Tab, `a` plus Shift modifier; expected2 Tabs/1 shifted Tab; actual mouse motion,1 button press/release. |
| Whole-root MIT-SHM capture while fixture changes | 1280×400,60 captures,60 changed frames,29.998fps; capture+fullframe C checksum mean2.55ms/max3.79ms;0 X errors. This is an authored moving rectangle, not a video decode benchmark. |
| Extension support | MIT-SHM, XTEST, DAMAGE and RANDR present. Dynamic RandR resize is not claimed. |
| Isolation | Native processes and the C probe have **zero external shared libraries**; native process maps also have **zero external mapped data files**. Missing-cookie X connection rejected; no X TCP listener. |
| Cleanup | Owned groups stopped; X socket, lock and authority removed; disposable container removed and inspection confirms it no longer exists. |

The C probe (`native_x_probe.c`) is compiled against authenticated Debian12 X11 headers and private X11/Xext/Xtst libraries, with a private interpreter/RUNPATH. Its own maximum GLIBC symbol need is2.34, satisfied by the private2.36 runtime. It does not depend on a newer host Python/Xlib library to perform its native input or capture. Header package hashes/versions are in `bookworm-devel-manifest.json`.

This qualification exposed additional real packaging gaps that the host-only run hid:

1. Ubuntu18 `/etc/nsswitch.conf` selects `compat` and causes the private new D-Bus process to load old host NSS/NIS libraries. The successful fixture uses a **container-only read-only NSS config** with files for user/group lookups and files/dns for hosts. Private GLIBC2.36 provides these implementations without loading old NSS modules. Production must isolate/configure that policy per session; do not overwrite firmware NSS configuration globally.
2. xfwm4 opens its defaults through compile-time `PACKAGE_DATADIR`; XDG_DATA_DIRS cannot redirect it. Exact corresponding xfwm4 source was fetched and hash-verified into `bookworm-source-evidence/` to confirm this. The successful container supplies read-only aliases from private `usr/share/xfwm4` and `usr/share/themes` to those absolute locations. A production source build should configure the immutable private prefix or use an appropriately isolated filesystem namespace. The earlier host run could otherwise silently use host defaults/themes.
3. GLIBC's default gconv path loaded old `/usr/lib/.../gconv/ISO8859-1.so`. **GCONV_PATH now points to the private bookworm gconv modules**. Mapping assertions detect this class of leak.
4. A missing private LOCPATH silently falls back to old image locale data. A separately authenticated matching `libc-bin2.36-9+deb12u14` package supplies the compiled **C.utf8 locale data** under `bookworm-locale`. Its files/hashes/source archives are in `bookworm-locale-manifest.json`; extracted libc-bin executable tools are not used or claimed as qualified. The strict final pass has no external locale mappings.

Apply `bookworm-runtime-isolation-env.json` **after** the core, MIME-assets and optional SVG overlays. It supplies GCONV_PATH, the real private LOCPATH and C.utf8 locale selection. Filesystem aliases/NSS configuration remain explicit in the Docker driver, not hidden modifications to the host. AT-SPI remains optional/unqualified as described above.

This proves a coherent native GUI userspace can operate on a GLIBC2.27 **base filesystem** using a private modern runtime. Docker still uses this host's Linux6.18 kernel and EPYC CPU; **MGU kernel, hardware performance, GPU/media acceleration, production namespaces/supervision and redistribution clearance remain open**. The parent's separate exact-engine/full-browser/media test is needed for browser behavior; the C rectangle test does not replace it.
