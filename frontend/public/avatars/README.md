# Teacher models

The 3D teachers shown beside the lesson:

- `teacher.glb`: shown for a female voice (author: LasquetiSpice)
- `teacher-male.glb`: shown for a male voice (author: pendekaralahmad)

**Credits and licence status: [CREDITS.md](CREDITS.md).** The authors are credited; their licence terms are not yet confirmed.

Each must be a rigged full-body GLB with the 52 ARKit and 15 viseme blendshapes. To use your own, prepare it with
`python tools/prepare_avatar_glb.py <source.glb> frontend/public/avatars/teacher.glb` (and `teacher-male.glb`).
Full guide: `docs/voice/TEACHER_AVATAR.md`. Without these files the 2D cartoon teacher is shown.
