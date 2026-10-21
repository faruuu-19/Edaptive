# Tests and evaluation criterias

## Latest repository verification — 21 October 2026

The complete `make check` gate passed against the isolated QA PostgreSQL database:
221 backend tests, 143 script/runtime tests and 25 voice-service tests. All 17
frontend regression tests also passed (406 automated tests total). Contract
generation, Ruff and formatting, architecture import boundaries, ESLint, TypeScript
and an isolated production build passed. Runtime verification checked 148 reviewed
lesson pairs and the existing 84-section saved example, with 19 main-path sections
and zero model calls. Local runtime data and credentials were excluded from the
commit inventory; the changed-file secret scan found no matches.

This verification checks the current code and bundled content integrity. The live
browser, latency and educational-quality observations below belong to their dated
runs and were not repeated as part of this repository-wide check.

## Previous evaluation run

Tested: 16 October 2026 (Asia/Karachi)
System: `output/github/class-exit`; frontend `http://127.0.0.1:3001`; backend `http://127.0.0.1:8000`

## Result summary

**Overall result: PASS for the implemented local-system scope.**

| Area | Result | Evidence |
|---|---:|---|
| Backend/API | PASS | 195/195 tests passed against a migrated, isolated QA PostgreSQL database in 7.10 s |
| Script agent/runtime | PASS | 142/142 tests passed in 1.51 s |
| Voice service | PASS | 18/18 tests passed in 2.08 s |
| Bounded concurrency check | PASS | 200/200 health requests succeeded with 20 concurrent clients; p95 27.56 ms |
| Content/runtime integrity | PASS | 93 lesson pairs, 84 saved-example sections and 19 main-path sections verified; 0 model calls |
| Architecture boundaries | PASS | 2/2 import contracts kept; 0 broken |
| Frontend quality | PASS | ESLint, TypeScript and production build passed; all 11 routes generated |
| Live browser smoke test | PASS | Profile, student home, timetable, auth guards, lesson preview, navigation and narration tested |
| Local HTTP latency | PASS | All sampled pages/APIs returned HTTP 200; p95 values were 1.68–22.99 ms |

Total automated test cases executed: **355 passed, 0 failed, 0 skipped** (195 + 142 + 18). The temporary QA database was removed after testing.

## Mid-assessment rubric alignment

The attached mid-assessment rubric is an evaluation guide for the supervisor. Its requirements are treated here as evaluation criteria, not as instructions to modify the application. This test log supports evidence for Form 2 Criterion 3 (live prototype) and Criterion 7 (testing), and Form 3 Criterion 8 (testing plan, results, tools and risks). It does not establish the score for those criteria or for the other report/presentation criteria.

