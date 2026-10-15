"use client";

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState, type FormEvent } from 'react';
import { Avatar } from '@/features/home-profile';
import { getProfile, signOut, type Profile } from '@/lib/api';
import { getSchoolRoutine, saveSchoolStartTime, type SchoolRoutine } from '@/lib/lesson-delivery-api';
import { getPermissions, setPermission, type PermissionKind, type Permissions } from '@/lib/parent-api';
import styles from './parent.module.css';

// Presentation fixtures only. Never saved as a child's measured progress,
// assessment result, mastery update or session event.
const SAMPLE_PROGRESS = [30, 42, 38, 56, 65, 74];
const SAMPLE_EVALUATIONS = [
  { title: 'Understanding the concept', result: 'Developing well', detail: 'Recognises the main idea and explains a simple example.' },
  { title: 'Independent practice', result: 'Needs a little support', detail: 'A short review could help with a more challenging question.' },
  { title: 'Learning habits', result: 'Steady effort', detail: 'Takes time to think and stays with the lesson.' },
];

function SampleProgress() {
  const points = SAMPLE_PROGRESS.map((v, i) => `${50 + i * 74},${158 - v * 1.2}`).join(' ');
  return <div className={styles.chart}>
    <svg viewBox="0 0 450 205" role="img" aria-label="Sample Maths progress over six lessons: 30, 42, 38, 56, 65 and 74 percent. These are illustrative figures.">
      {[0, 50, 100].map(v => <g key={v}>
        <line x1="44" x2="432" y1={158 - v * 1.2} y2={158 - v * 1.2} className={styles.gridLine} />
        <text x="34" y={163 - v * 1.2} textAnchor="end">{v}%</text>
      </g>)}
      <polyline points={points} className={styles.progressLine} />
      {SAMPLE_PROGRESS.map((v, i) => <g key={i}>
        <circle cx={50 + i * 74} cy={158 - v * 1.2} r="5" className={styles.progressDot} />
        <text x={50 + i * 74} y="188" textAnchor="middle">L{i + 1}</text>
      </g>)}
    </svg>
  </div>;
}

