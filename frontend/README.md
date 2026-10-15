# Frontend

Next.js + TypeScript. Owns the declarative widget engine, avatar, voice, lesson player and
replay (Track B), the verification badge (Track A), and the home/profile, timetable,
progress, attention and parent screens (Track C).

```bash
make dev-frontend     # http://localhost:3000, /api proxied to the backend on :8000
```

Each folder in `src/features/` names its owner. Import other features only through their
`index.ts`; types come from `src/contracts/generated` (run `make gen`, never hand-edit).
