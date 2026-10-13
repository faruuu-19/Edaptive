# Lesson and voice events — proposal for Ibrahim

Owner: Amna, Track B. These are proposals for team review, not registered payloads. `tutor.turn` already appears in the data-model proposal and belongs to Track A; the lesson/playback names below are suggested additions for agreement, not existing catalog entries. No code emits them yet and `contracts/` is unchanged. Existing registered `profile.selected`, `session.started`, `session.ended` events remain unchanged.

The current preview does not collect student identity, answers, transcripts, attention scores or audio. Production integration must use the shared identity resolver and event envelope, through authenticated endpoints and `appendEvent`/`append`.

| Proposed event | Meaning | Proposed payload fields to agree |
| --- | --- | --- |
| `lesson.started` | Learner starts a reviewed lesson | `concept_id`, `card_version`, script version/hash, subject voice profile |
| `tutor.turn` | A permitted script segment is delivered | `concept_id`, `card_version`, segment ID, displayed text, caption-only visual cue, zero live script-generation calls, latency |
| `voice.playback_started` | Local narration begins | `concept_id`, `card_version`, segment ID, voice/model revision, time to first audio |
| `voice.playback_paused` | Learner pauses narration | `concept_id`, `card_version`, segment ID, utterance index, playback position |
| `voice.playback_resumed` | Learner resumes narration | Same position identifiers |
| `lesson.completed` | Learner reaches the final permitted segment | `concept_id`, `card_version`, script version/hash; this is not a mastery verdict |

Keep utterance positions for replay without keeping learner audio. Before accepting any event: compare with `docs/DATA-MODEL.md` section 5, agree names/fields with the team, add versioned schemas and examples, register them, regenerate types and run contract checks. `student.answered` and assessment outcome events need the assessment/input modules; Continue in this preview is not an answer and must never be recorded as correct.

Open integration decisions: final subject voice mapping, whether to use existing `tutor.turn` for voice timings instead of separate voice events, parent approval of draft content, and production identity checks. Live student questions are outside the current stage.
