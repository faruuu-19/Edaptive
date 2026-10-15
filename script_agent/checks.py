"""Deterministic checks. Protected source text is never accepted from model output."""
from __future__ import annotations
import re
from collections import Counter
from .spoken import assemble_template

NUMBERS=re.compile(r"(?<!\w)\d+(?:[.,/]\d+)*(?!\w)|\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|half|quarter|double|twice)\b",re.I)
# Visible emoji sequences: keycaps, flag pairs, modifiers and ZWJ compounds.
# This covers the teaching emoji range without counting joined codepoints twice.
_EMOJI_BASE=r'[\U0001F300-\U0001FAFF\u2600-\u27BF]'
_EMOJI_PART=_EMOJI_BASE+r'[\uFE0E\uFE0F]?[\U0001F3FB-\U0001F3FF]?'
EMOJI=re.compile(r'(?:[0-9#*]\uFE0F?\u20E3|[\U0001F1E6-\U0001F1FF]{2}|'+_EMOJI_PART+r'(?:\u200D'+_EMOJI_PART+r')*)')
ADDRESS_REWRITE=re.compile(r"\b(?:you|your|you’re|you're|you’ll|you'll|let’s|let's|we|we’re|we're|our|us)\b",re.I)
ADDRESS=re.compile(r"\b(?:you|your|you’re|you're|you’ll|you'll|let’s|let's)\b",re.I)

def sentences(text):return [s.strip() for s in re.split(r'[.!?]+(?:\s+|$)|\n+',text) if s.strip()]
def words(text):return re.findall(r"\b[\w’']+\b",text)
def limit(grade):return 10 if grade<=1 else 14 if grade<=3 else 18

INVITES=re.compile(r"\b(?:together|let(?:'s|’s| us)|we can|let me)\b",re.I)
STOP_TERMS=set("that with have this they then from into what when your will each there here also only more some than them their were been make makes made look next take takes does just like very much many most other about after before over under again once".split())
_ONES={w:i for i,w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split())}
_TENS={'twenty':20,'thirty':30,'forty':40,'fifty':50,'sixty':60,'seventy':70,'eighty':80,'ninety':90}
_BIG={'hundred':100,'thousand':1000,'million':10**6,'billion':10**9}
_KEEP={'half','quarter','double','twice'}
_COMPOUND=re.compile(r'\b('+'|'.join(_TENS)+r')[- ](one|two|three|four|five|six|seven|eight|nine)\b',re.I)
_DIGITS=re.compile(r'\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?')
_EQ_NUMBER=r'([+-]?\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?)'
EQUATION=re.compile(r'(?<![\w./])'+_EQ_NUMBER+r'\s+(plus|minus|times|divided by)\s+'+_EQ_NUMBER+r'\s+(?:equals|is|makes|make|=)\s+'+_EQ_NUMBER+r'(?![\w/]|\.\d)',re.I)

def framing_key(text):
    text=EMOJI.sub(' ',text.lower());return ' '.join(re.sub(r"[^\w’' ]+",' ',text).split())

def opener_key(text):return ' '.join(w.lower() for w in words(EMOJI.sub(' ',text))[:3])

def _variety_errors(framing,history):
    if not history or not framing.strip():return []
    errors=[]
    if history['framings'][framing_key(framing)]>=2:errors.append('repeated_framing')
    if history['openers'][opener_key(framing)]>=3:errors.append('repeated_opener')
    return errors

def number_values(text):
    from .facts import number_mentions
    found={value for _,_,value in number_mentions(text)}
    found.update(w for w in re.findall(r"[a-z]+",text.lower()) if w in _KEEP)
    return found

def digitize(text):
    from .facts import digitize as normalize
    return normalize(text)

def equations(text):
    return {(a,op.lower(),b,c) for a,op,b,c in EQUATION.findall(digitize(text).replace(',',''))}

def key_terms(text):
    return {w[:5] for w in (x.lower().strip("'’") for x in words(text)) if len(w)>=4 and w not in STOP_TERMS and not w.isdigit()}

