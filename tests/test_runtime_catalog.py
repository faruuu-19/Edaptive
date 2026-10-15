import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from voice_service.catalog import content_path, load_catalog

ROOT = Path(__file__).resolve().parents[1]


class RuntimeCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        original = json.loads((ROOT / "docs/content/lesson-pairs.json").read_text())
        self.manifest = {**original, "pairs": [copy.deepcopy(original["pairs"][0])]}
        for kind in ("concept", "assessment"):
            relative = self.manifest["pairs"][0][kind]
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        (self.root / "docs/content").mkdir(parents=True)
        self.write_manifest()

    def write_manifest(self):
        (self.root / "docs/content/lesson-pairs.json").write_text(json.dumps(self.manifest))

    def test_catalog_survives_relocation_without_the_downloads_workspace(self):
        row, = load_catalog(self.root)
        self.assertTrue(Path(row["concept"]).is_relative_to(self.root.resolve()))
        self.assertTrue(row["plan_passed"])
        self.assertFalse(row["ready_for_delivery"])

    def test_absolute_and_parent_paths_are_rejected(self):
        for value in ("/private/file.json", "../outside.json"):
            with self.assertRaises(ValueError):
                content_path(self.root, value)

    def test_changed_content_is_rejected_before_planning(self):
        path = self.root / self.manifest["pairs"][0]["assessment"]
        path.write_text(path.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            load_catalog(self.root)

    def test_wrong_link_is_rejected_even_with_an_updated_file_hash(self):
        item = self.manifest["pairs"][0]
        path = self.root / item["assessment"]
        body = json.loads(path.read_text())
        body["linked_concept"]["concept_version"] += 1
        path.write_text(json.dumps(body))
        item["assessment_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.write_manifest()
        with self.assertRaises(ValueError):
            load_catalog(self.root)

    def test_duplicate_and_missing_pairs_are_not_silently_skipped(self):
        self.manifest["pairs"] *= 2
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            load_catalog(self.root)
        self.manifest["pairs"] = self.manifest["pairs"][:1]
        self.write_manifest()
        (self.root / self.manifest["pairs"][0]["concept"]).unlink()
        with self.assertRaises(FileNotFoundError):
            load_catalog(self.root)

    def test_all_published_pairs_and_the_new_module7_lessons_are_present(self):
        rows = load_catalog(ROOT)
        self.assertEqual(93, len(rows))
        self.assertEqual(91, sum(row["origin"] == "published_assessment_branch" for row in rows))
        module = [row for row in rows if row["grade"] == 2 and row["module"] == 7]
        self.assertEqual(set(range(1, 27)), {row["lesson"] for row in module})
        self.assertTrue(all(not row["ready_for_delivery"] for row in rows))


if __name__ == "__main__":
    unittest.main()
