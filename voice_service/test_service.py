import base64
import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from .service import handler_for, load_lesson


class FakeNarrator:
    def __init__(self):
        self.lock = threading.Lock()
        self.calls = []

    def frames(self, segment, voice):
        self.calls.append((segment['id'], voice))
        yield {'type': 'start', 'segment_id': segment['id']}
        yield {'type': 'audio', 'utterance': 0, 'caption': 'Fourteen is not forty.',
               'sample_rate': 24000, 'pcm_s16le': base64.b64encode(b'\0\0' * 240).decode()}
        yield {'type': 'done', 'segment_id': segment['id']}


class LessonTests(unittest.TestCase):
    def fixture(self, **changes):
        script = {'schema_version': 'script-0.1', 'validation': {'passed': True},
                  'concept_id': 'math_g2_m1_l1_pairs_to_ten', 'grade': 2, 'subject': 'math',
                  'delivery_policy': {'main_path': ['s1']},
                  'segments': [{'id': 's1', 'type': 'lecture', 'phase': 'main',
                                'text': 'Look here: 14 is ten and 4 ones.',
                                'visual_cue': '[show: Four ones next to ten.]'},
                               {'id': 'secret', 'type': 'answer_reveal', 'phase': 'conditional',
                                'text': 'The answer is 14.'}]}
        script.update(changes)
        return script

    def load(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'script.json'; p.write_text(json.dumps(data))
            return load_lesson(p)

    def test_only_main_path_is_exposed_and_visual_directions_are_not_spoken(self):
        lesson = self.load(self.fixture())
        self.assertEqual([s['id'] for s in lesson['segments']], ['s1'])
        s = lesson['segments'][0]
        self.assertNotIn('Look here', s['utterances'][0]['spoken'])
        self.assertIn('fourteen', s['utterances'][0]['spoken'])
        self.assertEqual(s['cues'], ['Look here', 'Four ones next to ten.'])
        self.assertFalse(lesson['ready_for_delivery'])

    def test_failed_script_checks_block_preview(self):
        with self.assertRaises(ValueError): self.load(self.fixture(validation={'passed': False}))

    def test_conditional_answer_cannot_be_promoted_to_main_path(self):
        with self.assertRaises(ValueError): self.load(self.fixture(delivery_policy={'main_path': ['secret']}))

    def test_duplicate_main_path_is_rejected(self):
        with self.assertRaises(ValueError): self.load(self.fixture(delivery_policy={'main_path': ['s1', 's1']}))


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.narrator = FakeNarrator()
        self.lesson = {'segments': [{'id': 's1', 'utterances': []}], 'preview_only': True}
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(self.lesson, self.narrator))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def post(self, data, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        connection.request('POST', '/narrate', json.dumps(data), headers or {'Content-Type': 'application/json'})
        response = connection.getresponse(); body = response.read(); connection.close()
        return response.status, body

    def test_no_arbitrary_text_or_conditional_answer_requests(self):
        for data in [{'text': 'anything', 'voice': 'af_heart'}, {'segment_id': 'secret', 'voice': 'af_heart'},
                     {'segment_id': 's1', 'voice': 'unknown'}]:
            self.assertEqual(self.post(data)[0], 400)
        self.assertEqual(self.narrator.calls, [])

    def test_stream_is_framed_and_busy_requests_are_rejected(self):
        request = {'segment_id': 's1', 'voice': 'af_heart'}
        self.narrator.lock.acquire()
        self.assertEqual(self.post(request)[0], 409)
        self.narrator.lock.release()
        status, body = self.post(request)
        self.assertEqual(status, 200)
        self.assertEqual([json.loads(line)['type'] for line in body.splitlines()], ['start', 'audio', 'done'])
        self.assertEqual(self.narrator.calls, [('s1', 'af_heart')])

    def test_remote_origin_cannot_request_speech(self):
        status, _ = self.post({'segment_id': 's1', 'voice': 'af_heart'}, {'Origin': 'https://example.com'})
        self.assertEqual(status, 403)


if __name__ == '__main__': unittest.main()