def statement_key(text):
    return ' '.join(re.findall(r'\w+',digitize(text)))

def tone_errors(segment,text,grade):
    errors=[]
    if re.search(r"\byou(?:['’]re| are| were)\s+(?:such\s+)?(?:a\s+)?(?:brilliant|genius|super|perfect|clever)\b|\b(?:little|super|brilliant)\s+(?:detective|builder|explorer)\b",text,re.I):
        errors.append('unsupported_praise')
    if segment.get('outcome')!='correct' and re.search(r"\b(?:great|good|excellent|nice|amazing)\s+(?:job|work)\b|\byou(?: have|['’]ve)?\s+(?:mastered|solved|understood)\b",text,re.I):
        errors.append('unsupported_praise')
    if segment.get('type')=='recap' and re.search(r"\b(?:now|next|let['’]s|we will)\s+(?:you\s+)?learn\b",text,re.I):
        errors.append('recap_restarts_lesson')
    return errors

def check_rewrite(segment,text,grade,history=None):
    """Checks a model's spoken rewrite of a card passage against that passage. Heuristic: numbers, equations,
    key terms, length, style. It cannot prove every sentence is true to the card."""
    errors=[]
    if not isinstance(text,str):return ['rewrite_not_text']
    if '<TRUNCATED>' in text:errors.append('truncated_output')
    if '<CONTENT>' in text:errors.append('content_marker_left')
    source=segment.get('content','')
    # Do not turn equality of specified attributes into equality of every part.
    general=re.compile(r'\b(?:every|all)\s+(?:part|parts|piece|pieces|feature|features)\s+(?:match(?:es)?|(?:is|are)\s+(?:the same|equal|identical))\b',re.I)
    if general.search(text) and not general.search(source):errors.append('rewrite_unsupported_generalisation')
    protected=segment.get('protected_statements',[])
    if any(statement_key(t) not in statement_key(text) for t in protected):errors.append('rewrite_changed_protected_fact')
    have=number_values(source);got=number_values(text)
    if got-have:errors.append('rewrite_invented_number')
    if have-got:errors.append('rewrite_dropped_number')
    if equations(source)!=equations(text):errors.append('rewrite_changed_equation')
    from .facts import quantity_bindings,pair_bindings
    if quantity_bindings(text)-quantity_bindings(source):errors.append('rewrite_changed_quantity')
    if pair_bindings(source)!=pair_bindings(text):errors.append('rewrite_changed_pairing')
    terms=key_terms(source)
    if len(terms)>=3 and len(terms&key_terms(text))/len(terms)<0.6:errors.append('rewrite_lost_terms')
    n_source=len(words(source));n_text=len(words(text))
    if n_text>1.7*n_source+30:errors.append('rewrite_too_long')
    if n_source>=8 and n_text<0.5*n_source:errors.append('rewrite_too_short')
    # Pasting the card's sentences after a lead-in is not teaching in a teacher's voice. Equation sentences are exempt: they must stay as written.
    protected_keys={statement_key(t) for t in protected}
    plain=[framing_key(x) for x in sentences(source) if not EQUATION.search(x.lower().replace(',','')) and statement_key(x) not in protected_keys]
    if len(plain)>=3 and sum(k in {framing_key(x) for x in sentences(text)} for k in plain)/len(plain)>=0.7:errors.append('rewrite_copied_source')
    if not ADDRESS_REWRITE.search(text):errors.append('direct_address')
    if any(len(words(s))>limit(grade) for s in sentences(text)):errors.append('sentence_length')
    if re.search(r'[=×÷+]',text) or re.search(r'(?<=\d)\s+[-−–]\s+(?=\d)',text):errors.append('non_spoken_symbols')
    emojis=len(EMOJI.findall(text))
    if emojis>2:errors.append('emoji_count')
    if any(EMOJI.search(s) and re.search(r'\d',s) for s in sentences(text)):errors.append('emoji_in_maths')
    if re.search(r'\b(?:stupid|baby|obviously|wrong again|easy peasy|duh)\b',text,re.I):errors.append('discouraging_tone')
    if re.search(r'https?://|\.(?:png|jpg|svg)\b|\b(?:image|picture above|see the photo)\b',text,re.I):errors.append('actual_image_reference')
    if any(marker in text for marker in ('```','<think>','</think>','[show:')) or re.search(r'^\s*(?:#|spoken|rewrite|script|answer)\s*:',text,re.I|re.M):errors.append('non_spoken_output')
    metaphor_words={'detectives':r'\b(?:detective|detectives)\b','builders':r'\b(?:builder|builders|building crew|building kit)\b','explorers':r'\b(?:explorer|explorers)\b'}
    if segment.get('metaphor') and any(re.search(pattern,text,re.I) for name,pattern in metaphor_words.items() if name!=segment['metaphor']):errors.append('mixed_metaphor')
    if history and history['openers'][opener_key(text)]>=3:errors.append('repeated_opener')
    errors+=tone_errors(segment,text,grade)
    return list(dict.fromkeys(errors))