| Rubric expectation | Evidence in this log | Gap / action needed for stronger evidence |
|---|---|---|
| Form 2 C3: live core module plus edge/failure cases demonstrated | Live profile selection, authorization redirect, lesson navigation and narration were exercised; automated API/service tests pass | Capture a short live demo checklist with normal and failure cases and observed outcome. Current automated coverage is backend-heavy; the demo did not exercise backend outage, malformed lesson content, denied consent or interrupted narration end to end. |
| Form 2 C4 and Form 3 C4: FRs/NFRs and acceptance tests align with implementation | General latency thresholds and feature checks are listed | **Missing traceability:** no requirement IDs map each implemented functional/non-functional requirement to a test ID and pass result. Add an FR/NFR-to-test matrix using the project SRS/proposal IDs; do not invent requirement IDs. |
| Form 2 C5 and Form 3 C5–C6: design artefacts match current code | Architecture/import boundaries and contract tests are evidenced | Tests do not prove that architecture, ERD/data-flow, activity/sequence/state diagrams match the current implementation. Provide an implementation-to-diagram review/checklist and update diagrams where needed. |
| Form 2 C6: milestones, commits and individual ownership | Test execution is recorded | This is not test coverage. Separately attach milestone/task-owner evidence, commit timeline and each member’s owned module evidence; the rubric asks for these repository/process artefacts. |
| Form 2 C7: tests run against the current module, including a failure/edge case discussed | 355 automated tests, live auth guard/logout edge, boundary/service cases, runtimes, and timings are recorded | **Partial:** test outcomes are logged, but there is no concise failure-case narrative with trigger, expected behavior, observed behavior and severity. Add that record for at least one relevant case and demonstrate it live. |
| Form 3 C7: reproducible implementation documentation | Reproduction commands and local system setup are referenced | Confirm the report gives the exact supported environment/configuration, migration steps and model/voice prerequisites. This test log alone is not sufficient setup documentation. |
| Form 3 C8: test plan, early results, tool disclosure, risks and privacy | Executed suites, test counts, measured latency and remaining risks are documented | **Partial:** add requirement-linked planned tests, owners, test data/environment, and pass thresholds. List all evaluation tools/models and their roles; list external dependencies and privacy/risk mitigations. The rubric explicitly expects transparent tool disclosure. |
| Testing accuracy / empirical validation | Deterministic tests and catalog integrity passed | **Not measured:** no reviewed live-model answer-accuracy set, educator scoring, misconception-classification precision/recall, or child-facing content quality evaluation. Do not present software test pass rate as educational accuracy. |

### Priority tests/evidence to add

1. **P1 — Requirement traceability:** map each accepted FR/NFR to one or more test IDs, test method, threshold, result and evidence link. This directly addresses the strongest Form 2 C4 / Form 3 C4 gap.
2. **P1 — Failure-path live demonstration:** show at least one safe failure and recovery in the current core flow (for example, voice unavailable or invalid lesson data), recording expected versus observed behavior. Do not use a real student profile for destructive scenarios.
3. **P1 — Tool and risk disclosure:** identify runtime libraries, local model(s), voice engine, browser, test tools and any AI-assisted output; state what each was used for, how output was validated, and relevant privacy/security risks.
4. **P2 — Learner-facing accuracy study:** create an educator-reviewed question/response set before evaluating answer correctness, hint quality and misconception handling. Report sample size and scoring method; current model-output accuracy is unknown.
5. **P2 — Automated UI and accessibility coverage:** add repeatable browser tests for student/parent flows, keyboard navigation, screen-reader names, focus, contrast and error states.
6. **P2 — Concurrency and recovery:** load test with at least 20 simultaneous local clients and measure success rate, p95 API latency and data integrity; test database/model/voice interruption and recovery.

The rubric also evaluates proposal corrections, iteration progress, repository contribution, report format/R&D, diagrams, and individual tool ownership. These are supervisor/repository/report evidence items rather than software tests; collect them separately. The rubric’s score caps and required forms are supervisory decisions and cannot be determined from this test report.

## Executed tests and acceptance criteria

