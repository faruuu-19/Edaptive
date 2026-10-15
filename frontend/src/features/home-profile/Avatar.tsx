import { avatarFill } from "./avatars";
import styles from "./home-profile.module.css";

export function Avatar({ name, avatarKey, size }: { name: string; avatarKey: string; size: number }) {
  return (
    <span
      className={styles.avatar}
      aria-hidden
      style={{ width: size, height: size, fontSize: size * 0.46, background: avatarFill(avatarKey) }}
    >
      {name.trim().charAt(0).toUpperCase()}
    </span>
  );
}
