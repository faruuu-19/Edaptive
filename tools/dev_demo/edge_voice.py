"""Development stand-in voice: Microsoft Edge neural voices (ONLINE, via the `edge-tts` package).

Sends only the lesson sentences to Microsoft's service. It exists because the real Kokoro voice cannot run at a usable
speed on every development machine. It is NOT the product's voice and breaks the project's offline rule, so it is
only for running the demo during development (see README.md in this folder).
"""
import asyncio
import base64

import edge_tts
import miniaudio

from voice_service.demo_server import ReplayNarrator  # noqa: E402  (the repository root is put on sys.path by serve.py)

# voice id -> (Edge voice, rate, pitch): bright, upbeat, slightly quicker than neutral.
VOICES = {
    "af_heart": ("en-US-EmmaNeural", "+6%", "+4Hz"),
    "am_michael": ("en-US-BrianNeural", "+4%", "+3Hz"),
}
RATE = 24000


async def speak(text, voice, rate, pitch):
    for attempt in range(5):  # Edge's service occasionally returns nothing; retry
        mp3 = bytearray()
        try:
            async for chunk in edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).stream():
                if chunk["type"] == "audio":
                    mp3 += chunk["data"]
        except Exception:
            mp3 = bytearray()
        if mp3:
            break
        await asyncio.sleep(0.5 * (attempt + 1))
    if not mp3:
        raise OSError("No audio returned")
    decoded = miniaudio.decode(bytes(mp3), output_format=miniaudio.SampleFormat.SIGNED16, nchannels=1, sample_rate=RATE)
    return decoded.samples.tobytes()


async def speak_all(texts, voice, rate, pitch):
    return await asyncio.gather(*(speak(t, voice, rate, pitch) for t in texts))


class EdgeNarrator(ReplayNarrator):
    def frames(self, segment, voice):
        yield {"type": "start", "segment_id": segment["id"]}
        name, rate, pitch = VOICES[voice]
        pcms = asyncio.run(speak_all([u["spoken"] for u in segment["utterances"]], name, rate, pitch))
        for i, (u, pcm) in enumerate(zip(segment["utterances"], pcms)):
            yield {"type": "audio", "utterance": i, "caption": u["caption"], "sample_rate": RATE,
                   "pcm_s16le": base64.b64encode(pcm).decode(), "ready_after_s": 0.0}
        yield {"type": "done", "segment_id": segment["id"]}
