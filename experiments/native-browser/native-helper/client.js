'use strict';

var childProcess = require('child_process');
var EventEmitter = require('events').EventEmitter;
var path = require('path');

var MAX_FRAME_BYTES = 4 * 1024 * 1024;
var MAX_RGBA_BYTES = MAX_FRAME_BYTES - 64;
var OPS = {SET_EPOCH: 1, PING: 2, CAPTURE: 3, KEY: 4, POINTER: 5, WHEEL: 6, RELEASE: 7, STOP: 8, TEXT: 9};
var STATUS = ['OK', 'BAD_OPCODE', 'BAD_LENGTH', 'STALE', 'BUSY', 'UNSUPPORTED', 'INVALID', 'INTERNAL', 'SHUTTING_DOWN'];
var KEYS = {Tab: 1, Enter: 2, Escape: 3, Space: 4, Backspace: 5, Delete: 6, Left: 7, Right: 8, Up: 9, Down: 10, Home: 11, End: 12, PageUp: 13, PageDown: 14, Insert: 15};
var PUNCTUATION = ['-', '=', '[', ']', '\\', ';', "'", '`', ',', '.', '/'];
var i;
for (i = 1; i <= 12; i++) KEYS['F' + i] = 15 + i;
for (i = 0; i < 26; i++) KEYS[String.fromCharCode(97 + i)] = 0x100 + i;
for (i = 0; i < 10; i++) KEYS[String(i)] = 0x130 + i;
for (i = 0; i < PUNCTUATION.length; i++) KEYS[PUNCTUATION[i]] = 0x140 + i;
KEYS.ArrowLeft = KEYS.Left; KEYS.ArrowRight = KEYS.Right; KEYS.ArrowUp = KEYS.Up; KEYS.ArrowDown = KEYS.Down;
var KEY_IDS = {};
Object.keys(KEYS).forEach(function (name) { KEY_IDS[KEYS[name]] = true; });

function failure(code, message) {
  var error = new Error(message);
  error.code = code;
  return error;
}

function integer(value, min, max, name) {
  if (typeof value !== 'number' || !isFinite(value) || Math.floor(value) !== value || value < min || value > max) {
    throw failure('INVALID', name + ' is outside its supported range');
  }
  return value;
}

function modifiers(options) {
  var value = options && options.modifiers;
  if (value === undefined) return 0;
  if (typeof value === 'number') return integer(value, 0, 15, 'Modifiers');
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw failure('INVALID', 'Modifiers must be a bit mask or an object');
  var mask = 0;
  Object.keys(value).forEach(function (name) {
    var bits = {shift: 1, ctrl: 2, alt: 4, meta: 8};
    if (!Object.prototype.hasOwnProperty.call(bits, name) || typeof value[name] !== 'boolean') throw failure('INVALID', 'Unknown modifier');
    if (value[name]) mask |= bits[name];
  });
  return mask;
}

// One allocation per bounded record. Chunks are copied into their final owner;
// repeated Buffer.concat on growing image data would be quadratic.
function FramedReader(min, max, onRecord, onError) {
  this.min = min; this.max = max; this.onRecord = onRecord; this.onError = onError;
  this.prefix = Buffer.alloc(4); this.prefixOffset = 0; this.body = null; this.bodyOffset = 0; this.failed = false;
}
FramedReader.prototype.push = function (chunk) {
  if (this.failed) return;
  var offset = 0;
  try {
    while (offset < chunk.length) {
      if (!this.body) {
        var n = Math.min(4 - this.prefixOffset, chunk.length - offset);
        chunk.copy(this.prefix, this.prefixOffset, offset, offset + n);
        this.prefixOffset += n; offset += n;
        if (this.prefixOffset !== 4) continue;
        var length = this.prefix.readUInt32LE(0);
        if (length < this.min || length > this.max) throw failure('PROTOCOL', 'Native helper record length is invalid');
        this.body = Buffer.alloc(length); this.bodyOffset = 0;
      }
      var remaining = Math.min(this.body.length - this.bodyOffset, chunk.length - offset);
      chunk.copy(this.body, this.bodyOffset, offset, offset + remaining);
      this.bodyOffset += remaining; offset += remaining;
      if (this.bodyOffset === this.body.length) {
        var body = this.body;
        this.body = null; this.bodyOffset = 0; this.prefixOffset = 0;
        this.onRecord(body);
        if (this.failed) return;
      }
    }
  } catch (error) {
    this.failed = true;
    this.body = null;
    this.onError(error);
  }
};
FramedReader.prototype.finish = function () {
  if (!this.failed && (this.prefixOffset || this.body)) {
    this.failed = true; this.body = null;
    this.onError(failure('PROTOCOL', 'Native helper ended an incomplete record'));
  }
};
FramedReader.prototype.discard = function () {
  this.failed = true; this.body = null; this.prefixOffset = 0; this.bodyOffset = 0;
};

