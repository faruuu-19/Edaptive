// Each child picks a colour; their tile shows it with the first letter of their name.
// Keys are stored as the profile's avatar_key. Older keys (and "default") fall back to mustard.
export const AVATAR_COLOURS: Record<string, { label: string; fill: string }> = {
  mustard: { label: "Mustard", fill: "#e3a92b" },
  teal: { label: "Teal", fill: "#7cc2be" },
  tomato: { label: "Tomato", fill: "#f09a84" },
  plum: { label: "Plum", fill: "#b9a3d6" },
  leaf: { label: "Leaf", fill: "#a8cf8e" },
};

export const DEFAULT_AVATAR = "mustard";

export const avatarFill = (key: string) => (AVATAR_COLOURS[key] ?? AVATAR_COLOURS[DEFAULT_AVATAR]).fill;
