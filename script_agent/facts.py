"""Conservative number normalization and explicit quantity bindings, not semantic proof."""
import re
from fractions import Fraction

ONES={w:i for i,w in enumerate('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split())}
TENS=dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(),range(20,100,10)))
SCALES={'hundred':100,'thousand':1000,'million':10**6,'billion':10**9}
TOKENS=re.compile(r'(?<!\w)[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:/\d+(?:\.\d+)?)?(?!\w)|[a-z]+|[^\w\s]',re.I)
FIGURATIVE_ONE=re.compile(r'\b(?:pick|choose|try|watch|take|show)\s+one\b(?!\s+(?:hundred|thousand|million|billion|plus|minus|times|divided|equals))|\bone\s+(?:step at a time|more for you|to look at)\b',re.I)

def canonical(value):
    try:return str(Fraction(value.replace(',','')))
    except (ValueError,ZeroDivisionError):return value

def number_mentions(text,figurative=True):
    """(start, end, value) triples; number phrases preserve their whole value."""
    ignored=[m.span() for m in FIGURATIVE_ONE.finditer(text)] if figurative else []
    tokens=list(TOKENS.finditer(text));result=[];i=0
    while i<len(tokens):
        t=tokens[i];w=t.group().lower()
        if w[0].isdigit() or (w[0] in '+-' and len(w)>1 and w[1].isdigit()):
            start=t.start();value=canonical(w)
            if i and tokens[i-1].group().lower()=='negative':start=tokens[i-1].start();value='-'+value
            result.append((start,t.end(),value));i+=1;continue
        if w not in ONES and w not in TENS and w not in SCALES:
            i+=1;continue
        if w=='one' and any(a<=t.start()<b for a,b in ignored):i+=1;continue
        start=t.start();end=t.end();current=0;total=0;last=None;j=i
        while j<len(tokens):
            token=tokens[j];word=token.group().lower()
            # Spaces and a hyphen may join number words; other punctuation ends a number.
            if j>i and not re.fullmatch(r'[\s-]*',text[end:token.start()]):break
            if word=='-' and j+1<len(tokens) and tokens[j+1].group().lower() in ONES:
                end=token.end();j+=1;continue
            if word=='and' and current+total>=100 and j+1<len(tokens) and tokens[j+1].group().lower() in ONES.keys()|TENS.keys():
                end=token.end();j+=1;continue
            if word in ONES or word in TENS:
                value=ONES.get(word,TENS.get(word))
                if last is not None and last!='scale' and not (last=='tens' and word in ONES and value<10):break
                current+=value;last='tens' if word in TENS else 'ones'
            elif word in SCALES:
                scale=SCALES[word]
                if scale==100:
                    current=max(1,current)*scale
                else:
                    total+=max(1,current)*scale;current=0
                last='scale'
            else:break
            end=token.end();j+=1
        value=str(total+current)
        # A spoken unary sign belongs to the value, unlike the binary operator "minus".
        if i and tokens[i-1].group().lower()=='negative':start=tokens[i-1].start();value='-'+value
        result.append((start,end,value));i=max(i+1,j)
    return result

def digitize(text):
    result=text
    for start,end,value in reversed(number_mentions(text,figurative=False)):
        result=result[:start]+value+result[end:]
    return result.lower()

ROLES={'area':'area','perimeter':'perimeter','width':'width','wide':'width',
       'length':'length','long':'length','height':'height','tall':'height',
       'radius':'radius','diameter':'diameter'}
_DIM_ROLE='(?:'+'|'.join(ROLES)+')'
ROLES.update({word:plural for plural in ('rows','columns','groups','dots','spots','squares','angles','sides','tens','ones') for word in (plural,plural[:-1])})
_VALUE=r'([+-]?\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?)'
_ROLE='(?:'+'|'.join(ROLES)+')'
_PREFIX=re.compile(r'\b('+_DIM_ROLE+r')\s+(?:(?:is|are|of|measures|equals|has|a|the)\s+){0,3}'+_VALUE+r'\b')
_COUNT_PREFIX=re.compile(r'\b('+_ROLE+r')\s+(?:is|are|equals)\s+'+_VALUE+r'\b')
_SUFFIX=re.compile(r'(?<!\w)'+_VALUE+r'\s+(?:(?:square\s+)?(?:units?|centimeters?|centimetres?|meters?|metres?|cm|m|feet|inches)\s+)?(?:(?:empty|full|filled|equal)\s+)?('+_ROLE+r')\b')

def quantity_bindings(text):
    """Explicit role/value pairs, e.g. perimeter=22 and width=4; prose remains heuristic."""
    text=digitize(text);pairs=set()
    for role,value in _PREFIX.findall(text)+_COUNT_PREFIX.findall(text):pairs.add((ROLES[role],canonical(value)))
    for value,role in _SUFFIX.findall(text):pairs.add((ROLES[role],canonical(value)))
    for tens,ones in re.findall(_VALUE+r'\s+tens\s+'+_VALUE,text):
        pairs.add(('tens',canonical(tens)));pairs.add(('ones',canonical(ones)))
    return pairs

_PAIR=re.compile(r'(?<![\w./])'+_VALUE+r'\s+(?:by|times|x|×)\s+'+_VALUE+r'(?![\w/]|\.\d)')

def pair_bindings(text):
    return {tuple(sorted((canonical(a),canonical(b)))) for a,b in _PAIR.findall(digitize(text))}
