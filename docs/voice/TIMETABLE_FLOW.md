# Timed lesson demo — Amna / Track B

The demo runs at `/timetable-demo`, with the existing `EDAPTIVE_VOICE_PREVIEW=1` flag and local voice service. The source of truth for matched content is the audited inventory in `docs/voice/PAIR_INVENTORY.md`. The demo catalog uses the 75 published maths pairs; two additional Grade 3 local review pairs are documented separately, bringing the full three-level draft-pair inventory to 77. No pair is approved for production child delivery.

## Flow

1. Choose a maths pair, a custom class time in Pakistan time, and a preparation lead time.
2. A deterministic timetable planner creates Maths, Break, Science, Break, English slots. The demo defaults to 20-minute classes and five-minute breaks. Science and English are visibly unavailable until their matching cards exist; no lessons are invented for them.
3. At `class time - lead time`, the service runs Amna's existing script agent against the selected concept and assessment cards. Kokoro releases its weights while Qwen prepares the script. Once generation and validation finish, Kokoro warms again.
4. Progress comes from completed script segments: planning, segment generation/rechecking, validation, and voice warm-up. A failed guard or flagged script never reaches ready/100%.
5. At class time, the browser displays an alarm and rings a gentle chime. Start class is enabled only after preparation is ready. It cannot start earlier, including by a direct API request.
6. Start class opens the prepared main path and starts live Kokoro narration. Reflections and questions wait for Continue. The student can pause, replay or switch teacher voice. No answer grading or mastery update is inferred from Continue.
7. Borrow 5 minutes stops the alarm and moves the class and every later slot five minutes forward, keeping their durations and breaks. Preparation already completed is retained.

## Preparation modes

- **Fresh:** `qwen3.5:9b-q4_K_M`, already installed, uses the existing script generator and its checks. No paid/cloud calls or model downloads. Actual preparation takes minutes and may fail validation or a memory guard; the failure stays visible and blocks Start.
- **Quick demo:** class in 30 seconds; rechecks the actual saved Grade 2 Module 1 Lesson 1 script against matching source hashes and current planner/checker rules. The worker reports each of its 84 completed sections. This uses no new LLM generation and does not simulate a slow progress animation. It is explicitly labeled in the UI.

Draft script outputs/checkpoints live outside the repositories at `~/edaptive-voice/lesson-preparation/<schedule-id>/`. No learner audio, answers, profile identifiers or mastery results are recorded. The timetable is a single active, in-memory review schedule and is lost if the service restarts. The demo tab must stay open for the browser alarm; this is not an OS alarm or notification service.

The standalone preview does not change Ibrahim's production scheduling, authentication or database modules. Production integration still requires household/student identity, reviewed content, agreed scheduling/event contracts, persistence and science/English pairs. The proposed event document remains a proposal; nothing is registered or sent.

## Validation

The 75 published pairs are byte-matched to content branch commit `cb2e64b1d19a624f3139e670f602cdfb74b7e3b6`, with matching concept versions and passing planner checks. Supplementary Grade 3 rounding/polygons pairs also pass the planner; the Grade 4 division pair has only two levels and is excluded.

Sixteen service/timetable tests cover main-path exclusion, early-start prevention, not-ready prevention, exact five-minute shifts, matching schedule IDs, cancellation and stale updates, invalid timestamps, concurrent requests and origins. The saved-script worker completed 86 progress messages (planning, 84 section checks, validation) in a real local recheck. Frontend lint and Next.js build pass. Browser verification reached ready/100%, the due-time alarm, a successful Borrow 5 minutes action with all slots shifted, and a started lesson with automatic narration. Cancelling a started class clears its active state and denies further scheduled lesson access. The five-minute state transition is also tested with an injected clock, without waiting five minutes.

Fresh generation uses the existing tested local script agent; a new full fresh-generation run is not being claimed for this demo verification. Performance numbers from earlier voice benchmarking remain separate from preparation progress.
