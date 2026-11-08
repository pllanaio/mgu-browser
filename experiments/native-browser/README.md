# Native desktop browser experiment — source review only

This is an **authored-only experimental source/evidence package**, based on production source commit `42256e71671ec370f05fa0a494941110e4f21463` (MGU Browser0.16). It is intended for the separate `codex/native-desktop-prototype` branch. It does not modify production 0.16, publish a Store component, enable a new browser mode, or update any vehicle.

The experiments demonstrate a legitimate ordinary Chromium window without headless/debugging/automation flags or webdriver spoofing. Exact Engine 0.1 runs sandboxed under an old-base Ubuntu 18 container with a coherent private Xvfb/GTK runtime. Native video/fullscreen/audio and normal extension metadata APIs work. `navigator.webdriver` is actually false. This is not a promise that a provider cannot detect software graphics or other environment details.

Start with:

- [Production integration plan](docs/production-plan.md): minimal separate session facade, existing frontend/protocol/audio reuse, and actual blockers.
- [Native window/video/audio proof](native-gui-proof/README.md): tested30 fps/fullscreen1280×400, native prompts,440Hz PCM and measured memory/performance limits.
- [Native extension/Native Messaging proof](extension-proof/README.md): tabs/URL/title, audible/mute, closed-shadow/OOPIF field metadata, partitioned cookies and downloads without CDP.
- [Bounded native helper](native-helper/README.md): separate-process X11 capture/input protocol, Node8 client and explicit validation status.
- [External input manifests](inputs/external-inputs.json): exact public package/source URLs+hashes. No referenced runtime payload is included.

The WebGL-capable profile sustained 30 fps in the authored host video fixture. WebGL-capable60 fps delivered about 57.5 changing frames/s with 5.6% video-frame drops. Measured total native memory is about 650–675 MiB. Physical headunit kernel/resources, real controller/keyboard integration and BMW speakers remain unqualified. The GUI runtime scratch dependency closure is broad and source/notices/packaging work is unfinished; it must not be shipped wholesale.

This tree intentionally contains no ELF/native addon, third-party runtime/library, .deb/archive, CDM/proprietary payload, private key, Xauthority, browser profile, raw cookie values, raw PCM or endpoint token. The extension manifest contains a **public identity key**, not a private signing key. Screenshots show only original fixture pages/native Chromium UI. [audit_source_only.py](audit_source_only.py) checks the intended source-only boundary; it is not a legal clearance or a proof against every possible encoded secret.

Historical proof drivers document their fixed scratch prefixes and required external inputs; explicit-input tools place downloads/builds/state outside this source tree. Do not run experiments against a real profile or patch a runtime currently used by another fixture. No production/CDM/provider account operations are needed to review the evidence.

All authored code here is supplied under [MIT](LICENSE). External components keep their own licenses and source obligations; the manifests are references, not a completed third-party distribution offer. The experiments have not been reviewed as an installable/security-qualified product. Root project release work remains separate.