def check_segment(segment,template,grade,history=None):
    errors=[]
    if not isinstance(template,str) or template.count('<CONTENT>') not in ((0,1) if not segment.get('content','').strip() else (1,)):
        errors.append('source_content_placeholder')
    if not isinstance(template,str):return errors
    if '<TRUNCATED>' in template:errors.append('truncated_output')
    framing=template.replace('<CONTENT>','').strip()
    if NUMBERS.search(framing) or any(char.isnumeric() for char in framing):errors.append('invented_number')
    if re.search(r'[=×÷+]|\b(?:equals|multiplied|divided)\b',framing,re.I):errors.append('invented_formula')
    if segment['type']=='question':
        for alias in segment.get('answer_aliases',[]):
            if alias.strip() and re.search(r'(?<!\w)'+re.escape(alias.strip())+r'(?!\w)',framing,re.I):
                errors.append('answer_leakage');break
        if re.search(r'\b(?:the answer is|answer equals|solution is|you get)\b',framing,re.I):errors.append('answer_leakage')
    if any(len(words(s))>limit(grade) for s in sentences(framing)):errors.append('sentence_length')
    if not ADDRESS.search(framing):errors.append('direct_address')
    if len(EMOJI.findall(framing))>1:errors.append('emoji_count')
    if segment.get('outcome')!='correct' and re.search(r"\b(?:correct|you got it(?: right)?|you nailed it|that['’]s right|perfect answer)\b",framing,re.I):errors.append('premature_correctness_claim')
    if segment.get('phase')=='your_turn' and '?' not in framing and '?' not in segment.get('content',''):errors.append('your_turn_question')
    if segment.get('phase')=='your_turn' and (len(words(framing))>12 or '?' in framing or re.search(r'\b(?:what|why|how|which|where|when)\b|\b(?:can|could|would|do|did)\s+you\b',framing,re.I)):
        errors.append('reflection_framing')
    if segment['type']=='question' and (len(words(framing))>14 or '?' in framing):errors.append('question_framing')
    errors+=tone_errors(segment,framing,grade)
    # The card's own line already invites the student ("Let us check this together"); do not say it twice.
    if segment.get('phase') in ('feedback','answer_reveal') and INVITES.search(segment.get('content','')) and re.search(r'\btogether\b',framing,re.I):errors.append('echoes_source')
    errors+=_variety_errors(framing,history)
    if re.search(r'\b(?:stupid|baby|obviously|wrong again|easy peasy|duh)\b',framing,re.I):errors.append('discouraging_tone')
    if re.search(r'https?://|\.(?:png|jpg|svg)\b|\b(?:image|picture above|see the photo)\b',framing,re.I):errors.append('actual_image_reference')
    if any(marker in framing for marker in ('```','<think>','</think>','[show:')):errors.append('non_spoken_output')
    budget=20 if segment['type'] in ('hook','lecture','worked_example','watch_out','recap') else 50
    if len(words(framing))>budget:errors.append('framing_too_long')
    metaphor_words={'detectives':r'\b(?:detective|detectives)\b','builders':r'\b(?:builder|builders|building crew|building kit)\b','explorers':r'\b(?:explorer|explorers)\b'}
    if segment.get('metaphor'):
        if any(re.search(pattern,framing,re.I) for name,pattern in metaphor_words.items() if name!=segment['metaphor']):errors.append('mixed_metaphor')
    # A conservative factual-claim signal, not a semantic proof.
    if re.search(r'\b(?:always|never|all shapes|every rectangle|a rectangle is|area is|perimeter is)\b',framing,re.I):errors.append('ungrounded_claim')
    return list(dict.fromkeys(errors))

