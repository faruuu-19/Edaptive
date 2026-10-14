"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { type Profile, signOut } from "@/lib/api";

import { Avatar } from "./Avatar";
import styles from "./home-profile.module.css";
import { BookIcon, FlaskIcon, MathsIcon, SwitchIcon } from "./icons";

// Maths is the Mid-1 slice; English and Science reuse the same pipeline later (roadmap).
const SUBJECTS = [
  { key: "math", Icon: MathsIcon, art: "var(--tomato-soft)", name: "Maths", note: "Your scheduled lessons", current: true },
  { key: "english", Icon: BookIcon, art: "var(--mustard-soft)", name: "English", note: "Coming soon", current: false },
  { key: "science", Icon: FlaskIcon, art: "var(--teal-soft)", name: "Science", note: "Coming soon", current: false },
];

export function ChildHome({ profile, mathsHref }: { profile: Profile; mathsHref?: string }) {
  const router = useRouter();

  async function switchProfile() {
    await signOut();
    router.push("/");
  }

  return (
    <div className="stack" style={{ gap: 30 }}>
      <div className="row spread">
        <div className={styles.hero}>
          <Avatar name={profile.display_name} avatarKey={profile.avatar_key} size={80} />
          <div>
            <h1>Hi, {profile.display_name}!</h1>
            <div className={styles.grade} style={{ marginTop: 4 }}>
              Grade {profile.grade}
            </div>
          </div>
        </div>
        <button className="btn" onClick={switchProfile}>
          <SwitchIcon /> Switch profile
        </button>
      </div>

      <h2 style={{ fontWeight: 600 }}>Your subjects</h2>
      <div className={styles.subjects}>
        {SUBJECTS.map(({ key, Icon, art, name, note, current }) => {
          const className = `${styles.subject} ${current ? styles.subjectCurrent : ""}`;
          const content = <>
            <div className={styles.subjectArt} style={{ background: art }}>
              <Icon />
            </div>
            <span className={styles.subjectName}>{name}</span>
            <span className={styles.subjectNote}>{note}</span>
          </>;
          return key === "math" && mathsHref ? (
            <Link key={key} className={`${className} ${styles.subjectLink}`} href={mathsHref}>
              {content}
            </Link>
          ) : <div key={key} className={className}>{content}</div>;
        })}
      </div>
    </div>
  );
}
