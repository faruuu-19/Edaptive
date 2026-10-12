# Grade 2 Module 5: standalone lesson pairs

All 20 lessons included in the source have separate concept and full assessment files.

Each `lesson-N` folder contains `math_g2_m5_lN_lesson.json` and its matching
`math_g2_m5_lN_lesson.assessment_card.json`. The concept is one lesson
object. The assessment is one v0.2 object with `card_type: assessment_card`;
pass it directly to the script agent with the matching concept. Select inputs
using `module_index.json`, and verify linked concept ID/version and both hashes.
Repository index paths are relative to the repository root. The downloadable
module ZIP uses paths relative to its extracted folder.

All original concept content and full assessment content are preserved.
Each assessment retains easy/medium/hard questions, two follow-ups, four local
rubrics, 15 hints and five guidance records with feedback, worked answers,
attempts, help, silence and fallback rules. Existing IDs and versions remain
the same. This is a file conversion of already validated assessments.

The original collection pair is retained in `../legacy/module-wide/` and
excluded from active indexes and ZIPs. Historical numeric-answer validation
still applies; conversion validation checks object equality, scoped references,
input hashes, full guidance, tutoring routes and package bytes.
All cards remain drafts requiring human educational review; actual script-agent
integration remains untested. Source review flags and educational limitations
are preserved, including numeric answers not verifying actual drawings.

Lesson 11 source `exp_1` says its tens total is 10, but including the new ten gives 11. The preserved assessment uses correct arithmetic.
