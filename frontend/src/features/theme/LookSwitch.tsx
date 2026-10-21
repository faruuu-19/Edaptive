"use client";

import { useSyncExternalStore } from "react";

import { applyLook, readLook, type Look } from "./look";

/** Parent-area switch between the Playful look and the original Storybook look (kept on this device). */
// The current look lives on <html data-theme>; this follows it without copying it into state.
function subscribe(notify: () => void) {
  const observer = new MutationObserver(notify);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => observer.disconnect();
}

export function LookSwitch() {
  const look = useSyncExternalStore<Look>(subscribe, readLook, () => "playful");

  function choose(next: Look) {
    applyLook(next);
  }

  return (
    <div className="card row spread" role="group" aria-label="App look">
      <div>
        <div className="eyebrow">App look</div>
        <p className="muted" style={{ margin: "4px 0 0" }}>
          Playful is the colourful scene. Storybook is the original calm paper look.
        </p>
      </div>
      <div className="row">
        {(["playful", "storybook"] as const).map((value) => (
          <button
            key={value}
            className={`btn ${look === value ? "btn-primary" : ""}`}
            aria-pressed={look === value}
            onClick={() => choose(value)}
          >
            {value === "playful" ? "Playful" : "Storybook"}
          </button>
        ))}
      </div>
    </div>
  );
}
