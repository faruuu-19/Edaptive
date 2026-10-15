import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_lesson_demo", ROOT / "tools/run_lesson_demo.py")
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


class PlanTests(unittest.TestCase):
    def plan(self, **changes):
        options = dict(root=ROOT, python="/py/python", npm="/node/npm", voice_port=8766, web_port=3001,
                       script=None, audio_dir=None)
        options.update(changes)
        return demo.build_plan(**options)

    def test_the_voice_stand_in_runs_from_the_repository_root(self):
        voice = self.plan()["voice"]
        self.assertEqual(voice["args"][:3], ["/py/python", "-m", "voice_service.demo_server"])
        self.assertEqual(voice["cwd"], ROOT)
        self.assertIn("--port", voice["args"])
        self.assertEqual(voice["args"][voice["args"].index("--port") + 1], "8766")
        self.assertNotIn("--audio-dir", voice["args"])
        self.assertNotIn("--script", voice["args"])

    def test_the_frontend_gets_the_demo_switches_and_only_loopback_addresses(self):
        web = self.plan(voice_port=9000, web_port=3005)["web"]
        self.assertEqual(web["args"], ["/node/npm", "run", "dev", "--", "--hostname", "127.0.0.1", "--port", "3005"])
        self.assertEqual(web["cwd"], ROOT / "frontend")
        env = web["env"]
        self.assertEqual(env["EDAPTIVE_VOICE_PREVIEW"], "1")
        self.assertEqual(env["EDAPTIVE_DEMO_JOB_ID"], "0de30de3-0de3-4de3-8de3-0de30de30de3")
        self.assertEqual(env["EDAPTIVE_VOICE_URL"], "http://127.0.0.1:9000")
        self.assertEqual(env["NEXT_TELEMETRY_DISABLED"], "1")

    def test_the_job_id_matches_the_demo_server(self):
        from voice_service.demo_server import DEMO_JOB_ID
        self.assertEqual(self.plan()["web"]["env"]["EDAPTIVE_DEMO_JOB_ID"], DEMO_JOB_ID)

    def test_script_and_recording_are_passed_through_as_absolute_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.plan(script=Path(tmp) / "a.json", audio_dir=Path(tmp) / "audio")["voice"]["args"]
        self.assertEqual(args[args.index("--script") + 1], str(Path(tmp) / "a.json"))
        self.assertEqual(args[args.index("--audio-dir") + 1], str(Path(tmp) / "audio"))


class PreflightTests(unittest.TestCase):
    def test_missing_dependencies_are_explained_in_plain_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            problems = demo.preflight(Path(tmp), npm=None, script=None, audio_dir=None)
        text = " ".join(problems)
        self.assertIn("Node.js", text)
        self.assertIn("npm install", text)

    def test_a_ready_checkout_has_no_problems(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "frontend/node_modules").mkdir(parents=True)
            (root / "examples/lessons").mkdir(parents=True)
            (root / "examples/lessons/grade2-module1-lesson1.script.json").write_text("{}")
            self.assertEqual(demo.preflight(root, npm="/node/npm", script=None, audio_dir=None), [])

    def test_a_missing_recording_folder_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "frontend/node_modules").mkdir(parents=True)
            (root / "examples/lessons").mkdir(parents=True)
            (root / "examples/lessons/grade2-module1-lesson1.script.json").write_text("{}")
            problems = demo.preflight(root, npm="/node/npm", script=None, audio_dir=root / "nope")
        self.assertEqual(len(problems), 1)
        self.assertIn("recording", problems[0])


if __name__ == "__main__":
    unittest.main()
