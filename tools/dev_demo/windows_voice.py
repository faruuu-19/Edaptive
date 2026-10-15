"""Offline stand-in voice for Windows: the built-in Microsoft voices (SAPI), no downloads and no internet.

Zira speaks the female teacher and David the male teacher, with a lighter, cheerful delivery. Robotic compared with the
real Kokoro voice; for running the demo during development (see README.md in this folder).
"""
import base64
import json
import subprocess
import tempfile
import wave
from pathlib import Path

from voice_service.demo_server import ReplayNarrator  # noqa: E402  (the repository root is put on sys.path by serve.py)

SAPI_VOICE = {"af_heart": "Microsoft Zira Desktop", "am_michael": "Microsoft David Desktop"}
# Softer, cheerful delivery: higher pitch, a little slower, rising phrase contour.
STYLE = {"af_heart": ("+28%", "-8%"), "am_michael": ("+12%", "-6%")}
PS = r"""
param($Voice, $Dir, $Json, $Pitch, $Rate)
Add-Type -AssemblyName System.Speech
$texts = Get-Content -Raw -Encoding UTF8 $Json | ConvertFrom-Json
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice($Voice)
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(24000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
for ($i = 0; $i -lt $texts.Count; $i++) {
  $s.SetOutputToWaveFile((Join-Path $Dir ("u{0}.wav" -f $i)), $fmt)
  $t = [System.Security.SecurityElement]::Escape([string]$texts[$i])
  $s.SpeakSsml('<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US"><prosody pitch="' + $Pitch + '" rate="' + $Rate + '" contour="(0%,+0%) (30%,+12%) (70%,+4%) (100%,-6%)">' + $t + '</prosody></speak>')
  $s.SetOutputToNull()
}
"""


class WindowsNarrator(ReplayNarrator):
    def frames(self, segment, voice):
        yield {"type": "start", "segment_id": segment["id"]}
        texts = [u["spoken"] for u in segment["utterances"]]
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "t.json").write_text(json.dumps(texts), encoding="utf-8")
            (tmp / "s.ps1").write_text(PS, encoding="utf-8-sig")
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(tmp / "s.ps1"),
                 "-Voice", SAPI_VOICE[voice], "-Dir", str(tmp), "-Json", str(tmp / "t.json"),
                 "-Pitch", STYLE[voice][0], "-Rate", STYLE[voice][1]],
                check=True, capture_output=True, timeout=300)
            for i, u in enumerate(segment["utterances"]):
                with wave.open(str(tmp / f"u{i}.wav"), "rb") as w:
                    rate, pcm = w.getframerate(), w.readframes(w.getnframes())
                yield {"type": "audio", "utterance": i, "caption": u["caption"], "sample_rate": rate,
                       "pcm_s16le": base64.b64encode(pcm).decode(), "ready_after_s": 0.0}
        yield {"type": "done", "segment_id": segment["id"]}