def check_coverage(plan,segments):
    expected={s['id']:s for s in plan['segments']}; seen=Counter(s.get('id') for s in segments); errors=[]
    for sid in expected:
        if seen[sid]!=1:errors.append('missing_or_duplicate_segment:'+sid)
    for s in segments:
        e=expected.get(s.get('id'))
        if e is None:errors.append('unexpected_segment:'+str(s.get('id')));continue
        for key in ('type','source_refs','content','question_id','phase','outcome','route_action','condition','visual_cue','hint_level','hint_index','protected_statements'):
            if s.get(key)!=e.get(key):errors.append('changed_'+key+':'+s['id'])
        mode=s.get('rewrite_mode')
        if mode=='rewritten':
            if not e.get('rewrite') or check_rewrite(e,s.get('text'),plan['grade']):errors.append('unverified_rewrite:'+s['id'])
        elif mode=='fallback_verbatim':
            if s.get('text')!=e['content'].strip():errors.append('changed_source_text:'+s['id'])
        elif 'text' in s and 'template' in s and s['text']!=assemble_template(s['template'],e['content']):errors.append('changed_source_text:'+s['id'])
    refs={(r['scope'],r['id']) for s in segments for r in s.get('source_refs',[])}
    for scope,card in [('concept_card',plan.get('source_cards',{}).get('concept',{})),('this_card',plan.get('source_cards',{}).get('assessment',{}))]:
        for field in ('explanations','examples','questions','follow_ups','misconceptions','hints','assets_required'):
            for item in card.get(field,[]):
                iid=item.get('id',item.get('asset_id'))
                if (scope,iid) not in refs:errors.append('uncovered_source:'+scope+':'+str(iid))
    return errors

def style_scores(segments,grade):
    text=[s.get('text',s.get('content','')) for s in segments]
    ss=[sentence for t in text for sentence in sentences(t)]
    lens=[len(words(s)) for s in ss];total_words=sum(lens)
    openers=[' '.join(words(t.lower())[:2]) for t in text if words(t)]
    repeated=sum(max(0,n-2) for n in Counter(openers).values())
    direct=sum(bool(ADDRESS.search(t)) for t in text)/max(1,len(text))
    short=sum(n<=limit(grade) for n in lens)/max(1,len(lens))
    question_rate=sum(t.count('?') for t in text)/max(1,len(ss))
    emojis=sum(len(EMOJI.findall(t)) for t in text)
    emoji_density=emojis/max(1,total_words)*100
    score=100*(.40*short+.25*direct+.15*min(1,question_rate/.12)+.10*max(0,1-max(0,emoji_density-1)/2)+.10*max(0,1-repeated/max(1,len(text))))
    return {'score':round(score,2),'sentence_word_limit':limit(grade),'mean_sentence_words':round(sum(lens)/max(1,len(lens)),2),'max_sentence_words':max(lens,default=0),'short_sentence_fraction':round(short,3),'direct_address_fraction':round(direct,3),'question_rate':round(question_rate,3),'emoji_count':emojis,'emojis_per_100_words':round(emoji_density,2),'repeated_openers':repeated,'words':total_words,'segments':len(text), 'heuristic_only':True}
