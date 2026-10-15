"""Resolve scoped card references and make an immutable, conditional segment plan."""
from __future__ import annotations
import copy
import re
from .spoken import spoken_math,strip_label,subkey

LEVELS = ('easy', 'medium', 'hard')
LEGACY_ROUTES = {
    'advance_to_next_question_or_close', 'use_only_if_partial_credit_eligible_else_same_as_incorrect',
    'give_next_hint_then_retry_until_max_attempts', 'reprompt_once_then_treat_as_incorrect',
    'retry_eligible_parts_with_hint_until_max_attempts', 'hint_then_retry_until_max_attempts',
    'followup_once_then_retry_parent_if_attempt_remains', 'followup_once_then_retry_missing_parts_if_attempt_remains',
    'return_to_parent_if_attempt_remains_else_reveal_parent_and_advance',
    'reveal_followup_then_return_to_parent_if_attempt_remains',
}


def answers(key):
    """All declared aliases, including nested multi-part and open-response keys."""
    found=[]
    def walk(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if k in ('accept','acceptable_answers','expected','value','answer'):
                    if isinstance(v,(str,int,float)):found.append(str(v))
                    elif isinstance(v,list):found.extend(str(i) for i in v if isinstance(i,(str,int,float)))
                else:walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(key)
    return list(dict.fromkeys(found))


REWRITE_TYPES=('hook','lecture','worked_example','watch_out','recap')


def plan_lesson(concept, assessment, metaphor='detectives', outline=None, rewrite=False):
    c=copy.deepcopy(concept); a=copy.deepcopy(assessment)
    if metaphor not in ('detectives','builders','explorers'):raise ValueError('Unknown metaphor')
    if a.get('linked_concept',{}).get('concept_id')!=c.get('concept_id'):raise ValueError('Linked concept mismatch')
    if a.get('linked_concept',{}).get('concept_version')!=c.get('card_version'):raise ValueError('Linked concept version mismatch')
    if a.get('grade')!=c.get('grade') or a.get('subject')!=c.get('subject'):raise ValueError('Grade/subject mismatch')
    if not isinstance(c.get('grade'),int) or c['grade']<1:raise ValueError('Invalid grade')
    if not re.fullmatch(r'[A-Za-z0-9_-]+',c['concept_id']):raise ValueError('Unsafe concept id')
    if sorted(q.get('difficulty','') for q in a.get('questions',[]))!=sorted(LEVELS):raise ValueError('Need exactly one easy, medium, hard question')
    indexes={}
    for scope,card in [('concept_card',c),('this_card',a)]:
        idx={}
        for field in ('explanations','examples','questions','follow_ups','rubrics','hints','misconceptions','assets_required'):
            for item in card.get(field,[]):
                iid=item.get('id',item.get('asset_id'))
                if not iid or iid in idx:raise ValueError('Missing/duplicate source id: '+str(iid))
                idx[iid]=item
        if scope=='concept_card':idx[c['objective']['id']]=c['objective']
        indexes[scope]=idx
    def resolve(ref):
        try:return indexes[ref['scope']][ref['id']]
        except (KeyError,TypeError):raise ValueError('Unresolved scoped reference: '+str(ref))
    def refs(*items):
        return [{'card_id':c['concept_id'] if scope=='concept_card' else a['assessment_card_id'], 'scope':scope,'id':iid} for scope,iid in items]
    def text_of(item):
        text=item.get('text',item.get('prompt',''))
        if not isinstance(text,str) or not text.strip():raise ValueError('Empty source text: '+str(item.get('id')))
        return spoken_math(text.strip())
    ss=[]
    def add(kind,content,ref,**meta):
        segment={'id':'s_%04d'%(len(ss)+1),'type':kind,'content':content,'source_refs':ref,'metaphor':metaphor,**meta}
        ss.append(segment);return segment
    def teaching_meta(item):
        raw=item.get('protected_statements',[])
        if not isinstance(raw,list) or any(not isinstance(t,str) for t in raw):raise ValueError('Invalid protected statements: '+item['id'])
        protected=[spoken_math(t) for t in raw]
        if any(not isinstance(t,str) or not t.strip() or t not in text_of(item) for t in protected):
            raise ValueError('Protected statement must occur in its teaching source: '+item['id'])
        return {'protected_statements':protected} if protected else {}
    def visual(ids,stimulus=None):
        cues=[]; rr=[]
        for iid in dict.fromkeys(ids):
            asset=resolve({'scope':'concept_card','id':iid});rr+=refs(('concept_card',iid))
            desc=asset.get('description') or asset.get('alt_text')
            if not desc:raise ValueError('Asset has no written description: '+iid)
            cues.append(desc)
        if stimulus:
            if stimulus.get('description'):cues.append(stimulus['description'])
            if stimulus.get('state'):cues.append(stimulus['state'])
            for value in stimulus.get('must_show_exactly',[]):cues.append(value)
        unique=[];seen=set()
        for cue in cues:
            key=re.sub(r'\W+',' ',cue.lower()).strip()
            if key not in seen:unique.append(cue);seen.add(key)
        return ({'visual_cue':'[show: '+'; '.join(unique)+']'} if unique else {}),rr
    objref=refs(('concept_card',c['objective']['id']))
    add('hook',text_of(c['objective']),objref,phase='main')
    # Match examples to ideas. The sub-lesson tag in an id (ex_l3_..., exp_l3_...) decides first; word overlap only
    # breaks ties inside that sub-lesson. Every example is used exactly once.
    groups=[[] for _ in c.get('explanations',[])]
    outlined=set()
    if outline:
        ideas={exp['id']:i for i,exp in enumerate(c.get('explanations',[]))}
        eligible={item['id']:item for item in c.get('examples',[])+c.get('explanations',[])}
        for idea,source_ids in outline.items():
            if idea not in ideas or not isinstance(source_ids,list):raise ValueError('Invalid lesson outline')
            for source_id in source_ids:
                if source_id not in eligible:raise ValueError('Outline must use card teaching sources: '+str(source_id))
                groups[ideas[idea]].append(eligible[source_id]);outlined.add(source_id)
    def words(t):return set(re.findall(r'[a-z]+',t.lower()))-set('the a an is of and or to in by for it its you can'.split())
    def bag(item):return words(item.get('text','')+' '+strip_label(item.get('title',''))+' '+item['id'].replace('_',' '))
    explanations=c.get('explanations',[])
    for ex in c.get('examples',[]):
        if ex['id'] in outlined or not groups:continue
        if ex.get('idea_id'):
            matches=[n for n,exp in enumerate(explanations) if exp['id']==ex['idea_id']]
            if not matches:raise ValueError('Example has an unknown idea_id: '+ex['id'])
            groups[matches[0]].append(ex);continue
        key=subkey(ex['id']);pool=[n for n,exp in enumerate(explanations) if key and subkey(exp['id'])==key] or list(range(len(explanations)))
        groups[max(pool,key=lambda n:len(bag(ex)&bag(explanations[n])))].append(ex)
    review_notes={'ideas_without_example':[exp['id'] for exp,g in zip(explanations,groups) if not g] if c.get('examples') else []}
    used_questions=set()
    for i,exp in enumerate(c.get('explanations',[])):
        cue,rr=visual(exp.get('asset_ids',[]))
        add('lecture',text_of(exp),refs(('concept_card',exp['id']))+rr,phase='main',**cue,**teaching_meta(exp))
        for ex in groups[i]:
            cue,rr=visual(ex.get('asset_ids',[]))
            title=spoken_math(strip_label(ex.get('title','')).rstrip('.'))
            add('worked_example',text_of(ex),refs(('concept_card',ex['id']))+rr,phase='main',idea_id=exp['id'],source_title=title,**cue,**teaching_meta(ex))
        # A reflection built from the card's own idea title; it asks the student to explain, and invents no task or number.
        idea=spoken_math(strip_label(exp.get('title','')).rstrip('.'))
        defaults=['How would you explain this idea: '+idea+'?', 'What would you tell someone about this idea: '+idea+'?', 'What helped you understand this idea: '+idea+'?']
        turn=spoken_math(exp.get('reflection_prompt') or (defaults[i%len(defaults)] if idea else 'What did you notice in that explanation?'))
        if '?' not in turn:raise ValueError('Authored reflection must ask a question: '+exp['id'])
        add('transition',turn,refs(('concept_card',exp['id'])),phase='your_turn',instruction='Write one short encouragement sentence, then <CONTENT>. The source already asks the reflection. No extra question, question stem, achievement claim, task or number. Wait for the student.')
    if not groups:
        for ex in c.get('examples',[]):
            cue,rr=visual(ex.get('asset_ids',[]));add('worked_example',text_of(ex),refs(('concept_card',ex['id']))+rr,phase='main',**cue)
    for mis in c.get('misconceptions',[]):
        content=spoken_math(mis.get('response_text') or mis.get('text') or '')
        if not content:raise ValueError('Misconception needs student-facing response_text: '+mis['id'])
        add('watch_out',content,refs(('concept_card',mis['id'])),phase='main')
    add('transition','',objref,phase='main',instruction='Invite the student into the check-in. Wait for their answers.')
    guidance=a.get('tutor_guidance',a.get('delivery_script',{}))
    gids={g['question_id']:g for g in guidance.get('questions',[])}
    routes_plan=[];used_hints=set(); assessment_question_ids={q['id'] for q in a['questions']+a.get('follow_ups',[])}
    def effective_routes(q,r,g,is_followup):
        raw=q.get('routes','default')
        result=copy.deepcopy(a.get('default_outcome_routes',{}) if raw=='default' else raw)
        if not isinstance(result,dict):raise ValueError('Invalid routes')
        if is_followup and raw=='default':
            result={'correct':q.get('on_resolved',''), 'incorrect':g.get('outcome_actions',{}).get('incorrect',q.get('on_resolved','')), 'unclear':result.get('unclear','reprompt_once_then_treat_as_incorrect')}
        if is_followup and raw!='default' and q.get('on_resolved') and result.get('correct')!=q['on_resolved']:
            raise ValueError('Follow-up resolution contradicts its correct route')
        if g.get('outcome_actions') and (not is_followup or raw!='default'):
            if g['outcome_actions']!=result:raise ValueError('Guidance/routes disagree: '+q['id'])
        for outcome,action in list(result.items()):
            if outcome=='partial' and action=='use_only_if_partial_credit_eligible_else_same_as_incorrect':
                if not r.get('partial_credit_eligible',r.get('partial') is not None):result[outcome]=result['incorrect']
            if outcome not in ('correct','partial','incomplete','incorrect','unclear'):raise ValueError('Unsupported outcome')
            if not action:raise ValueError('Missing route action')
            if action not in LEGACY_ROUTES and action not in guidance.get('route_definitions',{}):
                if action.startswith('give_followup_') and action.endswith('_then_bottom_out'):
                    fid=action[len('give_followup_'):-len('_then_bottom_out')]
                    if fid not in assessment_question_ids:raise ValueError('Missing route follow-up: '+fid)
                elif action.startswith('return_to_') and action.endswith('_then_bottom_out'):
                    if action[len('return_to_'):-len('_then_bottom_out')] not in assessment_question_ids:raise ValueError('Missing route parent')
                else:raise ValueError('Unsupported route action: '+action)
        if not {'correct','incorrect','unclear'}<=set(result):raise ValueError('Missing essential outcome route')
        return result
    def question(q,is_followup=False):
        qref=refs(('this_card',q['id'])); source=q
        if q.get('question_ref'):
            source=resolve(q['question_ref']);qref+=refs((q['question_ref']['scope'],q['question_ref']['id']));used_questions.add(source['id'])
        g=gids.get(q['id'],{});content=spoken_math(g.get('delivery_prompt') or '') or text_of(source)
        for p in q.get('parts',[]):content+='\n'+text_of(p)
        r=resolve(q['rubric_ref']);rref=refs((q['rubric_ref']['scope'],q['rubric_ref']['id']))
        alias=answers(r.get('answer_key',{}))
        stimulus=q.get('stimulus',{});ids=[]
        if stimulus.get('asset_ref'):
            ref=stimulus['asset_ref'];resolve(ref)
            if ref['scope']=='concept_card':ids.append(ref['id'])
        cue,rr=visual(ids,stimulus)
        cond={'triggered_by':q.get('triggered_by')} if is_followup else {}
        add('question',content,qref+rr,phase='follow_up_question' if is_followup else 'root_question',question_id=q['id'],difficulty=q.get('difficulty'),answer_aliases=alias,condition=cond or None,**cue)
        routes=effective_routes(q,r,g,is_followup)
        row={'question_id':q['id'],'routes':routes,'source_routes':q.get('routes','default'),'rubric_ref':q['rubric_ref'],'max_attempts':q.get('max_attempts',1 if is_followup else a.get('max_attempts_default',2)), 'branches':{},'hint_segments':[], 'follow_up_ref':q.get('follow_up_ref'),'triggered_by':q.get('triggered_by'),'on_resolved':q.get('on_resolved')}
        for outcome,action in routes.items():
            # Only student-facing guidance may supply factual feedback, never grading descriptions.
            feedback=spoken_math(g.get('feedback',{}).get(outcome) or '')
            seg=add('branch',feedback,qref+rref,phase='feedback',question_id=q['id'],outcome=outcome,route_action=action,condition={'question_id':q['id'],'outcome':outcome},instruction={'correct':'Celebrate effort and invite the next step.','partial':'Encourage the student to revisit unfinished reasoning; do not assert which parts were correct.','incomplete':'Invite the student to try the remaining parts; do not guess what is missing.','incorrect':'Gently invite another try. Do not give any hint in this feedback line.','unclear':'Gently ask the student to say their answer again; do not supply an answer.'}[outcome])
            row['branches'][outcome]=seg['id']
        hint_refs=g.get('hint_sequence',q.get('hint_refs',[]))
        previous_level=0
        for n,h in enumerate(hint_refs):
            hint=resolve(h);level=hint.get('level',n+1)
            if level<previous_level:raise ValueError('Hints must be in level order')
            previous_level=level;used_hints.add((h['scope'],h['id']))
            seg=add('branch',text_of(hint),qref+refs((h['scope'],h['id'])),phase='hint',question_id=q['id'],hint_level=level,hint_index=n,condition={'question_id':q['id'],'event':'next_hint','hint_index':n})
            row['hint_segments'].append(seg['id'])
        reveal=spoken_math(g.get('answer_reveal',{}).get('say') or '')
        if not reveal:
            key=r.get('answer_key',{})
            if key.get('mode')=='exact' and key.get('accept'):reveal='The answer is '+str(key['accept'][0])+'.'
            else:reveal='' # Explicit reference-only reveal; no invented multipart/open worked solution.
        seg=add('branch',reveal,qref+rref,phase='answer_reveal',question_id=q['id'],condition={'question_id':q['id'],'event':'answer_reveal_authorized_by_card'},instruction='Offer to work through it together. The lesson player resolves the linked rubric.',answer_reference_only=not bool(reveal))
        row['answer_reveal_segment']=seg['id'];routes_plan.append(row)
    followup_ids={q['id'] for q in a.get('follow_ups',[])}
    for parent in a['questions']:
        if parent.get('follow_up_ref'):
            ref=parent['follow_up_ref'];resolve(ref)
            if ref['scope']!='this_card' or ref['id'] not in followup_ids:raise ValueError('Parent must reference an assessment follow-up')
    for level in LEVELS:question(next(q for q in a['questions'] if q['difficulty']==level))
    for q in a.get('follow_ups',[]):
        trigger=q.get('triggered_by',{})
        if trigger.get('question_id') not in {p['id'] for p in a['questions']}:raise ValueError('Orphan follow-up')
        parent=next(p for p in a['questions'] if p['id']==trigger['question_id'])
        action=effective_routes(parent,resolve(parent['rubric_ref']),gids.get(parent['id'],{}),False).get(trigger.get('outcome'),'')
        if 'followup' not in action:raise ValueError('Follow-up trigger does not match route')
        if parent.get('follow_up_ref',{}).get('id')!=q['id']:raise ValueError('Follow-up must match the parent reference')
        if action.startswith('give_followup_') and action.endswith('_then_bottom_out'):
            if action[len('give_followup_'):-len('_then_bottom_out')]!=q['id']:raise ValueError('Named follow-up does not match trigger')
        question(q,True)
    # Every source question is preserved as optional practice, never an extra root check-in.
    for q in c.get('questions',[]):
        if q['id'] in used_questions:continue
        cue,rr=visual(q.get('asset_ids',[]))
        aliases=answers(resolve({'scope':'concept_card','id':q['rubric_id']}).get('answer_key',{})) if q.get('rubric_id') else []
        add('question',text_of(q),refs(('concept_card',q['id']))+rr,phase='optional_practice',answer_aliases=aliases,condition={'event':'optional_practice','question_ref':q['id']},**cue)
    for scope,card in [('concept_card',c),('this_card',a)]:
        for h in card.get('hints',[]):
            if (scope,h['id']) in used_hints:continue
            add('branch',text_of(h),refs((scope,h['id'])),phase='hint_bank',hint_level=h.get('level'),condition={'event':'source_hint_requested','hint_ref':h['id']})
    mentioned_assets={ref['id'] for s in ss for ref in s['source_refs'] if ref['scope']=='concept_card'}
    for asset in c.get('assets_required',[]):
        if asset['asset_id'] in mentioned_assets:continue
        cue,rr=visual([asset['asset_id']])
        add('branch','',rr,phase='asset_bank',condition={'event':'source_asset_requested','asset_ref':asset['asset_id']},**cue)
    # Summarise taught facts, rather than repeating the objective's future-tense "Learn...".
    recap=c['objective'].get('recap_text')
    recap_ideas=c.get('explanations',[]) if recap else c.get('explanations',[])[:3]
    if not recap:
        recap=' '.join(re.split(r'(?<=[.!?])\s+',text_of(exp))[0] for exp in recap_ideas)
    if not recap:recap='You can describe the ideas we explored today.'
    add('recap',spoken_math(recap),objref+refs(*[('concept_card',exp['id']) for exp in recap_ideas]),phase='main',instruction='Close warmly and summarise the taught facts. Do not restart the lesson or claim the student has mastered it.')
    if rewrite:
        for s in ss:
            if s['type'] in REWRITE_TYPES and s.get('phase')=='main':s['rewrite']=True
    return {'schema_version':'script-0.1','rewrite':bool(rewrite),'review_notes':review_notes,'concept_id':c['concept_id'],'assessment_card_id':a['assessment_card_id'],'grade':c['grade'],'subject':c['subject'],'metaphor':metaphor,'segments':ss,'route_plan':routes_plan,'delivery_policy':{'main_path':[s['id'] for s in ss if s.get('phase') in ('main','your_turn','root_question')], 'conditional_segments_are_not_read_sequentially':True,'default_outcome_routes':a.get('default_outcome_routes',{}),'fallback_rules':a.get('fallback_rules',{}),'tutor_guidance':guidance},'input_readiness':{'concept_review_status':c.get('review_status'),'assessment_review_status':a.get('review_status'),'assessment_readiness':a.get('readiness')},'source_cards':{'concept':c,'assessment':a}}
