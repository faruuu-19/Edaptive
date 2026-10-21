"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { type Profile, signOut } from "@/lib/api";

import { Avatar } from "./Avatar";
import styles from "./home-profile.module.css";
import { BookIcon, FlaskIcon, MathsIcon, SwitchIcon } from "./icons";
import { Pip } from "@/features/theme";

// Maths is the Mid-1 slice; English and Science reuse the same pipeline later (roadmap).
const SUBJECTS = [
  { key: "math", Icon: MathsIcon, art: "var(--tomato-soft)", name: "Maths", tag: "numbers & patterns", note: "", current: true },
  { key: "english", Icon: BookIcon, art: "var(--mustard-soft)", name: "English", tag: "stories & words", note: "Coming soon", current: false },
  { key: "science", Icon: FlaskIcon, art: "var(--teal-soft)", name: "Science", tag: "wonder & discovery", note: "Coming soon", current: false },
];

export function ChildHome({ profile, mathsHref, mathsNote, aside }: { profile: Profile; mathsHref?: string; mathsNote?: ReactNode; aside?: ReactNode }) {
  const router = useRouter();

  async function switchProfile() {
    await signOut();
    router.push("/");
  }

  return (
    <div className="stack ui-home" style={{ gap: 30 }}>
      <div className="row spread ui-hero-card">
        <div className={`${styles.hero} ui-hero-text`}>
          <Avatar name={profile.display_name} avatarKey={profile.avatar_key} size={80} />
          <div>
            <h1>Hi, <span className="ui-accent">{profile.display_name}!</span></h1>
            <div className={`${styles.grade} ui-grade`} style={{ marginTop: 4 }}>
              Grade {profile.grade}
            </div>
          </div>
        </div>
        <Pip className="ui-hero-pip" size={130} waving />
        <button className="btn" onClick={switchProfile}>
          <SwitchIcon /> Switch profile
        </button>
      </div>

      <div className="ui-home-main">
      <div className="ui-subjects-block">
      <h2 className="ui-section-title" style={{ fontWeight: 600 }}>Your <span className="ui-accent">subjects</span></h2>
      <div className={`${styles.subjects} ui-subjects`}>
        {SUBJECTS.map(({ key, Icon, art, name, tag, note, current }) => {
          const className = `${styles.subject} ${current ? styles.subjectCurrent : ""} ui-subject ${current ? "ui-subject-current" : ""}`;
          const content = <>
            <div className={`${styles.subjectArt} ui-subject-art`} style={{ background: art }}>
              <Icon />
            </div>
            <span className={`${styles.subjectName} ui-subject-name`}>{name}</span>
            <span className="ui-subject-tag ui-playful-only">{tag}</span>
            <span className={`${styles.subjectNote} ui-subject-note`}>{key === "math" ? mathsNote : note}</span>
            {key === "math" && mathsHref && <span className="ui-subject-go ui-playful-only" aria-hidden><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M7 17 17 7M8 7h9v9" /></svg></span>}
          </>;
          return key === "math" && mathsHref ? (
            <Link key={key} data-subject={key} className={`${className} ${styles.subjectLink}`} href={mathsHref}>
              {content}
            </Link>
          ) : <div key={key} data-subject={key} className={className}>{content}</div>;
        })}
      </div>
      </div>
      {aside && <div className="ui-home-aside">{aside}</div>}
      </div>
    </div>
  );
}
