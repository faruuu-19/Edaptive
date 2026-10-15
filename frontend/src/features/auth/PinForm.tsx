"use client";

import { type FormEvent, useState } from "react";

import { ApiError } from "@/lib/api";

const PIN = /^\d{4,6}$/;

type Props = {
  title: string;
  hint?: string;
  confirm?: boolean;
  submitLabel: string;
  onSubmit: (pin: string) => Promise<void>;
};

/** A PIN entry form. With `confirm`, asks for the PIN twice (used at first-run setup). */
export function PinForm({ title, hint, confirm = false, submitLabel, onSubmit }: Props) {
  const [pin, setPin] = useState("");
  const [again, setAgain] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!PIN.test(pin)) return setError("Use 4 to 6 digits.");
    if (confirm && pin !== again) return setError("The two PINs don't match.");
    setBusy(true);
    setError(null);
    try {
      await onSubmit(pin);
    } catch (err) {
      setPin("");
      setAgain("");
      if (err instanceof ApiError && err.status === 401) setError("That PIN isn't right.");
      else if (err instanceof ApiError && err.status === 429)
        setError(`Too many tries. Wait ${Math.ceil((err.retryAfter ?? 60) / 60)} min and try again.`);
      else setError("Something went wrong. Is the backend running?");
    } finally {
      setBusy(false);
    }
  }

  const digits = (v: string) => v.replace(/\D/g, "").slice(0, 6);

  return (
    <form className="card stack" onSubmit={submit}>
      <h2>{title}</h2>
      {hint && <p className="muted" style={{ margin: 0 }}>{hint}</p>}
      <label className="field">
        PIN
        <input
          className="input pin"
          type="password"
          inputMode="numeric"
          autoComplete={confirm ? "new-password" : "current-password"}
          autoFocus
          value={pin}
          onChange={(e) => setPin(digits(e.target.value))}
        />
      </label>
      {confirm && (
        <label className="field">
          Type it again
          <input
            className="input pin"
            type="password"
            inputMode="numeric"
            autoComplete="new-password"
            value={again}
            onChange={(e) => setAgain(digits(e.target.value))}
          />
        </label>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <button className="btn btn-primary" disabled={busy || pin.length < 4}>
        {busy ? "One moment…" : submitLabel}
      </button>
    </form>
  );
}
