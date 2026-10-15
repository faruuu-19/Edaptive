# Grade 5 Module 1: complete lesson pairs

Lessons 1–16 each have one concept JSON and one full assessment JSON named
`<concept_id>.assessment_card.json`. All 16 assessments are new. Every assessment
has easy, medium and hard questions, two follow-ups, four local rubrics, fifteen
hints and five question guidance records with feedback, worked answers and
bounded routes.

Use `module_index.json` to select the two inputs and verify linked ID/version
and hashes. Repository paths are relative to repository root. Module ZIP paths
are relative to its extracted directory. The original concept collection is
retained under `../legacy/module-wide/` for provenance; each concept object is
preserved exactly. No assessment bundle or duplicate draft is created.

All cards remain drafts requiring human educational review. Actual script-agent
integration is untested. Answers are decimals (or whole numbers); accept lists
give the digits, a "point" reading and a unit reading ("four and thirty five
hundredths"). Numeric responses do not verify place-value charts, number-line,
area-model or tape-diagram drawings or spoken reasoning. Fifteen of the sixteen
reused easy questions are partial-credit eligible because their source rubrics
carry a partial description; Lesson 6's easy answer is a comparison word
("greater than"). Hard questions state the decompositions their check part
needs.
