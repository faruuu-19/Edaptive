"""Tests for the second pass: pairing, spoken text, variety, and the verified rewrite. Written before the code."""
from __future__ import annotations
import copy
import json
import unittest
from collections import Counter
from pathlib import Path

from script_agent import plan_lesson, generate_lesson, check_segment, check_coverage
from script_agent.checks import check_rewrite
from script_agent.models import FakeModel
from script_agent.spoken import spoken_math, strip_label, subkey

import sys
sys.path.insert(0, str(Path(__file__).parent))
from test_script_agent import cards


def multi_cards():
    """Two sub-lessons whose examples are lexically misleading on purpose."""
    c, a = cards()
    c['explanations'] = [
        {'id': 'exp_l1_frame', 'title': 'L1 Ten-frame: 9 and 1 make 10', 'text': 'A ten-frame has 10 spots. Nine spots are full.'},
        {'id': 'exp_l2_next', 'title': 'L2 Next ten', 'text': 'Find the next ten after a number.'},
    ]
    c['examples'] = [
        # Words overlap the l1 explanation, but the id says sub-lesson 2.
        {'id': 'ex_l2_frame', 'title': 'L2 Ten-frame trick', 'text': 'The ten-frame has 10 spots. 8 plus 2 equals 10.'},
        {'id': 'ex_l1_frame_9', 'title': 'L1 Ten-frame with 9 dots', 'text': 'The ten-frame has 9 dots. 9 plus 1 equals 10.'},
    ]
    return c, a


class SpokenTextTests(unittest.TestCase):
    def test_label_is_stripped_from_titles(self):
        self.assertEqual('Ten-frame with 9 dots', strip_label('L1 Ten-frame with 9 dots'))
        self.assertEqual('Next ten', strip_label('L12: Next ten'))
        self.assertEqual('L-shapes', strip_label('L-shapes'))
        self.assertEqual('', strip_label(None))

    def test_symbols_become_words_only_between_numbers(self):
        self.assertEqual('10 minus 8 equals 2.', spoken_math('10 - 8 = 2.'))
        self.assertEqual('3 times 4 equals 12', spoken_math('3 × 4 = 12'))
        self.assertEqual('8 divided by 2 equals 4', spoken_math('8 ÷ 2 = 4'))
        self.assertEqual('5 plus 3 plus 2', spoken_math('5 + 3 + 2'))
        self.assertEqual('a ten-frame and the years 2020-2021', spoken_math('a ten-frame and the years 2020-2021'))
        self.assertEqual('Say ten 3.', spoken_math('Say ten 3.'))

    def test_subkey(self):
        self.assertEqual('3', subkey('ex_l3_51_20'))
        self.assertEqual('12', subkey('exp_L12_x'))
        self.assertIsNone(subkey('ex_rect_4x7'))
        self.assertIsNone(subkey('exp_pillar'))


