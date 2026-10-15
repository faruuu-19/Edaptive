"""Tests written before implementation; every safety rule has a deliberate break."""
import copy
import tempfile
import unittest
from pathlib import Path
from script_agent import plan_lesson, generate_lesson, check_segment, check_coverage, style_scores, write_lesson
from script_agent.models import FakeModel


def cards():
    concept = {'concept_id':'math_g4_m3_l1_test','card_version':1,'subject':'math','grade':4,
        'objective':{'id':'obj','text':'Find the area of rectangles.'},
        'explanations':[{'id':'exp','text':'Area counts square units inside a rectangle.'}],
        'examples':[{'id':'ex','text':'Multiply 3 by 4. The area is 12 square units.'}],
        'misconceptions':[{'id':'mis','response_text':'Check the units you use.'}],
        'questions':[{'id':'cq','text':'What is 3 times 4?','rubric_id':'cr'}],
        'rubrics':[{'id':'cr','answer_key':{'mode':'exact','accept':['12','twelve']}}],
        'hints':[{'id':'ch','level':1,'text':'Think about rows.'}], 'assets_required':[]}
    assessment={'assessment_card_id':'assess_test','card_version':1,'linked_concept':{'concept_id':concept['concept_id'],'concept_version':1},
        'subject':'math','grade':4, 'review_status':'draft', 'max_attempts_default':2,
        'default_outcome_routes':{'correct':'advance_to_next_question_or_close','partial':'use_only_if_partial_credit_eligible_else_same_as_incorrect','incorrect':'give_next_hint_then_retry_until_max_attempts','unclear':'reprompt_once_then_treat_as_incorrect'},
        'fallback_rules':{'on_repeated_failure':'after_max_attempts_reveal_answer_reference_and_advance'},
        'questions':[], 'follow_ups':[], 'rubrics':[], 'hints':[]}
    for level in ['easy','medium','hard']:
        qid='aq_'+level
        assessment['questions'].append({'id':qid,'difficulty':level,'prompt':'What is 3 times 4?', 'rubric_ref':{'scope':'this_card','id':'r_'+qid}, 'hint_refs':[{'scope':'this_card','id':'h_'+qid}], 'routes':'default'})
        assessment['rubrics'].append({'id':'r_'+qid,'answer_key':{'mode':'exact','accept':['12','twelve']},'partial_credit_eligible':False})
        assessment['hints'].append({'id':'h_'+qid,'level':1,'text':'Think about rows.'})
    q=assessment['questions'][2]; q['routes']={**assessment['default_outcome_routes'], 'incomplete':'give_followup_fu_hard_then_bottom_out'}
    q['follow_up_ref']={'scope':'this_card','id':'fu_hard'}
    assessment['follow_ups']=[{'id':'fu_hard','triggered_by':{'question_id':q['id'],'outcome':'incomplete'},'prompt':'What is 3 times 4?', 'rubric_ref':q['rubric_ref'],'hint_refs':q['hint_refs'],'on_resolved':'return_to_aq_hard_then_bottom_out'}]
    return concept,assessment


