"use client";

import { useEffect, useRef } from 'react';
import styles from './lesson-player.module.css';

/** The child must confirm before leaving a live class. "Stay" is the safe default. */
export function LeaveClassDialog({ open, busy, onConfirm, onStay }: { open: boolean; busy: boolean; onConfirm: () => void; onStay: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return <dialog ref={ref} className={styles.leaveDialog} aria-labelledby="leave-title" onCancel={event => { event.preventDefault(); if (!busy) onStay(); }}>
    <h2 id="leave-title">Leaving class?</h2>
    <p>Please confirm that you’re going. Your teacher will save your place, and you can come back before class time ends.</p>
    <div className={styles.leaveActions}>
      <button className="btn btn-primary" disabled={busy} onClick={onConfirm}>{busy ? 'Leaving…' : 'Yes, I’m going'}</button>
      <button className="btn" disabled={busy} autoFocus onClick={onStay}>No, stay in class</button>
    </div>
  </dialog>;
}
