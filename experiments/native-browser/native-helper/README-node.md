# Node 8 client

`client.js` is a dependency-free Node 8 wrapper for the separate native helper process. It never loads the private X11/GLIBC runtime into Node's address space. It launches only the explicitly supplied absolute executable, with `shell:false`, an explicit environment and four inherited pipe channels. No executable, X server, credentials, profile or runtime libraries are included here.

```js
var NativeHelper = require('./client');
var helper = new NativeHelper({
  helperPath: '/absolute/path/to/the/built/native-helper',
  env: {
    DISPLAY: ':91',
    XAUTHORITY: '/absolute/private/runtime/Xauthority',
    XLOCALEDIR: '/absolute/private/runtime/usr/share/X11/locale',
    GCONV_PATH: '/absolute/private/runtime/usr/lib/x86_64-linux-gnu/gconv',
    LOCPATH: '/absolute/private/locale/usr/lib/locale',
    LANG: 'C.utf8', LC_ALL: 'C.utf8'
  }
});

helper.setEpoch(1).then(function () {
  return helper.key('Tab', {modifiers: {shift: true}});
}).then(function () {
  return helper.capture();
}).then(function (frame) {
  // frame.data is owned RGBA8888 memory. Later captures never overwrite it.
  consumePixels(frame.width, frame.height, frame.data);
  return helper.stop();
}).catch(function (error) {
  return helper.stop().then(function () { throw error; });
});
```

These paths are caller inputs, not installed locations. The helper must already be built against a coherent private runtime; start an authenticated private X server separately. The caller owns its display, user, runtime directory and filesystem policy. An optional absolute `cwd` and up to eight explicit string `helperArgs` are supported; the production C helper itself currently takes no arguments. No environment values or image bytes are logged by this client.

## API

- `setEpoch(nonzeroUint32)` strictly increases the generation. It immediately rejects older pending promises with `STALE`. The helper's FIFO epoch barrier releases held input and rejects actions received with the old generation. Commands already executed before the barrier cannot be undone.
- `capture()` resolves one `{epoch,id,width,height,stride,format:'RGBA8888',data:Buffer}`. Exactly one capture promise may be pending. `BUSY` rejects an additional call. The buffer is independently owned, not a recycled view; JavaScript callers can mutate their own pixels and must bound any history they retain.
- `key(name, options)` supports the protocol's known keys, F1–F12, lowercase letters, digits and base punctuation keys. `action` is `press` (default), `down` or `up`. `modifiers` is either a bit mask (`shift=1,ctrl=2,alt=4,meta=8`) or a boolean object with those names. Uppercase input requires the corresponding individual key plus Shift; this is a native key API, not a text insertion API.
- `pointer(action,x,y,options)` supports `move`, `down`, `up`, `click`, `double`. Buttons are `left`, `middle`, `right` or1–3; move uses button0. `wheel(x,y,deltaX,deltaY,options)` uses bounded native ticks, each between−8 and8. Coordinates are integers; the helper additionally validates the actual root geometry. Use down/move/up for native pointer drags.
- `release()` releases held native keys/buttons/modifiers. `ping()` checks the active pipe. `stop()` / `destroy()` return a promise for owned-child closure and cancel pending work.
- `text()` explicitly rejects `UNSUPPORTED`, including ASCII strings. Unicode text, clipboard, IME composition and arbitrary key codes are not implemented and are never silently approximated.

Set an epoch before capture or input. `PING` and `STOP` also work in the initial epoch0. A partially transmitted old frame cannot be interrupted without breaking framing; the helper finishes it with its old epoch and the client discards it. A new capture can receive `BUSY` until that old frame drains. Retry the latest capture after the transport becomes ready; do not queue many capture requests.

## Bounds and failure behavior

The client has at most32 command requests and one capture pending. Record lengths are checked before allocation. The fd3 frame payload is capped at4MiB, RGBA pixels at4MiB−64, dimensions at1600×900, and stride must equal width×4. Each bounded record gets one final allocation; fragments are copied into it without repeatedly concatenating a growing image. The application must retain only the frames it needs.

Default command timeout is2000ms, frame timeout5000ms. Invalid framing, truncated frames, pipe failure or timeout rejects pending work and terminates the owned child. `stop()` requests normal shutdown, sends SIGTERM after500ms if needed, then SIGKILL250ms later. Options can bound these timeouts within the ranges validated by the constructor. OS process scheduling still applies; this does not supervise a whole X server/browser process tree.

The separate ACK and fd3 parsers allow key/control responses while an image is incomplete. Stderr is discarded by default, never retained. A caller may explicitly subscribe to `diagnostic` for up to1024 characters from each stderr chunk; avoid collecting sensitive diagnostics. Promise failures use short structured codes; the optional `failure` event does not include command contents. No reserved EventEmitter `error` event is emitted without a listener.

## Tests

```sh
/absolute/path/to/node8 test/client.test.js
```

The test file runs an authored child fixture using the same Node executable. It covers fragmented and coalesced responses, image ownership, independent ACK/frame streams, one capture credit, generation changes with a partial old image, oversized/truncated records, request limits/timeouts and forced shutdown. Its result marker is `NATIVE_HELPER_CLIENT_RESULT`. It does not claim real X11 input/capture; the separate real-runtime tests cover the C helper.
