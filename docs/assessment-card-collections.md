# Concept and assessment file pairing

Grade 2 Module 1 has eight standalone lesson pairs. Each concept is a single
object and its counterpart is a complete v0.2 assessment object with
`card_type: assessment_card`. Other covered sources retain collections with
`card_type: assessment_card_collection` until converted. Every source JSON
has one counterpart named `<source stem>.assessment_card.json` beside it.

For Module 1, select a lesson in the module's `lesson-wise/module_index.json`.
The index names the concept ID/version, both paths and their SHA-256 hashes.
Repository index paths are relative to the repository root. The downloadable
module ZIP has its own index whose paths are relative to the extracted folder.
Pass only the selected two objects to the script agent. The old combined pair
is in `legacy/module-wide` and is excluded from active indexes and packages.

## Reading either assessment format

```python
import hashlib
import json
from pathlib import Path

def load_pair(concept_path, assessment_path, expected_source_sha256=None):
    raw = Path(concept_path).read_bytes()
    if expected_source_sha256 is not None:
        assert hashlib.sha256(raw).hexdigest() == expected_source_sha256
    source = json.loads(raw)
    concepts = source if isinstance(source, list) else source.get("cards", [source])
    concept_by_id = {c["concept_id"]: c for c in concepts}
    assessment = json.loads(Path(assessment_path).read_text(encoding="utf-8"))
    if assessment["card_type"] == "assessment_card":
        assert len(concepts) == 1
        children = [assessment]
    else:
        assert assessment["card_type"] == "assessment_card_collection"
        assert assessment["linked_concept_file"]["file_name"] == Path(concept_path).name
        assert assessment["linked_concept_file"]["sha256"] == hashlib.sha256(raw).hexdigest()
        children = assessment["cards"]
    pairs = []
    for child in children:
        concept = concept_by_id[child["linked_concept"]["concept_id"]]
        assert concept["card_version"] == child["linked_concept"]["concept_version"]
        pairs.append((concept, child))
    return pairs
```

Collections have `schema_version`, `card_type`, `collection_id`, `review_status`,
`linked_concept_file`, `coverage` and `cards`. Their coverage includes the source
concept count, included assessment count, covered IDs and missing IDs. Partial
collections preserve source order, but consumers must match IDs rather than
zip arrays by position. Standalone assessments retain the exact lesson-level
v0.2 schema; hashes and coverage belong to the module index, not extra fields
added to the assessment.

Resolve `concept_card` references against the selected concept and `this_card`
references against the selected assessment. Keep attempts, hints and follow-up
state separate for each lesson. Local IDs can recur in other lessons.
The reference controller consumes one assessment object.

## Current coverage and verification

75 active entries are packaged in 19 matching files: eight standalone lesson
pairs and eleven collections. Grade 1 has six Lesson 1 entries. Grade 2 has
69 entries: Module 1 Lessons 1–8 individually, Module 3 its one included lesson,
Modules 5 and 6 Lessons 1–20 each, and Modules 7 and 8 Lessons 1–10 each.
The last two sources have 16 and 6 unassessed concepts. Twelve Grade 3/4 source
files have no assessments. Grade 2 Modules 2 and 4 have no provided sources.

67 earlier active entries are preserved exactly. The combined Module 1 entry
is archived unchanged and replaced with eight new entries; it is not counted
as an active lesson. Source/assessment names, hashes, scoped references, unique
IDs, coverage lists, archive preservation and package bytes were checked.
Module 1 extraction preserves 112 questions/rubrics; checks cover 96 numeric
keys/accept variants, one pair key, three text truths and 12 original open
rubrics. New assessment validation covers 96 equations and 192 routes.
Active cumulative totals are 713 equations, 1,820 routes and seven multipart
classification scenarios, excluding the archived assessment checks.

[Module 1 extraction validation](concept-cards-grade2-module1-lesson-wise-validation.json)
and [Module 1 assessment validation](assessment-cards-grade2-module1-lesson-wise-validation.json)
record the new evidence. [Pair mapping](assessment-card-collections-manifest.json)
records formats and paths; [current validation](assessment-card-collections-validation.json)
records active coverage and preservation. [Migration progress](grade2-lesson-file-migration.json)
tracks module-by-module file conversion separately from assessment coverage.

All entries are drafts and script-agent integration is untested. Objectives
and asset scopes are adapted from the combined JSON, without newly consulting
original lesson PDFs. Shared generic hints retain original provenance;
assessment grounds reference only the current lesson. Fixed ten/teen facts
can recur in new stories. Source open answers need semantic grading; source
`pair_of_parts` can use `valid_pairs`, while hard assessment keys use three
named parts. Earlier educational limits remain documented in previous reports
and the root README.
