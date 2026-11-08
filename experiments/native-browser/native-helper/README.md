# Bounded native capture/input helper — review prototype

**Authored-fixture validation passed; production integration is unimplemented.** This directory is reviewable source only, not a browser mode, package or replacement for MGU Browser0.16. Sanitized results are in [test-result.json](test-result.json). The tested runtime is a disposable Ubuntu18/glibc2.27 image with Node8.16.2 and a separate private X11/glibc2.36 helper process; no newer libc is loaded into Node8.

The helper is a small C sibling process for a private X11 session. It captures RGBA into a separate fd3 pipe and processes bounded native keyboard/mouse/wheel commands on stdin, with small stdout acknowledgements. One immutable frame may be pending; stalled frame consumers do not create a capture queue or block the command pipe. Epoch changes reject stale input and release held state. See [PROTOCOL.md](PROTOCOL.md) for the exact binary interface and shutdown limits.

Required inputs, supplied explicitly by the caller:

- A coherent qualified private Xvfb/X11/XTest/MIT-SHM runtime, loader and libraries. The tests do not download/install one. Keep its newer libc out of Node8's process.
- Matching X11/Xext headers, a C compiler and explicitly supplied library/loader paths for `build.py`. Build output must live **outside** this source-only review directory.
- A private authenticated X display in DISPLAY/XAUTHORITY, with MIT-SHM/XTEST and supported root geometry/pixel format. The owner must supply the runtime's own XKB/fonts/locale/MIME/NSS configuration and supervise its complete lifecycle.
- Three separate inherited pipes: stdin commands, stdout responses and fd3 raw frames. Node8's child-process stdio array can create these. No shell or filename operation is exposed by the runtime protocol.

Build example, replacing every placeholder with your own absolute input path:

```sh
python3 build.py --include-dir /private/headers/usr/include --lib-dir /private/runtime/lib/x86_64-linux-gnu --lib-dir /private/runtime/usr/lib/x86_64-linux-gnu --loader /private/runtime/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2 --output /scratch/native-helper
```

Node8 wrapper and focused tests are provided alongside the C helper. Do not enable a production native backend using this prototype alone. Unicode text/clipboard, AT-SPI focus/readiness, vehicle visibility/driving gates, recovery/supervision, MGU frame delivery and on-device kernel/performance qualification remain work. TEXT explicitly returns unsupported; individual logical native key events do not pretend to implement multilingual text entry.

## What was tested

- 10 focused wrapper cases on actual Node 8.16.2: fragmented/coalesced records, owned pixels, independent ACK/frame streams, one capture credit, stale partial-frame discard, malformed/oversized/truncated input, request bounds, EOF/timeouts and bounded child termination.
- 12 real native Xvfb cases inside Ubuntu 18 with private IPC, no network and no additional container capabilities. The fixture validates red/green RGBA channels, native XTest events (`send_event=false`), click/double-click/wheel/drag/key-up, stale epochs, one immutable partial frame under pressure, and held-key/button/modifier release plus SHM cleanup on STOP/EOF/SIGTERM/oversize/truncated commands. The real Node 8 wrapper also speaks directly to the C helper there.

While fd3 was deliberately unread and 32 further capture credits returned BUSY, a Shift+A key ACK arrived in 6ms; helper RSS was 7016KiB. These are observations on the test host, not a device latency or memory guarantee. Only a 1280×400 TrueColor root was exercised; other accepted dimensions require their own practical checks. This helper test uses an authored native X window and does not claim a new browser/DOM event audit, video decoder, Unicode/clipboard support or on-device performance. The separate architecture proof owns browser/media evidence.

The real fixture exposed and fixed close-before-confirmation input cleanup: shutdown now completes a native X roundtrip before closing the connection, under a2-second hard-exit watchdog. A hung/dead X server still requires restarting the whole private session; this helper is not that supervisor.

## Reproduce without hidden runtime paths

First build the helper outside this directory using the explicit sysroot paths above. The disposable old-base gate also needs an explicitly supplied Node8 executable, matching X11 headers and an external writable scratch directory. It builds its authored C fixture there; it does not fetch/install packages, reuse profiles, invoke Chromium or run a media/performance workload.

```sh
python3 test/run_ubuntu18.py --runtime-root /private/runtime --helper /scratch/native-helper --node /private/node8/bin/node --include-dir /private/headers/usr/include --workdir /scratch/native-helper-test
```

The supplied runtime must contain patched private-loader/RUNPATH Xvfb, X11/Xext/Xtst, xkbcomp, XKB data and fonts. The driver mounts those inputs read-only, supplies private files/dns NSS configuration and X locale/gconv paths, aliases only the runtime's xkbcomp to the server's compiled location, and creates/deletes a temporary private MIT cookie in the external workdir. It uses the pinned public Ubuntu18 image recorded in the test result. Docker and its namespaces/SysV IPC are prerequisites; the actual MGU kernel is untested. Source-only wrapper tests need no X runtime: `/absolute/node8 test/client.test.js`.

The code depends on X11/Xext/Xtst APIs. No third-party libraries, binaries, profiles, cookies, keys, screenshots or package archives belong in this review directory. Runtime dependencies have their own licenses/source obligations and must be qualified separately.