| ID | Test | Pass criterion | Observed result | Status |
|---|---|---|---|---:|
| A01 | Backend unit/integration/API suite | All tests pass on a clean migrated QA database | 195/195 passed | PASS |
| A02 | Database migrations | Revisions 0001–0007 apply without error | All seven applied | PASS |
| A03 | Contract validation | Every registered schema/example is valid | Contract tests passed | PASS |
| A04 | Auth/identity protection | Unauthorized child/parent resources are rejected or redirected | Automated auth/identity tests passed; `/home` redirected to `/` after logout | PASS |
| A05 | Profiles, consent, attendance and unenrolment | CRUD, authorization and edge-case tests pass transactionally | All related backend tests passed | PASS |
| A06 | Lesson delivery and routine | Schedule, actions, progress and delivery state tests pass | All lesson-delivery tests passed | PASS |
| A07 | Append-only session log | Valid events accepted; invalid/foreign/duplicate cases handled as specified | 11 session-log tests passed | PASS |
| A08 | Module isolation | No forbidden imports between feature modules/core | 2 contracts kept, 0 broken | PASS |
| A09 | Static analysis | No lint or TypeScript errors | Ruff, Ruff format, ESLint and `tsc --noEmit` passed | PASS |
| A10 | Production build | Optimized build completes and routes are generated | Build completed; 11 routes generated | PASS |
| A11 | Runtime content accuracy | Pair hashes, IDs, versions and saved script structure are valid | 93 pairs and 84 sections verified | PASS |
| A12 | Script-agent behavior | Planning, facts, rewrites, delivery and playback tests all pass | 142/142 passed | PASS |
| A13 | Voice API safety/behavior | Framing, busy handling, origin restriction and preparation rules pass | 18/18 passed | PASS |
| U01 | Profile selection | Selecting a child opens the matching home screen | Ali opened `/home`, showing `Hi, Ali!` and Grade 2 | PASS |
| U02 | Student timetable | Maths card opens the schedule and correct lesson/time content is shown | `/timetable` opened and rendered the daily schedule | PASS |
| U03 | Switch profile/logout | Switch returns to the profile picker and clears student access | Returned to `/`; direct `/home` access then redirected to `/` | PASS |
| U04 | Parent protection | Parent page must not expose management UI without PIN | `Parents only` PIN gate shown | PASS |
| U05 | PIN form guard | Unlock remains unavailable for an incomplete PIN | Unlock remained disabled | PASS |
| U06 | Lesson preview | Saved reviewed lesson loads without generating or recording progress | 19-part Grade 2 `Pairs to ten` preview loaded | PASS |
| U07 | Lesson navigation | Previous disabled on part 1; Next opens part 2; Previous returns to part 1 | All states observed | PASS |
| U08 | Local narration | Listen starts local narration and Pause stops/pauses it | Narration became active within 6.2 s; Pause changed to `Keep listening` | PASS |
| U09 | Responsive layout | Core screen remains usable at small-mobile and 1280×800 desktop sizes | No clipping/overlap observed at either size | PASS |
| U10 | Browser console | No application error/warning during tested flows | 0 errors, 0 warnings | PASS |

## Latency evaluation

Twenty sequential local requests were measured per endpoint after warm-up.

| Endpoint | Success | Average | p95 | Min–max | Criterion | Result |
|---|---:|---:|---:|---:|---:|---:|
| `/` | 20/20 | 12.08 ms | 22.99 ms | 7.83–26.37 ms | p95 < 500 ms | PASS |
| `/home` | 20/20 | 9.39 ms | 9.85 ms | 8.72–12.83 ms | p95 < 500 ms | PASS |
| `/parent` | 20/20 | 9.82 ms | 10.09 ms | 8.87–15.42 ms | p95 < 500 ms | PASS |
| `/timetable` | 20/20 | 10.74 ms | 14.69 ms | 9.63–15.51 ms | p95 < 500 ms | PASS |
| `/api/health` | 20/20 | 1.35 ms | 1.68 ms | 1.13–1.72 ms | p95 < 200 ms | PASS |
| `/api/auth/status` | 20/20 | 4.34 ms | 6.57 ms | 2.09–7.28 ms | p95 < 200 ms | PASS |
| `/api/profiles` | 20/20 | 7.38 ms | 8.89 ms | 4.57–9.05 ms | p95 < 200 ms | PASS |
| Narration start | 1 manual run | — | ≤ 6.2 s | — | < 10 s on provisioned local model | PASS |

These are local, single-user, warm-cache measurements. They do not represent internet deployment or concurrent-load performance.

### Bounded concurrent check

| Endpoint | Concurrency / requests | Success | Average | p95 | Maximum | Result |
|---|---:|---:|---:|---:|---:|---:|
| `/api/health` | 20 / 200 | 200/200 HTTP 200 | 17.72 ms | 27.56 ms | 29.71 ms | PASS |

This is a short smoke load against the health route only. It does not establish database, lesson-delivery, voice, or full-system capacity under load.

## Accuracy and quality criteria

