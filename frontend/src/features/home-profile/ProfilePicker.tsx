"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { listProfiles, pickProfile, type Profile } from "@/lib/api";

import { Avatar } from "./Avatar";
import styles from "./home-profile.module.css";
import { LockIcon } from "./icons";

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
    <div className={styles.scene}>
      <div className={styles.ground} aria-hidden />
      <div className={styles.sun} aria-hidden />
      <div className={`page stack ${styles.sceneContent}`} style={{ gap: 36 }}>
        <div className="row spread">
          <span className="wordmark">Edaptive</span>
          <Link className="btn" href="/parent">
            <LockIcon /> Parent
          </Link>
        </div>

        <h1>Who&apos;s learning today?</h1>

        {error && <p className="error">Something went wrong. Is the backend running?</p>}

        {profiles?.length === 0 && (
          <div className="card stack" style={{ maxWidth: 440 }}>
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
                <Avatar name={p.display_name} avatarKey={p.avatar_key} size={108} />
                <span className={styles.tileName}>{p.display_name}</span>
                <span className={styles.grade}>Grade {p.grade}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
