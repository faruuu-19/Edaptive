// Which gesture goes with what the teacher is saying. Plain JavaScript on purpose: the browser plays with it live
// and `tools/plan_gestures.mjs` runs the very same code under Node when a lecture is compiled ahead of time
// (voice_service/lecture.py), so there is one set of rules, not two. Types: gestures.d.mts.
//
// Names are TalkingHead's `playGesture` names: hand gestures (handup, index, ok, thumbup, thumbdown, side, shrug,
// namaste) and emoji animations, which are a facial expression, sometimes with a hand (✋ wave, 👍, 👌, 🤷).
//
// Planning is deterministic and runs sentence by sentence:
//  1. the first sentence of a part gets that part type's opening gesture;
//  2. otherwise a sentence that matches a text cue gets that cue's gesture;
//  3. otherwise most sentences get a rotating "beat" gesture, so she keeps moving naturally;
//  4. a long sentence gets a second gesture around its middle.
// Gestures keep a minimum spacing so they never pile up, never repeat the one just used, and the hands alternate.
//
// Only gestures that keep the mouth closed are used. TalkingHead's grin, big grin, wink and surprised faces open
// the jaw, which would open her mouth in the 1 s gaps between sentences.

/** Lesson part types (`kind` in the script) and the gestures that open each; they take turns so it is not always the same. */
const OPENERS = {
  hook: [{ name: "✋", seconds: 2.2 }], // always a wave hello: it is the start of the lesson
  lecture: [{ name: "😊", seconds: 2.4 }, { name: "side", seconds: 2.2 }], // a warm start to an explanation
  worked_example: [{ name: "index", seconds: 2.4 }, { name: "side", seconds: 2.2 }, { name: "😊", seconds: 2.4 }], // "let's work it out"
  transition: [{ name: "side", seconds: 2.2 }, { name: "👌", seconds: 2.2 }], // "your turn": open hand toward the child
  question: [{ name: "🤔", seconds: 2.6 }, { name: "side", seconds: 2.4 }], // think about it
  watch_out: [{ name: "index", seconds: 2.6 }, { name: "🤔", seconds: 2.4 }], // careful: raised finger
  recap: [{ name: "👍", seconds: 2.4 }, { name: "👌", seconds: 2.2 }, { name: "😊", seconds: 2.4 }], // what we learned: well done
};

