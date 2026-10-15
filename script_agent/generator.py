"""One call per segment, one repair, visible flags, deterministic assembly."""
from __future__ import annotations
import copy
import json
import time
from collections import Counter
from pathlib import Path
from .checks import check_segment,check_coverage,check_rewrite,style_scores,number_values,equations,key_terms,opener_key,framing_key,words,INVITES
from .expressions import suggest
from .spoken import assemble_template

EXAMPLES=Path(__file__).with_name('gold_examples.json')
REWRITES=Path(__file__).with_name('gold_rewrites.json')
SYSTEM="""You are a warm, enthusiastic primary-school teacher speaking to one student.
Write ONLY a short spoken-text template with exactly one literal <CONTENT> marker.
Code replaces that marker with the source text. Do not copy or rewrite the source.
Add happy framing and encouragement. No factual statements, numbers (digits OR words),
maths, answers, formulas, new examples, task instructions, images, or extra concepts.
Use you/your or let's. Use the lesson's chosen metaphor only. At most one emoji.
Never say 'correct' unless this is the correct branch. Never guess the student's work.
Use brief, calm encouragement. Do not call the student brilliant, super, or a little detective.
Outside a correct branch, never say great job/good work or claim solved/mastered/understood.
For teaching templates, keep the framing under 20 words, usually a single short sentence.
Write complete sentences, never a question stem before <CONTENT>. Avoid repeated metaphor labels.
No headings, JSON, labels, code fences or explanations of your output."""

def request_for(plan,segment,repair_errors=None,previous=None,recent_openers=None):
    examples=json.loads(EXAMPLES.read_text()) if EXAMPLES.exists() else []
    # Each hand-authored gold lesson contributes a matching segment, style only.
    few=[]
    for lesson in examples:
        choices=[s for s in lesson['segments'] if s['type']==segment['type'] and s.get('phase')==segment.get('phase') and s.get('outcome')==segment.get('outcome')]
        if not choices:choices=[s for s in lesson['segments'] if s['type']==segment['type']]
        if choices:
            s=choices[0];few.append({'grade':lesson['grade'],'metaphor':lesson['metaphor'],'type':s['type'],'template':s['template']})
    prompt={'grade':plan['grade'],'subject':plan['subject'],'metaphor':plan['metaphor'], 'type':segment['type'],'phase':segment.get('phase'),'outcome':segment.get('outcome'),'instruction':segment.get('instruction','Introduce the source kindly. Encourage the student.'),'max_words_per_sentence':10 if plan['grade']==1 else 14 if plan['grade']<=3 else 18,'max_framing_words':20 if segment['type'] in ('hook','lecture','worked_example','watch_out','recap') else 50,'style_examples':few,'avoid_recent_openers':recent_openers or [],'suggested_openers':suggest(segment,plan['metaphor'],recent_openers or []),'card_line_already_invites':bool(segment.get('phase') in ('feedback','answer_reveal') and INVITES.search(segment.get('content',''))),'output_rule':'Write your short spoken framing and exactly one literal <CONTENT>. Do not replace that marker; you are not given the factual passage.'}
    if segment.get('phase')=='your_turn':
        prompt['instruction']=segment.get('instruction','')+' Use at most 12 framing words. The source supplies the complete question.'
        prompt['style_examples']=[{'grade':g,'type':'transition','template':t} for g,t in [(1,'You can take your time. <CONTENT>'),(2,'Your turn to think. <CONTENT>'),(4,'Let’s pause here. <CONTENT>')]]
    if segment['type']=='question':prompt['instruction']='Write a short statement inviting the student to answer, then <CONTENT>. At most 14 framing words. No extra question or question stem.'
    if not segment.get('content','').strip():prompt['output_rule']='No protected passage follows. Return just your short spoken line. You may omit <CONTENT>; do not output it twice.'
    if segment.get('phase')=='hook':prompt['instruction']='Greet the student and set up a one-sentence mission in the lesson metaphor. No facts or numbers.'
    if repair_errors:prompt.update({'repair_errors':repair_errors,'previous_rejected_template':previous,'repair_instruction':'Fix precisely these errors. Return just the template with one <CONTENT> marker.'})
    return {'system':SYSTEM,'prompt':json.dumps(prompt,ensure_ascii=False),'segment':segment,'repair_errors':repair_errors or []}

