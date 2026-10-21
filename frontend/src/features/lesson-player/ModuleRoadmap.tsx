import { useState } from 'react';
import type { LearningProgress, MathsModule } from '@/lib/lesson-delivery-api';
import styles from './module-roadmap.module.css';

function StateMark({ complete }: { complete: boolean }) {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {complete ? <path d="m5 12 4 4L19 6" /> : <><rect x="5" y="10" width="14" height="11" rx="3" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></>}
  </svg>;
}

export function ModuleRoadmap({ grade, modules, progress, currentModule }: {
  grade: number; modules: MathsModule[]; progress: LearningProgress | null; currentModule?: number;
}) {
  const [selected, setSelected] = useState<number | null>(null);
  const saved = progress?.grade === grade ? progress : null;
  const current = saved?.next_required?.module ?? currentModule;
  const completed = modules.filter(item => saved?.modules.some(p => p.module === item.module && p.status === 'completed')).length;
  const rows = Array.from({ length: Math.ceil(modules.length / 2) }, (_, i) => modules.slice(i * 2, i * 2 + 2));

  if (!modules.length) return null;
  return <section className={`${styles.roadmap} ui-roadmap`} aria-labelledby="maths-path-heading">
    <header className={styles.header}>
      <div><span className={styles.grade}>GRADE {grade} · MATHS</span><h2 id="maths-path-heading">Your learning path</h2></div>
      <span className={styles.counter}>{completed} of {modules.length}<span>modules complete</span></span>
    </header>
    <p className={styles.intro}>Follow your next available lesson. Look what’s ahead.</p>
    <ol className={styles.path} aria-label={`Grade ${grade} Maths modules`}>
      {rows.map((row, rowIndex) => <li className={`${styles.pathRow} ${rowIndex % 2 ? styles.reverse : ''}`} key={row[0].module}>
        <ol className={styles.rowModules}>
          {row.map(item => {
            const state = saved?.modules.find(p => p.module === item.module);
            const complete = state?.status === 'completed';
            const here = !complete && item.module === current;
            const visited = !complete && !here && ((state?.delivered_lessons ?? 0) + (state?.unfinished_lessons ?? 0) > 0);
            const label = complete ? 'Completed' : here ? 'You are here' : visited ? 'Lessons taken' : current !== undefined ? 'Locked' : 'Up next';
            const detailId = `module-${item.module}-detail`;
            return <li key={item.module} className={`${styles.module} ${complete ? styles.complete : here ? styles.current : visited ? styles.visited : styles.locked}`}>
              <button type="button" className={styles.moduleButton} aria-label={`Module ${item.module}: ${item.title}. ${label}`} aria-current={here ? 'step' : undefined} aria-expanded={selected === item.module} aria-controls={detailId} onClick={() => setSelected(selected === item.module ? null : item.module)}>
                <span className={styles.node}>{item.module}</span>
                <span className={styles.moduleLabel}>Module {item.module}</span>
                <span className={styles.title}>{item.title}</span>
                <span className={styles.state}>{!here && <StateMark complete={complete} />}{label}</span>
              </button>
              <p className={styles.detail} id={detailId} hidden={selected !== item.module}>
                {complete ? 'You’ve finished this module’s lessons.' : here ? `${state?.delivered_lessons ?? 0}${state?.expected_lessons ? ` of ${state.expected_lessons}` : ''} lessons completed. Your next lesson follows your class schedule.` : visited ? `${state?.delivered_lessons ?? 0} lessons completed here. Your class follows the next available lesson in your grade.` : current !== undefined ? 'Your class will bring you here as you move through your modules.' : 'Your place will appear when your learning schedule is ready.'}
              </p>
            </li>;
          })}
        </ol>
      </li>)}
    </ol>
    <p className={styles.footer}>Little steps, steady progress.</p>
  </section>;
}
