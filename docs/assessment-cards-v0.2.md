# Assessment cards v0.2 draft

Each assessed concept ID now has one canonical standalone file named
`<concept_id>.assessment_card.json`. Supply it with the matching single concept
object. If the source JSON contains `cards[]`, select the concept by ID first.
See [loading rules](assessment-card-collections.md).

The full v0.2 schema and every retained assessment object are unchanged by
cleanup. All 118 cards remain drafts. Script-agent integration is untested.

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

118 concept IDs have 118 standalone assessments; no assessment collections remain.
Each includes three main questions, two follow-ups, four local rubrics, 15 hints
and five guidance records. Grade 2 Module 7 Lessons 1–26, Module 8 Lessons 1–16
and Grade 3 Module 2 Lessons 1–21 are complete, including sixteen, six and
twenty-one new full assessments respectively. See the root README for totals and coverage.

[Cleanup validation](assessment-cards-cleanup-validation.json) checks unchanged
content, IDs, references, guidance, hashes, worked arithmetic, tutoring routes
and ZIP bytes. Original independent answer verification remains applicable.
Human educational review and actual script-agent integration remain pending.
The [reference controller](assessment-cards-v0.2-routing-reference.py) is a
standalone example; the caller grades against actual rubrics and retains correct
hard parts. Numeric answers cannot verify actual drawings or spoken reasoning.

Module 7 Lessons 17, 18 and 24 have open easy answers; follow the source semantic and partial criteria. Lesson 18 unit measurements are approximate and choice codes are explicitly labelled. [New assessment validation](assessment-cards-grade2-module7-lessons11-26-validation.json) and [module-pair validation](assessment-cards-grade2-module7-lesson-wise-validation.json) retain the answer and preservation evidence.

Module 8 Lessons 11–16 ([new assessment validation](assessment-cards-grade2-module8-lessons11-16-validation.json),
[module-pair validation](assessment-cards-grade2-module8-lesson-wise-validation.json)) reuse
easy items with exact non-integer answers in Lessons 11 and 12 ("another fourth", "yes"),
use clock-number labels in the Lesson 13 hard question and explicit 1 = a.m. / 2 = p.m.
codes in the Lesson 15 medium follow-up. Numeric responses do not verify folds,
partitions, drawings or clock-hand positions. Cards written in these batches record
`generated_by: claude_manual_fixture`; earlier cards keep their original value.

Grade 3 Module 2 Lessons 1–21 ([new assessment validation](assessment-cards-grade3-module2-lessons1-21-validation.json),
[module-pair validation](assessment-cards-grade3-module2-lesson-wise-validation.json)) use whole-number
answers throughout. Their hard questions state the place-value decompositions that the
check part needs, so the check introduces no new numbers. Lesson 1's reused easy answer is
the word "minute". Numeric responses do not verify number-line drawings, clock or scale
readings or measuring.
