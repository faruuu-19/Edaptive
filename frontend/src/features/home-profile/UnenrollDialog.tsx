"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";

import { ApiError, type Profile, unenrollProfile } from "@/lib/api";

import styles from "./home-profile.module.css";

/** Permanent deletion, so the parent PIN is asked again. */
export function UnenrollDialog({ profile, onDone, onCancel }: { profile: Profile; onDone: () => void; onCancel: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await unenrollProfile(profile.id, pin);
      onDone();
    } catch (e) {
      setPin("");
      setError(
        e instanceof ApiError && e.status === 401
          ? "That PIN isn’t right."
          : e instanceof ApiError && e.status === 429
            ? "Too many tries. Please wait a few minutes and try again."
            : "Couldn’t unenroll. Please try again.",
      );
      setBusy(false);
    }
  }

  return (
    <dialog ref={ref} className={styles.unenrollDialog} aria-labelledby="unenroll-title" onCancel={(e) => { e.preventDefault(); if (!busy) onCancel(); }}>
      <form className="stack" onSubmit={submit}>
        <h2 id="unenroll-title">Unenroll {profile.display_name}?</h2>
        <p>
          This permanently deletes {profile.display_name}’s profile, lesson plan, progress and permissions. It can’t be undone.
        </p>
        <label className="field">
          Enter your parent PIN to confirm
          <input
            className="input"
            type="password"
            inputMode="numeric"
            autoComplete="off"
            pattern="[0-9]{4,6}"
            maxLength={6}
            value={pin}
            onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
            autoFocus
          />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <div className="row">
          <button className="btn btn-danger" disabled={busy || pin.length < 4}>
            {busy ? "Deleting…" : `Unenroll ${profile.display_name}`}
          </button>
          <button type="button" className="btn" disabled={busy} onClick={onCancel}>
            Cancel
          </button>
        </div>
      </form>
    </dialog>
  );
}
