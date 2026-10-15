"""Regression tests for the faults found in the first live polygon script."""
import copy
import json
import unittest
from pathlib import Path
from script_agent import plan_lesson,generate_lesson,check_segment,check_coverage
from script_agent.checks import check_rewrite
from script_agent.generator import request_for,rewrite_request
from script_agent.models import FakeModel
from test_script_agent import cards


class DeliveryFixTests(unittest.TestCase):
    def test_rewrite_cannot_expand_equal_sides_and_angles_to_every_part(self):
        s={'type':'lecture','content':'A regular polygon has all equal sides and all equal angles. A square is a regular quadrilateral.'}
        bad="You can picture a regular polygon with all equal sides and angles. A square is a regular quadrilateral where every part matches perfectly."
        self.assertIn('rewrite_unsupported_generalisation',check_rewrite(s,bad,3))
        plural=bad.replace('every part matches','all parts match')
        self.assertIn('rewrite_unsupported_generalisation',check_rewrite(s,plural,3))
        good="You can picture a regular polygon with all equal sides and angles. A square is a regular quadrilateral."
        self.assertNotIn('rewrite_unsupported_generalisation',check_rewrite(s,good,3))

    def test_openers_do_not_conflict_with_question_and_reflection_rules(self):
        from script_agent.expressions import BANK
        for purpose in ('question','optional_practice','your_turn'):
            s={'type':'transition' if purpose=='your_turn' else 'question','phase':purpose,'content':'What do you notice?'}
            for opener in BANK[purpose]:
                text=opener.format(role='detective')+' <CONTENT>'
                self.assertEqual([],check_segment(s,text,3),(purpose,text))

    def test_teaching_does_not_claim_unobserved_good_work(self):
        s={'type':'lecture','phase':'main','content':'Parallel sides do not meet.'}
        self.assertIn('unsupported_praise',check_segment(s,'You can look closely. <CONTENT> Great job being curious!',3))
        s['type']='branch';s['outcome']='correct'
        self.assertNotIn('unsupported_praise',check_segment(s,'Great job! You checked it. <CONTENT>',3))

    def test_teaching_framing_is_not_padded_with_repeated_encouragement(self):
        s={'type':'lecture','phase':'main','content':'Parallel sides do not meet.'}
        self.assertIn('framing_too_long',check_segment(s,"Let's explore together. You can watch how this works. We are detectives solving mysteries. You can look very closely with me. <CONTENT>",3))

    def test_empty_feedback_can_omit_marker_but_real_passage_cannot(self):
        s={'type':'branch','phase':'feedback','outcome':'unclear','content':''}
        self.assertEqual([],check_segment(s,'Could you say that again?',3))
        s['content']='Please explain your shape choice.'
        self.assertIn('source_content_placeholder',check_segment(s,'Could you say that again?',3))
        s['content']=''
        self.assertIn('source_content_placeholder',check_segment(s,'You can try. <CONTENT><CONTENT>',3))

    def test_reflection_does_not_get_an_extra_question_or_stem(self):
        s={'type':'transition','phase':'your_turn','content':'Why do the groups overlap?'}
        for text in ('What do you think, <CONTENT>','What would you say? <CONTENT>'):
            self.assertIn('reflection_framing',check_segment(s,text,3))
        self.assertEqual([],check_segment(s,'You can take your time. <CONTENT>',3))

    def test_praise_does_not_guess_ability_or_use_babyish_labels(self):
        s={'type':'transition','phase':'your_turn','content':'What do you notice?'}
        for text in ('You are a brilliant detective! <CONTENT>','You can do it, little detective! <CONTENT>'):
            self.assertIn('unsupported_praise',check_segment(s,text,3))
        self.assertIn('unsupported_praise',check_rewrite({'type':'recap','content':'A square has equal sides.'},'You are brilliant! A square has equal sides.',3))

    def test_a_source_reflection_is_used_instead_of_a_generic_title_question(self):
        c,a=cards();c['explanations'][0]['reflection_prompt']='How do square units help you describe area?'
        p=plan_lesson(c,a)
        turn=next(s for s in p['segments'] if s.get('phase')=='your_turn')
        self.assertEqual(c['explanations'][0]['reflection_prompt'],turn['content'])

    def test_recap_uses_taught_content_instead_of_restarting_the_objective(self):
        c,a=cards();c['objective']['text']='Learn how to find area.'
        p=plan_lesson(c,a)
        recap=p['segments'][-1]
        self.assertIn('Area counts square units',recap['content'])
        self.assertNotIn('Learn how',recap['content'])
        c['objective']['recap_text']='Area counts the square units inside your rectangle.'
        self.assertEqual(c['objective']['recap_text'],plan_lesson(c,a)['segments'][-1]['content'])

    def test_critical_source_statements_cannot_be_reversed_in_a_rewrite(self):
        s={'type':'lecture','content':'Not every rectangle is a rhombus. The groups overlap at squares.','protected_statements':['Not every rectangle is a rhombus.']}
        self.assertIn('rewrite_changed_protected_fact',check_rewrite(s,'You see that every rectangle is a rhombus. The groups overlap at squares.',3))
        p={'grade':3,'subject':'math','metaphor':'detectives'}
        self.assertEqual(s['protected_statements'],json.loads(rewrite_request(p,s)['prompt'])['protected_statements'])

    def test_unknown_authored_protected_statement_fails_preflight(self):
        c,a=cards();c['explanations'][0]['protected_statements']=['A square is a circle.']
        with self.assertRaises(ValueError):plan_lesson(c,a,rewrite=True)

    def test_assembly_keeps_spaces_at_marker_boundaries(self):
        c,a=cards()
        class Joined(FakeModel):
            def generate(self,r):
                if r['segment'].get('phase')=='answer_reveal':
                    self.calls.append(r);return "You can look now.<CONTENT>"
                return super().generate(r)
        p=plan_lesson(c,a);out=generate_lesson(p,Joined())
        reveal=next(s for s in out['segments'] if s.get('phase')=='answer_reveal' and s['content'])
        self.assertIn('now. The answer',reveal['text'])
        self.assertEqual([],check_coverage(p,out['segments']))

    def test_example_title_is_not_spoken_as_a_fragment(self):
        c,a=cards();c['examples'][0]['title']='A rectangle with square units'
        ex=next(s for s in plan_lesson(c,a)['segments'] if s['type']=='worked_example')
        self.assertEqual(c['examples'][0]['text'],ex['content'])

    def test_equivalent_visual_description_is_not_repeated(self):
        c,a=cards();c['assets_required']=[{'asset_id':'diagram','description':'Equal sides and marked angles.'}]
        a['questions'][0]['stimulus']={'asset_ref':{'scope':'concept_card','id':'diagram'},'state':'Equal sides and marked angles'}
        q=next(s for s in plan_lesson(c,a)['segments'] if s.get('question_id')=='aq_easy')
        self.assertEqual('[show: Equal sides and marked angles.]',q['visual_cue'])

    def test_reflection_prompt_requests_a_short_statement_not_another_question(self):
        c,a=cards();p=plan_lesson(c,a);turn=next(s for s in p['segments'] if s.get('phase')=='your_turn')
        prompt=json.loads(request_for(p,turn)['prompt'])
        self.assertIn('one short',prompt['instruction'].lower())
        self.assertTrue(all('?' not in s['template'].replace('<CONTENT>','') for s in prompt['style_examples']))

if __name__=='__main__':unittest.main()
