from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path

from lesson_run import PressureTolerance,Checkpoint

MIB=1024**2
ELEVATED='macOS reports elevated memory pressure; unload and close apps.'

class PressureToleranceTests(unittest.TestCase):
    def test_short_blip_is_tolerated_and_logged(self):
        t=PressureTolerance(sustained_seconds=60)
        self.assertEqual(t.check([ELEVATED],pressure_level=2,now=100),[])
        self.assertEqual(t.check([],pressure_level=1,now=106),[])
        self.assertEqual(len(t.blips),1)

    def test_sustained_pressure_stops(self):
        t=PressureTolerance(sustained_seconds=60)
        t.check([ELEVATED],pressure_level=2,now=100)
        self.assertEqual(t.check([ELEVATED],pressure_level=2,now=130),[])
        self.assertTrue(t.check([ELEVATED],pressure_level=2,now=161))

    def test_blip_timer_resets_after_recovery(self):
        t=PressureTolerance(sustained_seconds=60)
        t.check([ELEVATED],pressure_level=2,now=100)
        t.check([],pressure_level=1,now=110)
        self.assertEqual(t.check([ELEVATED],pressure_level=2,now=150),[])
        self.assertEqual(t.check([ELEVATED],pressure_level=2,now=190),[])

    def test_critical_pressure_stops_at_once(self):
        t=PressureTolerance(sustained_seconds=60)
        self.assertTrue(t.check([ELEVATED],pressure_level=4,now=100))

    def test_any_other_guard_issue_stops_at_once(self):
        t=PressureTolerance(sustained_seconds=60)
        issue='Less than 1.0 GiB disk headroom; user must free space.'
        self.assertEqual(t.check([issue],pressure_level=1,now=100),[issue])
        self.assertEqual(t.check([ELEVATED,issue],pressure_level=2,now=101),[issue])

    def test_swap_growth_stops_at_once(self):
        t=PressureTolerance(sustained_seconds=60,swap_growth_bytes=512*MIB)
        self.assertEqual(t.check([],pressure_level=1,now=100,swap_used=300*MIB,swap_start=300*MIB),[])
        self.assertTrue(t.check([],pressure_level=1,now=101,swap_used=900*MIB,swap_start=300*MIB))

class CheckpointTests(unittest.TestCase):
    def segment(self,i,template='Hi <CONTENT>'):
        return {'id':'s_%04d'%i,'template':template,'attempts_log':[{'attempt':1,'errors':[]}]}

    def test_saved_segments_are_reloaded(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'run.checkpoint.json'
            c=Checkpoint(path,'fp1')
            c.add(self.segment(1));c.add(self.segment(2,'Go <CONTENT>'))
            again=Checkpoint(path,'fp1')
            self.assertEqual(sorted(again.cache),['s_0001','s_0002'])
            self.assertEqual(again.cache['s_0002']['template'],'Go <CONTENT>')

    def test_changed_fingerprint_discards_old_segments(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'run.checkpoint.json'
            Checkpoint(path,'fp1').add(self.segment(1))
            self.assertEqual(Checkpoint(path,'fp2').cache,{})

    def test_corrupt_file_starts_fresh_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'run.checkpoint.json';path.write_text('{not json')
            self.assertEqual(Checkpoint(path,'fp1').cache,{})

    def test_write_is_atomic_json(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'run.checkpoint.json'
            Checkpoint(path,'fp1').add(self.segment(1))
            self.assertEqual(json.loads(path.read_text())['fingerprint'],'fp1')
            self.assertEqual([p.name for p in Path(d).iterdir()],['run.checkpoint.json'])

if __name__=='__main__':unittest.main()
