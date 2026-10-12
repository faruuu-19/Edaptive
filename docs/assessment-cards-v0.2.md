# Assessment cards v0.2 draft

Grade 2 Modules 1, 5 and 6 have eight, twenty and twenty standalone lesson assessments.
Module 3's available Lesson 1 is standalone; its other twenty source lessons
remain absent. Other sources still use collections: select a child from
`cards` by concept ID before following this contract. See
[file pairing and loader rules](assessment-card-collections.md).

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

The [reference controller](assessment-cards-v0.2-routing-reference.py) is a standalone example; the caller grades against actual rubrics and retains correct hard parts before passing an outcome to it.
