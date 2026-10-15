"""The corrected real lesson must teach and assess the rules used in its questions."""
import json
import unittest
from pathlib import Path
from script_agent.sample_inputs import load_card
from script_agent import plan_lesson

CID='math_g3_m7_l5_compare_classify_other_polygons'
CONCEPT=Path('tests/script_fixtures/polygons.concept.json')
ASSESSMENT=Path('tests/script_fixtures/polygons.assessment.json')

class PolygonRevisionTests(unittest.TestCase):
    def setUp(self):
        self.c=load_card(CONCEPT,CID);self.a=load_card(ASSESSMENT,assessment=True)

    def test_corrected_pair_is_versioned_and_records_the_manual_revision(self):
        self.assertEqual(2,self.c['card_version'])
        self.assertEqual(2,self.a['linked_concept']['concept_version'])
        self.assertEqual(2,self.a['card_version'])
        self.assertIn('manual_revision',self.a['provenance'])
        self.assertFalse(self.a['readiness']['ready_for_delivery'])

    def test_overlap_instead_of_a_false_chain_and_explicit_trapezoid_convention(self):
        text=' '.join(e['text'] for e in self.c['explanations'])
        self.assertIn('at least one pair',text)
        self.assertIn('Not every rectangle is a rhombus',text)
        self.assertIn('general group name',text)
        cue=next(a for a in self.c['assets_required'] if a['asset_id']=='a_quad_family')
        self.assertIn('overlap',cue['description'].lower())
        self.assertNotIn('Five nested groups',cue['must_show_exactly'])

    def test_every_idea_has_a_concrete_source_reflection_and_matching_example(self):
        self.assertTrue(all(e.get('reflection_prompt') and '?' in e['reflection_prompt'] for e in self.c['explanations']))
        p=plan_lesson(self.c,self.a)
        self.assertEqual([],p['review_notes']['ideas_without_example'])

    def test_measurement_has_a_ruler_cue_and_is_not_a_universal_smallest_unit_rule(self):
        exp=next(e for e in self.c['explanations'] if e['id']=='exp_precise_unit')
        self.assertIn('For this comparison',exp['text'])
        self.assertEqual(['a_inch_ruler'],exp['asset_ids'])
        self.assertNotIn('centimeter',next(q for q in self.c['questions'] if q['id']=='q_pr_1')['text'])

    def test_questions_now_check_classification_and_reasoning(self):
        med=next(q for q in self.a['questions'] if q['difficulty']=='medium')
        hard=next(q for q in self.a['questions'] if q['difficulty']=='hard')
        self.assertIn('parallel',med['prompt'])
        self.assertIn('Explain',hard['prompt'])
        r=next(r for r in self.a['rubrics'] if r['id']==hard['rubric_ref']['id'])
        self.assertEqual('open',r['answer_key']['mode'])
        self.assertTrue(r['partial_credit_eligible'])
        self.assertIn('partial',hard['routes'])
        guide={q['question_id']:q for q in self.a['tutor_guidance']['questions']}
        self.assertIn('rhombus',guide[hard['id']]['answer_reveal']['say'])

    def test_recap_summarises_rules_and_has_no_future_learn_instruction(self):
        recap=plan_lesson(self.c,self.a)['segments'][-1]
        self.assertIn('regular polygon',recap['content'])
        self.assertIn('overlap',recap['content'])
        self.assertNotIn('Learn what',recap['content'])

if __name__=='__main__':unittest.main()