class PlannerTests(unittest.TestCase):
    def test_example_goes_to_its_own_sub_lesson_not_the_lexical_twin(self):
        c, a = multi_cards()
        p = plan_lesson(c, a)
        by_idea = {s['idea_id']: s['source_refs'][0]['id'] for s in p['segments'] if s['type'] == 'worked_example'}
        self.assertEqual('ex_l1_frame_9', by_idea['exp_l1_frame'])
        self.assertEqual('ex_l2_frame', by_idea['exp_l2_next'])

    def test_idea_without_example_gets_none_and_is_noted_not_given_a_borrowed_one(self):
        c, a = multi_cards()
        c['explanations'].append({'id': 'exp_l3_lonely', 'title': 'L3 Lonely idea', 'text': 'Nothing pairs with this.'})
        p = plan_lesson(c, a)
        used = [s['source_refs'][0]['id'] for s in p['segments'] if s['type'] == 'worked_example']
        self.assertEqual(sorted(set(used)), sorted(used), 'no example may be repeated')
        self.assertIn('exp_l3_lonely', p['review_notes']['ideas_without_example'])

    def test_worked_example_label_is_not_spoken(self):
        c, a = multi_cards()
        p = plan_lesson(c, a)
        for s in p['segments']:
            if s['type'] == 'worked_example':
                self.assertNotRegex(s['content'], r'^L\d')

    def test_title_is_not_repeated_when_the_example_already_starts_with_it(self):
        c, a = multi_cards()
        c['examples'][1] = {'id': 'ex_l1_frame_9', 'title': 'L1 2 tens 8 is 28', 'text': '2 tens 8 is 28. 20 plus 8 equals 28.'}
        p = plan_lesson(c, a)
        ex = next(s for s in p['segments'] if s['source_refs'][0]['id'] == 'ex_l1_frame_9')
        self.assertEqual('2 tens 8 is 28. 20 plus 8 equals 28.', ex['content'])

    def test_symbols_in_source_text_become_spoken_words(self):
        c, a = cards()
        c['examples'][0]['text'] = 'Work it out: 12 - 3 = 9.'
        p = plan_lesson(c, a)
        ex = next(s for s in p['segments'] if s['type'] == 'worked_example')
        self.assertIn('12 minus 3 equals 9', ex['content'])
        self.assertNotIn('=', ex['content'])

    def test_your_turn_is_built_from_the_card_and_asks_a_question(self):
        c, a = multi_cards()
        p = plan_lesson(c, a)
        turns = [s for s in p['segments'] if s.get('phase') == 'your_turn']
        self.assertEqual(2, len(turns))
        self.assertIn('?', turns[0]['content'])
        self.assertIn('Ten-frame: 9 and 1 make 10', turns[0]['content'])
        self.assertNotIn('L1', turns[0]['content'])
        self.assertNotEqual(turns[0]['content'], turns[1]['content'])

    def test_rewrite_flag_marks_only_teaching_segments(self):
        c, a = cards()
        off = plan_lesson(c, a)
        self.assertFalse(any(s.get('rewrite') for s in off['segments']))
        on = plan_lesson(c, a, rewrite=True)
        kinds = {s['type'] for s in on['segments'] if s.get('rewrite')}
        self.assertEqual({'hook', 'lecture', 'worked_example', 'watch_out', 'recap'}, kinds)
        for s in on['segments']:
            if s['type'] in ('question', 'branch', 'transition'):
                self.assertFalse(s.get('rewrite'), s['id'])
        self.assertEqual([], check_coverage(on, on['segments']) and [e for e in check_coverage(on, on['segments']) if 'uncovered' in e])


class VarietyTests(unittest.TestCase):
    def setUp(self):
        c, a = cards()
        self.plan = plan_lesson(c, a)
        self.seg = next(s for s in self.plan['segments'] if s['type'] == 'lecture')

    def test_third_identical_framing_is_rejected(self):
        history = {'framings': Counter({'let us look closely': 2}), 'openers': Counter()}
        self.assertIn('repeated_framing', check_segment(self.seg, "Let us look closely. <CONTENT>", 4, history))
        history['framings']['let us look closely'] = 1
        self.assertNotIn('repeated_framing', check_segment(self.seg, "Let us look closely. <CONTENT>", 4, history))

    def test_opener_used_three_times_is_rejected(self):
        history = {'framings': Counter(), 'openers': Counter({"let's follow this": 3})}
        self.assertIn('repeated_opener', check_segment(self.seg, "Let's follow this path. <CONTENT>", 4, history))
        history['openers'][("let's follow this")] = 2
        self.assertNotIn('repeated_opener', check_segment(self.seg, "Let's follow this path. <CONTENT>", 4, history))

    def test_framing_must_not_echo_an_invitation_the_card_line_already_makes(self):
        seg = {'type': 'branch', 'phase': 'feedback', 'outcome': 'incorrect', 'content': 'Let us check this together, one step at a time.', 'metaphor': 'builders'}
        self.assertIn('echoes_source', check_segment(seg, "You can try again. Let's think together. <CONTENT>", 4))
        self.assertNotIn('echoes_source', check_segment(seg, "You can try again. <CONTENT>", 4))

    def test_your_turn_needs_no_question_in_framing_when_the_card_line_asks_one(self):
        seg = {'type': 'transition', 'phase': 'your_turn', 'content': 'Can you say it in your own words?', 'metaphor': 'builders'}
        self.assertNotIn('your_turn_question', check_segment(seg, "You can take your time. <CONTENT>", 4))
        seg['content'] = 'Say it.'
        self.assertIn('your_turn_question', check_segment(seg, "You can take your time. <CONTENT>", 4))

    def test_fake_model_replies_vary_so_full_lessons_pass_the_variety_rules(self):
        c, a = multi_cards()
        out = generate_lesson(plan_lesson(c, a), FakeModel())
        self.assertEqual(0, out['validation']['final_rule_violations'], [(s['id'], s['errors']) for s in out['segments'] if s['errors']])


SRC = 'The ten-frame has 9 dots and 1 empty spot. 9 plus 1 equals 10. 10 minus 1 equals 9.'
GOOD = "Look at your ten-frame, explorer. It has 9 dots and 1 empty spot. 9 plus 1 equals 10. And 10 minus 1 equals 9. 🧭"


