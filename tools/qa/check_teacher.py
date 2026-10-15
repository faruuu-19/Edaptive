"""Browser check of the teacher on /lesson-demo: renders, speaks, paces, gestures, switches voice.

    python tools/qa/check_teacher.py [--male] [--reach] [--seconds 22] [--url http://127.0.0.1:3001/lesson-demo]

Start the demo first (`python tools/dev_demo/run.py --prerender`). The check opens a headless browser with software 3D
(no GPU needed), presses Listen and reports:

  * which teacher showed (3D or the 2D fallback) and how long from the click until she was speaking;
  * for each sentence whether it played from a compiled lecture or live, and the 1 s pause before it;
  * the gestures that fired and when (planned versus played);
  * the silences between speech at the avatar's audio output (the pauses; the mouth is shut in them).

--male    then switch the Teacher voice dropdown to the male teacher, wait for him to load, and have him speak too.
--reach   also force the widest gestures (an arm out to each side, a raised hand) and save screenshots, to check an
          outstretched arm is not cut off by the edge of the stage.

Screenshots go to tools/qa/out/. Exit code 1 if the page logged an error or she never started speaking.
Needs: pip install aiohttp; and Edge, Chrome or Chromium (or set EDAPTIVE_BROWSER).
"""
import argparse
import asyncio
import json
import sys
import time

from _cdp import Browser

# Test hooks: the avatar code records sentences and gestures into these arrays only if a test created them first.
HOOK = """
window.__gestures = []; window.__audio = []; window.__tl = [];
(() => {
  const connect = AudioNode.prototype.connect;
  const seen = new WeakSet();
  AudioNode.prototype.connect = function (...args) {
    if (this instanceof AudioWorkletNode && !seen.has(this)) {
      seen.add(this);
      const analyser = this.context.createAnalyser(); analyser.fftSize = 1024;
      connect.call(this, analyser);
      const buffer = new Float32Array(1024);
      setInterval(() => { analyser.getFloatTimeDomainData(buffer); let peak = 0; for (const v of buffer) peak = Math.max(peak, Math.abs(v)); window.__tl.push([performance.now(), peak]); }, 40);
    }
    return connect.apply(this, args);
  };
})();
"""
SELECT_VOICE = """
(() => { const s = document.querySelector('select'); const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
  set.call(s, '%s'); s.dispatchEvent(new Event('change', { bubbles: true })); })()
"""
CLICK = "[...document.querySelectorAll('button')].find(b => /%s/i.test(b.innerText))?.click()"


async def speak(page, label, seconds):
    """Press Listen, time it to speaking, and report what the avatar did."""
    await page.ev("window.__gestures.length = 0; window.__audio.length = 0; window.__tl.length = 0; window.__clickAt = performance.now();")
    await page.ev(CLICK % "listen")
    started = time.time()
    speaking = None
    while time.time() - started < seconds:
        if speaking is None and "Listen and follow" in (await page.ev("document.querySelector('[role=status]')?.innerText || ''")):
            speaking = time.time() - started
        await asyncio.sleep(0.1)
    print(f"\n[{label}] click -> speaking: " + (f"{speaking:.2f} s" if speaking is not None else "NEVER"))
    sentences = json.loads(await page.ev("JSON.stringify(window.__audio)"))
    print(f"[{label}] sentences:", [(s["caption"][:22], f"gap {s['gapBeforeMs']} ms", "compiled" if s["compiled"] else "live") for s in sentences[:6]])
    gestures = json.loads(await page.ev("JSON.stringify(window.__gestures)"))
    print(f"[{label}] gestures (planned ms -> played ms):", [(g["name"], g["plannedMs"], g["playedMs"]) for g in gestures])
    timeline = json.loads(await page.ev("JSON.stringify(window.__tl)"))
    silences, talking, last = [], False, None
    for at, peak in timeline:
        if peak > 0.02 and not talking:
            talking = True
            if last is not None:
                silences.append(round((at - last) / 1000, 2))
        elif peak <= 0.02 and talking:
            talking, last = False, at
    print(f"[{label}] silences between speech bursts (s):", silences, "<- each pause is the 1 s gap plus the voice's own padding")
    return speaking is not None


async def reach(page, tag):
    box = await page.rect("div[role=img]")
    for name, mirror in [("side", False), ("side", True), ("handup", True), ("index", False)]:
        await page.ev(f"window.__head.playGesture('{name}', 3, {str(mirror).lower()}, 600)")
        await asyncio.sleep(1.5)
        await page.shot(f"{tag}-reach-{name}-{'R' if mirror else 'L'}.png", box)
        await page.ev("window.__head.stopGesture(300)")
        await asyncio.sleep(0.7)
    print(f"[{tag}] reach screenshots saved in tools/qa/out/")


async def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://127.0.0.1:3001/lesson-demo")
    parser.add_argument("--seconds", type=int, default=22)
    parser.add_argument("--male", action="store_true")
    parser.add_argument("--reach", action="store_true")
    args = parser.parse_args()

    ok = True
    async with Browser() as page:
        await page.goto(args.url, HOOK)
        for _ in range(90):
            await asyncio.sleep(1)
            mode = await page.ev("document.querySelector('div[role=img] canvas') ? '3d' : (document.querySelector('div[role=img] svg') ? '2d' : '')")
            if mode and (mode == "2d" or await page.ev("!!window.__head")):
                break
        print("teacher shown:", {"3d": "3D teacher", "2d": "2D cartoon (fallback)"}.get(mode, "nothing"))
        await asyncio.sleep(3)
        if mode == "3d":
            await page.shot("female.png", await page.rect("div[role=img]"))
            if args.reach:
                await reach(page, "female")
        ok &= await speak(page, "female", args.seconds)
        if args.male:
            await page.ev(SELECT_VOICE % "am_michael")
            for _ in range(240):
                await asyncio.sleep(0.5)
                if "Changing teacher" not in await page.ev("document.querySelector('div[role=img]')?.innerText || ''"):
                    break
            await asyncio.sleep(2)
            await page.shot("male.png", await page.rect("div[role=img]"))
            print("switched to the male teacher; screenshot tools/qa/out/male.png; canvases:", await page.ev("document.querySelectorAll('div[role=img] canvas').length"))
            if args.reach and mode == "3d":
                await reach(page, "male")
            ok &= await speak(page, "male", args.seconds)
        print("\nconsole errors:", page.errors or "none")
    sys.exit(0 if ok and not page.errors else 1)


if __name__ == "__main__":
    asyncio.run(main())