class ScriptTests(unittest.TestCase):
    def setUp(self):
        self.c,self.a=cards(); self.plan=plan_lesson(self.c,self.a)
    def question(self):
        return next(s for s in self.plan['segments'] if s['type']=='question' and s.get('question_id')=='aq_easy')
    def test_arc_and_all_types(self):
        ss=self.plan['segments']; self.assertEqual(ss[0]['type'],'hook'); self.assertEqual(ss[-1]['type'],'recap')
        self.assertEqual({'hook','lecture','worked_example','watch_out','transition','question','branch','recap'}, {s['type'] for s in ss})
        self.assertEqual(['easy','medium','hard'],[s['difficulty'] for s in ss if s.get('phase')=='root_question'])
        self.assertEqual([],check_coverage(self.plan,ss))
    def test_fake_segment_assembly_and_refs(self):
        m=FakeModel(); out=generate_lesson(self.plan,m)
        self.assertEqual(len(self.plan['segments']),len(m.calls))
        self.assertEqual(0,out['validation']['final_rule_violations'])
        self.assertTrue(all(s['source_refs'] for s in out['segments']))
        self.assertIn('Multiply 3 by 4. The area is 12 square units.', next(s['text'] for s in out['segments'] if s['type']=='worked_example'))
    def test_invented_number_and_word_caught(self):
        for text in ['You have 99 clues. <CONTENT>','You have ninety-nine clues. <CONTENT>',
                     'You have ⅓ of a clue. <CONTENT>','You have Ⅳ clues. <CONTENT>','You have ٩ clues. <CONTENT>']:
            self.assertIn('invented_number',check_segment(self.question(),text,4))
    def test_existing_number_changed_formula_caught(self):
        self.assertIn('invented_number',check_segment(self.question(),'You multiply 4 by 3. <CONTENT>',4))
    def test_answer_leak_digits_words_units_and_negation(self):
        for text in ['Your answer is 12. <CONTENT>','You found twelve square units. <CONTENT>',"Your answer is not twelve. <CONTENT>"]:
            self.assertIn('answer_leakage',check_segment(self.question(),text,4))
    def test_source_omission_and_duplication(self):
        for text in ['You can try it.','<CONTENT> You can try it. <CONTENT>']:
            self.assertIn('source_content_placeholder',check_segment(self.question(),text,4))
    def test_question_and_hint_coverage_break(self):
        for phase in ['root_question','hint']:
            ss=[s for s in self.plan['segments'] if s.get('phase')!=phase]
            self.assertTrue(check_coverage(self.plan,ss))
    def test_branch_coverage_break(self):
        ss=[s for s in self.plan['segments'] if s.get('outcome')!='incomplete']
        self.assertTrue(check_coverage(self.plan,ss))
    def test_route_tampering_break(self):
        ss=copy.deepcopy(self.plan['segments']); next(s for s in ss if s.get('outcome')=='incorrect')['route_action']='advance'
        self.assertTrue(check_coverage(self.plan,ss))
    def test_source_tampering_break(self):
        ss=copy.deepcopy(self.plan['segments']);ss[1]['source_refs']=[]
        self.assertTrue(check_coverage(self.plan,ss))
    def test_repair_once_then_explicit_failure(self):
        m=FakeModel(['You found 99. <CONTENT>']*2)
        out=generate_lesson(self.plan,m)
        self.assertEqual(2,out['segments'][0]['attempts'])
        self.assertEqual('flagged',out['segments'][0]['status'])
        self.assertFalse(out['validation']['passed'])
        self.assertIn('invented_number',m.calls[1]['repair_errors'])
    def test_repair_succeeds(self):
        out=generate_lesson(self.plan,FakeModel(['You found 99. <CONTENT>','You can try it. <CONTENT>']))
        self.assertEqual('passed',out['segments'][0]['status']);self.assertEqual(2,out['segments'][0]['attempts'])
    def test_wrong_link_and_missing_refs_fail_preflight(self):
        for mutation in ['link','hint','grade','levels']:
            a=copy.deepcopy(self.a)
            if mutation=='link':a['linked_concept']['concept_id']='other'
            if mutation=='hint':a['questions'][0]['hint_refs'][0]['id']='missing'
            if mutation=='grade':a['grade']=1
            if mutation=='levels':a['questions'].pop()
            with self.assertRaises(ValueError):plan_lesson(self.c,a)
    def test_partial_ineligible_uses_incorrect_route(self):
        s=next(s for s in self.plan['segments'] if s.get('question_id')=='aq_easy' and s.get('outcome')=='partial' and s.get('phase')=='feedback')
        self.assertEqual(self.a['default_outcome_routes']['incorrect'],s['route_action'])
    def test_followup_route_not_silently_fabricated(self):
        rows=self.plan['route_plan']; fu=next(r for r in rows if r['question_id']=='fu_hard')
        self.assertEqual('return_to_aq_hard_then_bottom_out',fu['routes']['correct'])
    def test_followup_explicit_outcomes_preserved(self):
        fu=self.a['follow_ups'][0]
        fu['routes']={**self.a['default_outcome_routes'],'correct':fu['on_resolved'],'incomplete':'hint_then_retry_until_max_attempts'}
        row=next(r for r in plan_lesson(self.c,self.a)['route_plan'] if r['question_id']==fu['id'])
        self.assertEqual('hint_then_retry_until_max_attempts',row['routes']['incomplete'])
    def test_contradictory_followup_resolution_rejected(self):
        self.a['follow_ups'][0]['routes']=self.a['default_outcome_routes']
        with self.assertRaises(ValueError):plan_lesson(self.c,self.a)
    def test_correctness_claim_only_in_correct_branch(self):
        for s in [self.question(),next(s for s in self.plan['segments'] if s.get('outcome')=='incorrect')]:
            self.assertIn('premature_correctness_claim',check_segment(s,'You got it right! <CONTENT>',4))
        correct=next(s for s in self.plan['segments'] if s.get('outcome')=='correct')
        self.assertNotIn('premature_correctness_claim',check_segment(correct,'You got it right! <CONTENT>',4))
    def test_named_followup_must_match_trigger_and_parent_ref(self):
        other=copy.deepcopy(self.a['follow_ups'][0]);other['id']='fu_other'
        self.a['follow_ups'].append(other)
        with self.assertRaises(ValueError):plan_lesson(self.c,self.a)
    def test_parent_reference_cannot_name_different_followup(self):
        self.a['questions'][2]['follow_up_ref']['id']='does_not_exist'
        with self.assertRaises(ValueError):plan_lesson(self.c,self.a)
    def test_visual_cue_is_written_only(self):
        self.c['assets_required']=[{'asset_id':'asset','description':'A rectangle with rows of squares.','status':'not_available'}]
        self.c['explanations'][0]['asset_ids']=['asset'];p=plan_lesson(self.c,self.a)
        s=next(s for s in p['segments'] if s['type']=='lecture')
        self.assertTrue(s['visual_cue'].startswith('[show:'));self.assertNotIn('image_url',s)
    def test_style_breaks(self):
        for text,error in [('You '+('wonderful '*25)+'. <CONTENT>','sentence_length'),('Try it. <CONTENT>','direct_address'),('You can try! 🎉🎉🎉 <CONTENT>','emoji_count')]:
            self.assertIn(error,check_segment(self.question(),text,1))
        score=style_scores([{'text':'You can try it.'}]*5,1)
        self.assertGreater(score['repeated_openers'],0);self.assertEqual(0,score['question_rate'])
    def test_compound_emoji_counts_as_one_visible_symbol(self):
        for emoji in ['🕵️‍♂️','👩🏽‍🏫','🏳️‍🌈','🇵🇰','1️⃣']:
            template='You can try it! '+emoji+' <CONTENT>'
            self.assertNotIn('emoji_count',check_segment(self.question(),template,4))
            self.assertEqual(1,style_scores([{'text':template}],4)['emoji_count'])
        self.assertIn('emoji_count',check_segment(self.question(),'You can try! 🕵️‍♂️ 👩🏽‍🏫 <CONTENT>',4))
    def test_markdown_separates_conditional_branches(self):
        out=generate_lesson(self.plan,FakeModel())
        with tempfile.TemporaryDirectory() as d:
            paths=write_lesson(out,Path(d)); md=paths[1].read_text()
            self.assertIn('Conditional',md);self.assertIn('source_refs',paths[0].read_text())
    def test_pair_answers_leakage(self):
        self.a['rubrics'][0]['answer_key']={'mode':'pair_of_parts','parts':[{'id':'p1','accept':['12','twelve']},{'id':'p2','accept':['8','eight']}]}
        q=next(s for s in plan_lesson(self.c,self.a)['segments'] if s.get('phase')=='root_question')
        self.assertIn('answer_leakage',check_segment(q,'You found eight. <CONTENT>',4))
    def test_source_text_not_rewritten(self):
        out=generate_lesson(self.plan,FakeModel());ss=copy.deepcopy(out['segments'])
        next(s for s in ss if s['type']=='worked_example')['text']='Multiply 3 by 4. The area is 13 square units.'
        self.assertTrue(check_coverage(self.plan,ss))