def rewrite_segment(content=SRC, typ='worked_example', metaphor='explorers'):
    return {'id': 's_0001', 'type': typ, 'phase': 'main', 'content': content, 'metaphor': metaphor, 'rewrite': True}


class RewriteCheckTests(unittest.TestCase):
    def test_good_rewrite_passes(self):
        self.assertEqual([], check_rewrite(rewrite_segment(), GOOD, 2))

    def test_each_rule_has_a_break(self):
        seg = rewrite_segment()
        cases = {
            'rewrite_invented_number': GOOD.replace('9 dots', '9 dots and 7 stars'),
            'rewrite_dropped_number': "Look at your ten-frame, explorer. It has 9 dots.",
            'rewrite_changed_equation': GOOD.replace('9 plus 1 equals 10', '9 plus 1 equals 11'),
            'rewrite_lost_terms': "You are doing so well, explorer. There are 9 and 1 and 10 here. 9 plus 1 equals 10. 10 minus 1 equals 9.",
            'rewrite_too_long': GOOD + ' ' + 'You can keep looking and thinking about it. ' * 12,
            'direct_address': "The ten-frame has 9 dots and 1 empty spot. 9 plus 1 equals 10. 10 minus 1 equals 9.",
            'non_spoken_symbols': GOOD.replace('9 plus 1 equals 10', '9 + 1 = 10'),
            'emoji_in_maths': GOOD.replace('9 plus 1 equals 10.', '9 plus 1 equals 10 🧭.'),
            'discouraging_tone': GOOD + ' Do not be stupid.',
            'actual_image_reference': GOOD + ' Look at the image above.',
            'mixed_metaphor': GOOD.replace('explorer', 'detective'),
            'non_spoken_output': '```' + GOOD,
            'content_marker_left': GOOD + ' <CONTENT>',
            'sentence_length': GOOD + ' You can look very carefully at every single dot in your ten-frame and count them one by one slowly.',
        }
        for code, text in cases.items():
            self.assertIn(code, check_rewrite(seg, text, 2), code)

    def test_number_words_and_digits_are_the_same_number(self):
        seg = rewrite_segment('Add 20 and 5 to get 25. Then 10 plus 2 equals 12.')
        ok = "You can add twenty and five to get twenty-five. Then 10 plus 2 equals 12."
        self.assertNotIn('rewrite_invented_number', check_rewrite(seg, ok, 4))
        self.assertNotIn('rewrite_dropped_number', check_rewrite(seg, ok, 4))

    def test_number_words_inside_an_equation_match_the_digits(self):
        seg=rewrite_segment('13 is ten 3. So 10 plus 3 equals 13.')
        self.assertNotIn('rewrite_changed_equation',check_rewrite(seg,'You can see 13 is ten 3. So ten plus 3 equals 13.',2))
        self.assertIn('rewrite_changed_equation',check_rewrite(seg,'You can see 13 is ten 3. So ten plus 4 equals 13.',2))

    def test_we_and_our_count_as_speaking_to_the_student_in_a_rewrite(self):
        seg=rewrite_segment('Use a ten to add.')
        self.assertNotIn('direct_address',check_rewrite(seg,'Today we use a ten to add, explorer.',2))
        self.assertIn('direct_address',check_rewrite(seg,'A ten is used to add.',2))

    def test_the_word_one_is_not_treated_as_a_number(self):
        seg = rewrite_segment('One part is 5. The other part is 5. 5 plus 5 equals 10.')
        text = "You can see one part is 5. The other part is 5 too. 5 plus 5 equals 10."
        self.assertEqual([], check_rewrite(seg, text, 2))

    def test_a_rewrite_that_just_pastes_the_card_sentences_is_rejected(self):
        src='A ten-frame has 10 spots. Here 9 spots are full. Only 1 spot is empty. 9 plus 1 equals 10.'
        pasted='You can look, explorer. A ten-frame has 10 spots. Here 9 spots are full. Only 1 spot is empty. 9 plus 1 equals 10.'
        fresh='Explorer, picture a ten-frame with 10 spots. You can see 9 of them are full. Just 1 spot is left empty. So 9 plus 1 equals 10.'
        self.assertIn('rewrite_copied_source',check_rewrite(rewrite_segment(src),pasted,2))
        self.assertNotIn('rewrite_copied_source',check_rewrite(rewrite_segment(src),fresh,2))

    def test_equation_sentences_may_stay_verbatim_and_short_sources_may_be_kept(self):
        self.assertNotIn('rewrite_copied_source',check_rewrite(rewrite_segment(),GOOD,2))
        self.assertNotIn('rewrite_copied_source',check_rewrite(rewrite_segment('Make a ten to add.'),'You can make a ten to add, explorer.',2))

    def test_a_rewrite_that_drops_most_of_the_passage_is_too_short(self):
        self.assertIn('rewrite_too_short',check_rewrite(rewrite_segment(),"You can look at it.",2))

    def test_more_than_two_emojis_in_a_rewrite_is_too_many(self):
        text="Look at your ten-frame, explorer 🧭! Are you ready 🌟? It has 9 dots and 1 empty spot. 9 plus 1 equals 10. 10 minus 1 equals 9. Great job 🎉!"
        self.assertIn('emoji_count',check_rewrite(rewrite_segment(),text,2))
        self.assertNotIn('emoji_in_maths',check_rewrite(rewrite_segment(),text,2))

    def test_pronoun_one_may_be_dropped_without_dropping_a_number(self):
        seg=rewrite_segment('Pick one side. 3 plus 4 equals 7.')
        self.assertNotIn('rewrite_dropped_number',check_rewrite(seg,'You can pick a side. 3 plus 4 equals 7.',2))

    def test_repeated_opener_is_checked_for_rewrites_too(self):
        history = {'framings': Counter(), 'openers': Counter({'look at your': 3})}
        self.assertIn('repeated_opener', check_rewrite(rewrite_segment(), GOOD, 2, history))

    def test_gold_rewrites_pass_their_own_checks(self):
        data = json.loads((Path(__file__).parents[1] / 'script_agent/gold_rewrites.json').read_text())
        self.assertGreaterEqual(len(data), 3)
        self.assertEqual({1, 2, 4}, {d['grade'] for d in data})
        for d in data:
            seg = rewrite_segment(d['source'], d['type'], d['metaphor'])
            self.assertEqual([], check_rewrite(seg, d['spoken'], d['grade']), d['spoken'])


