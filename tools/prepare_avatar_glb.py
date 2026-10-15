#!/usr/bin/env python3
"""Make a rigged GLB loadable by the 3D teacher (TalkingHead). Python standard library only.

    python tools/prepare_avatar_glb.py "My Teacher.glb" frontend/public/avatars/teacher.glb

Many exporters (Babylon.js and others) write the blendshapes without the names loaders look up, and leave out
ARKit shapes TalkingHead drives (eye gaze, tongue). This script, on a COPY of the file:

  1. copies the blendshape names from the accessor labels ("jawOpen - POSITION") to `mesh.extras.targetNames`,
     where three.js reads them (only if they are missing);
  2. adds any missing ARKit shape as an empty shape (zero movement), so TalkingHead's lookups never fail;
  3. renames the scene's root node to "Armature", TalkingHead's default root name.

It cannot invent the 15 mouth-sound shapes (viseme_*) or a skeleton: if those are missing it says so and stops.
Details: docs/voice/TEACHER_AVATAR.md.
"""
import argparse
import json
import struct
import sys

ARKIT = (
    "browDownLeft browDownRight browInnerUp browOuterUpLeft browOuterUpRight cheekPuff cheekSquintLeft cheekSquintRight "
    "eyeBlinkLeft eyeBlinkRight eyeLookDownLeft eyeLookDownRight eyeLookInLeft eyeLookInRight eyeLookOutLeft eyeLookOutRight "
    "eyeLookUpLeft eyeLookUpRight eyeSquintLeft eyeSquintRight eyeWideLeft eyeWideRight jawForward jawLeft jawOpen jawRight "
    "mouthClose mouthDimpleLeft mouthDimpleRight mouthFrownLeft mouthFrownRight mouthFunnel mouthLeft mouthLowerDownLeft "
    "mouthLowerDownRight mouthPressLeft mouthPressRight mouthPucker mouthRight mouthRollLower mouthRollUpper mouthShrugLower "
    "mouthShrugUpper mouthSmileLeft mouthSmileRight mouthStretchLeft mouthStretchRight mouthUpperUpLeft mouthUpperUpRight "
    "noseSneerLeft noseSneerRight tongueOut"
).split()
VISEMES = ["viseme_" + v for v in "sil PP FF TH DD kk CH SS nn RR aa E I O U".split()]
BONES = "Hips Spine Spine1 Spine2 Neck Head LeftEye RightEye LeftShoulder LeftArm LeftForeArm LeftHand RightShoulder RightArm RightForeArm RightHand LeftUpLeg LeftLeg LeftFoot RightUpLeg RightLeg RightFoot".split()


def read_glb(path):
    raw = open(path, "rb").read()
    magic, version, _total = struct.unpack("<4sII", raw[:12])
    if magic != b"glTF" or version != 2:
        sys.exit("Not a binary glTF 2 (.glb) file.")
    json_len, json_type = struct.unpack("<I4s", raw[12:20])
    if json_type != b"JSON":
        sys.exit("Unexpected GLB layout (first chunk is not JSON).")
    gltf = json.loads(raw[20:20 + json_len])
    rest = raw[20 + json_len:]
    if not rest:
        sys.exit("This GLB has no binary chunk.")
    bin_len, bin_type = struct.unpack("<I4s", rest[:8])
    if bin_type != b"BIN\x00" or len(rest) != 8 + bin_len:
        sys.exit("Unexpected GLB layout (expected exactly one BIN chunk after the JSON).")
    return gltf, bytearray(rest[8:8 + bin_len])


def target_names(gltf, mesh):
    named = mesh.get("extras", {}).get("targetNames")
    if named:
        return list(named)
    names = []
    for target in mesh["primitives"][0]["targets"]:
        label = gltf["accessors"][target["POSITION"]].get("name") or ""
        names.append(label.replace(" - POSITION", "").replace("_POSITION", ""))
    return names


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="the rigged .glb to read (never modified)")
    parser.add_argument("output", help="where to write the repaired copy")
    args = parser.parse_args()

    gltf, binary = read_glb(args.source)
    nodes = gltf["nodes"]
    joint_names = {nodes[j].get("name", "").replace("mixamorig:", "").replace("mixamorig", "") for skin in gltf.get("skins", []) for j in skin["joints"]}
    missing_bones = [b for b in BONES if b not in joint_names]
    if missing_bones:
        sys.exit("The skeleton is not Mixamo-compatible; missing bones: " + ", ".join(missing_bones))

    meshes = [m for m in gltf["meshes"] if m["primitives"] and m["primitives"][0].get("targets")]
    if not meshes:
        sys.exit("This model has no blendshapes (morph targets), so it cannot lip-sync. It needs the 52 ARKit and 15 viseme shapes.")

    added = set()
    for mesh in meshes:
        names = target_names(gltf, mesh)
        if not any(names):
            sys.exit("The blendshapes have no names anywhere in the file, so they cannot be matched to mouth sounds.")
        missing_visemes = [v for v in VISEMES if v not in names]
        if missing_visemes:
            sys.exit("Missing mouth-sound shapes (cannot be invented): " + ", ".join(missing_visemes))
        missing = [n for n in ARKIT if n not in names]
        if missing:
            position = gltf["accessors"][mesh["primitives"][0]["attributes"]["POSITION"]]["count"]
            binary.extend(b"\x00" * (-len(binary) % 4))
            gltf["bufferViews"].append({"buffer": 0, "byteOffset": len(binary), "byteLength": position * 12, "name": "empty shape deltas"})
            binary.extend(b"\x00" * (position * 12))  # one zero VEC3 per vertex, shared by every added shape
            gltf["accessors"].append({"bufferView": len(gltf["bufferViews"]) - 1, "componentType": 5126, "count": position,
                                      "type": "VEC3", "min": [0, 0, 0], "max": [0, 0, 0], "name": "empty shape - POSITION"})
            accessor = len(gltf["accessors"]) - 1
            for primitive in mesh["primitives"]:
                primitive["targets"].extend({"POSITION": accessor} for _ in missing)
            mesh["weights"] = list(mesh.get("weights", [0] * len(names))) + [0] * len(missing)
            names += missing
            added.update(missing)
        mesh.setdefault("extras", {})["targetNames"] = names
    gltf["buffers"][0]["byteLength"] = len(binary)

    root = gltf["scenes"][gltf.get("scene", 0)]["nodes"][0]
    renamed = nodes[root].get("name") != "Armature"
    nodes[root]["name"] = "Armature"

    body = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    body += b" " * (-len(body) % 4)
    binary.extend(b"\x00" * (-len(binary) % 4))
    out = (struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(body) + 8 + len(binary)) + struct.pack("<I4s", len(body), b"JSON") + body
           + struct.pack("<I4s", len(binary), b"BIN\x00") + bytes(binary))
    with open(args.output, "wb") as f:
        f.write(out)
    print(f"Wrote {args.output} ({len(out) / 1e6:.1f} MB)")
    print(f"  blendshapes: {len(names)} (added {len(added)} empty: {', '.join(sorted(added)) or 'none'})")
    print(f"  root renamed to Armature: {renamed}")


if __name__ == "__main__":
    main()
