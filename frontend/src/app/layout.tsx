import { ScheduledAlarm } from "@/features/lesson-player";
import type { Metadata } from "next";

// Fonts are bundled from npm (@fontsource, OFL licence) so the app works fully offline.
// Fraunces for headings; Andika (designed for beginning readers) for everything else.
import "@fontsource/andika/400.css";
import "@fontsource/andika/700.css";
import "@fontsource/fraunces/600.css";
import "@fontsource/fraunces/800.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Edaptive",
  description: "Local, offline homeschool tutor for Grades 1-5",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body><ScheduledAlarm />{children}</body>
    </html>
  );
}
