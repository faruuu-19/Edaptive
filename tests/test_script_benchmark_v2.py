"""The comparison must measure the new teaching mode and expose its fallbacks."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from script_agent.benchmark import benchmark_one
from script_agent.models import FakeModel
from script_agent.resources import GIB
from run_script_agent_comparison import review_pair


class BenchmarkV2Tests(unittest.TestCase):
    def test_rewrite_mode_reaches_generation_and_reports_fallbacks(self):
        class Model(FakeModel):
            endpoint='http://127.0.0.1:11434';backend='ollama'
            def unload(self):pass
        class Sampler:
            def __init__(self,*args):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def peaks(self):return {'server_rss_bytes':None,'ollama_model_allocated_bytes':None,'ollama_vram_allocated_bytes':None}
        resource={'physical_memory_bytes':16*GIB,'disk_free_bytes':20*GIB,'vm_pressure_level':1}
        sample=json.loads((Path(__file__).parent/'script_fixtures/manifest.json').read_text())[0]
        model=Model()
        with tempfile.TemporaryDirectory() as folder, patch('script_agent.benchmark.LocalModel',return_value=model), patch('script_agent.benchmark.identity',return_value={'size':100,'digest':'fake'}), patch('script_agent.benchmark.snapshot',return_value=resource), patch('script_agent.benchmark.MemorySampler',Sampler), patch('builtins.print'):
            row=benchmark_one(sample,{'model':'fake','weight_gb':0.1},folder,rewrite=True)
        self.assertTrue(row['rewrite_enabled'])
        self.assertGreater(row['rewritten_segments'],0)
        self.assertIn('fallback_segments',row)
        self.assertTrue(any('source_text' in json.loads(r['prompt']) for r in model.calls))
        self.assertFalse(any('source_text' in json.loads(r['prompt']) for r in model.calls if r['segment']['type']=='question'))

    def test_many_fallbacks_do_not_beat_successful_natural_rewrites(self):
        rows=[]
        for model,fallbacks,style in [('natural',0,80),('mostly_card_text',20,100),('another_natural',1,85)]:
            for lesson in ['area_perimeter','grade1','shape_attributes']:
                rows.append({'model':model,'lesson':lesson,'status':'measured','final_violations':0,'fallback_segments':fallbacks,'style_score':style})
        self.assertEqual(['natural','another_natural'],[r['model'] for r in review_pair(rows)])

if __name__=='__main__':unittest.main()
