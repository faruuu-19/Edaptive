# One assessment JSON per concept JSON

There are 48 lesson assessment entries in 10 matching assessment JSON files.
Each covered source concept JSON has one counterpart, including sources that
contain many lessons. Grade 2 Modules 5 and 6 now each cover Lessons 1–20. All ten covered source
files have complete assessment collections.

## Naming and root shape

`math_g2_m6_Lessons.json` pairs with
`math_g2_m6_Lessons.assessment_card.json` in the same folder. The spelling and
case of the source stem are retained. Every output uses this root structure,
including sources with only one concept card:

```json
{
  "schema_version": "0.2-draft",
  "card_type": "assessment_card_collection",
  "collection_id": "<source stem>_assessment_collection",
  "review_status": "draft",
  "linked_concept_file": {
    "file_name": "<source filename>.json",
    "sha256": "<SHA-256 of the source file bytes>"
  },
  "coverage": {
    "status": "complete or partial",
    "concept_cards_in_source": 20,
    "assessment_cards_included": 10,
    "assessed_concept_ids": ["<covered concept IDs, in source order>"],
    "missing_concept_ids": ["<unassessed concept IDs, in source order>"]
  },
  "cards": ["<full lesson assessment objects>"]
}
```

The example shows the shape; `cards` contains objects, not strings. Each child
has `card_type: assessment_card` and the unchanged complete v0.2 lesson schema,
including hints and tutor guidance. `card_type` distinguishes the collection
container from a lesson assessment. A file's complete coverage is separate from
its draft review status and delivery readiness.

## Loading the two script-agent inputs

Source JSON files have three shapes: a single concept object, an array of
concepts, or an object with a `cards` array. Normalize the source, then look up
concept IDs. Never zip the two arrays by position: partial coverage is explicit
and an assessment's matching concept may occur later in the source array.

```python
import hashlib
import json
from pathlib import Path

concept_path = Path("math_g2_m6_Lessons.json")
assessment_path = concept_path.with_name(
    concept_path.stem + ".assessment_card.json"
)
source_bytes = concept_path.read_bytes()
source = json.loads(source_bytes.decode("utf-8"))
collection = json.loads(assessment_path.read_text(encoding="utf-8"))
assert collection["card_type"] == "assessment_card_collection"
assert collection["linked_concept_file"]["file_name"] == concept_path.name
assert collection["linked_concept_file"]["sha256"] == hashlib.sha256(source_bytes).hexdigest()

concepts = source if isinstance(source, list) else source.get("cards", [source])
concept_by_id = {concept["concept_id"]: concept for concept in concepts}
for assessment in collection["cards"]:
    concept = concept_by_id[assessment["linked_concept"]["concept_id"]]
    assert concept["card_version"] == assessment["linked_concept"]["concept_version"]
    # Give this matched concept object and assessment object to the script agent.
```

Resolve `concept_card` references against that matched concept only, and
`this_card` references against that child assessment only. For example,
`aq_med_01` and `h_aq_med_01_1` may occur in many children; they are distinct
because they belong to different linked concepts. Keep attempt, hint, and
follow-up state separate for each assessment. The reference controller expects
one child assessment object, not the collection wrapper.

## Coverage and verification

Six Grade 1 source files contain six assessments. Six Grade 2 source files
contain 62 assessments: Module 1 one combined concept, Module 3 its one included
concept, Module 5 Lessons 1–20, Module 6 Lessons 1–20, and Modules 7 and 8 Lessons
1–10 each. Ten collections are complete for included source concepts. Module 7
is partial at 10 of 26 concepts; Module 8 is partial at 10 of 16. They list 22
missing IDs in all. Twelve other source lesson files have no assessments.

All 68 entries match validated build inputs; the previous 58 are preserved
exactly. Names, source hashes and order, scoped references, unique IDs, coverage
status, missing IDs and ZIP byte equality were checked. The ten new Module 8
entries have independently checked geometry, counts, rational shares and every
accept variant. Numeric choice-key meanings, cube attributes, triangle
composition and square/rhombus classification were checked. There are 28 new
worked-equation checks and 240 route scenarios. Cumulative evidence covers
627 equations, 1,652 routes and seven multipart classification scenarios.

Every child is a draft and script-agent integration is untested. Numeric
choices cannot verify spoken vocabulary or actual drawings, folds and joins.
The [Module 8 validation](assessment-cards-grade2-module8-lessons1-10-validation.json)
records educational limits and source review blockers for Lessons 3 and 5.
Previous reports retain money, open-answer grading and drawing limitations,
and the Module 5 source arithmetic discrepancy.

[Pair mapping](assessment-card-collections-manifest.json) lists source and
assessment paths. [Collection validation](assessment-card-collections-validation.json)
records per-pair results. The root README lists the curriculum hierarchy.