class NativeHelperClient extends EventEmitter {
  constructor(options) {
    super();
    options = options || {};
    if (typeof options.helperPath !== 'string' || !path.isAbsolute(options.helperPath)) throw failure('INVALID', 'An absolute helperPath is required');
    if (!options.env || typeof options.env !== 'object' || Array.isArray(options.env)) throw failure('INVALID', 'An explicit helper environment is required');
    var args = options.helperArgs || [];
    if (!Array.isArray(args) || args.length > 8 || args.some(function (arg) { return typeof arg !== 'string' || arg.length > 1024; })) throw failure('INVALID', 'Helper arguments are invalid');
    if (options.cwd !== undefined && (typeof options.cwd !== 'string' || !path.isAbsolute(options.cwd))) throw failure('INVALID', 'cwd must be an absolute path');
    this.maxFrameBytes = integer(options.maxFrameBytes === undefined ? MAX_FRAME_BYTES : options.maxFrameBytes, 36, MAX_FRAME_BYTES, 'Frame byte limit');
    this.requestTimeoutMs = integer(options.requestTimeoutMs === undefined ? 2000 : options.requestTimeoutMs, 50, 30000, 'Request timeout');
    this.frameTimeoutMs = integer(options.frameTimeoutMs === undefined ? 5000 : options.frameTimeoutMs, 100, 30000, 'Frame timeout');
    this.stopTimeoutMs = integer(options.stopTimeoutMs === undefined ? 500 : options.stopTimeoutMs, 50, 2000, 'Stop timeout');
    this.epoch = 0; this._nextId = 1; this._pending = new Map(); this._capture = null;
    this._state = 'open'; this._terminalError = null; this._stopPromise = null; this._termTimer = null; this._killTimer = null;
    var self = this;
    this._closePromise = new Promise(function (resolve) { self._resolveClose = resolve; });
    this._responses = new FramedReader(20, 20, function (body) { self._response(body); }, function (error) { self._fail(error); });
    this._frames = new FramedReader(36, this.maxFrameBytes, function (body) { self._frame(body); }, function (error) { self._fail(error); });
    this._child = childProcess.spawn(options.helperPath, args, {env: options.env, cwd: options.cwd, shell: false, stdio: ['pipe', 'pipe', 'pipe', 'pipe']});
    this._child.stdout.on('data', function (chunk) { self._responses.push(chunk); });
    this._child.stdio[3].on('data', function (chunk) { self._frames.push(chunk); });
    this._child.stderr.on('data', function (chunk) {
      // Nothing is retained or logged. Diagnostics are an explicit opt-in.
      if (self.listenerCount('diagnostic')) self.emit('diagnostic', chunk.slice(0, 1024).toString('utf8'));
    });
    this._child.stdin.on('error', function (error) { if (self._state === 'open') self._fail(failure('PIPE', 'Native helper command pipe closed')); });
    this._child.stdout.on('error', function () { self._fail(failure('PIPE', 'Native helper response pipe failed')); });
    this._child.stdio[3].on('error', function () { self._fail(failure('PIPE', 'Native helper frame pipe failed')); });
    this._child.stdout.on('end', function () {
      if (self._state === 'open') { self._responses.finish(); if (self._state === 'open') self._fail(failure('PIPE', 'Native helper response pipe closed')); }
    });
    this._child.stdio[3].on('end', function () {
      if (self._state === 'open') { self._frames.finish(); if (self._state === 'open') self._fail(failure('PIPE', 'Native helper frame pipe closed')); }
    });
    this._child.on('error', function () { self._fail(failure('SPAWN', 'Native helper could not start')); });
    this._child.on('close', function (code, signal) { self._closed(code, signal); });
  }

