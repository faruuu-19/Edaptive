# Credits for the 3D teacher models

| File | Teacher | Author |
|---|---|---|
| `teacher.glb` | Female teacher in a tweed suit ("Teacher Female Narration 01", distributed as "animated-female-teacher-for-narration") | **LasquetiSpice** |
| `teacher-male.glb` | Male teacher (`mechar`, distributed as "teacher-char-3d") | **pendekaralahmad** |

The meshes, textures, skeletons and blendshapes are the authors' work. The files here were **modified** only by
`tools/prepare_avatar_glb.py`: blendshape names were copied to where the loader looks for them, empty eye-gaze and tongue
shapes were added so the avatar library's lookups succeed, and the root object was renamed `Armature`. Nothing was
re-modelled.

**Licence: not yet confirmed.** The licence terms of these two models were not recorded when the files were obtained.
The authors are credited above as their creators. Before wider or commercial distribution, confirm the licence at the
original source and update this file; if it does not allow redistribution, remove the two `.glb` files (they stay in git
history, so removal needs a history clean-up) and see `docs/voice/TEACHER_AVATAR.md` for how to use your own models.

## Software

* [TalkingHead](https://github.com/met4citizen/TalkingHead) by Mika Suominen (MIT): the 3D avatar's lip-sync, blinking and gestures.
* [three.js](https://threejs.org) (MIT): 3D rendering.
