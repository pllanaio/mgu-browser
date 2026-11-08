# Native integration extension: exact-engine proof

This is an original MIT-licensed, disposable architecture experiment. It is not a production release or an installer. No MGU Browser0.16 production source was changed by this experiment.

The exact published Engine0.1 Chromium156.0.8078.79 runs an ordinary native X11 window under the private Xvfb/Bookworm GUI runtime inside pinned Ubuntu18. It has no headless, debugging-port, debugging-pipe, enable-automation, webdriver override or AutomationControlled suppression. An own ManifestV3 extension obtains normal extension APIs and connects to an immutable NativeMessaging host, which forwards to a private Node8 endpoint. Native input and screenshots use the separate authored XTest/XShm helper.

## Measured result

[evidence/result.json](evidence/result.json) contains the final passing run:

- Authored page reports actual `navigator.webdriver === false`; native process command lines contain none of the prohibited flags. Every captured native process runs UID1000. All captured renderer processes retain `NoNewPrivs=1` and `Seccomp=2`.
- Real title/URL/tab creation, navigation and closure work through `chrome.tabs`.
- Native `audible` transitions cover ordinary video, a closed-shadow video, a cross-origin child video and that child's closed-shadow video. Native tab mute/unmute produces `mutedInfo` events. `audible` is a recent audio activity indicator with a retention tail; it is not an instantaneous PCM meter and does not replace vehicle audio-focus handling.
- Isolated content scripts report email-field metadata, a closed password field and a password-to-textarea switch inside the same closed root. No field values, password contents, page text or selection text are read. The cross-origin child's browser-supplied frame/document IDs are distinct.
- HttpOnly, session, expiration, host-only and partition-key cookie fields are exposed. All-partition enumeration and overwrite/remove-then-insert events work. Values remain private, generated fixture data and are excluded from this package's evidence.
- Native download filename and exact36byte content match; the slow download reports393216 received bytes through `downloads.search`, then native cancellation returns `USER_CANCELED`.
- NativeMessaging manifest is root-owned0444 and its ordinary, non-setuid bridge is root-owned0555. Wrong extension origin is rejected. Both Unix-socket directions check kernel `SO_PEERCRED`. Native and control sockets are0600 inside a0700 run directory.
- The disposable container exits0; private X socket, lock and authority are removed.

[evidence/native-task-manager.png](evidence/native-task-manager.png) is an actual native screenshot. Chromium's Task Manager displays the main tab in PID164 and `Subframe: http://localhost/` in PID163. Both are captured sandboxed renderer PIDs. The authored parent is `http://127.0.0.1:39093/` and its only child is `http://localhost:39093/child`. This independently confirms that the tested child is an OOPIF without using CDP.

No account, vendor runtime, CDM, proprietary payload or protected provider playback was used. Physical MGU input hardware and vehicle speakers were not tested by this extension proof.

## Exact required inputs and rerun

The proof driver intentionally uses these fixed prefixes because the prepared private GUI binaries have ELF interpreter/RPATH and data references to them. It **deletes and recreates only** `/tmp/mgu-native-extension-prototype/state` at startup. It does not delete the GUI runtime or any real browser profile. Do not point it at a real profile.

1. Copy this authored source subtree to `/tmp/mgu-native-extension-prototype`, preserving `extension/` and `native-host-manifest.json`. The manifest's `key` is a **public identity key**. No private signing key, DER file or secret is necessary for an unpacked Chromium extension. Its stable ID is `cioniecfpnfdjfkfhcijhdpjabcpbplj`.
2. Prepare the separately documented GUI inputs under `/tmp/mgu-native-window-prototype`: `bookworm-root`, `bookworm-extra`, `bookworm-locale`, auxiliary asset trees, four `bookworm-*-env.json` files, `bookworm-fonts.conf`, `bookworm-dbus.conf`, original `xkb_private_path.so`, `combined_x_control` and the authored `clip.webm`. These are listed by the common package input/provenance manifests. Rebuild the authored helper/shim from their source; no compiled payload is included here.
3. Extract the existing, unmodified Engine0.1 payload to `/tmp/mgu-native-window-prototype/published-engine`. Its `chromium` binary must hash to `9c94b57491fcc1a4b5a013ecb8fa13a637cc9a16aebea5041899c3cb033e5a13`. The already published Engine archive SHA256 is `0b6a73c964354214262d01f2d9bec2d0ab253cac8d27de04708912e804ef0874`.
4. Supply official Node8.16.2 at `/workspace/mgu-browser/.local/backend-start-audit/node-v8.16.2-linux-x64/bin/node`. Its official archive SHA256 is `88617a293f5828cc94ee99c94a43fbea12b989e34fe643fc14885a14748a8da6`. This historical version is used solely to match the MGU runtime ABI in the disposable fixture.
5. On Linux x86_64, compile the two original helpers with a C compiler and libc development/static-link support:

   ```sh
   cd /tmp/mgu-native-extension-prototype
   cc -static -O2 -o native_host native_host.c
   cc -shared -fPIC -O2 -o peercred.node peercred.c
   python run.py
   ```

   Host prerequisites are Python3, Docker with the locally available pinned Ubuntu18 image, and Pillow for inspecting the optional screenshot. The driver itself uses only Python standard-library modules. The private X helper and GUI runtime have their own documented build dependencies.

The image is `ubuntu@sha256:152dc042452c496007f07ca9127571cb9c29697f42acbfad72324b2bb2e43c98`. The fixture has network disabled, private IPC with128MiB shared memory, and read-only Engine/GUI/source binds. A separate writable fixture state bind is used. `SYS_ADMIN` and fixture AppArmor-unconfined are used to permit Chromium's own sandbox in this test environment; no privileged-container or Chrome no-sandbox switch is used. Root preparation copies the original sandbox helper to a root-owned4755 container-local file, then starts all GUI/endpoint/browser processes as UID1000. The NativeMessaging bridge is not setuid.

`run.py` writes fresh local evidence under `/tmp/mgu-native-extension-prototype/result.json` and `state/`, not into this review package. Raw state contains generated cookie values and browser profile files and must not be published. The driver cleans its named container in `finally`; it does not use external account operations or external networking. The optional `MGU_EXTENSION_TASK_ONLY=1` mode stops after the native Task Manager capture and is not the full success gate.

## Requirements before any production migration

This proves API availability and the architecture, not a complete replacement BrowserSession. Follow [protocol.md](protocol.md) for the current contract and the explicitly missing production behavior. In particular, add bounded snapshot batches/reconnect resync, verified frame/document lifecycle, native-window generation invalidation, encrypted profile/cookie recovery, download staging policy and controller/phone integration. The current fixed paths, small-fixture whole snapshots and Python driver are test scaffolding.

The extension cookie API does not expose every internal Chromium cookie field and is not a lossless whole-profile archive. Native `chrome.tabs` provides tab metadata, not the complete browser history/bookmark/profile transaction model. The extension does not handle site authentication, permissions, file choosers or downloads via page scripting: the normal native browser UI remains responsible for those flows.

Recent branded Google Chrome restricts command-line unpacked-extension loading; this proof uses the exact unbranded Debian Chromium Engine0.1. A future separately installed vendor Chrome runtime needs a supported extension installation path and its own tests. This experiment does not solve DRM provisioning or guarantee any provider's anti-abuse decision.