  _id() {
    var id = this._nextId;
    do {
      id = this._nextId;
      this._nextId = (this._nextId + 1) >>> 0;
      if (!this._nextId) this._nextId = 1;
    } while (!id || this._pending.has(id));
    return id;
  }

  _send(opcode, payload, epoch, allowStopping, id) {
    var self = this;
    if (this._state !== 'open' && !(allowStopping && this._state === 'stopping')) return Promise.reject(this._terminalError || failure('CLOSED', 'Native helper is closed'));
    if (this._pending.size >= 32) return Promise.reject(failure('QUEUE_FULL', 'Native helper has 32 pending requests'));
    payload = payload || Buffer.alloc(0);
    if (payload.length > 116) return Promise.reject(failure('INVALID', 'Native helper command is too long'));
    id = id || this._id();
    var command = Buffer.alloc(16 + payload.length);
    command.writeUInt32LE(12 + payload.length, 0); command[4] = 1; command[5] = opcode;
    command.writeUInt32LE(epoch, 8); command.writeUInt32LE(id, 12); payload.copy(command, 16);
    return new Promise(function (resolve, reject) {
      var timer = setTimeout(function () { self._fail(failure('TIMEOUT', 'Native helper request timed out')); }, self.requestTimeoutMs);
      self._pending.set(id, {id: id, opcode: opcode, epoch: epoch, resolve: resolve, reject: reject, timer: timer});
      try {
        self._child.stdin.write(command, function (error) { if (error && self._state === 'open') self._fail(failure('PIPE', 'Native helper command write failed')); });
      } catch (error) { self._fail(failure('PIPE', 'Native helper command write failed')); }
    });
  }

  _response(body) {
    if (body[0] !== 1 || !(body[1] & 0x80) || body.readUInt16LE(2) > 8) throw failure('PROTOCOL', 'Native helper response header is invalid');
    var id = body.readUInt32LE(8), entry = this._pending.get(id);
    if (!entry) return; // Cancelled epochs can still have in-flight ACKs.
    if ((body[1] & 0x7f) !== entry.opcode || body.readUInt32LE(4) !== entry.epoch) throw failure('PROTOCOL', 'Native helper response does not match its request');
    var status = body.readUInt16LE(2);
    var response = {id: id, opcode: entry.opcode, epoch: entry.epoch, activeEpoch: body.readUInt32LE(12), value: body.readUInt32LE(16)};
    if (!status && response.activeEpoch !== entry.epoch) throw failure('PROTOCOL', 'Native helper acknowledged a different active epoch');
    this._pending.delete(id); clearTimeout(entry.timer);
    if (status) {
      var error = failure(STATUS[status], 'Native helper rejected a request: ' + STATUS[status]);
      error.status = status; entry.reject(error); return;
    }
    entry.resolve(response);
  }

  _frame(body) {
    if (body.readUInt32LE(0) !== 0x4655474d || body.readUInt16LE(4) !== 1 || body.readUInt16LE(6) !== 32 || body.readUInt32LE(28) !== 1) throw failure('PROTOCOL', 'Native helper frame header is invalid');
    var epoch = body.readUInt32LE(8), id = body.readUInt32LE(12), width = body.readUInt32LE(16), height = body.readUInt32LE(20), stride = body.readUInt32LE(24);
    if (!width || width > 1600 || !height || height > 900 || stride !== width * 4 || body.length !== 32 + stride * height || stride * height > MAX_RGBA_BYTES) throw failure('PROTOCOL', 'Native helper frame geometry is invalid');
    if (this._state !== 'open' || epoch !== this.epoch) return;
    var capture = this._capture;
    if (!capture || capture.id !== id || capture.epoch !== epoch || capture.frame) throw failure('PROTOCOL', 'Native helper sent an unexpected frame');
    // This allocation belongs to this frame only and is never reused by the reader.
    capture.frame = {id: id, epoch: epoch, width: width, height: height, stride: stride, format: 'RGBA8888', data: body.slice(32)};
    this._finishCapture(capture);
  }

