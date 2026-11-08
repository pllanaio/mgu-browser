# Native helper protocol v1 — prototype

Validation status: the authored private-Xvfb/Node8 gates passed; the sanitized result and tested bounds are recorded in `test-result.json`. This is a sibling process, not a native addon loaded into Node8 or a production browser mode.

All integers are little-endian. No stream contains JSON, shell commands, filenames, clipboard contents or executable expressions. stdin is commands, stdout is small acknowledgements, inherited **fd3** is RGBA frames, stderr is diagnostics. All three protocol pipes are nonblocking. The owner supplies DISPLAY/XAUTHORITY and owns the entire private X session.

## Commands / responses

A command is `u32 bodyLength`, then this12-byte header, then the opcode payload:

| Offset in body | Type | Meaning |
| --- | --- | --- |
|0|u8|version1|
|1|u8|opcode|
|2|u16|flags, must0|
|4|u32|epoch|
|8|u32|request id|

Body length must be12..128. Fragmented and coalesced writes are supported. Invalid framing length is fatal immediately, with a best-effort BAD_LENGTH response and bounded shutdown; the helper never allocates or drains the advertised oversize body. Validly framed invalid commands get a response and no input action.

Each response is `u32 length=20`, then `u8 version=1`, `u8 opcode|0x80`, `u16 status`, `u32 echoedEpoch`, `u32 requestId`, `u32 activeEpoch`, `u32 value`. It is always24 bytes including the length. Statuses:0 OK,1 BAD_OPCODE,2 BAD_LENGTH,3 STALE,4 BUSY,5 UNSUPPORTED,6 INVALID,7 INTERNAL,8 SHUTTING_DOWN. The stdout queue has128 fixed slots; stdin is backpressured when it is full. No unbounded response or command queue exists.

| Opcode | Payload | Behavior / value |
| --- | --- | --- |
|1 SET_EPOCH|none|Header epoch must be nonzero and strictly greater than current. Releases held inputs. `value` is an old partially transmitted frame's epoch, or0.|
|2 PING|none|`value` bit0 means a frame is pending, bit1 held modifiers. Bootstrap epoch0 allowed.|
|3 CAPTURE|none|One pull credit. OK value is RGBA byte count; BUSY means no credit was queued.|
|4 KEY|u16 logicalKey,u16 action,u32 modifiers|Actions0 press,1 down,2 up; see below.|
|5 POINTER|u8 action,u8 button,u16 reserved0,i32 x,i32 y,u32 modifiers|Actions0 move,1 down,2 up,3 click,4 double-click. Button0 for move;1 left,2 middle,3 right otherwise.|
|6 WHEEL|i32 x,i32 y,i32 deltaX,i32 deltaY,u32 modifiers|Coarse native wheel ticks, each delta bounded-8..8. NegativeY scrolls up; positiveY down; negativeX left.|
|7 RELEASE_INPUT|none|Releases all helper-held buttons, keys and modifiers.|
|8 STOP|none|Releases input immediately, sends best-effort ACK, exits after at most200ms response drain under normal X-server operation. Bootstrap epoch0 allowed.|
|9 TEXT|any bounded payload|Always UNSUPPORTED. No ASCII substitution, DOM injection or clipboard access.|

All other operations require a matching current nonzero epoch. Unknown keys/opcodes, illegal modifiers, reserved bits, invalid lengths, out-of-range coordinates and duplicate down/unmatched up operations are rejected before input changes. Coordinates refer to current physical root pixels and must be inside it; they are not silently clamped. Modifiers: SHIFT1,CTRL2,ALT4,META8, no other bits.

Logical keys:1 Tab,2 Enter,3 Escape,4 Space,5 Backspace,6 Delete,7 Left,8 Right,9 Up,10 Down,11 Home,12 End,13 PageUp,14 PageDown,15 Insert;16..27 F1..F12;0x100..0x119 logical a..z;0x130..0x139 digits0..9;0x140..0x14a base punctuation `- = [ ] backslash ; apostrophe grave , . /`. These are native logical key events resolved through the private X keyboard map, not a Unicode text API. Unsupported keyboard mappings return UNSUPPORTED. No promise of multilingual/IME/text-entry parity is made.

KEY press and pointer click/double-click/wheel apply transient requested modifiers in addition to already-held modifiers, then restore the prior mask. KEY down / pointer down/move apply a persistent explicit modifier mask. KEY up / pointer up release the key/button first, then apply the supplied remaining modifier mask. A drag is validated pointer down→moves→up; no arbitrary timed macro or script runs. RELEASE_INPUT, accepted SET_EPOCH, EOF and SIGTERM release all held inputs.

## Frames / ownership

fd3 carries `u32 bodyLength`, then this32-byte header, then tightly packed RGBA8888 with alpha255:

| Offset in body | Type | Meaning |
| --- | --- | --- |
|0|u32|magic0x4655474d, bytes `MGUF`|
|4|u16|version1|
|6|u16|headerBytes32|
|8|u32|epoch|
|12|u32|capture request id|
|16|u32|width|
|20|u32|height|
|24|u32|stride=width×4|
|28|u32|format1 RGBA8888|

Body length must equal32+width×height×4. Geometry is bounded to1600×900 **and** RGBA≤4MiB-64 bytes, fitting the current MGU IPC's4MiB-20 allowance with margin. Thus1600×900 is rejected;1600×533 is accepted. Only the qualified little-endian32-bit BGRX TrueColor Xvfb format is currently supported; capture rejects other formats explicitly.

There is at most **one immutable pending output frame**. Capture copies the XShm snapshot into an owned RGBA buffer before sending its header. While any frame bytes remain unwritten, further CAPTURE credits return BUSY. fd3 pressure never overwrites partially written bytes. On SET_EPOCH, an entirely unwritten old frame is discarded; a partial old frame finishes with its original epoch/id. The owner must discard old-epoch frames and may retry a BUSY new capture after it consumes the old one. No extra pending-capture slot exists.

At most one XShm image and one RGBA allocation are retained (under~8MiB plus Xlib/protocol state), plus the kernel pipe buffer. Response/command parsing is fixed-size. fd3 writes are capped to32KiB per loop, with stdin/ACK processing first; this keeps input active under frame pressure. The client must also keep bounded credit/stream parsing and stop reading when its own consumer is full.

## Shutdown / limits

EOF, SIGTERM, STOP or output-pipe failure stop capture and release input. A partial frame may terminate at EOF during shutdown; the reader must discard it, not combine it with another session. On Linux, the SHM segment is marked IPC_RMID immediately after the helper attaches, before the server roundtrip, detached on normal exit, and released by the X server when its client connection closes. A final X roundtrip confirms the release requests before closing; the shutdown watchdog bounds a stalled server.

The trusted X server's synchronous capture/geometry operations can still stall if that server hangs. SIGTERM arms a2-second hard exit watchdog; the session owner must stop/restart the whole private X session after X I/O failure or a helper crash, because input cannot be repaired over a dead connection. No production supervisor, privilege separation, vehicle gate, clipboard, AT-SPI focus metadata, hardware decoder or MGU upload transport is implemented here.
