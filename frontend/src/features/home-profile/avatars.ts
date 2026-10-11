// Picker icons a child recognises without reading. Keys are stored on the profile.
export const AVATARS: Record<string, string> = {
  default: "🙂",
  lion: "🦁",
  panda: "🐼",
  fox: "🦊",
  owl: "🦉",
  turtle: "🐢",
  frog: "🐸",
  rocket: "🚀",
  star: "⭐",
};

export const avatarFor = (key: string) => AVATARS[key] ?? AVATARS.default;
