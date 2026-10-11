# Contracts

The only things the three tracks share. Build against these, never against another
module's internals. Everything here is JSON Schema (draft 2020-12).

| Path | What | Owner |
|---|---|---|
| `common/ids.schema.json` | UUIDs, curriculum node ids (`math.g3.m5.l1`), subject, grade | all |
| `events/envelope.schema.json` | Shape of every session-log event | all |
| `events/registry.json` | Every allowed event type, its version and payload schema; namespace → owning track | all (each track edits its own namespaces) |
| `events/payloads/*.vN.schema.json` | Payload per event type and version | namespace owner |
| `auth/actor.schema.json` | Who is acting (household → parent → students); every module reads it | Track C |
| `curriculum/node.schema.json` | Curriculum graph node | Track C |
| `examples/` | One valid instance per contract; tests validate them | whoever changes the contract |

## Rules

1. **The session log rejects anything not in `events/registry.json`.** To emit a new event, add a
   payload schema under your track's namespace, register it, and add an example.
2. **Additive changes only** within a version: new optional fields are fine. Removing a field,
   renaming it, making it required, or narrowing an enum is a breaking change: create
   `<type>.v2.schema.json`, bump `version` in the registry, and keep v1 until every reader is
   moved over.
3. **Never reuse or renumber a curriculum node id** once data references it.
4. After any change run `make gen` and commit the regenerated types
   (`frontend/src/contracts/generated`). `make check` fails if they are stale.
5. Contract PRs are small, separate from feature work, and approved by **all three tracks**.