  _finishCapture(capture) {
    if (this._capture !== capture || !capture.ack || !capture.frame) return;
    if (capture.expectedBytes !== capture.frame.data.length) { this._fail(failure('PROTOCOL', 'Native helper capture size does not match its frame')); return; }
    clearTimeout(capture.timer); this._capture = null;
    capture.resolve(capture.frame);
  }

  _rejectCapture(error) {
    var capture = this._capture;
    if (!capture) return;
    this._capture = null; clearTimeout(capture.timer); capture.reject(error);
  }

  _cancel(error) {
    this._pending.forEach(function (entry) { clearTimeout(entry.timer); entry.reject(error); });
    this._pending.clear(); this._rejectCapture(error);
  }

  _fail(error) {
    if (this._state === 'closed') return;
    this._terminalError = error; this._state = 'closed'; this._cancel(error);
    this._responses.discard(); this._frames.discard();
    this.emit('failure', error);
    try { this._child.stdin.destroy(); this._child.kill('SIGTERM'); } catch (ignored) {}
    var self = this;
    if (!this._killTimer) this._killTimer = setTimeout(function () { try { self._child.kill('SIGKILL'); } catch (ignored) {} }, 250);
  }

  _closed(code, signal) {
    clearTimeout(this._termTimer); clearTimeout(this._killTimer);
    this._state = 'closed'; this._cancel(this._terminalError || failure('CLOSED', 'Native helper exited'));
    this._responses.discard(); this._frames.discard();
    this._resolveClose({code: code, signal: signal}); this.emit('close', code, signal);
  }

  _active() {
    if (!this.epoch) throw failure('INVALID', 'setEpoch must establish an input generation first');
  }

  setEpoch(epoch) {
    try { integer(epoch, 1, 0xffffffff, 'Epoch'); if (epoch <= this.epoch) throw failure('INVALID', 'Epoch must strictly increase'); }
    catch (error) { return Promise.reject(error); }
    if (this._state !== 'open') return Promise.reject(this._terminalError || failure('CLOSED', 'Native helper is closed'));
    this.epoch = epoch; this._cancel(failure('STALE', 'Native helper generation changed'));
    var self = this;
    return this._send(OPS.SET_EPOCH, null, epoch).then(function (response) { return response; }, function (error) {
      if (error.code !== 'STALE') self._fail(error);
      throw error;
    });
  }

  ping() { return this._send(OPS.PING, null, this.epoch); }

  capture() {
    try { this._active(); } catch (error) { return Promise.reject(error); }
    if (this._state !== 'open') return Promise.reject(this._terminalError || failure('CLOSED', 'Native helper is closed'));
    if (this._capture) return Promise.reject(failure('BUSY', 'A native frame is already pending'));
    var self = this, id = this._id();
    return new Promise(function (resolve, reject) {
      var capture = {id: id, epoch: self.epoch, resolve: resolve, reject: reject, ack: false, frame: null};
      capture.timer = setTimeout(function () { self._fail(failure('TIMEOUT', 'Native helper frame timed out')); }, self.frameTimeoutMs);
      self._capture = capture;
      self._send(OPS.CAPTURE, null, capture.epoch, false, id).then(function (response) {
        if (self._capture !== capture) return;
        if (response.value < 4 || response.value > Math.min(MAX_RGBA_BYTES, self.maxFrameBytes - 32)) { self._fail(failure('PROTOCOL', 'Native helper capture size is invalid')); return; }
        capture.expectedBytes = response.value; capture.ack = true; self._finishCapture(capture);
      }, function (error) { if (self._capture === capture) self._rejectCapture(error); });
    });
  }

