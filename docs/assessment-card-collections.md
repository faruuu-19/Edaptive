# Concept and assessment file pairing

Grade 2 Modules 1 and 5 have eight and twenty standalone lesson pairs.
Module 3 has its available Lesson 1 pair standalone; Lessons 2–21 lack supplied
concept sources. Each concept is a single object and its matching full
assessment has `card_type: assessment_card`. Other covered sources retain
collections with `card_type: assessment_card_collection`. Every active source
JSON has one counterpart named `<source stem>.assessment_card.json` beside it.

Select the lesson in its module's `lesson-wise/module_index.json`. The index
names linked concept ID/version, both paths and their SHA-256 hashes. Repository
paths are relative to the repository root; downloadable module ZIP indexes use
paths relative to their extracted folder. Pass only the selected two objects
to the script agent. Original combined files are preserved under
`legacy/module-wide/` and excluded from active indexes and packages.
Module 3's index lists all twenty missing source/assessment lessons.

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

75 active entries are packaged in 38 matching files: 29 standalone lesson
pairs and nine collections. Grade 1 has six Lesson 1 entries. Grade 2 has
69 entries: Module 1 Lessons 1–8 individually, Module 3 Lesson 1 individually,
Module 5 Lessons 1–20 individually, Module 6 Lessons 1–20 in a collection, and
Modules 7 and 8 Lessons 1–10 in collections. Modules 7/8 have 16/6 pending
assessments. Module 3 expects 21 lessons but includes one source concept.
Twelve Grade 3/4 source files have no assessments. Grade 2 Modules 2/4 have no
provided source files.

All 75 earlier active entries are preserved exactly. The original Module 3/5
collections are archived byte-for-byte and their unchanged lesson assessments
remain active. Module 1's old mixed entry is retired and excluded. Matching
formats, names, scoped references, source/index hashes, unique IDs, pending
lists, archive preservation and ZIP bytes were checked. Conversion validation
independently rechecks all numeric answers/accept variants, 308 equations and
504 tutoring routes for the 21 converted pairs. Repeat checks are not counted
again in cumulative totals, which remain 713 equations, 1,820 routes and seven
multipart classification scenarios.

[Module 3/5 conversion validation](assessment-cards-grade2-modules3-5-lesson-wise-validation.json)
records current conversion evidence. [Pair mapping](assessment-card-collections-manifest.json)
records active paths/formats and archive mapping; [current validation](assessment-card-collections-validation.json)
records coverage and package preservation. [Migration progress](grade2-lesson-file-migration.json)
tracks module conversion separately from assessment coverage. Historical
Module 1 extraction/assessment reports retain their original evidence.

All entries remain drafts; human educational review and actual script-agent
integration remain outstanding. Source review flags and limitations are
preserved. Module 5 Lesson 11 source exp_1 gives 10 for a tens total that is 11
including the new ten; its assessment uses correct arithmetic. Numeric answers
do not verify actual drawings, folds, graphs or chosen coin combinations.
Source open questions need semantic grading. Source `pair_of_parts` keys can
use `valid_pairs`; hard assessment keys use three named parts. Read the actual
answer-key shape. Original concept IDs and versions are unchanged in the
Module 3/5 standalone files.
