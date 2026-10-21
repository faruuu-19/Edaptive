export const LOOK_KEY = "edaptive-look";
export type Look = "playful" | "storybook";

/** Runs before first paint: `?look=storybook` (or `playful`) is remembered on this device. */
export const LOOK_BOOTSTRAP = `(function(){try{var q=new URLSearchParams(location.search).get("look");if(q==="storybook"||q==="playful")localStorage.setItem("${LOOK_KEY}",q);document.documentElement.dataset.theme=localStorage.getItem("${LOOK_KEY}")==="storybook"?"storybook":"playful"}catch(e){}})();`;

export function readLook(): Look {
  return document.documentElement.dataset.theme === "storybook" ? "storybook" : "playful";
}

export function applyLook(look: Look) {
  document.documentElement.dataset.theme = look;
  try {
    localStorage.setItem(LOOK_KEY, look);
  } catch {
    /* private mode: the look still applies for this visit */
  }
}
