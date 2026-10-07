import type { Metadata } from "next";
import "./globals.css";

// No next/font/google here: Edaptive must build and run fully offline.
export const metadata: Metadata = {
  title: "Edaptive",
  description: "Local, offline homeschool tutor for Grades 1-5",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