REWRITE_SYSTEM="""You are a warm, enthusiastic primary-school teacher speaking to one student.
Rewrite the SOURCE passage as natural spoken teaching, in the lesson's metaphor, using you/your/let's.
Do NOT copy the unprotected source sentences. Say those ideas in fresh, simple words for one child,
and invite the student to notice or picture it. Equation sentences and listed protected statements stay exactly as written.
Keep every number and every key maths word from the source. Say numbers and operations in words
(plus, minus, times, divided by, equals), never as symbols. Do not add any fact, number, example or maths task that is not in the source.
Short sentences and familiar words; explain a new term the first time it appears. At most one emoji, never in a maths sentence.
Use the metaphor lightly. Avoid little detective, super detective, brilliant, great job, good work, and guessed achievements.
Keep any protected statements exactly as supplied, while rewriting the surrounding explanation.
Return ONLY the spoken text: no headings, labels, JSON, code fences or notes."""
REWRITE_FOCUS={'hook':'Open with a one-sentence mission in the metaphor, then say the goal from the source.',
 'lecture':'Teach the idea warmly, in the order of the source. A short friendly lead-in is fine.',
 'worked_example':'Walk through the example step by step, keeping each equation sentence exactly as written.',
 'watch_out':'Warn the student kindly about the mix-up, never scolding.',
 'recap':'Summarise the taught facts from this source and close warmly. Do not say now learn, restart the lesson, or claim mastery.'}

def rewrite_request(plan,segment,repair_errors=None,previous=None,recent_openers=None):
    gold=json.loads(REWRITES.read_text()) if REWRITES.exists() else []
    few=[{'grade':g['grade'],'metaphor':g['metaphor'],'source':g['source'],'spoken':g['spoken']} for g in gold if g['type']==segment['type']][:3]
    source=segment['content']
    terms=sorted({w.lower() for w in words(source) if w[:5].lower() in key_terms(source) and len(w)>=4})[:10]
    prompt={'grade':plan['grade'],'subject':plan['subject'],'metaphor':plan['metaphor'],'type':segment['type'],'focus':REWRITE_FOCUS.get(segment['type'],''),
        'source_text':source,'protected_statements':segment.get('protected_statements',[]),'must_keep_numbers':sorted(number_values(source)),'must_keep_equations':sorted('%s %s %s equals %s'%e for e in equations(source)),'must_keep_words':terms,
        'max_words_per_sentence':10 if plan['grade']==1 else 14 if plan['grade']<=3 else 18,'target_length_words':max(12,int(len(words(source))*1.3)+8),
        'style_examples':few,'avoid_recent_openers':recent_openers or [],'suggested_openers':suggest(segment,plan['metaphor'],recent_openers or [])}
    if repair_errors:prompt.update({'repair_errors':repair_errors,'previous_rejected_rewrite':previous,'repair_instruction':'Fix precisely these errors and return only the corrected spoken text.'})
    return {'system':REWRITE_SYSTEM,'prompt':json.dumps(prompt,ensure_ascii=False),'segment':segment,'repair_errors':repair_errors or [],'max_tokens':320}

