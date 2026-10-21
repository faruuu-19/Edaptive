import { test, before } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';

let gestures;
before(async () => { gestures = await import(pathToFileURL(path.resolve('src/features/avatar/gestures.mjs')).href); });

function load(file, imports, globals = {}) {
  const source = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const loadedModule = { exports: {} };
  vm.runInNewContext(source, {
    module: loadedModule, exports: loadedModule.exports, require: id => {
      if (!(id in imports)) throw new Error(`Unexpected import: ${id}`);
      return imports[id];
    }, AbortController, atob, Int16Array, Float32Array, ArrayBuffer, ...globals,
  });
  return loadedModule.exports;
}

const frame = (utterance, caption = 'Find a partner to ten.') => ({
  type: 'audio', utterance, caption, sample_rate: 24000,
  pcm_s16le: Buffer.from(new Int16Array(2400).fill(1000).buffer).toString('base64'),
});

function narratorHarness(frames, sink) {
  const contexts = [];
  class Context {
    currentTime = 0;
    sources = [];
    destination = {};
    constructor() { contexts.push(this); }
    createAnalyser() { return { connect() {}, disconnect() {} }; }
    createBuffer(channels, samples, rate) { return { duration: samples / rate, getChannelData: () => new Float32Array(samples) }; }
    createBufferSource() {
      const source = { connect() {}, disconnect() {}, stop() {}, start(at) { this.at = at; }, onended: null };
      this.sources.push(source);
      return source;
    }
    async resume() {}
    async suspend() {}
    async close() { this.closed = true; }
  }
  let route;
  const { LiveNarrator } = load('src/features/voice/live-narrator.ts', {
    '@/lib/voice-preview-api': { streamPreviewSpeech: async (part, voice, signal, onFrame, delivery) => {
      route = delivery;
      for (const item of frames) { if (signal.aborted) break; await onFrame(item); }
    } },
  }, { AudioContext: Context, requestAnimationFrame: () => 1, cancelAnimationFrame() {} });
  const events = [];
  const callbacks = { onPlaying: () => events.push('playing'), onCaption: n => events.push(`caption:${n}`), onComplete: () => events.push('complete') };
  return { narrator: new LiveNarrator(sink), contexts, callbacks, events, route: () => route };
}

test('scheduled progress waits for the actual avatar audio to drain, with one audible source', async () => {
  let playback;
  const received = [];
  const sink = {
    async prepare(rate, callbacks) { playback = callbacks; },
    audio(...args) { received.push(args); }, end() {}, stop() {}, pause() {}, resume() {},
  };
  const h = narratorHarness([frame(0), { type: 'done' }], sink);
  const delivery = { timetableId: 'saved-day', slotId: 'maths-slot' };
  await h.narrator.speak('hook', 'af_heart', h.callbacks, delivery);
  assert.equal(h.route(), delivery);
  assert.equal(received.length, 1);
  assert.equal(h.contexts[0].sources.length, 0, 'must not play a second copy of the avatar audio');
  assert.deepEqual(h.events, [], 'network done must not finish a scheduled lesson');
  playback.onPlaying(); playback.onCaption(0); playback.onComplete();
  assert.deepEqual(h.events, ['playing', 'caption:0', 'complete']);
  playback.onComplete();
  assert.equal(h.events.filter(e => e === 'complete').length, 1);
});

test('unavailable avatar audio falls back to the normal narrator and finishes after playback', async () => {
  let stopped = false;
  const sink = { async prepare() { throw new Error('Worklet unavailable'); }, stop() { stopped = true; } };
  const h = narratorHarness([frame(0), { type: 'done' }], sink);
  await h.narrator.speak('hook', 'af_heart', h.callbacks);
  assert.ok(stopped);
  assert.equal(h.contexts[0].sources.length, 1);
  assert.ok(!h.events.includes('complete'));
  h.contexts[0].sources[0].onended();
  assert.equal(h.events.at(-1), 'complete');
});

test('a Kokoro sentence split into chunks gets no pause or repeated caption inside the sentence', async () => {
  const audio = [];
  const sink = { async prepare() {}, audio(...args) { audio.push(args); }, end() {}, stop() {}, pause() {}, resume() {} };
  const h = narratorHarness([frame(0), frame(0), frame(1), { type: 'done' }], sink);
  await h.narrator.speak('lecture', 'af_heart', h.callbacks);
  assert.deepEqual(audio.map(a => a[3]), [0, 0, 1000]);
  assert.equal(audio[1][2], '');
  h.narrator.cancel();
});