if __name__=='__main__':unittest.main()

class ScriptIntegrationTests(unittest.TestCase):
    def test_review_pair_prioritizes_rules_and_requires_three_lessons(self):
        from run_script_agent_comparison import review_pair
        rows=[]
        for model,violations,style in [('safe',0,70),('pretty_but_flagged',30,100),('second',1,80)]:
            for lesson in ['area_perimeter','grade1','shape_attributes']:
                rows.append({'model':model,'lesson':lesson,'status':'measured','final_violations':violations,'style_score':style})
        rows.append({'model':'incomplete','lesson':'area_perimeter','status':'measured','final_violations':0,'style_score':100})
        self.assertEqual(['safe','second'],[r['model'] for r in review_pair(rows)])
    def test_real_three_sample_cards_full_coverage(self):
        import json
        root=Path(__file__).parent/'script_fixtures'
        for name in ['area_perimeter','grade1','shape_attributes']:
            c=json.loads((root/(name+'.concept.json')).read_text());a=json.loads((root/(name+'.assessment.json')).read_text())
            p=plan_lesson(c,a);r=generate_lesson(p,FakeModel())
            self.assertEqual(0,r['validation']['final_rule_violations'],name)
            seen={(x['scope'],x['id']) for s in r['segments'] for x in s['source_refs']}
            for field in ['explanations','examples','misconceptions','questions','hints']:
                for item in c.get(field,[]):self.assertIn(('concept_card',item['id']),seen,(name,field,item['id']))
            for field in ['questions','follow_ups','hints']:
                for item in a.get(field,[]):self.assertIn(('this_card',item['id']),seen,(name,field,item['id']))
            roots=[s for s in r['segments'] if s.get('phase')=='root_question']
            self.assertEqual(3,len(roots))
            for s in r['segments']:
                if s.get('phase')=='hint' and name!='area_perimeter':self.assertEqual('this_card',s['source_refs'][-1]['scope'])
    def test_golden_templates_are_used_in_requests(self):
        from script_agent.generator import request_for
        import json
        c,a=cards();p=plan_lesson(c,a);request=request_for(p,p['segments'][0])
        examples=json.loads(request['prompt'])['style_examples'];self.assertEqual({1,2,4},{e['grade'] for e in examples})
    def test_resource_gates(self):
        from script_agent.resources import guard,GIB
        self.assertTrue(guard({'physical_memory_bytes':16*GIB,'disk_free_bytes':GIB/2},5*GIB))
        self.assertTrue(guard({'physical_memory_bytes':16*GIB,'disk_free_bytes':20*GIB},12*GIB))
        self.assertTrue(guard({'physical_memory_bytes':None,'disk_free_bytes':20*GIB},GIB))
        self.assertFalse(guard({'physical_memory_bytes':16*GIB,'disk_free_bytes':20*GIB},5*GIB))
    def test_checkpoint_resume_makes_no_new_successful_calls(self):
        c,a=cards();p=plan_lesson(c,a);first=generate_lesson(p,FakeModel());m=FakeModel()
        second=generate_lesson(p,m,cache={s['id']:s for s in first['segments']})
        self.assertEqual(0,len(m.calls));self.assertEqual(first['segments'],second['segments'])
    def test_checkpoint_retains_truncation_and_provider_failure(self):
        c,a=cards();p=plan_lesson(c,a)
        first=generate_lesson(p,FakeModel(['You can try. <CONTENT> <TRUNCATED>']*2))
        resumed=generate_lesson(p,FakeModel(),cache={s['id']:s for s in first['segments']})
        self.assertIn('truncated_output',resumed['segments'][0]['errors'])
        class Broken(FakeModel):
            def generate(self,request):raise OSError('Provider failure')
        first=generate_lesson(p,Broken())
        resumed=generate_lesson(p,FakeModel(),cache={s['id']:s for s in first['segments']})
        self.assertIn('model_call_failed',resumed['segments'][0]['errors'])
    def test_local_provider_failure_is_counted_without_error_payload(self):
        from script_agent.models import LocalModel
        from unittest.mock import patch
        from script_agent.generator import request_for
        c,a=cards();p=plan_lesson(c,a);m=LocalModel('local-test')
        with patch.object(m,'_post',side_effect=OSError('private provider payload')):
            with self.assertRaises(OSError):m.generate(request_for(p,p['segments'][0]))
        self.assertEqual(1,len(m.metrics))
        self.assertNotIn('private',str(m.metrics))
    def test_malformed_provider_reply_counts_one_attempt(self):
        from script_agent.models import LocalModel
        from unittest.mock import patch
        from script_agent.generator import request_for
        c,a=cards();p=plan_lesson(c,a);m=LocalModel('local-test')
        with patch.object(m,'_post',return_value={'message':{'content':None}}):
            with self.assertRaises(OSError):m.generate(request_for(p,p['segments'][0]))
        self.assertEqual(1,len(m.metrics));self.assertFalse(m.metrics[0]['success'])
    def test_provider_failure_cannot_be_ranked_as_completed_benchmark(self):
        import json
        from unittest.mock import patch
        from script_agent.benchmark import benchmark_one
        from script_agent.resources import GIB
        class Broken(FakeModel):
            endpoint='http://127.0.0.1:11434';backend='ollama'
            def generate(self,request):raise OSError('Unavailable')
            def unload(self):pass
        class Sampler:
            def __init__(self,*args):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def peaks(self):return {'server_rss_bytes':None,'ollama_model_allocated_bytes':None,'ollama_vram_allocated_bytes':None}
        resource={'physical_memory_bytes':16*GIB,'disk_free_bytes':20*GIB,'vm_pressure_level':1}
        sample=json.loads((Path(__file__).parent/'script_fixtures/manifest.json').read_text())[0]
        with tempfile.TemporaryDirectory() as folder, patch('script_agent.benchmark.LocalModel',return_value=Broken()), patch('script_agent.benchmark.identity',return_value={'size':100,'digest':'fake'}), patch('script_agent.benchmark.snapshot',return_value=resource), patch('script_agent.benchmark.MemorySampler',Sampler), patch('builtins.print'):
            row=benchmark_one(sample,{'model':'fake','weight_gb':0.1},folder)
        self.assertEqual('not_completed',row['status']);self.assertTrue(row['terminal'])
    def test_local_endpoint_only(self):
        from script_agent.models import LocalModel
        for endpoint in ['https://example.com','http://key@localhost:8080','http://localhost:8080?key=secret']:
            with self.assertRaises(ValueError):LocalModel('any',endpoint=endpoint)
    def test_unknown_route_is_flagged_at_preflight(self):
        c,a=cards();a['questions'][0]['routes']={'correct':'invented_action','incorrect':'advance_to_next_question_or_close','unclear':'reprompt_once_then_treat_as_incorrect'}
        with self.assertRaises(ValueError):plan_lesson(c,a)
    def test_handwritten_gold_passes(self):
        import json
        data=json.loads((Path(__file__).parents[1]/'script_agent/gold_examples.json').read_text())
        for lesson in data:
            for segment in lesson['segments']:
                self.assertFalse(check_segment(segment,segment['template'],lesson['grade']),(lesson['name'],segment['template']))

