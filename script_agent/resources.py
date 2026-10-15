"""Read-only Mac resources and a conservative guard before local inference."""
from __future__ import annotations
import json
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from urllib.request import urlopen

GIB=1024**3

def command(args):
    try:return subprocess.check_output(args,text=True,stderr=subprocess.DEVNULL,timeout=10).strip()
    except (OSError,subprocess.SubprocessError):return None

def snapshot(path='.'):
    mem=command(['sysctl','-n','hw.memsize']); vm=command(['vm_stat']);swap=command(['sysctl','vm.swapusage'])
    pressure=command(['sysctl','-n','kern.memorystatus_vm_pressure_level'])
    result={'physical_memory_bytes':int(mem) if mem and mem.isdigit() else None,'model':command(['sysctl','-n','hw.model']),'disk_free_bytes':shutil.disk_usage(path).free,'vm_stat':vm,'swap_usage':swap,'ollama_version':command(['ollama','--version']),'vm_pressure_level':int(pressure) if pressure and pressure.isdigit() else None}
    if vm:
        page=int(re.search(r'page size of (\d+)',vm).group(1));pages={k:int(v) for k,v in re.findall(r'^([\w ]+):\s+(\d+)\.',vm,re.M)}
        result['reclaimable_estimate_bytes']=sum(pages.get(k,0) for k in ('Pages free','Pages inactive','Pages speculative','Pages purgeable'))*page
        result['wired_bytes']=pages.get('Pages wired down',0)*page;result['compressor_bytes']=pages.get('Pages occupied by compressor',0)*page
    if swap:
        match=re.search(r'used = ([\d.]+)M',swap)
        result['swap_used_bytes']=float(match.group(1))*1024**2 if match else None
    return result

def guard(resources,weight_bytes,reserve_gib=6,runtime_gib=2,min_disk_gib=1,current_model_loaded=False):
    reasons=[];physical=resources.get('physical_memory_bytes')
    if physical is None:reasons.append('Cannot read physical memory; run resource inspection with host access.')
    elif weight_bytes+runtime_gib*GIB>physical-reserve_gib*GIB:reasons.append('Weights plus runtime would breach OS memory reserve.')
    if resources['disk_free_bytes']<min_disk_gib*GIB:reasons.append('Less than %.1f GiB disk headroom; user must free space.'%min_disk_gib)
    available=resources.get('reclaimable_estimate_bytes')
    pressure=resources.get('vm_pressure_level')
    if pressure is not None and pressure!=1:reasons.append('macOS reports elevated memory pressure; unload and close apps.')
    if not current_model_loaded and pressure!=1 and available is not None and available<weight_bytes+runtime_gib*GIB:
        reasons.append('Current reclaimable memory is below weights plus runtime; close memory-heavy apps.')
    elif pressure is None and available is None and resources.get('swap_used_bytes',0)>2*GIB:
        reasons.append('High swap and unknown reclaimable memory; resource headroom cannot be established.')
    return reasons

class MemorySampler:
    """Samples process RSS and Ollama allocation, neither is total unified-memory use."""
    def __init__(self,endpoint,backend):
        self.endpoint=endpoint;self.backend=backend;self.stop_event=threading.Event();self.samples=[]
    def _sample(self):
        while not self.stop_event.is_set():
            row={'at_monotonic':time.monotonic(),'server_rss_bytes':None,'ollama_model_allocated_bytes':None,'ollama_vram_allocated_bytes':None}
            output=command(['ps','-axo','rss=,comm='])
            if output:
                matched=[]
                for line in output.splitlines():
                    values=line.strip().split(None,1)
                    if len(values)==2 and any(word in values[1] for word in ('ollama','llama-server','mlx_lm')):
                        try:matched.append(int(values[0])*1024)
                        except ValueError:pass
                if matched:row['server_rss_bytes']=sum(matched)
            if self.backend=='ollama':
                try:
                    with urlopen(self.endpoint+'/api/ps',timeout=2) as response:data=json.load(response)
                    row['ollama_model_allocated_bytes']=sum(m.get('size',0) for m in data.get('models',[]))
                    row['ollama_vram_allocated_bytes']=sum(m.get('size_vram',0) for m in data.get('models',[]))
                except (OSError,ValueError):pass
            self.samples.append(row);self.stop_event.wait(.5)
    def __enter__(self):
        self.thread=threading.Thread(target=self._sample,daemon=True);self.thread.start();return self
    def __exit__(self,*args):self.stop_event.set();self.thread.join(timeout=5)
    def peaks(self):
        return {key:max((s[key] for s in self.samples if s[key] is not None),default=None) for key in ('server_rss_bytes','ollama_model_allocated_bytes','ollama_vram_allocated_bytes')}