test('replay or leaving class cancels audio and ignores stale completion/caption callbacks', async () => {
  let playback;
  let stopped = 0;
  const sink = { async prepare(rate, callbacks) { playback = callbacks; }, audio() {}, end() {}, stop() { stopped++; }, pause() {}, resume() {} };
  const h = narratorHarness([frame(0), { type: 'done' }], sink);
  await h.narrator.speak('lecture', 'af_heart', h.callbacks);
  h.narrator.cancel();
  playback.onPlaying(); playback.onCaption(1); playback.onComplete();
  assert.ok(stopped);
  assert.deepEqual(h.events, []);
});

function avatarHarness() {
  const ticks = new Set();
  const audio = [];
  const head = {
    audioCtx: { currentTime: 0 },
    async streamStart(options, onStart, onEnd) { this.onStart = onStart; this.onEnd = onEnd; },
    streamAudio(part) { audio.push(part); }, streamNotifyEnd() {}, streamInterrupt() {},
    stopSpeaking() {}, stopGesture() {}, playGesture() {}, start() {}, stop() {},
  };
  const api = load('src/features/avatar/avatar-voice.ts', { './gestures.mjs': gestures }, {
    window: {}, performance: { now: () => 0 },
    setInterval(fn) { ticks.add(fn); return fn; }, clearInterval(fn) { ticks.delete(fn); },
  });
  return { head, audio, ...api, tick: () => { for (const tick of ticks) tick(); } };
}

test('pure silence produces no mouth movements, while speech excludes TTS padding', () => {
  const h = avatarHarness();
  const silence = h.speechBounds(new Int16Array(2400), 24000);
  assert.equal(h.wordTimings('Quiet padding', silence.startMs, silence.endMs).words.length, 0);
  const pcm = new Int16Array(2400); pcm.fill(2000, 240, 2160);
  const bounds = h.speechBounds(pcm, 24000);
  assert.equal(bounds.startMs, 10);
  assert.equal(bounds.endMs, 90);
});

test('captions follow the real audio clock; a paused clock cannot advance them', async () => {
  const h = avatarHarness();
  const sink = new h.AvatarVoice(h.head);
  const captions = [];
  await sink.prepare(24000, { onPlaying() {}, onComplete() {}, onCaption: n => captions.push(n) });
  sink.audio(new Int16Array(24000).fill(1000), 24000, 'First sentence', 0, 0);
  sink.audio(new Int16Array(24000).fill(1000), 24000, 'Second sentence', 1000, 1);
  h.head.onStart();
  assert.deepEqual(captions, [0]);
  sink.pause(); h.tick(); h.tick();
  assert.deepEqual(captions, [0]);
  sink.resume(); h.head.audioCtx.currentTime = 2.1; h.tick();
  assert.deepEqual(captions, [0, 1]);
  assert.equal(h.audio[1].words, undefined, 'sentence gap must be silence with no visemes');
  sink.stop();
});

test('temporary stream underruns never finish a lesson, and cancellation rejects stale end events', async () => {
  const h = avatarHarness();
  const sink = new h.AvatarVoice(h.head);
  let complete = 0;
  await sink.prepare(24000, { onPlaying() {}, onCaption() {}, onComplete() { complete++; } });
  sink.audio(new Int16Array(2400).fill(1000), 24000, 'Think about ten', 0, 0);
  h.head.onStart(); h.head.onEnd();
  assert.equal(complete, 0);
  sink.end(); h.head.onEnd();
  assert.equal(complete, 1);
  sink.stop(); h.head.onEnd();
  assert.equal(complete, 1);
});

test('a delayed network done frame still completes when the audio already drained', async () => {
  const h = avatarHarness();
  const sink = new h.AvatarVoice(h.head);
  let complete = 0;
  await sink.prepare(24000, { onPlaying() {}, onCaption() {}, onComplete() { complete++; } });
  sink.audio(new Int16Array(2400).fill(1000), 24000, 'Think about ten', 0, 0);
  h.head.onStart(); h.head.onEnd();
  assert.equal(complete, 0);
  sink.end();
  assert.equal(complete, 1);
  sink.stop();
});

test('lip sync restarts at the next sentence after a live synthesis underrun', async () => {
  const h = avatarHarness();
  const sink = new h.AvatarVoice(h.head);
  await sink.prepare(24000, { onPlaying() {}, onCaption() {}, onComplete() {} });
  sink.audio(new Int16Array(2400).fill(1000), 24000, 'First sentence', 0, 0);
  h.head.onStart(); h.head.audioCtx.currentTime = 3; h.head.onEnd();
  sink.audio(new Int16Array(2400).fill(1000), 24000, 'Second sentence', 1000, 1);
  assert.equal(h.audio.at(-1).wtimes[0], 1000, 'visemes must follow the new stream’s gap, not the old part’s absolute offset');
  sink.stop();
});
