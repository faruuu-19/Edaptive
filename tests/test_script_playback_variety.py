"""Variety applies to lines heard together, rather than mutually exclusive banks."""
import unittest
from script_agent import plan_lesson,generate_lesson
from script_agent.models import FakeModel
from script_agent.expressions import BANK
from script_agent.checks import ADDRESS,NUMBERS
from test_script_agent import cards


class PlaybackVarietyTests(unittest.TestCase):
    def test_suggested_openers_meet_framing_rules(self):
        for purpose,entries in BANK.items():
            for entry in entries:
                text=entry.format(role='detective')
                self.assertIsNone(NUMBERS.search(text),(purpose,text))
                self.assertIsNotNone(ADDRESS.search(text),(purpose,text))

    def test_separate_optional_questions_do_not_share_a_hard_repeat_budget(self):
        c,a=cards()
        c['questions'] += [{'id':'optional_'+str(i),'text':'What is 3 times 4?','rubric_id':'cr'} for i in range(8)]
        class Canned(FakeModel):
            def generate(self,r):
                if r['segment'].get('phase')=='optional_practice':
                    self.calls.append(r);return 'You can try it. <CONTENT>'
                return super().generate(r)
        result=generate_lesson(plan_lesson(c,a),Canned())
        for s in result['segments']:
            if s.get('phase')=='optional_practice':self.assertEqual([],s['errors'])

    def test_main_lesson_still_rejects_repeated_lecture_framing(self):
        c,a=cards()
        c['explanations'] += [{'id':'idea_'+str(i),'text':'Area counts square units inside a rectangle.'} for i in range(3)]
        class Canned(FakeModel):
            def generate(self,r):
                if r['segment']['type']=='lecture':
                    self.calls.append(r);return 'You can look closely. <CONTENT>'
                return super().generate(r)
        result=generate_lesson(plan_lesson(c,a),Canned())
        self.assertTrue(any('repeated_framing' in s['errors'] for s in result['segments'] if s['type']=='lecture'))

if __name__=='__main__':unittest.main()
