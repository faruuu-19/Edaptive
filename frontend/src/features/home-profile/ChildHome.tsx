"use client";

import { useRouter } from "next/navigation";

import { type Profile, signOut } from "@/lib/api";

import { avatarFor } from "./avatars";
import styles from "./home-profile.module.css";

// Maths is the Mid-1 slice; English and Science reuse the same pipeline later (roadmap).
const SUBJECTS = [
  { key: "math", icon: "🔢", name: "Maths", note: "Lessons are on their way" },
  { key: "english", icon: "📖", name: "English", note: "Coming later" },
  { key: "science", icon: "🔬", name: "Science", note: "Coming later" },
];

export function ChildHome({ profile }: { profile: Profile }) {
  const router = useRouter();

  async function switchProfile() {
    await signOut();
    router.push("/");
  }

  return (
    <div className="stack" style={{ gap: 28 }}>
      <div className="row spread">
        <div className={styles.hero}>
          <span className={styles.heroIcon} aria-hidden>
            {avatarFor(profile.avatar_key)}
          </span>
          <div>
            <h1>Hi, {profile.display_name}!</h1>
            <p className="muted" style={{ margin: "4px 0 0" }}>
              Grade {profile.grade}
            </p>
          </div>
        </div>
        <button className="btn" onClick={switchProfile}>
          Switch profile
        </button>
      </div>

      <h2>Your subjects</h2>
      <div className={styles.tiles}>
        {SUBJECTS.map((s) => (
          <button key={s.key} className={`${styles.subject} ${styles.subjectSoon}`} disabled>
            <span className={styles.tileIcon} aria-hidden>
              {s.icon}
            </span>
            <span className={styles.tileName}>{s.name}</span>
            <span className={styles.badge}>{s.note}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
