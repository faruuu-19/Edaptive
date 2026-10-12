# Concept and assessment file pairing

Grade 2 Modules 1, 5 and 6 have eight, twenty and twenty standalone lesson pairs.
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

75 active assessments have 57 matching files: 49 standalone lesson pairs and
eight collections. Grade 2 Modules 1, 5 and 6 are converted for all included
lessons. Module 3 has only its available Lesson 1 converted; Lessons 2–21 remain
pending due to missing concepts. Modules 7/8 contain ten assessments each in
partial collections, with 16/6 pending. Grade 1 has six Lesson 1 entries in six
collections. Grade 2 Modules 2/4 have no provided source files. Twelve Grade
3/4 source files have no assessments.

Active totals remain 225 main questions, 150 follow-ups, 300 local rubrics,
1,125 hints and 375 guidance records. All 75 earlier active entries are
preserved. Original Module 3/5/6 collection bytes are archived. Module 1's old
mixed assessment is retired and excluded.

[Module 6 conversion validation](assessment-cards-grade2-module6-lesson-wise-validation.json)
records twenty unchanged standalone pairs and 700 preserved concept questions
and rubrics. Numeric/parity answers and accept variants, 150 worked equations
and 506 tutoring routes were independently rechecked. Scoped references, full
guidance, index hashes, archive bytes and portable package bytes also passed.
This conversion creates no new assessment entries. Repeat checks do not
increase cumulative totals: 713 equations, 1,820 routes and seven multipart
classification scenarios.

[Module 3/5 conversion validation](assessment-cards-grade2-modules3-5-lesson-wise-validation.json)
retains evidence for the preceding conversion. [Pair mapping](assessment-card-collections-manifest.json)
records active paths/formats and archives; [current validation](assessment-card-collections-validation.json)
records coverage and package preservation. [Migration progress](grade2-lesson-file-migration.json)
tracks conversion separately from assessment coverage. Earlier reports retain
mathematical validation history, including Module 1's rebuilt assessments.

All entries remain drafts. Educational review and actual script-agent
integration remain outstanding. Module 6 Lessons 18–20 reuse open questions:
grade equivalent explanations against source rubrics and apply partial credit
only for the stated criteria. Generated parity questions use explicitly
labelled numeric codes. Numeric answers do not verify drawings, folds, graph
labels, spoken vocabulary or coin choices. Source review flags and worksheet
uncertainties are preserved, including the Module 5 Lesson 11 exp_1 discrepancy;
its assessment uses correct arithmetic. Read actual accept lists and answer-key
shapes: source `pair_of_parts` keys can use `valid_pairs`, while hard assessment
keys use three named parts. Original IDs, versions and content are unchanged
by file conversion.