class MoreRuleBreakTests(unittest.TestCase):
    def test_every_declared_deterministic_rule_has_a_break(self):
        c,a=cards();p=plan_lesson(c,a);q=next(s for s in p['segments'] if s.get('phase')=='root_question')
        broken=[('You get P = l × w. <CONTENT>','invented_formula'),('You are stupid. <CONTENT>','discouraging_tone'),('You can see the image. <CONTENT>','actual_image_reference'),('You can try. ``` <CONTENT>','non_spoken_output'),('You can try '+('very '*55)+'hard. <CONTENT>','framing_too_long'),('Your area is tiny. <CONTENT>','ungrounded_claim')]
        for text,error in broken:self.assertIn(error,check_segment(q,text,4),(text,error))
    def test_hint_order_and_orphan_followup_break(self):
        c,a=cards();a['hints']+= [{'id':'higher','level':3,'text':'Try rows.'},{'id':'lower','level':1,'text':'Try groups.'}]
        a['questions'][0]['hint_refs']=[{'scope':'this_card','id':'higher'},{'scope':'this_card','id':'lower'}]
        with self.assertRaises(ValueError):plan_lesson(c,a)
        c,a=cards();a['follow_ups'][0]['triggered_by']['question_id']='missing'
        with self.assertRaises(ValueError):plan_lesson(c,a)
    def test_dynamic_memory_shortage_break(self):
        from script_agent.resources import guard,GIB
        r={'physical_memory_bytes':16*GIB,'disk_free_bytes':20*GIB,'reclaimable_estimate_bytes':2*GIB}
        self.assertTrue(guard(r,5*GIB))