/** First match wins, so the more specific cues come first. */
const RULES = [
  { when: /\b(hello|hi there|welcome|good (morning|afternoon)|let'?s (begin|start)|mission starts)\b/i, name: "✋", seconds: 2.2 },
  { when: /\b(thank you|thanks|goodbye|bye|see you)\b/i, name: "✋", seconds: 2.2 },
  { when: /\b(great|well done|good job|excellent|fantastic|amazing|awesome|nice work|you did it|that'?s right|correct|exactly|perfect|brilliant|super|good thinking)\b/i, name: "👍", seconds: 2.2 },
  { when: /\b(wow|hooray|yay|fun|surprise|guess what)\b/i, name: "😊", seconds: 2.4 },
  { when: /\b(you can do this|you'?ve got this|take your time|no rush|doing great|together|detective|team|friend)\b/i, name: "😊", seconds: 2.4 },
  { when: /\b(careful|watch out|don'?t forget|remember|be sure|make sure|mistake|tricky|oops|not quite|slow down|wait)\b/i, name: "index", seconds: 2.6 },
  { when: /\b(look|notice|watch|spot|check|see (how|that|what)|show|point|here is|this is|these are)\b/i, name: "index", seconds: 2.2 },
  { when: /\b(maybe|might|not sure|perhaps|could be|it depends|sometimes)\b/i, name: "🤷", seconds: 2.4 },
  { when: /\b(think|wonder|guess|predict|imagine|picture|hmm|what if|why|how (many|much|do|can))\b|\?\s*$/i, name: "🤔", seconds: 2.4 },
  { when: /\b(first|second|third|next|then|finally|step|now|after|before|last)\b/i, name: "side", seconds: 2 },
  { when: /\b(more|less|bigger|smaller|greater|fewer|same|different|compare|altogether|total|whole|parts?)\b/i, name: "side", seconds: 2.2 },
  { when: /\b(you|your|you'?re|let'?s|we)\b.*\b(try|turn|choose|pick|say|tell|find|name|solve|count|draw|write|take|make|use)\b/i, name: "side", seconds: 2.2 },
  { when: /\b(listen|hear|sound|say)\b/i, name: "index", seconds: 2 },
  { when: /\b(yes|okay|ok|got it|right|sure|fine)\b/i, name: "👌", seconds: 2 },
  { when: /\w+\W+\w+\W+\w+.*!\s*$/, name: "😊", seconds: 2.4 }, // an excited sentence of three or more words
];

/** Gentle gestures for sentences with no cue, in turn, so there is always something natural going on. */
const BEATS = [
  { name: "side", seconds: 2 },
  { name: "🙂", seconds: 2.2 },
  { name: "index", seconds: 2 },
  { name: "😊", seconds: 2.2 },
  { name: "👌", seconds: 2 },
];

/** Shortest spacing between two gestures, the shortest sentence worth one, and the length that earns a second. */
export const MIN_SPACING_MS = 2500;
export const MIN_SENTENCE_MS = 1100;
export const LONG_SENTENCE_MS = 4500;
/** Every Nth sentence without a cue is left still, so she does not move on every single line. */
const BEAT_EVERY = 4;

export class GesturePlanner {
  /** @param {number} [seed] where the opener and beat rotations start, so parts planned separately still vary */
  constructor(seed = 0) {
    this.seed = seed;
    this.lastAtMs = -Infinity;
    this.lastName = "";
    this.mirror = false;
    this.opened = false;
    this.sentences = 0;
    // These survive reset(): the openers and the beats keep taking turns from one part to the next.
    this.openerTurn = seed;
    this.beatTurn = seed;
  }

  reset() {
    this.lastAtMs = -Infinity;
    this.lastName = "";
    this.mirror = false;
    this.opened = false;
    this.sentences = 0;
  }

  /**
   * The gestures for one sentence (none, one, or two for a long one).
   * `startMs` is when she starts speaking it, `speechMs` how long she speaks.
   */
  plan(kind, caption, startMs, speechMs) {
    if (speechMs < MIN_SENTENCE_MS) return [];
    const out = [];
    const index = this.sentences++;
    let choice;
    if (!this.opened) {
      this.opened = true; // the first sentence of a part is the part's opening gesture, if it has one
      const options = OPENERS[kind];
      choice = options ? options[this.openerTurn++ % options.length] : undefined;
    }
    choice ??= RULES.find(rule => rule.when.test(caption));
    if (choice && choice.name === this.lastName) choice = undefined; // never the same twice in a row; fall to a beat
    choice ??= index % BEAT_EVERY === BEAT_EVERY - 1 ? undefined : this.beat();
    const first = choice && this.place(choice, startMs, speechMs);
    if (first) out.push(first);
    if (speechMs >= LONG_SENTENCE_MS) {
      const at = startMs + speechMs * 0.55;
      const second = this.place(this.beat(), at, startMs + speechMs - at);
      if (second) out.push(second);
    }
    return out;
  }

  beat() {
    for (let tries = 0; tries < BEATS.length; tries++) {
      const choice = BEATS[this.beatTurn++ % BEATS.length];
      if (choice.name !== this.lastName) return choice;
    }
    return BEATS[0];
  }

  place(choice, atMs, availableMs) {
    if (atMs - this.lastAtMs < MIN_SPACING_MS) return null;
    this.lastAtMs = atMs;
    this.lastName = choice.name;
    this.mirror = !this.mirror;
    // Single-hand gestures swap hands in turn; two-handed or face-only ones are unaffected.
    return { atMs, gesture: { name: choice.name, seconds: Math.min(choice.seconds, availableMs / 1000), mirror: this.mirror } };
  }
}

/**
 * Plan a whole part ahead of time (what `tools/plan_gestures.mjs` runs when a lecture is compiled).
 * `sentences` are `{ caption, startMs, speechMs }` in the order she speaks them.
 */
export function planPart(kind, sentences, seed = 0) {
  const planner = new GesturePlanner(seed);
  const plan = [];
  for (const sentence of sentences) {
    for (const placed of planner.plan(kind, sentence.caption, sentence.startMs, sentence.speechMs)) {
      plan.push({ atMs: placed.atMs, name: placed.gesture.name, seconds: placed.gesture.seconds, mirror: placed.gesture.mirror });
    }
  }
  return plan;
}
