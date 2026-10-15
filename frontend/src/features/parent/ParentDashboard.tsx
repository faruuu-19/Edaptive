"use client";

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState, type FormEvent } from 'react';
import { Avatar } from '@/features/home-profile';
import { lessonAlarm } from '@/features/voice';
import { getProfile, signOut, type Profile } from '@/lib/api';
import { getSchoolRoutine, saveSchoolStartTime, type SchoolRoutine } from '@/lib/lesson-delivery-api';
import { getPermissions, setPermission, type PermissionKind, type Permissions } from '@/lib/parent-api';
import { AttendanceLog } from './AttendanceLog';
import { ClassStatus } from './ClassStatus';
import { ProgressCard } from './ProgressCard';
import styles from './parent.module.css';

const permissionText = (name: string): Record<PermissionKind, { title: string; about: string; allow: string }> => ({
  camera: { title: 'Camera', about: 'Permission for future camera features.', allow: 'Allow camera' },
  microphone: { title: 'Voice input', about: 'Permission for future microphone features.', allow: 'Allow voice input' },
  lesson_alarm: { title: 'Lesson alarm sound', about: `Plays a short chime on ${name}’s device when class time starts. ${name} can’t turn this on or off.`, allow: 'Allow lesson alarm' },
});

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
    // Clicking Allow is the browser gesture that lets this device play the chime later.
    if (kind === 'lesson_alarm' && granted) void lessonAlarm().unlock();
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
    <ClassStatus studentId={studentId} name={profile.display_name} />
    <AttendanceLog studentId={studentId} name={profile.display_name} />
    <div className={styles.grid}>
      <ProgressCard studentId={studentId} name={profile.display_name} />
      <section className="card stack" aria-labelledby="school-time-title">
        <h2 id="school-time-title">School start time</h2>
        <p>Choose the daily time that suits {profile.display_name}. The system organises lessons, class length, breaks and preparation.</p>
        <form className="stack" onSubmit={saveTime}>
          <label className="field">Daily start · Pakistan time<input className="input" type="time" required value={startTime} onChange={event => { setStartTime(event.target.value); setTimeSaved(false); }} /></label>
          <button className="btn btn-primary" disabled={saving || !startTime}>{saving ? 'Saving…' : 'Save start time'}</button>
          {timeSaved && <p className="notice" role="status">Daily start time saved.</p>}
          {routine && <p className="muted">{routine.message}</p>}
        </form>
        <Link className="btn" href={`/timetable?student=${studentId}`}>See {profile.display_name}’s day</Link>
      </section>
      <section className="card stack" aria-labelledby="evaluations-title">
        <h2 id="evaluations-title">Evaluations</h2>
        <p role="status"><strong>No evaluations yet.</strong> Results will appear here once {profile.display_name} has been assessed.</p>
      </section>
      <section className="card stack" aria-labelledby="permissions-title">
        <h2 id="permissions-title">Permissions</h2>
        <p>Your choices are saved for this child. Camera and voice input are not active in this stage; the lesson alarm sound is.</p>
        {permissions.permissions.map(permission => { const text = permissionText(profile.display_name)[permission.kind]; return <div className={styles.permission} key={permission.kind}>
          <div className="row spread"><h3>{text.title}</h3><span className={styles.permissionStatus}>{permission.granted ? 'Allowed' : 'Not allowed'}</span></div>
          <p>{text.about}</p>
          <button className="btn" disabled={savingPermission !== null} onClick={() => void decide(permission.kind, !permission.granted)}>{savingPermission === permission.kind ? 'Saving…' : permission.granted ? 'Revoke permission' : text.allow}</button>
        </div>; })}
        <p className="notice">Saving permission does not turn on the camera or microphone. No audio or video is collected.</p>
        <p className="muted">The lesson teacher’s spoken voice works independently of microphone permission.</p>
      </section>
    </div>
  </div>;
}