def generate_lesson(plan,model,on_segment=None,cache=None):
    start=time.monotonic();ss=[];attempt_log=[];initial_violations=0;recent=[]
    histories={}
    for original in plan['segments']:
        s=copy.deepcopy(original);errors=[];attempts=[];template=''
        if s['id'] in plan['delivery_policy']['main_path']:
            scope=('main',)
        elif s.get('phase') in ('optional_practice','hint_bank','asset_bank'):
            scope=('bank',s['id'])
        else:
            scope=('question',s.get('question_id',s['id']))
        history=histories.setdefault(scope,{'framings':Counter(),'openers':Counter()})
        rewriting=bool(s.get('rewrite'))
        check=(lambda text:check_rewrite(s,text,plan['grade'],history)) if rewriting else (lambda text:check_segment(s,text,plan['grade'],history))
        framed=False
        if cache and original['id'] in cache:
            template=cache[original['id']]['template'];attempts=cache[original['id']]['attempts_log']
            framed=rewriting and bool(attempts) and attempts[-1].get('mode')=='framed'
            errors=check_segment(s,template,plan['grade'],history) if framed or not rewriting else check(template)
            if attempts and 'model_call_failed' in attempts[-1]['errors']:errors.append('model_call_failed')
            initial_violations+=sum(len(a['errors']) for a in attempts[:1])
            rewrite_errors=(attempts[1] if len(attempts)>1 else attempts[0])['errors'] if framed and attempts else errors
        else:
            for attempt in range(2):
                request=(rewrite_request if rewriting else request_for)(plan,s,errors,template if attempt else None,recent[-10:])
                try:template=model.generate(request);errors=check(template)
                except (OSError,KeyError,ValueError,TimeoutError):
                    # Do not log arbitrary provider exception text or request headers.
                    template='';errors=['model_call_failed']
                attempts.append({'attempt':attempt+1,'errors':errors[:]})
                if attempt==0:initial_violations+=len(errors)
                if not errors:break
            rewrite_errors=errors
            if rewriting and errors and 'model_call_failed' not in errors:
                # Last resort before bare card text: one short framing line around the card's own passage (the original design).
                framed=True
                try:template=model.generate(request_for(plan,s,None,None,recent[-10:]));errors=check_segment(s,template,plan['grade'],history)
                except (OSError,KeyError,ValueError,TimeoutError):template='';errors=['model_call_failed']
                attempts.append({'attempt':3,'mode':'framed','errors':errors[:]})
        extra={}
        if rewriting:
            clean=[e for e in rewrite_errors if e!='model_call_failed']
            if not framed and not errors:
                text=template.strip();extra={'rewrite_mode':'rewritten','rewrite_errors':[]}
                history['openers'][opener_key(text)]+=1;recent.append(opener_key(text))
            elif framed and not errors:
                text=assemble_template(template,s['content']);extra={'rewrite_mode':'fallback_framed','rewrite_errors':clean}
                framing=template.replace('<CONTENT>','')
                if framing.strip():history['framings'][framing_key(framing)]+=1;history['openers'][opener_key(framing)]+=1;recent.append(opener_key(framing))
            else:
                # Everything failed: the card's own words, reported. A provider failure additionally stays a flagged error.
                text=s['content'].strip();extra={'rewrite_mode':'fallback_verbatim','rewrite_errors':clean}
                errors=['model_call_failed'] if 'model_call_failed' in errors+rewrite_errors else []
        else:
            text=assemble_template(template,s['content'])
            framing=template.replace('<CONTENT>','')
            if framing.strip():history['framings'][framing_key(framing)]+=1;history['openers'][opener_key(framing)]+=1;recent.append(opener_key(framing))
        s.update({'template':template,'text':text,'status':'flagged' if errors else 'passed','errors':errors,'attempts':len(attempts),'attempts_log':attempts,**extra})
        ss.append(s);attempt_log+=attempts
        if on_segment:on_segment(s)
    coverage=check_coverage(plan,ss);violations=sum(len(s['errors']) for s in ss)+len(coverage)
    result={k:copy.deepcopy(v) for k,v in plan.items() if k not in ('source_cards','segments')}
    main=[s for s in ss if s['id'] in plan['delivery_policy']['main_path']]
    result.update({'model':model.name,'segments':ss,'validation':{'passed':violations==0,'initial_rule_violations':initial_violations,'final_rule_violations':violations,'coverage_errors':coverage,'repairs':sum(s['attempts']>=2 for s in ss),'rewrite':{'enabled':bool(plan.get('rewrite')),'rewritten':sum(s.get('rewrite_mode')=='rewritten' for s in ss),'fallback_framed':[s['id'] for s in ss if s.get('rewrite_mode')=='fallback_framed'],'fallback_verbatim':[s['id'] for s in ss if s.get('rewrite_mode')=='fallback_verbatim']},'style':style_scores(main,plan['grade']),'all_segment_style':style_scores(ss,plan['grade']),'generated_framing_style':style_scores([{'text':s['template'].replace('<CONTENT>','')} for s in ss if s.get('rewrite_mode')!='rewritten'],plan['grade']),'review_required':['Free framing has heuristic checks, not semantic proof.','Teaching rewrites have heuristic fact checks; source accuracy, meaning and reading level still need human review.' if plan.get('rewrite') else 'Protected card text is preserved verbatim; source errors and reading level need review.','Input card readiness and human model selection still apply.']},'metrics':{'lesson_wall_seconds':time.monotonic()-start,'model_calls':len(getattr(model,'metrics',[])) or len(getattr(model,'calls',[])),'calls':getattr(model,'metrics',[])}})
    return result

