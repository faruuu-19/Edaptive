import json
import tempfile
import unittest
from pathlib import Path
from .timetable import Timetable, slots


class TimetableTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
        p=root/'docs/voice-module';p.mkdir(parents=True)
        (p/'PAIR_INVENTORY.json').write_text(json.dumps({'pairs':[{'concept_id':'math_g2_m1_l1_pairs_to_ten','grade':2,'module':1,'plan_passed':True}]}))
        self.now=1000000
        self.manager=Timetable(root,root/'saved.script.json',None,None,clock=lambda:self.now)
        self.record=self.manager.create({'concept_id':'math_g2_m1_l1_pairs_to_ten','mode':'reuse','start_ms':self.now+30000,'lead_seconds':30},start_thread=False)['schedule']

    def tearDown(self):self.tmp.cleanup()

    def act(self,kind):return self.manager.action({'schedule_id':self.record['id'],'action':kind})['schedule']

    def test_timetable_alternates_subjects_and_preserves_breaks(self):
        rows=slots(self.now)
        self.assertEqual([s['subject']for s in rows],['math','break','science','break','english'])
        self.assertEqual(rows[1]['end_ms']-rows[1]['start_ms'],300000)
        self.assertFalse(rows[2]['content_available'])

    def test_cannot_start_early_even_if_prepared(self):
        self.manager.update(self.record['id'],preparation='ready',percent=100)
        with self.assertRaises(ValueError):self.act('start')

    def test_alarm_is_due_even_when_preparation_is_not_ready_and_start_is_blocked(self):
        self.now+=30000
        self.assertEqual(self.manager.snapshot()['schedule']['class_phase'],'ringing')
        with self.assertRaises(ValueError):self.act('start')

    def test_borrow_adds_five_minutes_to_all_slots_and_preserves_preparation(self):
        self.now+=30000
        self.manager.update(self.record['id'],preparation='ready',percent=100)
        state=self.act('borrow')
        self.assertEqual(state['start_ms'],self.record['start_ms']+300000)
        self.assertEqual(state['borrowed_minutes'],5)
        for old,new in zip(self.record['slots'],state['slots']):self.assertEqual(new['start_ms']-old['start_ms'],300000)
        self.assertEqual(state['preparation'],'ready')
        self.assertEqual(state['class_phase'],'waiting')

    def test_started_lesson_requires_matching_schedule_and_prepared_data(self):
        self.now+=30000
        self.manager.update(self.record['id'],preparation='ready',percent=100)
        self.manager.prepared={'segments':['checked']}
        self.act('start')
        self.assertEqual(self.manager.lesson(self.record['id']),{'segments':['checked']})
        with self.assertRaises(ValueError):self.manager.lesson('wrong-id')
        self.assertEqual(self.act('finish')['class_phase'],'completed')

    def test_cancelled_job_cannot_publish_old_progress_or_start(self):
        self.act('cancel')
        self.manager.update(self.record['id'],percent=100,preparation='ready')
        self.assertEqual(self.manager.snapshot()['schedule']['percent'],0)
        with self.assertRaises(ValueError):self.act('start')

    def test_cancelling_a_started_class_clears_started_and_denies_narration(self):
        self.now+=30000
        self.manager.update(self.record['id'],preparation='ready',percent=100)
        self.manager.prepared={'segments':['checked']}
        self.act('start')
        state=self.act('cancel')
        self.assertEqual(state['class_phase'],'cancelled')
        self.assertFalse(self.manager.state['started'])
        with self.assertRaises(ValueError):self.manager.lesson(self.record['id'])

    def test_nonfinite_and_past_times_are_rejected(self):
        self.act('cancel')
        for start in [float('nan'),float('inf'),True,self.now-1]:
            with self.assertRaises(ValueError):self.manager.create({'concept_id':self.record['concept_id'],'start_ms':start},start_thread=False)

    def test_previous_worker_must_stop_before_replacing_the_schedule(self):
        self.act('cancel');self.manager.worker_active=True
        with self.assertRaises(ValueError):self.manager.create({'concept_id':self.record['concept_id'],'start_ms':self.now+30000},start_thread=False)
        self.assertEqual(self.manager.snapshot()['schedule']['class_phase'],'cancelled')


if __name__=='__main__':unittest.main()