  key(name, options) {
    try {
      this._active(); options = options || {};
      var code = typeof name === 'number' ? name : KEYS[name];
      if (!KEY_IDS[code]) throw failure('UNSUPPORTED', 'That native key is not supported');
      var actions = {press: 0, down: 1, up: 2}, action = options.action === undefined ? 0 : (Object.prototype.hasOwnProperty.call(actions, options.action) ? actions[options.action] : undefined);
      if (action === undefined) throw failure('INVALID', 'Native key action is invalid');
      var data = Buffer.alloc(8); data.writeUInt16LE(code, 0); data.writeUInt16LE(action, 2); data.writeUInt32LE(modifiers(options), 4);
      return this._send(OPS.KEY, data, this.epoch);
    } catch (error) { return Promise.reject(error); }
  }

  pointer(action, x, y, options) {
    try {
      this._active(); options = options || {};
      var actions = {move: 0, down: 1, up: 2, click: 3, double: 4}, value = Object.prototype.hasOwnProperty.call(actions, action) ? actions[action] : undefined;
      if (value === undefined) throw failure('INVALID', 'Native pointer action is invalid');
      integer(x, 0, 1599, 'Pointer x'); integer(y, 0, 899, 'Pointer y');
      var button = options.button === undefined ? (value ? 1 : 0) : options.button;
      if (typeof button === 'string') button = {left: 1, middle: 2, right: 3}[button];
      integer(button, value ? 1 : 0, value ? 3 : 0, 'Pointer button');
      var data = Buffer.alloc(16); data[0] = value; data[1] = button; data.writeInt32LE(x, 4); data.writeInt32LE(y, 8); data.writeUInt32LE(modifiers(options), 12);
      return this._send(OPS.POINTER, data, this.epoch);
    } catch (error) { return Promise.reject(error); }
  }

  wheel(x, y, deltaX, deltaY, options) {
    try {
      this._active(); integer(x, 0, 1599, 'Wheel x'); integer(y, 0, 899, 'Wheel y');
      integer(deltaX, -8, 8, 'Wheel horizontal ticks'); integer(deltaY, -8, 8, 'Wheel vertical ticks');
      var data = Buffer.alloc(20); data.writeInt32LE(x, 0); data.writeInt32LE(y, 4); data.writeInt32LE(deltaX, 8); data.writeInt32LE(deltaY, 12); data.writeUInt32LE(modifiers(options), 16);
      return this._send(OPS.WHEEL, data, this.epoch);
    } catch (error) { return Promise.reject(error); }
  }

  release() { try { this._active(); return this._send(OPS.RELEASE, null, this.epoch); } catch (error) { return Promise.reject(error); } }
  text() { return Promise.reject(failure('UNSUPPORTED', 'Text and clipboard input are not supported by the native helper')); }

  stop() {
    if (this._stopPromise) return this._stopPromise;
    if (this._state === 'closed') return this._closePromise;
    this._state = 'stopping'; this._cancel(failure('CLOSED', 'Native helper is stopping'));
    var self = this;
    this._send(OPS.STOP, null, this.epoch, true).then(function () { self._child.stdin.end(); }, function () {});
    this._termTimer = setTimeout(function () {
      try { self._child.kill('SIGTERM'); } catch (ignored) {}
      self._killTimer = setTimeout(function () { try { self._child.kill('SIGKILL'); } catch (ignored) {} }, 250);
    }, this.stopTimeoutMs);
    this._stopPromise = this._closePromise;
    return this._stopPromise;
  }

  destroy() { return this.stop(); }
}

NativeHelperClient.OPCODES = OPS;
NativeHelperClient.KEYS = KEYS;
Object.freeze(OPS); Object.freeze(KEYS);
NativeHelperClient.MAX_FRAME_BYTES = MAX_FRAME_BYTES;
NativeHelperClient.MAX_RGBA_BYTES = MAX_RGBA_BYTES;
module.exports = NativeHelperClient;