class RewriteGenerationTests(unittest.TestCase):
    def setUp(self):
        self.c, self.a = cards()
        self.plan = plan_lesson(self.c, self.a, rewrite=True)
        self.ex = next(s for s in self.plan['segments'] if s['type'] == 'worked_example')
        self.src = self.ex['content']

    def good(self):
        return 'You can multiply 3 by 4, detective. The area is 12 square units.'

    def run_with(self, replies_for_example):
        """FakeModel: scripted replies for the worked example, canned varied replies for the rest."""
        class Scripted(FakeModel):
            def generate(inner, request):
                if request['segment']['id'] == self.ex['id'] and replies_for_example:
                    inner.calls.append(request)
                    return replies_for_example.pop(0)
                return super().generate(request)
        return generate_lesson(self.plan, Scripted())

    def seg(self, out):
        return next(s for s in out['segments'] if s['id'] == self.ex['id'])

    def test_good_rewrite_is_used_and_verified(self):
        out = self.run_with([self.good()])
        s = self.seg(out)
        self.assertEqual('rewritten', s['rewrite_mode'])
        self.assertEqual(self.good(), s['text'])
        self.assertEqual(self.src, s['content'])
        self.assertEqual([], check_coverage(self.plan, out['segments']))

    def test_bad_then_good_uses_the_repair(self):
        out = self.run_with(['You can multiply 3 by 5. The area is 15 square units.', self.good()])
        s = self.seg(out)
        self.assertEqual('rewritten', s['rewrite_mode'])
        self.assertEqual(2, s['attempts'])

    def test_two_bad_rewrites_fall_back_to_framing_around_the_card_text_visibly(self):
        bad = 'You can multiply 3 by 5. The area is 15 square units.'
        out = self.run_with([bad, bad])
        s = self.seg(out)
        self.assertEqual('fallback_framed', s['rewrite_mode'])
        self.assertTrue(s['text'].endswith(self.src))
        self.assertGreater(len(s['text']), len(self.src))
        self.assertIn('rewrite_invented_number', s['rewrite_errors'])
        self.assertIn(self.ex['id'], out['validation']['rewrite']['fallback_framed'])
        self.assertEqual([], check_coverage(self.plan, out['segments']))

    def test_if_the_framing_also_fails_the_bare_card_text_is_used_and_reported(self):
        bad = 'You can multiply 3 by 5. The area is 15 square units.'
        out = self.run_with([bad, bad, 'There is no marker in this reply.'])
        s = self.seg(out)
        self.assertEqual('fallback_verbatim', s['rewrite_mode'])
        self.assertEqual(self.src, s['text'])
        self.assertIn(self.ex['id'], out['validation']['rewrite']['fallback_verbatim'])
        self.assertEqual([], check_coverage(self.plan, out['segments']))

    def test_framed_fallback_replays_from_the_checkpoint_without_new_calls(self):
        bad = 'You can multiply 3 by 5. The area is 15 square units.'
        out = self.run_with([bad, bad])
        cache = {s['id']: {'template': s['template'], 'attempts_log': s['attempts_log']} for s in out['segments']}
        m = FakeModel()
        again = generate_lesson(self.plan, m, cache=cache)
        self.assertEqual(0, len(m.calls))
        self.assertEqual('fallback_framed', self.seg(again)['rewrite_mode'])
        self.assertEqual(self.seg(out)['text'], self.seg(again)['text'])

    def test_changed_fallback_text_is_caught_by_the_coverage_audit(self):
        bad='You can multiply 3 by 5. The area is 15 square units.'
        out=self.run_with([bad,bad,'There is no marker in this reply.']);segs=copy.deepcopy(out['segments'])
        next(s for s in segs if s['id']==self.ex['id'])['text']='Multiply 3 by 4. The area is 13 square units.'
        self.assertTrue(check_coverage(self.plan,segs))

    def test_provider_failure_is_a_flagged_error_not_a_silent_fallback(self):
        class Boom(FakeModel):
            def generate(inner, request):
                if request['segment']['id'] == self.ex['id']:
                    raise OSError('down')
                return super().generate(request)
        out = generate_lesson(self.plan, Boom())
        s = self.seg(out)
        self.assertEqual('flagged', s['status'])
        self.assertIn('model_call_failed', s['errors'])

    def test_tampered_rewrite_is_caught_by_the_coverage_audit(self):
        out = self.run_with([self.good()])
        segs = copy.deepcopy(out['segments'])
        next(s for s in segs if s['id'] == self.ex['id'])['text'] = 'You can multiply 3 by 4, detective. The area is 13 square units.'
        self.assertTrue(check_coverage(self.plan, segs))

    def test_rewrite_request_shows_source_and_demands_the_numbers_back(self):
        from script_agent.generator import rewrite_request
        r = rewrite_request(self.plan, self.ex)
        p = json.loads(r['prompt'])
        self.assertIn(self.src, p['source_text'])
        self.assertIn('3', p['must_keep_numbers'])
        self.assertGreaterEqual(r['max_tokens'], 200)
        self.assertTrue(p['style_examples'])

    def test_checkpoint_cache_replays_rewrites_without_new_calls(self):
        out = self.run_with([self.good()])
        cache = {s['id']: {'template': s['template'], 'attempts_log': s['attempts_log']} for s in out['segments']}
        m = FakeModel()
        again = generate_lesson(self.plan, m, cache=cache)
        self.assertEqual(0, len(m.calls))
        self.assertEqual(self.good(), self.seg(again)['text'])

    def test_rewrite_off_leaves_the_original_template_path_untouched(self):
        c, a = cards()
        plain = plan_lesson(c, a)
        out = generate_lesson(plain, FakeModel())
        self.assertTrue(all(s.get('rewrite_mode') is None for s in out['segments']))
        self.assertIsNone(out['validation'].get('rewrite', {}).get('enabled') or None)


class PromptVarietyTests(unittest.TestCase):
    def test_request_suggests_openers_and_lists_recent_ones(self):
        from script_agent.generator import request_for
        c, a = cards()
        p = plan_lesson(c, a)
        r = request_for(p, p['segments'][1], recent_openers=["let's follow this", 'look at the'])
        body = json.loads(r['prompt'])
        self.assertTrue(body['suggested_openers'])
        self.assertNotIn("let's follow this", [o.lower() for o in body['suggested_openers']])

    def test_request_warns_when_the_card_line_already_invites(self):
        from script_agent.generator import request_for
        c, a = cards()
        p = plan_lesson(c, a)
        seg = {'id': 's_9', 'type': 'branch', 'phase': 'feedback', 'outcome': 'incorrect', 'content': 'Let us check this together.', 'metaphor': 'builders'}
        body = json.loads(request_for(p, seg)['prompt'])
        self.assertTrue(body['card_line_already_invites'])
        self.assertNotIn('Let us check this together.', request_for(p, seg)['prompt'])


if __name__ == '__main__':
    unittest.main()
