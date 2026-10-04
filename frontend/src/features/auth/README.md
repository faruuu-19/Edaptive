# auth

**Owner:** Track C · **Ships in:** Mid-1

Parent gate (unlock/lock parent-only areas) and the current-actor state the rest of the UI
reads. Identity hierarchy: household → parent → students; the shape is the `Actor` type in
`@/contracts/generated`.

Other features never handle PINs, cookies or tokens. They ask this feature who is acting
(via its `index.ts`), and parent-only screens are wrapped by its gate.

Other features import only from `@/features/auth`, never from files inside it.
