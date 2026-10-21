import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';

const nodeRequire = createRequire(import.meta.url);
function load(file, overrides = {}) {
  const source = ts.transpileModule(fs.readFileSync(new URL('../' + file, import.meta.url), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText;
  const loaded = { exports: {} };
  vm.runInNewContext(source, {
    module: loaded, exports: loaded.exports,
    require: id => id in overrides ? overrides[id] : id.endsWith('.css') ? { default: {} } : nodeRequire(id),
  });
  return loaded.exports;
}

const preparation = load('src/features/lesson-player/preparation-message.ts');
const time = load('src/features/lesson-player/prepare-time.ts');
const { describeClass } = load('src/features/parent/ClassStatus.tsx', {
  '@/features/lesson-player': { ...preparation, ...time },
  '@/lib/lesson-delivery-api': {},
});
const { ChildClass } = load('src/features/lesson-player/ChildClass.tsx', {
  'next/link': ({ children }) => React.createElement('a', null, children),
  './preparation-message': preparation,
  './ModuleRoadmap': { ModuleRoadmap: () => null },
  '@/features/theme': { Pip: () => null },
});
const start = Date.parse('2026-10-19T15:45:00+05:00');
const slot = { id: 'maths', kind: 'lesson', subject: 'math', class_phase: 'waiting', start_ms: start, end_ms: start + 20 * 60000, delay_notice: 'Old delay: 4:30 pm; still preparing', preparation: { status: 'ready', percent: 100, message: 'Lesson ready' } };
const day = { status: 'active', current_slot_id: 'maths', server_now_ms: start - 60000, slots: [slot] };

test('a ready child lesson says it is ready and hides stale preparation delays', () => {
  const html = renderToStaticMarkup(React.createElement(ChildClass, { loaded: true, schedule: day, slot, mathsModules: {}, progress: null, busy: false, error: '', onJoin() {}, onSnooze() {}, onRejoin() {} }));
  assert.ok(html.includes('Your lesson is ready.'));
  assert.ok(!html.includes('Old delay'));
});

test('the parent sees the actual start time and readiness after a delayed job finishes', () => {
  const summary = describeClass('Ali', day);
  assert.ok(summary.headline.includes('03:45'));
  assert.equal(summary.detail, 'The lesson is prepared and ready for class.');
  assert.equal(summary.attention, false);
});

test('a paused status cannot be presented as ready merely because the counter is 100', () => {
  const paused = { ...slot, preparation: { status: 'paused', percent: 100, message: 'Memory pressure' } };
  const summary = describeClass('Ali', { ...day, slots: [paused] });
  assert.ok(summary.headline.includes('paused'));
  assert.equal(summary.attention, true);
});