class ProductionPromptTests(unittest.TestCase):
    def test_model_never_receives_math_passage_it_should_not_rewrite(self):
        from script_agent.generator import request_for
        c,a=cards();p=plan_lesson(c,a);s=next(s for s in p['segments'] if s['type']=='worked_example');r=request_for(p,s)
        self.assertNotIn(s['content'],r['prompt'])
    def test_explanation_outline_uses_only_card_sources(self):
        c,a=cards();p=plan_lesson(c,a,outline={'exp':['ex']})
        ex=next(s for s in p['segments'] if s['type']=='worked_example')
        self.assertEqual('exp',ex['idea_id'])
        with self.assertRaises(ValueError):plan_lesson(c,a,outline={'exp':['invented']})
    def test_framing_must_keep_lesson_metaphor(self):
        c,a=cards();p=plan_lesson(c,a,metaphor='builders')
        self.assertIn('mixed_metaphor',check_segment(p['segments'][0],'You are a detective. <CONTENT>',4))
    def test_coverage_is_checked_against_cards_not_only_plan(self):
        c,a=cards();p=plan_lesson(c,a)
        p['segments']=[s for s in p['segments'] if not any(r['id']=='mis' for r in s['source_refs'])]
        self.assertTrue(check_coverage(p,p['segments']))
    def test_model_allocation_is_not_counted_twice_on_progress(self):
        from script_agent.resources import guard,GIB
        r={'physical_memory_bytes':16*GIB,'disk_free_bytes':20*GIB,'reclaimable_estimate_bytes':3*GIB,'vm_pressure_level':1}
        self.assertFalse(guard(r,5*GIB,current_model_loaded=True))
