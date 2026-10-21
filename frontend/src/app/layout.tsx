import { ScheduledAlarm } from "@/features/lesson-player";
import { LOOK_BOOTSTRAP, Scenery } from "@/features/theme";
import type { Metadata } from "next";

// Fonts are bundled from npm (@fontsource, OFL licence) so the app works fully offline.
// Fraunces for headings; Andika (designed for beginning readers) for everything else.
import "@fontsource/andika/400.css";
import "@fontsource/andika/700.css";
import "@fontsource/fraunces/600.css";
import "@fontsource/fraunces/800.css";
// Light serif and italic serif used only by the Playful look (headings and accent words).
import "@fontsource/fraunces/300.css";
import "@fontsource/fraunces/300-italic.css";
import "./globals.css";
// Opt-in colourful look; the Storybook look in globals.css is what you get when it is switched off.
import "./theme-playful.css";

export const metadata: Metadata = {
  title: "Edaptive",
  description: "Local, offline homeschool tutor for Grades 1-5",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-theme="playful" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: LOOK_BOOTSTRAP }} />
      </head>
      <body><Scenery /><ScheduledAlarm />{children}</body>
    </html>
  );
}
