# One assessment per concept ID

The canonical dataset has 97 assessment files for 97 concept IDs. Each is named
`<concept_id>.assessment_card.json` and has `card_type: assessment_card`.
Assessment `cards[]` collections, obsolete versions and duplicate snapshots
were removed. Concept sources are preserved; some still contain `cards[]`.
Use `assessment-card-collections-manifest.json` as the canonical concept-ID
index despite its historical filename. Its format is
`one_assessment_object_per_concept_id`. Repository paths start with `ciriculam/`.

```python
import hashlib
import json
from pathlib import Path

def load_pair(entry):
    source_bytes = Path(entry['source_file']).read_bytes()
    assessment_bytes = Path(entry['assessment_file']).read_bytes()
    assert hashlib.sha256(source_bytes).hexdigest() == entry['source_sha256']
    assert hashlib.sha256(assessment_bytes).hexdigest() == entry['assessment_sha256']
    source = json.loads(source_bytes)
    concepts = source if isinstance(source, list) else source.get('cards', [source])
    concept = next(c for c in concepts if c['concept_id'] == entry['concept_id'])
    assessment = json.loads(assessment_bytes)
    assert assessment['card_type'] == 'assessment_card' and 'cards' not in assessment
    assert assessment['linked_concept'] == {
        'concept_id': concept['concept_id'], 'concept_version': concept['card_version']
    }
    return concept, assessment
```

Resolve `concept_card` references only against that selected concept, and
`this_card` references against that single assessment. Local IDs can recur in
other lessons. Keep attempts, hints, follow-ups and correct-part state separate.
The complete v0.2 schema, hints, feedback and routing content are unchanged.
Lesson module indexes use repository paths; ZIP indexes use extracted-folder
paths. The source-plus-assessment ZIP contains one extracted concept object and
one assessment object per concept ID.

Grade 1 has six assessments, covering Lesson 1 in Modules 1–6. Grade 2 has 91:
Module 1 Lessons 1–8; Module 3 Lesson 1; Modules 5/6 Lessons 1–20; Module 7
Lessons 1–26; Module 8 Lessons 1–16. Grade 2 Modules 1/3/5/6/7/8 have standalone
lesson concepts. Module 3 has twenty missing source concepts; Grade 2 Modules 2/4
have no supplied source.

[Module 7 new assessment validation](assessment-cards-grade2-module7-lessons11-26-validation.json)
records independent answer/accept-list checks and 390 route scenarios for sixteen
cards. [Module 7 lesson-pair validation](assessment-cards-grade2-module7-lesson-wise-validation.json)
checks all 26 pairs and 980 preserved source questions.
[Module 8 new assessment validation](assessment-cards-grade2-module8-lessons11-16-validation.json)
records independent answer/accept-list checks, 35 worked equations and 144 route
scenarios for six new cards; [Module 8 lesson-pair validation](assessment-cards-grade2-module8-lesson-wise-validation.json)
checks all 16 pairs, preserved source objects and ZIP bytes. Current totals are
291 main questions, 194 follow-ups, 388 local rubrics, 1,455 hints and 485 guidance
records. Cumulative evidence is 857 equations, 2,354 routes and seven multipart
classification scenarios; repeated module/package checks are kept separate.

[Cleanup validation](assessment-cards-cleanup-validation.json) records exact
assessment preservation, unique IDs, refs, hashes, guidance, routes and ZIPs.
Historical mathematical reports retain their original evidence; removed
assessment bundles can be recovered from Git history. All cards remain drafts;
human educational review and actual script-agent integration remain outstanding.
