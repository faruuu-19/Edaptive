## What & why

<!-- One or two lines. Link the module / iteration (e.g. Track C · Mid-1 · Curriculum Compiler). -->

## Checklist

- [ ] Only touches my track's paths, **or** this is a contract PR reviewed by all three tracks
- [ ] Contract changed? Ran `make gen` and committed the generated types; added/updated an example in `contracts/examples/`
- [ ] New event type? Registered in `contracts/events/registry.json` under my track's namespace
- [ ] `make check` passes locally (paste the last lines below)
- [ ] No paid API, cloud service or network call at runtime; no unverified LLM output reaches the UI
- [ ] Any child data added is minimal and consent-gated
