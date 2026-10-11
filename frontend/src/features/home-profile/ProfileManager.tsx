"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import {
  archiveProfile,
  createProfile,
  listProfiles,
  type Profile,
  type ProfileInput,
  signOut,
  updateProfile,
} from "@/lib/api";

import { AVATARS, avatarFor } from "./avatars";
import styles from "./home-profile.module.css";

const EMPTY: ProfileInput = { display_name: "", grade: 1, avatar_key: "default" };

/** Parent-only: add, edit and archive children. Render inside the auth feature's ParentGate. */
export function ProfileManager() {
  const router = useRouter();
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [editing, setEditing] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = () => listProfiles().then(setProfiles, () => setError("Couldn't load profiles."));
  useEffect(() => {
    void reload();
  }, []);

  async function save(input: ProfileInput) {
    setError(null);
    try {
      if (editing) await updateProfile(editing.id, input);
      else await createProfile(input);
      setEditing(null);
      await reload();
      return true;
    } catch {
      setError("Couldn't save. Check the name (1–30 characters) and grade.");
      return false;
    }
  }

  async function archive(profile: Profile) {
    if (!window.confirm(`Remove ${profile.display_name}'s profile? Their learning history is kept.`)) return;
    await archiveProfile(profile.id);
    if (editing?.id === profile.id) setEditing(null);
    await reload();
  }

  async function lock() {
    await signOut();
    router.push("/");
  }

  return (
    <div className="stack" style={{ gap: 24 }}>
      <div className="row spread">
        <h1>Children</h1>
        <div className="row">
          <Link className="btn" href="/">
            Profiles screen
          </Link>
          <button className="btn" onClick={lock}>
            🔒 Lock
          </button>
        </div>
      </div>

      <p className="notice">
        Keep it minimal: a first name or nickname and a grade is all Edaptive needs.
      </p>

      <div className="card">
        {profiles.length === 0 && <p className="muted" style={{ margin: 0 }}>No children added yet.</p>}
        {profiles.map((p) => (
          <div key={p.id} className={styles.listItem}>
            <span className={styles.listIcon} aria-hidden>
              {avatarFor(p.avatar_key)}
            </span>
            <div className={styles.grow}>
              <strong>{p.display_name}</strong>
              <div className="muted">Grade {p.grade}</div>
            </div>
            <button className="btn" onClick={() => setEditing(p)}>
              Edit
            </button>
            <button className="btn btn-quiet btn-danger" onClick={() => archive(p)}>
              Remove
            </button>
          </div>
        ))}
      </div>

      <ProfileForm
        key={editing?.id ?? "new"}
        initial={editing ?? EMPTY}
        title={editing ? `Edit ${editing.display_name}` : "Add a child"}
        submitLabel={editing ? "Save changes" : "Add child"}
        onSubmit={save}
        onCancel={editing ? () => setEditing(null) : undefined}
      />
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

type FormProps = {
  initial: ProfileInput;
  title: string;
  submitLabel: string;
  onSubmit: (input: ProfileInput) => Promise<boolean>;
  onCancel?: () => void;
};

function ProfileForm({ initial, title, submitLabel, onSubmit, onCancel }: FormProps) {
  const [form, setForm] = useState<ProfileInput>({
    display_name: initial.display_name,
    grade: initial.grade,
    avatar_key: initial.avatar_key,
  });
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    const ok = await onSubmit({ ...form, display_name: form.display_name.trim() });
    setBusy(false);
    if (ok && !onCancel) setForm(EMPTY);
  }

  return (
    <form className="card stack" onSubmit={submit}>
      <h2>{title}</h2>
      <label className="field">
        First name or nickname
        <input
          className="input"
          maxLength={30}
          value={form.display_name}
          onChange={(e) => setForm({ ...form, display_name: e.target.value })}
        />
      </label>
      <label className="field">
        Grade
        <select
          className="input"
          value={form.grade}
          onChange={(e) => setForm({ ...form, grade: Number(e.target.value) })}
        >
          {[1, 2, 3, 4, 5].map((g) => (
            <option key={g} value={g}>
              Grade {g}
            </option>
          ))}
        </select>
      </label>
      <div className="field">
        Picture
        <div className={styles.avatarChoices}>
          {Object.entries(AVATARS).map(([key, icon]) => (
            <button
              key={key}
              type="button"
              className={styles.avatarChoice}
              aria-pressed={form.avatar_key === key}
              aria-label={key}
              onClick={() => setForm({ ...form, avatar_key: key })}
            >
              {icon}
            </button>
          ))}
        </div>
      </div>
      <div className="row">
        <button className="btn btn-primary" disabled={busy || !form.display_name.trim()}>
          {busy ? "Saving…" : submitLabel}
        </button>
        {onCancel && (
          <button type="button" className="btn btn-quiet" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