| Metric | Acceptance criterion | Result |
|---|---|---:|
| Automated correctness | 100% of deterministic tests pass | 355/355 (100%) PASS |
| API reliability | 100% successful responses for sampled healthy GET endpoints | 140/140 (100%) PASS |
| Content integrity | 100% of catalogued lesson pairs pass ID/version/hash checks | 93/93 (100%) PASS |
| Saved lesson structure | All required sections and main-path sections validate | 84/84 sections; 19/19 main path PASS |
| Frontend correctness | No lint/type/build errors | PASS |
| Runtime console stability | No console errors in core tested flows | PASS |

“Accuracy” here means deterministic software correctness and content integrity. It does **not** claim pedagogical or generative-model accuracy. Any live model output must continue to be schema constrained and deterministically verified before reaching a child.

## Necessary acceptance criteria for future/release testing

These remain required before claiming full production readiness:

| Area | Required criterion | Current status |
|---|---|---|
| Frontend regression automation | Playwright tests for profile, auth guard, timetable, lesson controls and parent workflows in CI | NOT IMPLEMENTED; manual smoke test passed |
| Accessibility | Automated WCAG 2.1 AA scan; keyboard-only flow; visible focus; contrast; screen-reader labels | PARTIAL; semantic labels/roles observed, full audit not run |
| Load/stress | At least 20 concurrent local clients, ≥99% success, API p95 < 500 ms, no data corruption | PARTIAL: health route passed 200/200; business APIs and data integrity under load not run |
| Cold-start performance | Backend, frontend, local model and voice cold-start timings captured on target hardware | NOT RUN |
| Live-model factual accuracy | Reviewed evaluation set; 100% unsafe/unverified outputs blocked; target answer correctness agreed with educators | NOT RUN; deterministic saved example tested only |
| Pedagogical quality | Human educator review of age appropriateness, hint quality and misconception handling | NOT RUN |
| Privacy/security | Verify no child media leaves device; cookie flags, rate limits, CSRF assumptions, authorization and log redaction reviewed | PARTIAL; automated auth/origin tests passed |
| Browser coverage | Latest Chromium, Safari and Firefox at mobile/tablet/desktop breakpoints | NOT RUN; in-app Chromium tested |
| Failure recovery | Database unavailable, voice unavailable, model timeout, malformed content and interrupted playback show safe recovery UI | PARTIAL; automated transport/service tests passed |
| Camera/microphone consent | Permission denial/revocation and no-storage behavior tested on real devices | NOT RUN |

## Findings and limitations

1. Plain `make check` needs `uv`, which is not on this machine’s shell `PATH`. The quality gate passed using the provisioned backend/voice environments; the equivalent command is recorded below.
2. The first backend run correctly skipped database tests when no test database was configured. A separate QA database was then created, migrated and used; all 195 tests passed. The household database was not used or modified.
3. The lesson preview is explicitly marked draft/review mode and does not record answers or progress. Current documentation also states that answer submission, grading and mastery updates are not yet part of this flow; they therefore cannot be accepted as implemented features.
4. No automated frontend end-to-end or accessibility test suite exists. This is the largest remaining test-coverage gap.

## Rubric crosswalk: testing evidence and remaining work

The assessment rubric asks for executed unit/module tests and at least one failure or edge case that can be actively discussed (Form 2, Testing & Early Validation), plus a clear test plan, early results, disclosed tools/dependencies and risks (Form 3, Testing Plan & Tool / Risk Disclosure).

### Failure and edge cases already executed

These are concrete cases in the passing suites, with the expected behavior encoded by their assertions. The suite totals above include these cases.

