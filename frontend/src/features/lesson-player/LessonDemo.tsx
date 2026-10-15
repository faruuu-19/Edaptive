"use client";
import { useEffect } from 'react';
import { LessonPlayer } from './LessonPlayer';

function release() {
  void fetch('/voice-preview-api/release', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}', keepalive: true }).catch(() => undefined);
}
export function LessonDemo() {
  useEffect(() => () => release(), []);
  return <div className="stack"><p className="notice">Prepared demo lecture. This page uses an existing checked script and live local narration. It does not generate another script or record a child’s learning progress.</p><LessonPlayer onFinished={release} /></div>;
}
