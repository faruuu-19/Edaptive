# Live narration — Amna / Track B

Public API: `LiveNarrator` from this folder's `index.ts`.

Schedules local Kokoro PCM audio in Web Audio as sentences arrive. Pause freezes the audio clock; navigation/replay cancel the current request and audio. Audio remains in memory. No microphone, voice cloning, cloud fallback or recording. The provisional preview HTTP client lives in `src/lib/voice-preview-api.ts`; production contract/event integration is proposed separately.
