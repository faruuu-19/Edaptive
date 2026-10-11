"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { listProfiles, pickProfile, type Profile } from "@/lib/api";

import { avatarFor } from "./avatars";
import styles from "./home-profile.module.css";

/** "Who's learning today?" Children tap their own tile; no passwords. */
export function ProfilePicker() {
  const router = useRouter();
  const [profiles, setProfiles] = useState<Profile[] | null>(null);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    listProfiles().then(setProfiles, () => setError(true));
  }, []);

  async function choose(profile: Profile) {
    setBusy(profile.id);
    try {
      await pickProfile(profile.id);
      router.push("/home");
    } catch {
      setError(true);
      setBusy(null);
    }
  }

  return (
    <div className="stack" style={{ gap: 28 }}>
      <div className="row spread">
        <h1>Who&apos;s learning today?</h1>
        <Link className="btn btn-quiet" href="/parent">
          🔒 Parent
        </Link>
      </div>

      {error && <p className="error">Something went wrong. Is the backend running?</p>}

      {profiles?.length === 0 && (
        <div className="card stack">
          <h2>No profiles yet</h2>
          <p className="muted" style={{ margin: 0 }}>
            A parent needs to add each child first.
          </p>
          <Link className="btn btn-primary" href="/parent" style={{ alignSelf: "flex-start" }}>
            Add a child
          </Link>
        </div>
      )}

      {profiles && profiles.length > 0 && (
        <div className={styles.tiles}>
          {profiles.map((p) => (
            <button key={p.id} className={styles.tile} disabled={busy !== null} onClick={() => choose(p)}>
              <span className={styles.tileIcon} aria-hidden>
                {avatarFor(p.avatar_key)}
              </span>
              <span className={styles.tileName}>{p.display_name}</span>
              <span className="muted">Grade {p.grade}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
