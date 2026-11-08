# Integration protocol and trust boundary

The extension, manifest, bridge, endpoint and pages in this subtree are original MIT sources. This protocol exists only in the disposable proof.

## Transport

The extension calls `chrome.runtime.connectNative('org.mgu.browser.prototype')`. Chromium checks the root-owned system manifest's exact `allowed_origins` entry. The native executable checks the same originating-extension argument, then connects to `/tmp/mgu-native-extension-prototype/state/native.sock` and verifies the server's Linux `SO_PEERCRED` UID equals its own. The Node8 receiver verifies the accepted peer UID through the small Node-API helper. A separate private `control.sock` is the fixture driver's trusted command endpoint and has the same UID check.

Both sockets have0600 permissions inside the0700 dedicated run directory. The extension and host executable/manifest are copied to immutable root-owned container paths, with no write permission for UID1000. The bridge has no setuid bit. Public pages cannot use NativeMessaging or the local Unix socket, and there is no web-accessible extension resource, `window.postMessage` relay, `onMessageExternal` or `onConnectExternal` listener.

The framing is a four-byte little-endian unsigned JSON UTF-8 length followed by exactly that many bytes. This matches native endianness on the tested x86_64 platform. The bridge rejects zero or lengths above256KiB before forwarding; Node applies the same maximum. NativeMessaging's browser limits are larger; this is a deliberately stricter fixture limit. Node uses UTF-8-safe decoding on its control channel, bounds pending extension commands to32, rejects excessive outgoing buffered bytes and handles socket errors.

`allowed_origins` authenticates an extension to Chromium's launcher. The argv origin can be forged by arbitrary local code, so it is not an independent secret. UID/socket permissions exclude other user IDs, not arbitrary hostile code already executing as the dedicated browser UID or a privileged administrator. Production must retain a dedicated browser profile/UID/process trust boundary and immutable launch/configuration paths. No claim of protection against root or same-UID compromise is made.

## Messages

Commands originate only in the trusted private endpoint:

```json
{"v":1,"id":"request-7","kind":"command","op":"tabs.query","args":{}}
```

The worker returns exactly one correlated response:

```json
{"v":1,"id":"request-7","kind":"response","ok":true,"result":[]}
```

Errors contain a bounded message and no credential logging. A disconnected native port rejects outstanding endpoint requests rather than silently replaying commands. Current request IDs increase for the endpoint's lifetime. Unsolicited events are:

```json
{"v":1,"seq":42,"kind":"event","event":"tabUpdated","data":{}}
```

The proof operations are:

| Operation | Native API / purpose |
| --- | --- |
| `tabs.query` | Current native tab metadata |
| `tabs.create` | Explicit HTTP(S) URL, active/background |
| `tabs.update` | Explicit HTTP(S) navigation, activation or native tab mute |
| `tabs.remove` | Close explicit tab ID |
| `cookies.getAll` | Dedicated profile cookie snapshot; use `partitionKey:{}` for all partitions |
| `cookies.set` / `cookies.remove` | Explicit cookie roundtrip with full partition identity |
| `downloads.search` | Native filenames/state and bounded active-download progress polling |
| `downloads.cancel` | Explicit native download cancellation |

Events are `hello`, `tabs`, `tabCreated`, `tabUpdated`, `tabActivated`, `tabRemoved`, `cookieChanged`, `downloadCreated`, `downloadChanged` and `focus`.

The worker never derives a privileged command from page-controlled metadata. `runtime.onMessage` accepts only its own extension ID with a browser-supplied tab and frame/document identity, and only the fixed `focus` schema. The content script runs in the isolated extension world in all permitted frames. It has no page-world shim. It reads the deepest focused element using the legitimate `chrome.dom.openOrClosedShadowRoot` API. A WeakSet installs focus listeners on visited roots so transitions within one closed root remain visible. It reports type/editability/read-only/disabled/maxLength/password-kind/multiline, not value, DOM text or selected text. `closedRoots` counts roots whose native `mode` is `closed`.

A parent frame's `activeElement` can be an IFRAME while the child's field is focused. The `delegatesFocus` flag records this, and the proof consumer keeps each frame's latest metadata before choosing the nondelegating focused frame. Taking the last global event would be incorrect. Browser-supplied `documentId` separates navigated documents. Production still needs explicit frame lifecycle ownership and stale-document invalidation; this small proof does not implement a full navigation tree.

## Cookie and media semantics

Cookie identity includes storeId, name, domain, path and the complete partition key. `partitionKey.topLevelSite` and `hasCrossSiteAncestor` must both survive roundtrip. `getAll({})` omits partitioned cookies, whereas `getAll({partitionKey:{}})` includes all partitions and unpartitioned cookies in this exact engine. Preserve host-only cookies by omitting `domain` when calling `set`; preserve session cookies by omitting `expirationDate`. `session` and `hostOnly` are returned metadata rather than writable set fields. HttpOnly is exposed through the authorized extension API. Overwrite is reported as removed/cause-overwrite then inserted/cause-explicit. No cookie values are included in published evidence.

The extension cookie API lacks some internal Chromium cookie fields, so it cannot replace complete encrypted profile recovery. Storage, IndexedDB, service workers, browser session/history, downloads and native profile databases need a coherent stopped-writer archive/recovery plan. Persistent cookie expiry metadata was tested; whole-profile restart/crash recovery was not retested by this extension experiment.

Native `tabs.audible` is recent audio activity, including child and closed-root playback. It has a tail after silence and is independent of `mutedInfo.muted`. Combine both with native media/window lifecycle and vehicle audio focus. This experiment measures extension state, not vehicle speaker output. `downloads.onChanged` intentionally omits bytesReceived; use bounded `downloads.search` polling only while downloads are active.

## Production gates still required

- A browser-run generation, native-port generation, tab/frame/document ownership map and explicit close/navigation invalidation across every queued input/command.
- Bounded snapshot batches with a snapshot barrier plus subsequent sequence numbers; reconnect resync for tabs, cookies, downloads and focus. Whole-profile cookie/download results can exceed256KiB, and MV3 worker restart can reset the current sequence.
- Strict total queue/event-byte budgets and bounded page-controlled URLs/titles/change records. The proof retains at most4096 events but is not yet a production byte-budgeted event journal.
- Frame lifecycle support beyond passive focus events, including detached frames and documents replaced without a top-tab navigation. Explicit unknown/truncated focus state beyond the current16-root traversal bound.
- Dedicated private profile and immutable extension/host installation, authenticated/encrypted profile recovery, configured download staging and secure vault integration only through explicit future commands.
- Native full-window capture/input lifecycle, controller and phone input parity, audio focus, native browser prompts and performance on real MGU hardware.

Official references: [NativeMessaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging), [cookies](https://developer.chrome.com/docs/extensions/reference/api/cookies), [dom](https://developer.chrome.com/docs/extensions/reference/api/dom), [tabs](https://developer.chrome.com/docs/extensions/reference/api/tabs), [downloads](https://developer.chrome.com/docs/extensions/reference/api/downloads). Exact-engine cookie semantics were checked against [Chromium156 cookies_helpers.cc](https://chromium.googlesource.com/chromium/src/+/156.0.8078.79/chrome/browser/extensions/api/cookies/cookies_helpers.cc).