def markdown(result):
    lines=['# '+result['concept_id']+' — '+result['model'],'', 'Validation: '+('passed deterministic checks' if result['validation']['passed'] else 'FLAGGED — review errors before use')+'. Human tone and source review required.','', '## Spoken lesson','']
    for s in result['segments']:
        if s['id'] not in result['delivery_policy']['main_path']:continue
        lines+=['### '+s['id']+' · '+s['type'],'']
        if s.get('visual_cue'):lines+=[s['visual_cue'],'']
        lines+=[s['text'],'']
        if s.get('rewrite_mode')=='fallback_framed':lines+=['**FALLBACK — rewrite rejected; short framing around the card text:** '+', '.join(s.get('rewrite_errors',[])),'']
        if s.get('rewrite_mode')=='fallback_verbatim':lines+=['**FALLBACK — rewrite rejected; bare card text used:** '+', '.join(s.get('rewrite_errors',[])),'']
        if s['errors']:lines+=['**FLAGGED:** '+', '.join(s['errors']),'']
    lines+=['## Conditional Q&A lines','', 'Read only the branch selected by the lesson player. Hints are delivered individually. The agent never judges answers.','']
    for s in result['segments']:
        if s['id'] in result['delivery_policy']['main_path'] or s.get('phase') in ('optional_practice','hint_bank','asset_bank'):continue
        lines+=['### '+s['id']+' · '+str(s.get('question_id',''))+' · '+str(s.get('outcome',s.get('phase'))),'', '`'+json.dumps(s.get('condition'),ensure_ascii=False)+'`','',s['text'],'']
        if s.get('visual_cue'):lines+=[s['visual_cue'],'']
        if s.get('route_action'):lines+=['Route: `'+s['route_action']+'`','']
        if s['errors']:lines+=['**FLAGGED:** '+', '.join(s['errors']),'']
    lines+=['## Optional source practice and hint bank','','<details><summary>Additional card material; not read on the main lesson path</summary>','']
    for s in result['segments']:
        if s.get('phase') in ('optional_practice','hint_bank','asset_bank'):
            lines+=['**'+s['id']+' · '+s['phase']+'**','',s.get('visual_cue',''),s['text'],'']
            if s['errors']:lines+=['**FLAGGED:** '+', '.join(s['errors']),'']
    lines+=['</details>','','## Scores','', '```json',json.dumps(result['validation'],ensure_ascii=False,indent=2),'```','']
    return '\n'.join(lines)

def write_lesson(result,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    base=output/result['concept_id'];js=base.with_suffix('.script.json');md=base.with_suffix('.script.md')
    for path,content in [(js,json.dumps(result,ensure_ascii=False,indent=2)+'\n'),(md,markdown(result))]:
        tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(content);tmp.replace(path)
    return js,md
