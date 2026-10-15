# Grade 2 Module 8: complete lesson pairs

Lessons 1–16 each have one concept JSON and one full assessment JSON named
`<concept_id>.assessment_card.json`. The existing ten assessments are unchanged;
six missing assessments (Lessons 11–16) were added. Every assessment has easy,
medium and hard questions, two follow-ups, four local rubrics, fifteen hints and
five question guidance records with feedback, worked answers and bounded routes.

Use `module_index.json` to select the two inputs and verify linked ID/version
and hashes. Repository paths are relative to repository root. Module ZIP paths
are relative to its extracted directory. The original concept collection is
retained under `../legacy/module-wide/` for provenance; each concept object is
preserved exactly. No assessment bundle or duplicate draft is created.

All cards remain drafts requiring human educational review. Actual script-agent
integration is untested. Numeric responses do not verify actual folds,
partitions, drawings, clock-hand positions or spoken reasoning. Lessons 11 and
12 reuse easy questions with exact non-integer answers ("another fourth",
"yes"); Lesson 13 hard answers are clock-number labels; Lesson 15 uses explicit
1 = a.m. / 2 = p.m. codes in its medium follow-up. Source review flags are preserved.
