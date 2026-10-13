"""Local, deterministic timetable demo. No household records or production scheduling changes."""
import copy
import json
import math
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path


def slots(start_ms, class_minutes=20, break_minutes=5):
    result=[]; at=start_ms
    for subject, title, minutes, available in [('math','Maths',class_minutes,True), ('break','Break',break_minutes,True),
        ('science','Science',class_minutes,False), ('break','Break',break_minutes,True), ('english','English',class_minutes,False)]:
        result.append({'subject':subject,'title':title,'start_ms':at,'end_ms':at+minutes*60000,'content_available':available})
        at += minutes*60000
    return result


class Timetable:
    def __init__(self, root, base_script, narrator, lesson_loader, clock=None):
        self.root=Path(root); self.base_script=Path(base_script); self.narrator=narrator
        self.lesson_loader=lesson_loader; self.clock=clock or (lambda: time.time()*1000)
        self.lock=threading.RLock(); self.state=None; self.process=None; self.prepared=None
        self.worker_active=False
        data=json.loads((self.root/'docs/voice-module/PAIR_INVENTORY.json').read_text())
        self.catalog={p['concept_id']:p for p in data['pairs'] if p['plan_passed']}

    def list_cards(self):
        return [{'id':p['concept_id'],'grade':p['grade'],'module':p['module'],
                 'title':p['concept_id'].split('_',4)[-1].replace('_',' ').capitalize(),
                 'quick_demo_available':p['concept_id']=='math_g2_m1_l1_pairs_to_ten'} for p in self.catalog.values()]

    def snapshot(self):
        with self.lock:
            if not self.state: return {'schedule':None,'server_now_ms':self.clock()}
            state=copy.deepcopy(self.state); now=self.clock()
            state['class_phase']='cancelled' if state.get('cancelled') else 'completed' if state.get('finished') else 'started' if state.get('started') else 'ringing' if now>=state['start_ms'] else 'waiting'
            state['server_now_ms']=now
            return {'schedule':state,'server_now_ms':now}

    def create(self, request, start_thread=True):
        now=self.clock(); cid=request.get('concept_id'); start=request.get('start_ms'); lead=request.get('lead_seconds',300)
        mode=request.get('mode','fresh')
        if cid not in self.catalog or mode not in {'fresh','reuse'}: raise ValueError('Choose an available maths pair and preparation mode.')
        if isinstance(start,bool) or not isinstance(start,(int,float)) or not math.isfinite(start) or not now+3000<=start<=now+86400000:
            raise ValueError('Choose a class time at least three seconds ahead, within the next 24 hours.')
        if isinstance(lead,bool) or not isinstance(lead,(int,float)) or not math.isfinite(lead) or not 0<=lead<=3600:
            raise ValueError('Preparation lead time must be between zero and 60 minutes.')
        if mode=='reuse' and cid!='math_g2_m1_l1_pairs_to_ten': raise ValueError('Quick demo is available only for the checked pairs-to-ten script.')
        with self.lock:
            if self.worker_active:raise ValueError('The previous preparation is still stopping. Please try again shortly.')
            if self.state and not self.state.get('cancelled') and not self.state.get('finished'): raise ValueError('Cancel the current timetable before creating another.')
            self.state={'id':str(uuid.uuid4()),'concept_id':cid,'mode':mode,'start_ms':start,'prepare_at_ms':start-lead*1000,
                        'preparation':'waiting','percent':0,'completed':0,'total':None,'message':'Waiting to prepare',
                        'slots':slots(start),'borrowed_minutes':0,'started':False,'finished':False,'cancelled':False}
            self.prepared=None; sid=self.state['id']
            if start_thread:self.worker_active=True
        if start_thread:
            threading.Thread(target=self.run,args=(sid,),daemon=True).start()
        return self.snapshot()

    def update(self,sid,**values):
        with self.lock:
            if self.state and self.state['id']==sid and not self.state.get('cancelled'): self.state.update(values)

    def run(self,sid):
        try:self._run(sid)
        finally:self.worker_active=False

    def _run(self,sid):
        while True:
            with self.lock:
                if not self.state or self.state['id']!=sid or self.state['cancelled']: return
                remaining=self.state['prepare_at_ms']-self.clock()
            if remaining<=0:break
            time.sleep(min(.25,remaining/1000))
        try:
            self.update(sid,preparation='preparing',message='Planning the lesson',percent=1)
            self.narrator.release()
            row=self.catalog[self.state['concept_id']]
            out=Path.home()/'edaptive-voice/lesson-preparation'/sid
            command=[sys.executable,'-B','-m','voice_service.preparation_worker','--root',str(self.root),
                     '--concept',row['concept'],'--assessment',row['assessment'],'--concept-id',row['concept_id'],
                     '--assessment-id',row['assessment_id'],'--output',str(out)]
            if self.state['mode']=='reuse':command+=['--reuse',str(self.base_script)]
            self.process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
            script=None; error=None
            for line in self.process.stdout:
                try:data=json.loads(line)
                except ValueError:continue
                if data.get('error'):error=data['error']
                if data.get('script'):script=data['script']
                if 'percent' in data:self.update(sid,percent=data['percent'],completed=data.get('completed',0),total=data.get('total'),
                                                message={'rechecking':'Rechecking the saved script','generating':'Preparing the lesson script','validated':'Checking narration readiness'}.get(data['phase'],'Planning the lesson'))
            code=self.process.wait(); self.process=None
            with self.lock:
                if self.state['cancelled']:return
            if code!=0 or not script:raise ValueError(error or 'The local script agent could not finish. Please retry.')
            prepared=self.lesson_loader(Path(script))
            self.update(sid,percent=98,message='Warming the local teacher voice')
            self.narrator.warm()
            with self.lock:
                if self.state['id']!=sid or self.state['cancelled']:return
                self.prepared=prepared
            self.update(sid,percent=100,preparation='ready',message='Lesson ready')
        except Exception as error:
            self.update(sid,preparation='failed',message=str(error)[:500])

    def action(self,request):
        with self.lock:
            if not self.state or request.get('schedule_id')!=self.state['id'] or self.state['cancelled']:
                raise ValueError('This timetable is no longer active.')
            kind=request.get('action')
            if kind=='cancel':
                self.state['cancelled']=True
                self.state['started']=False
                if self.process:self.process.terminate()
            elif kind=='borrow':
                if self.state['started'] or self.state['finished'] or self.clock()<self.state['start_ms']:raise ValueError('Borrow five minutes when the class alarm rings.')
                self.state['start_ms']+=300000; self.state['borrowed_minutes']+=5
                for slot in self.state['slots']:slot['start_ms']+=300000;slot['end_ms']+=300000
            elif kind=='start':
                if self.clock()<self.state['start_ms'] or self.state['preparation']!='ready':raise ValueError('The class starts at its scheduled time, after preparation is complete.')
                self.state['started']=True
            elif kind=='finish':
                if not self.state['started']:raise ValueError('The class has not started.')
                self.state['started']=False;self.state['finished']=True
            else:raise ValueError('Unknown timetable action.')
            return self.snapshot()

    def lesson(self,sid):
        with self.lock:
            if not self.state or self.state['id']!=sid or self.state['cancelled'] or not self.state['started'] or not self.prepared:
                raise ValueError('The scheduled class is not active.')
            return self.prepared
