'use strict';

// The same file doubles as a dependency-free child fixture. It never accesses X11.
if (process.argv[2] === '--fixture') {
  var fs = require('fs');
  var input = Buffer.alloc(0), active = 0, captures = 0, busy = false;
  var mode = process.env.NATIVE_HELPER_TEST_MODE || 'normal';
  var output = [], writing = false;
  function response(op, epoch, id, status, value) {
    var b = Buffer.alloc(24); b.writeUInt32LE(20, 0); b[4] = 1; b[5] = op | 0x80;
    b.writeUInt16LE(status || 0, 6); b.writeUInt32LE(epoch, 8); b.writeUInt32LE(id, 12); b.writeUInt32LE(active, 16); b.writeUInt32LE(value || 0, 20);
    output.push(b); flush();
  }
  function flush() {
    if (writing || !output.length) return;
    writing = true;
    if (mode === 'coalesce') {
      setImmediate(function () { var combined = Buffer.concat(output); output = []; process.stdout.write(combined); writing = false; flush(); });
      return;
    }
    var b = output.shift(), offset = 0;
    function next() {
      if (offset === b.length) { writing = false; flush(); return; }
      var size = mode === 'fragment' ? Math.min((offset % 5) + 1, b.length - offset) : b.length;
      process.stdout.write(b.slice(offset, offset + size)); offset += size; setImmediate(next);
    }
    next();
  }
  function image(epoch, id) {
    var b = Buffer.alloc(52); b.writeUInt32LE(48, 0); b.writeUInt32LE(0x4655474d, 4); b.writeUInt16LE(1, 8); b.writeUInt16LE(32, 10);
    b.writeUInt32LE(epoch, 12); b.writeUInt32LE(id, 16); b.writeUInt32LE(2, 20); b.writeUInt32LE(2, 24); b.writeUInt32LE(8, 28); b.writeUInt32LE(1, 32);
    for (var i = 36; i < b.length; i += 4) { b[i] = captures; b[i + 1] = 60; b[i + 2] = 120; b[i + 3] = 255; }
    return b;
  }
  function frame(epoch, id) {
    var b = image(epoch, id);
    if (mode === 'oversize') { var bad = Buffer.alloc(4); bad.writeUInt32LE(4 * 1024 * 1024 + 1, 0); fs.writeSync(3, bad); return; }
    if (mode === 'truncated') { fs.writeSync(3, b.slice(0, 13)); setTimeout(function () { process.exit(0); }, 25); return; }
    if (mode === 'blocked' || mode === 'epoch') {
      fs.writeSync(3, b.slice(0, 9));
      setTimeout(function () { fs.writeSync(3, b.slice(9)); busy = false; }, mode === 'epoch' ? 130 : 300);
      return;
    }
    if (mode === 'fragment') {
      var offset = 0;
      function next() { if (offset === b.length) { busy = false; return; } var n = Math.min((offset % 7) + 1, b.length - offset); fs.writeSync(3, b.slice(offset, offset + n)); offset += n; setImmediate(next); }
      next();
    } else { fs.writeSync(3, b); busy = false; }
  }
  if (mode === 'ignore-stop') process.on('SIGTERM', function () {});
  process.stdin.on('data', function (chunk) {
    input = Buffer.concat([input, chunk]);
    while (input.length >= 4 && input.length >= input.readUInt32LE(0) + 4) {
      var n = input.readUInt32LE(0), b = input.slice(4, 4 + n); input = input.slice(4 + n);
      var op = b[1], epoch = b.readUInt32LE(4), id = b.readUInt32LE(8);
      if (mode === 'hang' && op !== 8) continue;
      if (op === 1) { active = epoch; response(op, epoch, id); if (mode === 'frame-eof') setTimeout(function () { fs.closeSync(3); }, 25); }
      else if (op === 2) response(op, epoch, id, 0, captures);
      else if (op === 3) {
        if (busy) { response(op, epoch, id, 4); continue; }
        busy = true; captures++; response(op, epoch, id, 0, 16); frame(epoch, id);
      } else if (op === 8) {
        response(op, epoch, id);
        if (mode !== 'ignore-stop') setTimeout(function () { process.exit(0); }, 20);
      } else response(op, epoch, id);
    }
  });
  process.stdin.on('end', function () { if (mode !== 'ignore-stop') process.exit(0); });
  // Keep ignore-stop alive so the client's bounded SIGKILL fallback is exercised.
  if (mode === 'ignore-stop') setInterval(function () {}, 1000);
} else {
  var assert = require('assert');
  var NativeHelperClient = require('../client');
  var passed = [], clients = [];
  function delay(ms) { return new Promise(function (resolve) { setTimeout(resolve, ms); }); }
  function rejected(promise, code) {
    return promise.then(function () { throw new Error('Expected rejection ' + code); }, function (error) { assert.strictEqual(error.code, code); return error; });
  }
  function client(mode, extra) {
    var options = {helperPath: process.execPath, helperArgs: [__filename, '--fixture'], env: {NATIVE_HELPER_TEST_MODE: mode}, requestTimeoutMs: 700, frameTimeoutMs: 1000, stopTimeoutMs: 80};
    Object.keys(extra || {}).forEach(function (key) { options[key] = extra[key]; });
    var created = new NativeHelperClient(options); clients.push(created); return created;
  }
  async function test(name, fn) { await fn(); passed.push(name); }
  async function run() {
    await test('explicit options and input validation', async function () {
      assert.throws(function () { return new NativeHelperClient({helperPath: 'relative'}); });
      var c = client('normal');
      await rejected(c.capture(), 'INVALID'); await c.setEpoch(1);
      assert.strictEqual(NativeHelperClient.KEYS['\\'], 0x144); assert.strictEqual(Object.keys(NativeHelperClient.KEYS).filter(function (name) { return NativeHelperClient.KEYS[name] === 0x144; })[0].length, 1);
      await c.key('\\'); await c.key('-', {modifiers: {shift: true}});
      await rejected(c.key('ß'), 'UNSUPPORTED'); await rejected(c.text('ASCII is not a Unicode workaround'), 'UNSUPPORTED');
      await rejected(c.key('a', {action: 'toString'}), 'INVALID'); await rejected(c.pointer('toString', 1, 1), 'INVALID');
      await rejected(c.pointer('click', -1, 2), 'INVALID'); await rejected(c.wheel(1, 2, 9, 0), 'INVALID');
      await rejected(c.setEpoch(1), 'INVALID'); await c.stop();
    });
    await test('fragmented ACK and frame with stable owned pixels', async function () {
      var c = client('fragment'); await c.setEpoch(2);
      var both = await Promise.all([c.ping(), c.key('Tab', {modifiers: {shift: true}})]); assert.strictEqual(both.length, 2);
      var first = await c.capture(); assert.strictEqual(first.epoch, 2); assert.strictEqual(first.width, 2); assert.strictEqual(first.data[3], 255);
      var original = Buffer.from(first.data); var second = await c.capture(); assert.notStrictEqual(first.data[0], second.data[0]); assert(first.data.equals(original));
      await c.pointer('down', 1, 1, {button: 'left'}); await c.pointer('move', 2, 2); await c.pointer('up', 2, 2); await c.wheel(1, 1, -1, 2); await c.release(); await c.stop();
    });
    await test('single frame credit and independent timely input', async function () {
      var c = client('blocked'); await c.setEpoch(1); var capture = c.capture();
      await rejected(c.capture(), 'BUSY'); var start = Date.now(); await c.key('Enter'); assert(Date.now() - start < 200);
      assert.strictEqual((await c.ping()).value, 1); var frame = await capture; assert.strictEqual(frame.data.length, 16); await c.stop();
    });
    await test('coalesced responses retain individual request identities', async function () {
      var c = client('coalesce'); await c.setEpoch(3); var pending = [];
      for (var i = 0; i < 8; i++) pending.push(c.ping());
      var results = await Promise.all(pending), ids = {};
      results.forEach(function (result) { assert.strictEqual(result.epoch, 3); assert(!ids[result.id]); ids[result.id] = true; });
      await c.stop();
    });
    await test('epoch cancellation discards an old partial frame', async function () {
      var c = client('epoch'); await c.setEpoch(1); var old = rejected(c.capture(), 'STALE'); await delay(20); await c.setEpoch(2); await old;
      await rejected(c.capture(), 'BUSY'); await delay(170); var current = await c.capture(); assert.strictEqual(current.epoch, 2); await c.stop();
    });
    await test('oversized frame fails without allocating payload', async function () {
      var c = client('oversize'); await c.setEpoch(1); await rejected(c.capture(), 'PROTOCOL'); await c.stop(); assert.strictEqual(c._frames.body, null);
    });
    await test('EOF rejects a truncated native frame', async function () {
      var c = client('truncated'); await c.setEpoch(1); await rejected(c.capture(), 'PROTOCOL'); await c.stop();
    });
    await test('unexpected frame-pipe EOF closes the owned helper', async function () {
      var c = client('frame-eof'); await c.setEpoch(1); var error = await new Promise(function (resolve) { c.once('failure', resolve); });
      assert.strictEqual(error.code, 'PIPE'); await rejected(c.ping(), 'PIPE'); await c.stop();
    });
    await test('pending requests bounded and command timeout kills helper', async function () {
      var c = client('hang', {requestTimeoutMs: 100}); var pending = [];
      for (var i = 0; i < 32; i++) pending.push(rejected(c.ping(), 'TIMEOUT'));
      await rejected(c.ping(), 'QUEUE_FULL'); await Promise.all(pending); await c.stop(); assert.strictEqual(c._pending.size, 0);
    });
    await test('stop cancels partial frame and has a bounded kill fallback', async function () {
      var c = client('blocked'); await c.setEpoch(1); var capture = rejected(c.capture(), 'CLOSED'); await delay(15); await c.stop(); await capture;
      var stubborn = client('ignore-stop'); await stubborn.setEpoch(1); var start = Date.now(); var end = await stubborn.stop(); assert(Date.now() - start < 1200); assert.strictEqual(end.signal, 'SIGKILL');
    });
    process.stdout.write('NATIVE_HELPER_CLIENT_RESULT ' + JSON.stringify({success: true, node: process.version, passed: passed}) + '\n');
  }
  run().catch(function (error) {
    process.stderr.write(error.stack + '\n');
    return Promise.all(clients.map(function (c) { return c.stop(); })).then(function () { process.exitCode = 1; });
  });
}
