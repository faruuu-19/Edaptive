"""Reference v0.2 controller for script-agent integration, not the app runtime.
The caller grades an answer against the supplied rubric, retaining correct
parts, and passes the classified outcome here. Counters persist per session.
"""
from dataclasses import dataclass,field

@dataclass
class Session:
    card:dict
    attempts:dict=field(default_factory=dict)
    hints:dict=field(default_factory=dict)
    clarifications:dict=field(default_factory=dict)
    followups_used:set=field(default_factory=set)
    completed:set=field(default_factory=set)

    def item(self,qid):
        return next(q for q in self.card['questions']+self.card['follow_ups'] if q['id']==qid)

    def hint(self,qid):
        seq=self.item(qid)['hint_refs'];index=min(self.hints.get(qid,0),len(seq)-1)
        self.hints[qid]=min(index+1,len(seq))
        return ('hint',seq[index]['id'])

    def advance(self,qid):
        self.completed.add(qid)
        ids=[q['id'] for q in self.card['questions']]
        index=ids.index(qid)+1
        return [('advance',ids[index])] if index<len(ids) else [('close',None)]

    def return_parent(self,fu):
        parent=fu['triggered_by']['question_id']
        item=self.item(parent)
        if self.attempts.get(parent,0)>=item.get('max_attempts',self.card['max_attempts_default']):
            return [('reveal',parent)]+self.advance(parent)
        return [('retry_unresolved',parent)]

    def respond(self,qid,event):
        if qid in self.completed:return [('already_completed',qid)]
        item=self.item(qid);fu=qid.startswith('fu_')
        if event=='help':return [self.hint(qid),('reprompt_pending',qid)]
        if event=='answer_requested':
            self.completed.add(qid)
            return [('reveal',qid)]+(self.return_parent(item) if fu else self.advance(qid))
        if event=='silence':event='unclear'
        if event=='unclear':
            if self.clarifications.get(qid,0)==0:
                self.clarifications[qid]=1
                return [('reprompt',qid)]
            event='incorrect'
        guidance=next(g for g in self.card['tutor_guidance']['questions']if g['question_id']==qid)
        if event=='partial' and not guidance['partial_credit_eligible']:event='incorrect'
        assert event in {'correct','partial','incorrect','incomplete'}
        assert event!='incomplete' or item['response_type']=='multi_part'
        self.attempts[qid]=self.attempts.get(qid,0)+1
        if event=='correct':
            self.completed.add(qid)
            return [('feedback_correct',qid)]+(self.return_parent(item) if fu else self.advance(qid))
        limit=item.get('max_attempts',self.card['max_attempts_default'])
        if fu:
            self.completed.add(qid)
            return [('feedback_incorrect',qid),('reveal',qid)]+self.return_parent(item)
        if self.attempts[qid]>=limit:
            return [('feedback_'+event,qid),('reveal',qid)]+self.advance(qid)
        actions=[('feedback_'+event,qid),self.hint(qid)]
        needs_fu=(qid=='aq_med_01' and event=='incorrect') or (qid=='aq_hard_01' and event=='incomplete')
        if needs_fu and qid not in self.followups_used:
            self.followups_used.add(qid)
            actions.append(('ask_followup',item['follow_up_ref']['id']))
        else:actions.append(('retry_unresolved',qid))
        return actions

def classify_parts(required, supplied, correct_ids, ambiguous_ids=()):
    """correct_ids includes previously retained correct parts."""
    present=set(supplied)|set(correct_ids)
    if ambiguous_ids or not present:return 'unclear'
    if set(required)-present:return 'incomplete'
    if set(required)<=set(correct_ids):return 'correct'
    if correct_ids:return 'partial'
    return 'incorrect'
