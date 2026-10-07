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

## Open decision (team): mechanism

Proposed, offline-first: children pick their profile (no child passwords); a parent PIN,
stored only as a hash, unlocks parent-only areas; a short-lived HTTP-only session cookie;
no accounts, cloud identity or admin role. Confirm against the proposal before building.

## When this lands

- Turn on actor checks for `POST/GET /api/events`: the event's `student_id` must pass
  `ensure_student_access`.
- Parent, consent, scheduling-controls and privacy endpoints use `ParentActor`.