| Case | Expected behavior | Recorded evidence |
|---|---|---|
| Five incorrect parent PIN attempts | Further attempts are locked out | `backend/tests/test_auth.py::test_lockout_after_five_wrong_pins` passed |
| Unknown profile or signed-out profile management | Sign-in/manage request is denied | `test_unknown_profile_cannot_sign_in`, `test_signed_out_cannot_manage_profiles` passed |
| Duplicate/invalid/unregistered session event | Duplicate append is idempotent; invalid or unregistered event is rejected and not stored | `test_append_is_idempotent`, `test_invalid_event_is_never_stored`, `test_http_rejects_unregistered_type` passed |
| Lesson preparation outage/failure | Save the parent’s time safely and retry; do not wait indefinitely for a failed job | `test_outage_saves_time_and_system_retries_automatically`, `test_a_failed_preparation_is_not_waited_for` passed |
| Voice endpoint gets a remote origin or a second request while busy | Remote request is rejected; active stream stays correctly framed and busy request is rejected | `test_remote_origin_cannot_request_speech`, `test_stream_is_framed_and_busy_requests_are_rejected` passed |
| Malformed model response or invalid catalog pair | Count the malformed attempt, repair once or fail visibly; missing/duplicate pairs fail closed | `test_malformed_provider_reply_counts_one_attempt`, `test_repair_once_then_explicit_failure`, `test_duplicate_and_missing_pairs_are_not_silently_skipped` passed |

For the live supervisor demo, show the running app’s parent PIN gate and signed-out `/home` redirect, then run the automated failure cases above and explain the expected recovery/rejection. This supplies a concrete failure-case walkthrough; the supervisor meeting itself has not yet occurred, so no claim is made that it was already demonstrated there.

### Model and learning accuracy evaluation protocol (planned, not yet scored)

The current app test totals measure implementation correctness, not tutor answer accuracy or educational quality. Use this evaluation before reporting those as achieved metrics:

| Metric | Measurement | Proposed acceptance target |
|---|---|---:|
| Verified answer correctness | 100 curated Grade 1–5 math prompts (20 per grade), balanced across correct answers, common misconceptions, ambiguous inputs and out-of-scope inputs; compare response against educator-authored answer/rationale key | ≥95% correct on in-scope prompts |
| False acceptance by verifier | Incorrect or unsupported model claims that the deterministic verifier allows through ÷ all incorrect/unsupported claims in the set | 0% |
| False rejection by verifier | Correct claims incorrectly blocked ÷ all correct claims in the set | ≤5% |
| Curriculum alignment | Two educators independently score grade/topic fit and concept alignment on a 1–4 rubric; report mean and agreement | Mean ≥3.5/4; report agreement statistic |
| Socratic/pedagogical quality | Same reviewers score age-appropriate language, useful hinting and misconception response on a 1–4 rubric | Mean ≥3.5/4 on each dimension |
| Response latency | 30 cold and 100 warm runs on the target machine; report first-token/first-audio p50 and p95 separately | Proposed warm p95 ≤10 s to first audio |

These are proposed targets for the team/supervisor to approve. No model evaluation set was run for this report; do not present these target values as results. Record model name/version, prompt version, verifier version, hardware, run date, all sample IDs, per-case outcomes, reviewer identities/roles and disagreements with the eventual results.

### Reproducible commands

Run from `output/github/class-exit`. With the already provisioned local environments used for this evaluation:

```sh
PATH=/Users/amnahameed/edaptive-backend/venv/bin:/Users/amnahameed/edaptive-voice/venv/bin:$PATH \
  make check BACKEND_RUN=env PYTHON=/Users/amnahameed/edaptive-backend/venv/bin/python
```

This runs lint, frontend typecheck, backend tests, runtime catalog checks, script-agent tests, voice tests and the production build. For database-backed backend coverage, configure `DATABASE_URL` to a disposable QA PostgreSQL database, apply migrations with `cd backend && alembic upgrade head`, then run `cd backend && REQUIRE_DB=1 pytest`. The database must not contain household data.

To repeat the bounded health smoke load on the local app:

```sh
seq 1 200 | xargs -P20 -I@ curl -sS -o /dev/null -w '%{http_code} %{time_total}\n' \
  http://127.0.0.1:3001/api/health
```
