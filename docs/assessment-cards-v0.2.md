# Assessment cards v0.2 draft

Assessment files are now collections, one per source concept JSON. Unwrap each
object in the collection's `cards` array and match it by concept ID before
following this lesson-level contract. See [collection naming and loader rules](assessment-card-collections.md).

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

The set has 68 lesson assessments in 12 matching files: Grade 1 Modules 1–6
Lesson 1; Grade 2 Module 1 Lessons 1–8 in one combined source card, Module 3
Lesson 1, Modules 5 and 6 Lessons 1–20 each, and Modules 7 and 8 Lessons 1–10
each. Modules 7 and 8 contain 26 and 16 source concepts, so their collections
list 16 and 6 missing IDs respectively. The root README gives the hierarchy.
Totals are 204 main questions, 136 follow-ups, 272 local rubrics, 1,020 generated
hints and 340 guidance records.

Python checks passed for source/local references, exact fields, copied source
assets, independently recomputed answers and accept variants, hints, worked
answers and 627 cumulative equations. The reference controller passed 1,652
route scenarios and seven multipart classification scenarios.
[Original lesson validation](assessment-cards-v0.2-validation.json),
[Module 5 validation](assessment-cards-grade2-module5-lessons9-20-validation.json),
[Module 6 validation](assessment-cards-grade2-module6-lessons11-20-validation.json)
and [Module 7 validation](assessment-cards-grade2-module7-lessons1-10-validation.json)
retain historical evidence. Open answers use the source rubric with equivalent
explanations; explicit numeric codes in parity items denote classifications.

[New Module 8 validation](assessment-cards-grade2-module8-lessons1-10-validation.json)
records ten additions with geometric and rational equal-share checks,
28 equations and 240 routes. Choice keys explicitly map numbers to shape and
share names. A correct choice code cannot verify spoken vocabulary, explanations
or actual constructions, drawings, folds and joins. The source trapezoid
definition is inclusive; the square question requests the most specific listed
name. Source high flags naming reused questions in Lessons 3 and 5 are retained
as review blockers.

[Collection validation](assessment-card-collections-validation.json) records
current coverage and preservation. All cards remain drafts. These checks do
not replace educational review or testing the eventual script agent.
The [reference controller](assessment-cards-v0.2-routing-reference.py) is a
standalone example; the caller grades against rubrics and retains correct hard
parts before passing an outcome to it.