export function ParentDashboard({ studentId }: { studentId: string }) {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [routine, setRoutine] = useState<SchoolRoutine | null>(null);
  const [permissions, setPermissions] = useState<Permissions | null>(null);
  const [startTime, setStartTime] = useState('');
  const [loadError, setLoadError] = useState('');
  const [actionError, setActionError] = useState('');
  const [timeSaved, setTimeSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savingPermission, setSavingPermission] = useState<PermissionKind | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([getProfile(studentId), getSchoolRoutine(studentId), getPermissions(studentId)]).then(([child, school, consent]) => {
      if (active) { setProfile(child); setRoutine(school.routine); setStartTime(school.routine?.start_time ?? ''); setPermissions(consent); }
    }, () => { if (active) setLoadError('We couldn’t load this dashboard. Return to Children and try again.'); });
    return () => { active = false; };
  }, [studentId]);

  async function saveTime(event: FormEvent) {
    event.preventDefault(); setSaving(true); setActionError(''); setTimeSaved(false);
    try { const result = await saveSchoolStartTime(studentId, startTime); setRoutine(result.routine); setTimeSaved(true); }
    catch (error) { setActionError((error as Error).message); }
    finally { setSaving(false); }
  }
  async function decide(kind: PermissionKind, granted: boolean) {
    setSavingPermission(kind); setActionError('');
    try { setPermissions(await setPermission(studentId, kind, granted)); }
    catch (error) { setActionError((error as Error).message); }
    finally { setSavingPermission(null); }
  }
  async function lock() {
    try { await signOut(); router.push('/'); }
    catch { setActionError('Couldn’t lock the parent area. Please try again.'); }
  }

  if (loadError) return <div className="stack"><p className="error" role="alert">{loadError}</p><Link className="btn" href="/parent">Back to Children</Link></div>;
  if (!profile || !permissions) return <p role="status">Loading your child’s dashboard…</p>;

  return <div className={`stack ${styles.dashboard}`}>
    <header className="row spread">
      <div><p className="eyebrow">Parent area</p><h1>{profile.display_name}’s dashboard</h1></div>
      <div className="row"><Link className="btn" href="/parent">Children</Link><button className="btn btn-dark" onClick={() => void lock()}>Lock</button></div>
    </header>
    <div className={`card row spread ${styles.childSummary}`}>
      <div className="row"><Avatar name={profile.display_name} avatarKey={profile.avatar_key} size={58} /><div><strong>{profile.display_name}</strong><p className="muted">Grade {profile.grade}</p></div></div>
      <div><span className="eyebrow">Daily school time</span><p className={styles.schoolTime}>{routine?.start_time ?? 'Not set yet'}</p><small className="muted">Pakistan time</small></div>
    </div>
    {actionError && <p className="error" role="alert">{actionError}</p>}
    <div className={styles.grid}>
      <section className="card stack" aria-labelledby="progress-title">
        <div className="row spread"><h2 id="progress-title">Learning progress</h2><span className={styles.sampleBadge}>Sample data</span></div>
        <p className="muted">An example of how Maths progress will appear.</p>
        <SampleProgress />
        <div className={styles.progressSummary}><div><strong>6</strong><span>Sample lessons</span></div><div><strong>74%</strong><span>Illustrative progress</span></div></div>
        <p className={styles.sampleNote}>These figures are examples, not {profile.display_name}’s recorded results.</p>
      </section>
      <section className="card stack" aria-labelledby="school-time-title">
        <h2 id="school-time-title">School start time</h2>
        <p>Choose the daily time that suits {profile.display_name}. The system organises lessons, class length, breaks and preparation.</p>
        <form className="stack" onSubmit={saveTime}>
          <label className="field">Daily start · Pakistan time<input className="input" type="time" required value={startTime} onChange={event => { setStartTime(event.target.value); setTimeSaved(false); }} /></label>
          <button className="btn btn-primary" disabled={saving || !startTime}>{saving ? 'Saving…' : 'Save start time'}</button>
          {timeSaved && <p className="notice" role="status">Daily start time saved.</p>}
          {routine && <p className="muted">{routine.message}</p>}
        </form>
      </section>
      <section className="card stack" aria-labelledby="evaluations-title">
        <div className="row spread"><h2 id="evaluations-title">Evaluations</h2><span className={styles.sampleBadge}>Sample data</span></div>
        <p className="muted">Example feedback from future learning evaluations.</p>
        <ul className={styles.evaluations}>{SAMPLE_EVALUATIONS.map(item => <li key={item.title}>
          <h3>{item.title}</h3><span className={styles.evaluationResult}>{item.result}</span><p>{item.detail}</p>
        </li>)}</ul>
        <p className={styles.sampleNote}>No evaluation has been run from these examples.</p>
      </section>
      <section className="card stack" aria-labelledby="permissions-title">
        <h2 id="permissions-title">Camera &amp; voice permissions</h2>
        <p>Your choices are saved for this child. Camera and voice input are not active in this stage.</p>
        {permissions.permissions.map(permission => <div className={styles.permission} key={permission.kind}>
          <div className="row spread"><h3>{permission.kind === 'camera' ? 'Camera' : 'Voice input'}</h3><span className={styles.permissionStatus}>{permission.granted ? 'Allowed' : 'Not allowed'}</span></div>
          <p>{permission.kind === 'camera' ? 'Permission for future camera features.' : 'Permission for future microphone features.'}</p>
          <button className="btn" disabled={savingPermission !== null} onClick={() => void decide(permission.kind, !permission.granted)}>{savingPermission === permission.kind ? 'Saving…' : permission.granted ? 'Revoke permission' : `Allow ${permission.kind === 'camera' ? 'camera' : 'voice input'}`}</button>
        </div>)}
        <p className="notice">Saving permission does not turn on the camera or microphone. No audio or video is collected.</p>
        <p className="muted">The lesson teacher’s spoken voice works independently of microphone permission.</p>
      </section>
    </div>
  </div>;
}
