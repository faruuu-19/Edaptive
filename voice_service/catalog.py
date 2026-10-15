"""Load hash-checked lesson pairs using repository-relative paths only."""

import hashlib
import json
from pathlib import Path

from script_agent import plan_lesson
from script_agent.sample_inputs import load_card


def content_path(root, value):
    if not isinstance(value, str) or Path(value).is_absolute():
        raise ValueError("Content paths must be relative to the configured content root.")
    root = Path(root).resolve()
    path = (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise ValueError("Content path escapes the configured content root.") from None
    return path


def load_catalog(root):
    root = Path(root).resolve()
    manifest = json.loads((root / "docs/content/lesson-pairs.json").read_text())
    if manifest.get("format") != "edaptive-lesson-pairs-v1":
        raise ValueError("Unsupported lesson-pair manifest.")
    catalog = []
    concepts, assessments = set(), set()
    for item in manifest["pairs"]:
        if item["concept_id"] in concepts or item["assessment_id"] in assessments:
            raise ValueError("Duplicate concept or assessment in the lesson catalog.")
        concepts.add(item["concept_id"])
        assessments.add(item["assessment_id"])
        paths = {}
        for kind in ("concept", "assessment"):
            path = content_path(root, item[kind])
            if hashlib.sha256(path.read_bytes()).hexdigest() != item[kind + "_sha256"]:
                raise ValueError("Content hash mismatch for " + item["concept_id"])
            paths[kind] = path
        concept = load_card(paths["concept"], item["concept_id"])
        assessment = load_card(paths["assessment"], item["assessment_id"], True)
        plan = plan_lesson(concept, assessment, "detectives", rewrite=True)
        if (concept["grade"] != item["grade"]
                or concept["card_version"] != item["concept_version"]):
            raise ValueError("Catalog grade or version does not match its concept.")
        reviewed = {"reviewed", "approved"}
        catalog.append({
            **item,
            "concept": str(paths["concept"]),
            "assessment": str(paths["assessment"]),
            "linked_version": assessment["linked_concept"]["concept_version"],
            "review_status": concept.get("review_status"),
            "assessment_review_status": assessment.get("review_status"),
            "ready_for_delivery": bool(
                assessment.get("readiness", {}).get("ready_for_delivery")
                and concept.get("review_status") in reviewed
                and assessment.get("review_status") in reviewed),
            "plan_passed": True,
            "plan_segments": len(plan["segments"]),
            "main_segments": len(plan["delivery_policy"]["main_path"]),
        })
    return catalog
