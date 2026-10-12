# Assessment cards v0.2 draft

Grade 2 Module 1 has one standalone assessment object per lesson, paired with
one standalone lesson concept. Other sources still use assessment collections:
select a child from `cards` by concept ID before following this contract.
See [file pairing and loader rules](assessment-card-collections.md).

These assessments are complete data inputs for a future script agent. Supply one
assessment and the concept card matching `linked_concept.concept_id` and
`linked_concept.concept_version`. Every card remains a draft for human review.

The format extends v0.1 with root `hints` and `tutor_guidance`; it also changes
route tokens to make retries and follow-up returns explicit. Consumers must
support v0.2 deliberately. The assessment ID ends in `_v2`, `card_version` is 2,
and `schema_version` is `0.2-draft`. This data upgrade does not change the app
runtime or establish script-agent compatibility.

## Structure

Each card preserves the original fields for identity, concept linkage, subject,
grade, objectives, provenance, readiness, levels, default attempts, default
routes, fallbacks, questions, follow-ups and rubrics. There are three main
questions, two diagnostic follow-ups and four local rubrics. The easy question
and rubric reference the linked concept. Generated questions reference their
local rubrics and explanation/example IDs from the linked concept.

Each of the 15 entries in `hints` has `id`, `question_id`, `level`, `text`,
`origin`, and `grounded_in`. Each main question and follow-up has three local
`hint_refs`, in levels 1, 2 and 3. Deliver those local hints. The easy question's
original hint references are retained in its guidance as `source_hint_refs`;
they are provenance rather than a second delivery sequence.

`tutor_guidance` contains `delivery_order`, `input_contract`, `attempt_policy`,
`outcome_classification`, `hint_policy`, `silence_policy`, `route_definitions`,
`closing`, and `questions`. Each of its five question records contains:

- `question_id`, `delivery_prompt`, and `part_delivery_prompts`.
- `partial_credit_eligible`, `hint_sequence`, and `source_hint_refs`.
- `feedback` for correct, partial, incorrect, unclear and incomplete outcomes; inapplicable partial/incomplete feedback is null.
- `outcome_actions`, `reprompt`, and `max_attempts`.
- `answer_reveal`, containing `rubric_ref`, `answer_key`, `say`, and `worked_steps`.

The hard answer-key mode retains the original name `pair_of_parts`; its `parts`
array contains all three required parts. `final_part_id` is `p2`, and `p3` is an
independent check reaching the same result. All three answers are required for
full credit, including the check. Interpret an open source answer semantically
against its rubric. Apply source partial-credit rules when explicitly present,
including numeric source questions whose learner stops a count early.

## Delivery and routing

Ask main questions in `delivery_order`. Ask hard parts individually. Follow-ups
appear only when triggered, rather than as extra main questions. Use the linked
concept to resolve references and the assessment to obtain ready-to-speak
feedback, hints, and worked answers. Use the exact visual state/specification
for reused visual questions. Generated questions are answerable from their text.

A main question allows two answer attempts. A follow-up allows one and consumes
no parent attempt. Preserve the parent counter after returning. A parent can
trigger its follow-up once: medium on incorrect, hard on incomplete. Give the
next parent hint before that follow-up; after resolving it, retry the parent if
an attempt remains. For partial hard work, retain correct parts and retry only
incorrect parts. For incomplete work, retry missing or incorrect parts.

At the parent attempt limit, a correct response advances; any other outcome
reveals the worked answer and advances. Do not launch another follow-up. A
failed follow-up reveals its own answer before returning to the parent; if no
parent attempt remains, reveal the parent answer and advance. Every route token
has its normative definition in `tutor_guidance.route_definitions`.

Help gives the next unused hint without an attempt. Give one hint at a time.
After the third hint, repeated help repeats the last hint and the pending
question. An explicit answer request reveals the worked answer and advances a
main question or returns a follow-up to its parent. One unclear response or
20 seconds of silence gets one clarification without an attempt; repeated
unclear/silence counts as an incorrect attempt and takes that question's route.

For hard responses, unclear means an answer cannot be understood or a supplied
part is ambiguous. Incomplete means at least one part is understood and one is
missing. Correct means all required parts match. Partial means all parts are
present and understood but only some match. Incorrect means none match. Keep
previously correct parts when grading the next attempt. Record revealed answers
separately from independently correct answers.

## Coverage and checks

There are 75 active assessments in 19 matching files. Grade 2 Module 1 has
eight standalone concept/assessment pairs for Lessons 1–8. Eleven other
covered sources retain collections. The old combined Module 1 pair is archived
and excluded from active totals. The root README has the complete hierarchy;
the [migration index](grade2-lesson-file-migration.json) tracks conversion.
Active totals are 225 main questions, 150 follow-ups, 300 local rubrics,
1,125 hints and 375 guidance records.

[Module 1 assessment validation](assessment-cards-grade2-module1-lesson-wise-validation.json)
records eight new assessments with prompt-based answers/accept variants,
96 worked equations, 192 route scenarios and current-lesson-only grounding.
[Concept extraction validation](concept-cards-grade2-module1-lesson-wise-validation.json)
records 112 original questions/rubrics preserved exactly, 96 numeric keys,
one pair key, three text truths, 12 preserved open rubrics, source references,
asset scopes and package hashes. New concepts use card version 2; assessments
link to that exact version. Original shared support hints retain provenance.

[Current pair validation](assessment-card-collections-validation.json) checks
75 active entries, preserved earlier entries, archived original bytes, pair
formats and ZIP equality. Active cumulative evidence covers 713 worked
equations, 1,820 routes and seven multipart classification scenarios; archived
assessment checks are excluded. Earlier reports retain historical evidence.

Source concept rubrics with mode `exact` can accept words as well as numbers.
Read their actual accept lists. Open answers need semantic grading; source
`pair_of_parts` can provide unordered `valid_pairs`. The assessment hard rubric
uses three named `parts`. Do not confuse these answer-key shapes.

All entries remain drafts. Numeric responses do not verify actual drawings,
folds, graphs, spoken mathematical vocabulary or selected coin combinations.
Lesson extraction uses the combined JSON rather than newly read original PDFs.
The checks do not replace educational review or script-agent integration tests.
The [reference controller](assessment-cards-v0.2-routing-reference.py) is a
standalone example; the caller grades against the actual rubric and retains
correct hard parts before passing an outcome to it.
