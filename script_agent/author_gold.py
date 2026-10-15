"""Handwritten teacher templates, paired with verbatim real card content; no model calls."""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
from .planner import plan_lesson
from .generator import generate_lesson,write_lesson

GOLD={
'grade1':{
 'metaphor':'detectives',
 'hook':['Ready, detective? You can find hidden clues today! 🔎 <CONTENT>'],
 'lecture':["You can look for a hidden clue. <CONTENT>","Let's look at how the clues fit. <CONTENT>","Now you can spot a group. <CONTENT>","Your hands can help you look for clues. <CONTENT>"],
 'worked_example':["Let's try this together. <CONTENT>","You can follow along with me. <CONTENT>"],
 'your_turn':["What do you notice, detective? <CONTENT>","What would you try next? <CONTENT>","Can you tell me what helped you? <CONTENT>","What clue would you look for? <CONTENT>"],
 'watch_out':["You can pause and take another look. <CONTENT>"],
 'transition':["Now it's your turn, detective. Tell me what you think. <CONTENT>"],
 'question':["You can take your time. <CONTENT>","Let's look for the next clue. <CONTENT>","You can tell me how you think about it. <CONTENT>"],
 'recap':["You worked hard, detective! 🌟 <CONTENT> What helped you today?"]},
'area_perimeter':{
 'metaphor':'builders',
 'hook':["Welcome to the building crew! 🛠️ You get to plan with me today. <CONTENT>"],
 'lecture':["Let's walk through our plan together. <CONTENT>","You can keep this handy in your building kit. <CONTENT>","Now let's look closely at our building plan. <CONTENT>","You can pause and look for a useful clue. <CONTENT>","Let's explore the choices in our plan. <CONTENT>","Before you finish, check the labels in your plan. <CONTENT>"],
 'worked_example':["Let's work through this plan together. <CONTENT>","You can follow the steps at your own pace. <CONTENT>","Here's another plan for you to explore. <CONTENT>","Let's check our work together. <CONTENT>","You can look for the clue that helps us start. <CONTENT>","Stay with me as we work through this plan. <CONTENT>","Let's compare the choices in our building kit. <CONTENT>"],
 'your_turn':["What would you check in your plan? <CONTENT>","Can you talk me through how you would start? <CONTENT>","What would you pay attention to here? <CONTENT>","What clue would help you begin? <CONTENT>","How would you check your reasoning? <CONTENT>","What would you check before you finish? <CONTENT>"],
 'watch_out':["You can stop and check your plan with me. <CONTENT>"],
 'transition':["Your building kit is ready. Let's try the check-in together! <CONTENT>"],
 'question':["You're in charge of this plan. Take your time. <CONTENT>","Let's see how you would approach the next plan. <CONTENT>","You've reached a new challenge. Tell me how you think it through. <CONTENT>"],
 'recap':["You kept thinking and checking like a careful builder! 🌟 <CONTENT> How would you explain your approach?"]},
'shape_attributes':{
 'metaphor':'explorers',
 'hook':["Come exploring with me! You can look for clues as we go. 🧭 <CONTENT>"],
 'lecture':["Let's look closely, explorer. <CONTENT>","You can pause and notice where the clues meet. <CONTENT>","Now let's try the next activity together. <CONTENT>","You can compare the clues with me. <CONTENT>"],
 'worked_example':["Let's follow this carefully together. <CONTENT>","You can look closely at this example. <CONTENT>"],
 'your_turn':["What would you look for first? <CONTENT>","What can you notice here? <CONTENT>","How would you check your work? <CONTENT>","What clues would you compare? <CONTENT>"],
 'watch_out':["You can stop and look again. <CONTENT>","Let's check the clues carefully together. <CONTENT>"],
 'transition':["You're ready to explore the check-in. Tell me what you think! <CONTENT>"],
 'question':["You can look for the clues at your own pace. <CONTENT>","Let's explore the next question together. <CONTENT>","Take your time with this challenge, explorer. <CONTENT>"],
 'recap':["You looked closely and kept exploring! 🌟 <CONTENT> What helped you notice the clues?"]}}

BRANCHES={
 'correct':["You did it! Let's keep going. <CONTENT>","Your careful work paid off. You can feel proud of your effort! <CONTENT>"],
 'partial':["You can keep working on this. Let's revisit what needs another try. <CONTENT>"],
 'incomplete':["You can take your time. Let's try the remaining parts. <CONTENT>"],
 'incorrect':["You can try again. I'm here to help you think it through. <CONTENT>","Let's pause and take another look together. <CONTENT>"],
 'unclear':["Could you say your answer again? I want to understand your thinking. <CONTENT>"],
 'hint':["Let's look at a helpful clue together. <CONTENT>","You can use this clue to take another look. <CONTENT>","Let's pause and work with this clue. <CONTENT>"],
 'answer_reveal':["You kept trying. Let's work through this together. <CONTENT>"],
 'optional_practice':["You can try this when you want another challenge. <CONTENT>","Here's another question for you to explore. <CONTENT>"],
 'follow_up_question':["Let's take our time with a helpful question. <CONTENT>"],
 'asset_bank':["You can use this cue when you need it. <CONTENT>"],
 'hint_bank':["You can use this clue when you need it. <CONTENT>"]}

class HandwrittenModel:
    name='handwritten-gold-not-model-output'
    def __init__(self,name):self.gold=GOLD[name];self.counts=defaultdict(int);self.calls=[]
    def generate(self,request):
        self.calls.append(request);s=request['segment'];key=s.get('outcome') or s.get('phase')
        if key not in BRANCHES and key not in self.gold:key=s['type']
        bank=self.gold.get(key,BRANCHES.get(key))
        if bank is None:raise ValueError('Missing handwritten template '+str(key))
        n=self.counts[key];self.counts[key]+=1
        return bank[n%len(bank)]

def build_gold(manifest,output):
    lessons=[]
    for sample in manifest:
        c=json.loads(Path(sample['concept']).read_text());a=json.loads(Path(sample['assessment']).read_text());style=GOLD[sample['name']]
        plan=plan_lesson(c,a,style['metaphor'],sample.get('outline'));result=generate_lesson(plan,HandwrittenModel(sample['name']))
        result['authorship']='Teacher framing written by Codex; teaching content copied verbatim from the supplied cards. No local or cloud inference.'
        write_lesson(result,Path(output)/sample['name'])
        lessons.append({'name':sample['name'],'grade':plan['grade'],'metaphor':plan['metaphor'],'source_concept_id':plan['concept_id'],'segments':[{k:s.get(k) for k in ('type','phase','outcome','template','content','text','source_refs')} for s in result['segments']]})
        print(sample['name'],'gold checks:',result['validation']['final_rule_violations'],'style:',result['validation']['style']['score'])
    Path(__file__).with_name('gold_examples.json').write_text(json.dumps(lessons,ensure_ascii=False,indent=2)+'\n')
    return lessons

if __name__=='__main__':
    manifest=json.loads(Path('tests/script_fixtures/manifest.json').read_text());build_gold(manifest,'artifacts/script-agent/gold')
