"""A bank of teacher expressions, so the model is steered towards variety instead of one favourite opener.

None contains a number, a fact or a formula. {role} becomes the lesson metaphor (detective, builder, explorer).
"""
from __future__ import annotations

ROLE={'detectives':'detective','builders':'builder','explorers':'explorer'}

BANK={
    'hook':["Are you ready, {role}?","Your mission starts today, {role}!","You can join me, {role}!","You can come with me, {role}!","Your new adventure starts now!"],
    'lecture':["Let's look closely.","Here is something for you to notice.","You can watch how this works.","Let's find out together.","Here is your clue.","Let's take a careful look."],
    'worked_example':["You can watch me try this.","Let's see it in action.","Here is something for you to look at.","Let me show you how it goes.","You can come see this."],
    'watch_out':["You can slow down here, {role}.","Here is a tricky spot for you.","Let's slow down for a moment.","Let's watch this tricky spot."],
    'your_turn':["Now it is your turn.","Your thinking time.","Over to you, {role}.","You can take your time."],
    'transition':["Let’s move to the check-in.","You can share your thinking now.","You can try the check-in now!"],
    'question':["Take your time.","Here comes a question for you.","Think it through at your own pace.","You can do this."],
    'feedback_correct':["You did it!","Your thinking paid off!","You checked it carefully!","Your effort paid off!"],
    'feedback_incorrect':["You gave it a try.","Let's take another look.","You can try again.","Thank you for trying."],
    'feedback_unclear':["Could you say that again?","I did not quite catch your answer.","Could you tell me again?"],
    'hint':["Here is your clue.","You can try looking at it this way.","A little help for you.","Here is something for you to try."],
    'answer_reveal':["You kept going, and that matters.","Let's look at it now.","You can see how it works out."],
    'optional_practice':["Here is another question for you.","Your extra practice is ready.","A bonus for you, {role}.","You can try this if you like."],
    'recap':["Let’s remember the ideas we explored.","Here is your closing reminder.","You can keep noticing these clues."],
}

def purpose(segment):
    phase=segment.get('phase')
    if phase=='feedback':return 'feedback_'+str(segment.get('outcome') or 'incorrect') if segment.get('outcome') in ('correct','incorrect','unclear') else 'feedback_incorrect'
    if phase in ('hint','hint_bank'):return 'hint'
    if phase=='answer_reveal':return 'answer_reveal'
    if phase=='optional_practice':return 'optional_practice'
    if phase=='your_turn':return 'your_turn'
    if phase in ('root_question','follow_up_question'):return 'question'
    return segment.get('type') if segment.get('type') in BANK else 'transition'

def suggest(segment,metaphor,recent,count=3):
    """Up to `count` openers for this kind of segment that were not used recently. Deterministic: rotates by segment id."""
    role=ROLE.get(metaphor,'learner');options=[o.format(role=role) for o in BANK[purpose(segment)]]
    recent=[r.lower() for r in recent]
    fresh=[o for o in options if not any(o.lower().startswith(r) or r.startswith(o.lower()[:len(r)]) for r in recent if r)]
    pool=fresh or options
    try:start=int(str(segment.get('id','0')).split('_')[-1])
    except ValueError:start=0
    return [pool[(start+n)%len(pool)] for n in range(min(count,len(pool)))]
