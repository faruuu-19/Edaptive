"""Small plain-text calls, local endpoints only. No paid-provider/key support."""
from __future__ import annotations
import json
import time
from urllib.request import Request, urlopen
from urllib.parse import urlparse

_VERBS="notice spot find see say try check trace count compare name show tell draw sort match read think guess explain picture imagine measure test build follow search wonder listen discover explore study practice remember share use pick group order solve describe predict connect plan sketch review repeat wait watch hold press mark learn start finish choose".split()
_TAILS=["slowly","with care","your way","step by step","today","right now","with a smile"]

def lead_in(n):
    """A unique, valid, direct-address lead-in for the n-th canned reply (distinct opener for 60 replies, distinct sentence for 420)."""
    return 'You can %s it %s.'%(_VERBS[n%len(_VERBS)],_TAILS[(n//len(_VERBS))%len(_TAILS)])

class FakeModel:
    """Canned, varied replies for tests. Never a benchmark. A rewrite request gets a lead-in plus the source, which is always valid."""
    name='fake-canned-not-a-benchmark'
    def __init__(self,replies=None):self.replies=list(replies or []);self.calls=[];self.metrics=[];self.n=0
    def generate(self,request):
        self.calls.append(request)
        if self.replies:return self.replies.pop(0)
        lead=lead_in(self.n);self.n+=1
        body=json.loads(request['prompt'])
        if 'source_text' in body:return lead+' '+body['source_text']
        return lead+' <CONTENT>'

class LocalModel:
    """Ollama or OpenAI-compatible localhost server (MLX-LM/llama.cpp)."""
    def __init__(self,name,backend='ollama',endpoint=None,context=4096):
        self.name=name;self.backend=backend;self.context=context;self.metrics=[]
        self.endpoint=endpoint or ('http://127.0.0.1:11434' if backend=='ollama' else 'http://127.0.0.1:8080')
        parsed=urlparse(self.endpoint)
        if parsed.hostname not in ('127.0.0.1','localhost','::1') or parsed.username or parsed.password or parsed.query:raise ValueError('Only local, credential-free endpoints are supported')
    def _post(self,path,body):
        req=Request(self.endpoint+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=120) as r:return json.load(r)
    def generate(self,request):
        start=time.monotonic()
        try:return self._generate(request)
        except (OSError,KeyError,ValueError,TimeoutError,TypeError,IndexError,AttributeError):
            self.metrics.append({'wall_seconds':time.monotonic()-start,'segment_id':request['segment']['id'],'repair':bool(request['repair_errors']),'success':False,'error_code':'model_call_failed','output_tokens':None,'decode_seconds':None})
            raise OSError('Local model call failed') from None
    def _generate(self,request):
        start=time.monotonic()
        messages=[{'role':'system','content':request['system']},{'role':'user','content':request['prompt']}]
        if self.backend=='ollama':
            r=self._post('/api/chat',{'model':self.name,'messages':messages,'stream':False,'think':False,'keep_alive':'5m','options':{'temperature':.5,'seed':42,'num_ctx':self.context,'num_predict':request.get('max_tokens',128)}})
            output=r['message']['content'];n=r.get('eval_count',0);decode=r.get('eval_duration',0)/1e9
            metric={'output_tokens':n,'prompt_tokens':r.get('prompt_eval_count'), 'decode_seconds':decode,'decode_tokens_per_second':n/decode if decode else None,'load_seconds':r.get('load_duration',0)/1e9,'done_reason':r.get('done_reason')}
        else:
            r=self._post('/v1/chat/completions',{'model':self.name,'messages':messages,'stream':False,'temperature':.5,'max_tokens':request.get('max_tokens',128)})
            output=r['choices'][0]['message']['content'];usage=r.get('usage',{});timings=r.get('timings',{})
            metric={'output_tokens':usage.get('completion_tokens'), 'prompt_tokens':usage.get('prompt_tokens'),'decode_tokens_per_second':timings.get('predicted_per_second'),'done_reason':r['choices'][0].get('finish_reason')}
        if not isinstance(output,str):raise ValueError('Malformed local response')
        metric.update({'wall_seconds':time.monotonic()-start,'segment_id':request['segment']['id'],'repair':bool(request['repair_errors']),'success':True});self.metrics.append(metric)
        # Truncation is explicitly invalid and gets the same single repair budget.
        if metric['done_reason'] in ('length','limit'):return output+' <TRUNCATED>'
        return output.strip()
    def unload(self):
        if self.backend=='ollama':self._post('/api/generate',{'model':self.name,'keep_alive':0})
