"""Benchmark sources only. Area companion is manually curated, never pipeline-generated."""
from __future__ import annotations
import copy
import json
from pathlib import Path


def collection(path):
    data=json.loads(Path(path).read_text());return data.get('cards',[data]) if isinstance(data,dict) else data

def load_card(path,card_id=None,assessment=False):
    key='assessment_card_id' if assessment else 'concept_id';items=collection(path)
    found=[c for c in items if card_id is None or c.get(key)==card_id]
    if len(found)!=1:raise ValueError('Select exactly one '+key+' from '+str(path))
    return found[0]

def prepare_samples(root,output):
    root=Path(root);output=Path(output);output.mkdir(parents=True,exist_ok=True);curr=root/'Maths Concept Cards Curriculum'
    definitions=[('area_perimeter','math_g4_m3_l1_area_perimeter_formulas','**/math_g4_m3_Lessons.json'),('grade1','math_g1_m1_l1_embedded_numbers','**/math_g1_m1_l1_lesson.json'),('shape_attributes','math_g2_m8_l1_shape_attributes','**/math_g2_m8_Lessons.json')]
    manifest=[]
    for name,cid,glob in definitions:
        p=next(curr.glob(glob));c=load_card(p,cid)
        if name=='area_perimeter':
            index={q['id']:q for q in c['questions']}
            a={'schema_version':'0.1-draft','card_type':'assessment_card','assessment_card_id':'benchmark_assess_'+cid,'card_version':1,'linked_concept':{'concept_id':cid,'concept_version':c['card_version']},'subject':c['subject'],'grade':c['grade'],'review_status':'draft','objective_refs':[c['objective']['id']],'provenance':{'generated_by':'hand_authored_script_benchmark_fixture','note':'No paired Grade 4 assessment was present. All questions, answer keys and hints reference existing concept-card items. Difficulty is a manual benchmark choice.'},'readiness':{'ready_for_delivery':False,'blocking_issues':['Benchmark-only fixture; needs owner review.']},'difficulty_levels':['easy','medium','hard'],'max_attempts_default':2,'default_outcome_routes':{'correct':'advance_to_next_question_or_close','partial':'use_only_if_partial_credit_eligible_else_same_as_incorrect','incorrect':'give_next_hint_then_retry_until_max_attempts','unclear':'reprompt_once_then_treat_as_incorrect'},'fallback_rules':{'on_help_requested':'give_next_hint_level_without_using_an_attempt','on_repeated_failure':'after_max_attempts_reveal_answer_reference_and_advance'},'questions':[],'follow_ups':[],'rubrics':[],'hints':[]}
            # Select prompts whose source already stands alone; no invented maths.
            for level,qid in [('easy','q_pr_2'),('medium','q_pr_16'),('hard','q_ps_1')]:
                q=index[qid];hids=q['hint_ids'];order={h['id']:h['level'] for h in c['hints']};hids=sorted(hids,key=lambda h:order[h])
                a['questions'].append({'id':'aq_'+level,'difficulty':level,'origin':'reused','question_ref':{'scope':'concept_card','id':qid},'rubric_ref':{'scope':'concept_card','id':q['rubric_id']},'hint_refs':[{'scope':'concept_card','id':h} for h in hids],'response_type':'short_text','routes':'default','stimulus':{'kind':'none'}})
            # Follow-up reuses a source question; route and trigger explicitly agree.
            parent=a['questions'][-1];parent['routes']={**a['default_outcome_routes'],'incorrect':'give_followup_fu_hard_then_bottom_out'};parent['follow_up_ref']={'scope':'this_card','id':'fu_hard'}
            q=index['q_pr_17'];a['follow_ups'].append({'id':'fu_hard','question_ref':{'scope':'concept_card','id':q['id']},'triggered_by':{'question_id':'aq_hard','outcome':'incorrect'},'rubric_ref':{'scope':'concept_card','id':q['rubric_id']},'hint_refs':[{'scope':'concept_card','id':h} for h in q['hint_ids']],'response_type':'short_text','max_attempts':1,'on_resolved':'return_to_aq_hard_then_bottom_out','stimulus':{'kind':'none'}})
        else:
            ap=p.with_suffix('.assessment_card.json');aa=collection(ap);a=next(a for a in aa if a['linked_concept']['concept_id']==cid)
        cp=output/(name+'.concept.json');ap=output/(name+'.assessment.json')
        cp.write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n');ap.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n')
        manifest.append({'name':name,'concept':str(cp.resolve()),'assessment':str(ap.resolve()),'concept_id':cid,'source_concept_file':str(p.resolve()),'assessment_fixture_only':name=='area_perimeter'})
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');return manifest
