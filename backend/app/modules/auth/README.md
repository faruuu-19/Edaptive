# auth

**Owner:** Track C · **Ships in:** Mid-1 (alongside profiles)

Establishes who is acting and hands every other module an `Actor`
(`contracts/auth/actor.schema.json`). Identity hierarchy: **household → parent → students**.

## Contract with the rest of the system

- Other modules never read tokens, cookies or PINs. They depend on `CurrentActor` /
  `ParentActor` and call `ensure_student_access` from `app.core.identity`.
- This module installs the resolver from `router.py`:

  ```python
  router = APIRouter()


  def on_mount(api):
      install_actor_resolver(api, resolve_actor_from_request)
  ```

- Auth events go in the `auth.*` namespace (registered to Track C), e.g. parent unlocked or
  locked. Never log PINs, tokens or anything secret in an event payload.

## Mechanism (implemented; confirm with the team)

- **First run:** the parent creates a 4–6 digit PIN (`POST /api/auth/setup`). One household
  per installation.
- **Children:** pick their profile from the picker (`POST /api/auth/student`); no child
  passwords. Each pick is logged as `profile.selected`.
- **Parent:** unlocks parent-only areas with the PIN (`POST /api/auth/parent`). 5 wrong PINs
  lock it for 5 minutes.
- **Sessions:** HTTP-only, SameSite=Strict cookie. Only a SHA-256 of the token is stored.
  Parent sessions last 15 minutes, student sessions 12 hours. Archiving a profile signs that
  child out immediately.
- PINs are stored as salted scrypt hashes (Python standard library, no extra dependency).
- No accounts, no cloud identity, no admin role.

The session log (`/api/events`) now requires a signed-in actor: students can read and write
only their own events, and parents can access any of their children's.
