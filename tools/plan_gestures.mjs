#!/usr/bin/env node
// Plan the teacher's gestures for lecture parts ahead of time, with the same code the browser uses.
// Reads {"parts":[{"kind","seed","sentences":[{"caption","startMs","speechMs"}]}]} on stdin and prints
// {"plans":[[{"atMs","name","seconds","mirror"}...]...]}. Called by voice_service/lecture.py.
import { planPart } from "../frontend/src/features/avatar/gestures.mjs";

let input = "";
process.stdin.setEncoding("utf8");
for await (const chunk of process.stdin) input += chunk;
const { parts } = JSON.parse(input);
process.stdout.write(JSON.stringify({ plans: parts.map(part => planPart(part.kind, part.sentences, part.seed ?? 0)) }));
