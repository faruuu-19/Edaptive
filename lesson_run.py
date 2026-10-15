"""Run-time helpers for build_lesson_script.py: tolerate a short memory-pressure blip, resume from a checkpoint.

Kept outside script_agent/ on purpose: the benchmark fingerprints script_agent/, and these helpers do not change what a
model is asked or how a segment is checked.
"""
from __future__ import annotations
import json
import os
from pathlib import Path

ELEVATED_MARKER='elevated memory pressure'
CRITICAL_LEVEL=4

class PressureTolerance:
    """Turns guard() issues into the ones that must stop a run.

    macOS "warn" pressure (level 2) for a few seconds is normal while a 6 GB model is loaded, so it is logged, not fatal.
    Fatal: pressure that stays elevated for `sustained_seconds`, critical pressure (4), swap growth beyond
    `swap_growth_bytes`, and every other guard issue (disk, weights vs reserve, ...) immediately.
    """
    def __init__(self,sustained_seconds=60,swap_growth_bytes=512*1024**2):
        self.sustained_seconds=sustained_seconds;self.swap_growth_bytes=swap_growth_bytes
        self.elevated_since=None;self.blips=[]

    def check(self,issues,pressure_level,now,swap_used=None,swap_start=None):
        fatal=[i for i in issues if ELEVATED_MARKER not in i]
        if swap_used is not None and swap_start is not None and swap_used>swap_start+self.swap_growth_bytes:
            fatal.append('Swap increased more than %d MiB.'%(self.swap_growth_bytes//1024**2))
        elevated=any(ELEVATED_MARKER in i for i in issues)
        if elevated:
            if self.elevated_since is None:self.elevated_since=now
            if pressure_level is not None and pressure_level>=CRITICAL_LEVEL:
                fatal.append('macOS reports critical memory pressure.')
            elif now-self.elevated_since>self.sustained_seconds:
                fatal.append('macOS memory pressure stayed elevated for over %d seconds.'%self.sustained_seconds)
        elif self.elevated_since is not None:
            self.blips.append({'seconds':round(now-self.elevated_since,1)});self.elevated_since=None
        return fatal

class Checkpoint:
    """Finished segments, saved atomically after each one. A different fingerprint (other cards, model, plan or code)
    discards them, so stale text is never reused. `cache` has the shape generate_lesson(cache=...) expects."""
    def __init__(self,path,fingerprint):
        self.path=Path(path);self.fingerprint=fingerprint;self.cache={}
        try:
            saved=json.loads(self.path.read_text())
            if saved.get('fingerprint')==fingerprint:self.cache=dict(saved.get('segments',{}))
        except (OSError,ValueError,AttributeError):self.cache={}

    def add(self,segment):
        self.cache[segment['id']]={'template':segment['template'],'attempts_log':segment['attempts_log']}
        tmp=self.path.with_name(self.path.name+'.tmp')
        tmp.write_text(json.dumps({'fingerprint':self.fingerprint,'segments':self.cache},ensure_ascii=False))
        os.replace(tmp,self.path)
