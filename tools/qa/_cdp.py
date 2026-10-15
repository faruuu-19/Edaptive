"""A tiny Chrome DevTools Protocol helper for the browser checks in this folder. Needs `aiohttp` (pip install aiohttp).

Starts a headless Chromium-family browser (Edge, Chrome or Chromium) with software 3D, so no GPU is needed, and gives a
`Page` with just what the checks use. Set EDAPTIVE_BROWSER to a browser executable to override the automatic choice.
"""
import asyncio
import base64
import json
import os
import shutil
import socket
import subprocess
import tempfile
import urllib.request
from pathlib import Path

import aiohttp

OUT = Path(__file__).resolve().parent / "out"  # screenshots; git-ignored

CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "msedge", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
]


def find_browser() -> str:
    chosen = os.environ.get("EDAPTIVE_BROWSER")
    if chosen:
        return chosen
    for candidate in CANDIDATES:
        found = candidate if os.path.isfile(candidate) else shutil.which(candidate)
        if found:
            return found
    raise SystemExit("No Edge, Chrome or Chromium found. Install one or set EDAPTIVE_BROWSER to its executable.")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Page:
    def __init__(self, ws):
        self.ws, self._n, self.errors = ws, 0, []

    async def call(self, method, params=None):
        self._n += 1
        mid = self._n
        await self.ws.send_json({"id": mid, "method": method, "params": params or {}})
        while True:
            message = await self.ws.receive_json()
            if message.get("id") == mid:
                return message.get("result", message.get("error"))
            kind = message.get("method")
            if kind == "Runtime.exceptionThrown":
                detail = message["params"]["exceptionDetails"]
                self.errors.append("EXCEPTION: " + str(detail.get("exception", {}).get("description", detail.get("text")))[:300])
            elif kind == "Log.entryAdded" and message["params"]["entry"]["level"] == "error":
                entry = message["params"]["entry"]
                if "auth/status" not in entry.get("url", "") + entry["text"]:  # the demo runs without the backend
                    self.errors.append("LOG error: " + entry["text"][:200] + " " + entry.get("url", ""))

    async def ev(self, expression):
        result = await self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
        return result["result"].get("value")

    async def rect(self, selector):
        return json.loads(await self.ev(f"JSON.stringify(document.querySelector({json.dumps(selector)}).getBoundingClientRect())"))

    async def shot(self, name, clip=None):
        params = {"format": "png"}
        if clip:
            params["clip"] = {"x": clip["x"], "y": clip["y"], "width": clip["width"], "height": clip["height"], "scale": 1}
        data = await self.call("Page.captureScreenshot", params)
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / name).write_bytes(base64.b64decode(data["data"]))

    async def goto(self, url, init_script=None, width=1100, height=900):
        await self.call("Runtime.enable")
        await self.call("Log.enable")
        await self.call("Page.enable")
        await self.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False})
        if init_script:
            await self.call("Page.addScriptToEvaluateOnNewDocument", {"source": init_script})
        await self.call("Page.navigate", {"url": url})


class Browser:
    """`async with Browser() as page:` starts the browser, gives its first tab, and always closes it."""

    async def __aenter__(self):
        port = _free_port()
        self.profile = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.proc = subprocess.Popen(
            [find_browser(), "--headless=new", f"--remote-debugging-port={port}", "--autoplay-policy=no-user-gesture-required",
             "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
             "--window-size=1100,900", f"--user-data-dir={self.profile.name}", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        tab = None
        for _ in range(60):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2))
                tab = next(t for t in tabs if t["type"] == "page")
                break
            except Exception:
                await asyncio.sleep(0.5)
        if tab is None:
            self.proc.terminate()
            raise SystemExit("The browser did not start.")
        self.session = aiohttp.ClientSession()
        self.ws = await self.session.ws_connect(tab["webSocketDebuggerUrl"], max_msg_size=0)
        return Page(self.ws)

    async def __aexit__(self, *exc):
        await self.ws.close()
        await self.session.close()
        self.proc.terminate()
        self.profile.cleanup()
