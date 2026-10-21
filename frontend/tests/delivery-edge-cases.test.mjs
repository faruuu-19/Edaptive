import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

function load(file, imports = {}) {
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const loaded = { exports: {} };
  vm.runInNewContext(code, { module: loaded, exports: loaded.exports, require: id => imports[id] });
  return loaded.exports;
}

test('only confirmed ready lessons display 100%, including bad legacy percentages', () => {
  const { preparationPercent } = load('src/features/lesson-player/preparation-message.ts');
  for (const status of ['preparing', 'checking', 'paused', 'failed', 'cancelled']) {
    assert.ok(preparationPercent({ status, percent: 100 }) < 100);
  }
  assert.equal(preparationPercent({ status: 'ready', percent: 98 }), 100);
  assert.equal(preparationPercent({ status: 'preparing', percent: -20 }), 0);
});

test('service retries and validation problems are not presented as low memory', () => {
  const { needsMemoryHelp } = load('src/features/lesson-player/preparation-message.ts');
  assert.equal(needsMemoryHelp({ status: 'paused', failure_kind: 'service', message: 'Service restarting' }), false);
  assert.equal(needsMemoryHelp({ status: 'failed', failure_kind: 'validation', message: 'Critical factual issue' }), false);
  assert.equal(needsMemoryHelp({ status: 'paused', failure_kind: 'memory', message: 'Not enough memory' }), true);
  assert.equal(needsMemoryHelp({ status: 'ready', message: 'Memory restored' }), false);
});

test('simultaneous timetable readers share one request, but different students never share data', async () => {
  const waiting = [];
  const { getTimetables } = load('src/lib/lesson-delivery-api.ts', {
    './api': { request: url => new Promise(resolve => waiting.push({ url, resolve })) },
  });
  const ali = getTimetables('ali-id');
  assert.equal(getTimetables('ali-id'), ali);
  const noor = getTimetables('noor-id');
  assert.notEqual(ali, noor);
  assert.equal(waiting.length, 2);
  const response = id => ({ timetables: [{ student_id: id }], routine: null, learning_progress: null });
  waiting[0].resolve(response('ali-id')); waiting[1].resolve(response('noor-id'));
  assert.equal((await ali).timetables[0].student_id, 'ali-id');
  await noor;
  const fresh = getTimetables('ali-id');
  assert.equal(waiting.length, 3, 'finished requests must not become stale cached progress');
  waiting[2].resolve(response('ali-id')); await fresh;
});

test('a mismatched-profile response is rejected and the next poll can recover', async () => {
  let count = 0;
  const { getTimetables } = load('src/lib/lesson-delivery-api.ts', {
    './api': { request: async () => ({ timetables: [{ student_id: ++count === 1 ? 'old-profile' : 'new-profile' }], routine: null, learning_progress: null }) },
  });
  await assert.rejects(getTimetables('new-profile'), /selected profile/);
  assert.equal((await getTimetables('new-profile')).timetables[0].student_id, 'new-profile');
});

test('class chime starts after a gesture even when class became due first', async () => {
  let allowed = false; let contexts = 0; let tones = 0; let timer = null;
  class AudioContext {
    state = 'suspended'; currentTime = 0; destination = {};
    constructor() { contexts++; }
    async resume() { if (allowed) this.state = 'running'; }
    createOscillator() { return { frequency: { value: 0 }, connect() {}, start() { tones++; }, stop() {}, disconnect() {}, onended: null }; }
    createGain() { return { gain: { setValueAtTime() {}, linearRampToValueAtTime() {}, exponentialRampToValueAtTime() {} }, connect() {}, disconnect() {} }; }
    async close() { this.state = 'closed'; }
  }
  const code = ts.transpileModule(fs.readFileSync('src/features/voice/local-alarm.ts', 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const loaded = { exports: {} };
  vm.runInNewContext(code, { module: loaded, exports: loaded.exports, AudioContext,
    setInterval: fn => { timer = fn; return 1; }, clearInterval: () => { timer = null; } });
  const alarm = new loaded.exports.LocalAlarm();
  assert.equal(contexts, 0, 'page loading must not create a suspended audio context');
  assert.equal(alarm.ring(), false);
  assert.equal(tones, 0);
  allowed = true;
  assert.equal(await alarm.unlock(), true);
  assert.equal(tones, 2, 'the missed due-time chime starts on the enabling tap');
  timer();
  assert.equal(tones, 4);
  alarm.stop();
  assert.equal(timer, null);
  alarm.close();
});
