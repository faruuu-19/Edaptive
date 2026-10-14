# Parent dashboard

Owner: Ibrahim / Track C, with the local integration requested by Amna. Public API: `ParentDashboard` through `index.ts`. Child profile rows in the original parent Children screen open `/parent/<student_id>`. The original home/profile theme and existing Edit/Remove controls are preserved; the reference prototype's design was not imported.

The route is PIN-gated by the existing `ParentGate`. Viewing a dashboard keeps the parent session and loads that child's real profile, saved daily start-time routine, and saved camera/microphone consent via shared API clients. A parent supplies only `HH:MM`; the system keeps responsibility for dates, lesson choice, preparation, duration and breaks. Permissions are application consent choices and do not request or activate sensor input. All permission choices start denied and survive refresh through local Postgres; teacher voice output is independent of microphone permission.

Progress chart and evaluation feedback are deliberately **sample data** in this stage, visibly labelled in each section. These are frontend-only fixtures, never written to the session log, mastery state, assessment results or the database. They will be replaced by the corresponding real modules. The sample graph covers Maths only; no Science/English teaching functionality is implemented.

The dashboard uses existing theme tokens, Fraunces/Andika fonts, native form labels, keyboard-accessible links/buttons, and a single-column layout below 680 px. No cloud chart library, external font, media API or model call is used by the dashboard itself. Saving the real daily school time can trigger the existing system's scheduled lesson preparation.
