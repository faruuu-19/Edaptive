# Grade 2 Module 1: one lesson, two inputs

All eight lessons have separate concept and assessment files. Each folder
`lesson-1` through `lesson-8` contains `math_g2_m1_lN_lesson.json` and
`math_g2_m1_lN_lesson.assessment_card.json`. The assessment is one complete
v0.2 object, with `card_type: assessment_card`; do not look for a `cards` array.
Use `module_index.json` to select a lesson and verify ID, version and file hashes.
Repository index paths are relative to the repository root; the downloadable
module ZIP has an index with paths relative to its extracted folder.

Each concept has its own objective and original questions, rubrics,
explanations/examples and referenced hints. All 112 original questions and
rubrics are preserved exactly across the eight lessons. Shared original hints
retain their provenance; later-lesson explanations are not imported. Lesson
objectives, visual scopes and review metadata are adapted from the combined
concept. Concept version is 2 and each assessment links to that exact version.

Each assessment has easy, medium and hard questions, two follow-ups, four local
rubrics, 15 progressive hints and five guidance records. Feedback, worked
answers, attempts, help, silence and follow-up return rules are explicit.
The assessments were rebuilt for their own lesson methods and ranges.

All files are drafts. Python checks covered the 96 numeric concept answer
keys/accept variants, one pair key, three text truths, preservation of 12 open
rubrics, scoped references and asset specs. New assessment checks covered
96 worked equations and 192 tutoring routes. ZIP hashes and matching input IDs
were checked. Open source rubrics need semantic grading; source
`pair_of_parts` can contain `valid_pairs`, whereas the hard assessment rubric
contains three named parts. Read the actual key shape when grading.
Human educational review and script-agent integration tests remain outstanding.

The original combined pair is preserved in `../legacy/module-wide/` for
provenance and is excluded from active script inputs and packages.
