"""Real TripStar generation evaluation. Never substitutes model/tool responses.

Run from project root with backend/.venv/bin/python evals/run_live_eval.py --run.
Each scenario is executed twice in a fresh subprocess. Production source is not
edited; instrumentation records real calls and adds shared request pacing only.
"""
from __future__ import annotations
import argparse, asyncio, contextlib, datetime as dt, fcntl, hashlib, io, json, os
from pathlib import Path
import signal, subprocess, sys, threading, time, traceback
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'evals'/'live-100-20261026'
sys.path.insert(0,str(ROOT/'backend'))
sys.path.insert(0,str(ROOT/'evals'))
from live_cases import cases

def stamp(): return dt.datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
def save(path, obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    tmp.replace(path)

def pace(name, interval):
    p=OUT/'locks'/name
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('a+') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        f.seek(0)
        try: last=float(f.read() or '0')
        except ValueError: last=0
        delay=interval-(time.time()-last)
        if delay>0: time.sleep(delay)
        f.seek(0); f.truncate(); f.write(str(time.time())); f.flush()
        fcntl.flock(f,fcntl.LOCK_UN)

def worker(run_id):
    os.chdir(ROOT/'backend')
    os.environ['ENABLE_USER_MEMORY']='false'
    os.environ['PYTHONDONTWRITEBYTECODE']='1'
    os.environ['UV_CACHE_DIR']=str(ROOT/'.uv-cache')
    os.environ['PATH']=str(OUT/'bin')+':'+str(ROOT/'backend/.venv/bin')+':'+str(Path.home()/'.local/bin')+':'+str(Path.home()/'.hermes/node/bin')+':'+os.environ.get('PATH','')
    from app.config import get_settings
    settings=get_settings()
    secret_values=[getattr(settings,k,'') for k in ('openai_api_key','vite_amap_web_key','vite_amap_web_js_key','google_maps_api_key','xhs_cookie')]
    cookie=getattr(settings,'xhs_cookie','')
    secret_values += [x.split('=',1)[1].strip() for x in cookie.split(';') if '=' in x]
    secret_values=[x for x in secret_values if isinstance(x,str) and len(x)>=8]
    def redact(value):
        s=str(value)
        for secret in secret_values: s=s.replace(secret,'[REDACTED]')
        return s
    def clean(obj): return json.loads(redact(json.dumps(obj,ensure_ascii=False,default=str)))
    class SafeLog(io.TextIOBase):
        def __init__(self,p): self.file=p.open('w',encoding='utf-8')
        def write(self,s): self.file.write(redact(s)); self.file.flush(); return len(s)
        def flush(self): self.file.flush()
        def fileno(self): return self.file.fileno()
        def isatty(self): return False
    for d in ('runs','traces','logs','ratings'): (OUT/d).mkdir(parents=True,exist_ok=True)
    trace_path=OUT/'traces'/f'{run_id}.jsonl'
    lock=threading.Lock()
    trace=[]
    def emit(kind, **fields):
        row=clean({'kind':kind,'at':stamp(),**fields})
        with lock:
            trace.append(row)
            with trace_path.open('a',encoding='utf-8') as f: f.write(json.dumps(row,ensure_ascii=False)+'\n')
    case_id,repeat=run_id.split('-r')
    case=next(c for c in cases() if c['id']==case_id)
    result={'run_id':run_id,'case_id':case_id,'repeat':int(repeat),'case':case,
            'started_at':stamp(),'status':'started','real_external_calls':True,
            'session_mode':'fresh subprocess; production planner and real tools',
            'model_requested':settings.openai_model}
    save(OUT/'runs'/f'{run_id}.json',result)
    started=time.perf_counter()
    log=SafeLog(OUT/'logs'/f'{run_id}.log')
    with contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        try:
            from app.models.schemas import TripRequest
            from app.agents import trip_planner_agent as agent_mod
            from app.services import community_search as xhs
            from app.services.llm_service import DirectOpenAILLM
            from app.services.knowledge_graph_service import build_knowledge_graph
            from hello_agents import SimpleAgent
            from openai.resources.chat.completions.completions import Completions

            # Observe provider usage, including streaming terminal usage chunks.
            original_create=Completions.create
            def observed_create(owner,*args,**kwargs):
                cid=f'api-{sum(x["kind"]=="llm_api_start" for x in trace)+1}'
                stream=kwargs.get('stream',False)
                if stream: kwargs.setdefault('stream_options',{'include_usage':True})
                emit('llm_api_start',call_id=cid,stream=stream,model=kwargs.get('model'))
                begin=time.perf_counter()
                try: response=original_create(owner,*args,**kwargs)
                except Exception as exc:
                    emit('llm_api_end',call_id=cid,ok=False,seconds=time.perf_counter()-begin,error=f'{type(exc).__name__}: {exc}')
                    raise
                if not stream:
                    usage=getattr(response,'usage',None)
                    emit('llm_api_end',call_id=cid,ok=True,seconds=time.perf_counter()-begin,
                         usage=usage.model_dump() if usage else None,model_returned=getattr(response,'model',None))
                    return response
                def stream_iter():
                    usage=None; model=None
                    try:
                        for chunk in response:
                            model=getattr(chunk,'model',None) or model
                            if getattr(chunk,'usage',None): usage=chunk.usage.model_dump()
                            yield chunk
                        emit('llm_api_end',call_id=cid,ok=True,seconds=time.perf_counter()-begin,usage=usage,model_returned=model)
                    except Exception as exc:
                        emit('llm_api_end',call_id=cid,ok=False,seconds=time.perf_counter()-begin,usage=usage,error=f'{type(exc).__name__}: {exc}')
                        raise
                    finally: response.close()
                return stream_iter()
            Completions.create=observed_create

            original_invoke=DirectOpenAILLM.invoke
            def observed_invoke(owner,messages,**kwargs):
                system=messages[0].get('content','') if messages else ''
                role=('planner' if '你是行程规划专家' in system else 'weather' if '你是天气查询专家' in system
                      else 'hotel' if '你是酒店推荐专家' in system else 'extract_or_repair')
                cid=f'invoke-{sum(x["kind"]=="llm_start" for x in trace)+1}'
                begin=time.perf_counter()
                emit('llm_start',call_id=cid,role=role,messages=messages,parameters=kwargs)
                try:
                    text=original_invoke(owner,messages,**kwargs)
                    emit('llm_end',call_id=cid,role=role,ok=True,seconds=time.perf_counter()-begin,output=text)
                    return text
                except Exception as exc:
                    emit('llm_end',call_id=cid,role=role,ok=False,seconds=time.perf_counter()-begin,error=f'{type(exc).__name__}: {exc}')
                    raise
            DirectOpenAILLM.invoke=observed_invoke
            original_tool=SimpleAgent._execute_tool_call
            def observed_tool(owner,name,parameters):
                begin=time.perf_counter(); emit('tool_start',agent=owner.name,tool=name,parameters=parameters)
                try:
                    value=original_tool(owner,name,parameters)
                    emit('tool_end',agent=owner.name,tool=name,seconds=time.perf_counter()-begin,output=value)
                    return value
                except Exception as exc:
                    emit('tool_error',tool=name,seconds=time.perf_counter()-begin,error=str(exc)); raise
            SimpleAgent._execute_tool_call=observed_tool

            original_search=xhs.CommunityClient.search_notes
            def observed_search(owner,keyword,page=1,sort_type=0,page_size=20):
                pace('xhs-search',1.5)
                begin=time.perf_counter(); emit('xhs_search_start',keyword=keyword,page=page,page_size=page_size,sort_type=sort_type)
                try:
                    response=original_search(owner,keyword,page,sort_type,page_size)
                    items=response.get('data',{}).get('items',[])
                    emit('xhs_search_end',seconds=time.perf_counter()-begin,returned_count=len(items),
                         first_items=[{'id':x.get('id'),'type':x.get('model_type'),'title':x.get('note_card',{}).get('display_title','')} for x in items[:4]])
                    return response
                except Exception as exc:
                    emit('xhs_search_error',seconds=time.perf_counter()-begin,error=f'{type(exc).__name__}: {exc}'); raise
            xhs.CommunityClient.search_notes=observed_search
            original_detail=xhs.CommunityClient.get_note_detail
            def observed_detail(owner,note_id,*args,**kwargs):
                pace('xhs-detail',.45)
                response=original_detail(owner,note_id,*args,**kwargs)
                items=response.get('data',{}).get('items',[])
                emit('xhs_detail',note_id=note_id,source_url=f'https://www.xiaohongshu.com/explore/{note_id}',
                     notes=[{'title':x.get('note_card',{}).get('title',''),'desc':x.get('note_card',{}).get('desc','')} for x in items])
                return response
            xhs.CommunityClient.get_note_detail=observed_detail
            original_geo=xhs.geocode_amap
            def observed_geo(*args,**kwargs):
                begin=time.perf_counter(); value=original_geo(*args,**kwargs)
                emit('geocode',address=args[0] if args else '',city=args[1] if len(args)>1 else '',
                     seconds=time.perf_counter()-begin,result=value)
                return value
            xhs.geocode_amap=observed_geo
            xhs._wait_for_amap_geocode_slot=lambda: pace('geocode',.36)
            request=TripRequest(**case['request'])
            init_start=time.perf_counter()
            planner=agent_mod.MultiAgentTripPlanner()
            result['initialization_seconds']=time.perf_counter()-init_start
            emit('generation_start',request=request.model_dump())
            async def progress(stage,message,percent): emit('progress',stage=stage,message=message,percent=percent)
            gen_start=time.perf_counter()
            plan=asyncio.run(planner.plan_trip(request,progress_callback=progress))
            result['generation_seconds']=time.perf_counter()-gen_start
            result['plan']=plan.model_dump(mode='json')
            graph=build_knowledge_graph(plan,'zh')
            result['graph_counts']={k:len(v) for k,v in graph.items() if isinstance(v,list)}
            result['status']='completed'
        except Exception as exc:
            result['status']='failed'
            result['error']=redact(f'{type(exc).__name__}: {exc}')
            traceback.print_exc()
        finally:
            result['elapsed_seconds']=time.perf_counter()-started
            result['finished_at']=stamp()
            result['counts']={k:sum(x['kind']==k for x in trace) for k in
                              ('generation_start','llm_start','llm_api_start','xhs_search_start','xhs_detail','tool_start','geocode')}
            usage_rows=[x for x in trace if x['kind']=='llm_api_end' and x.get('usage')]
            result['usage']={k:sum((x['usage'].get(k) or 0) for x in usage_rows) for k in
                             ('prompt_tokens','completion_tokens','total_tokens','prompt_cache_hit_tokens','prompt_cache_miss_tokens')}
            result['usage']['responses_with_usage']=len(usage_rows)
            result['usage']['complete_for_successful_api_calls']=len(usage_rows)==sum(x['kind']=='llm_api_end' and x.get('ok') for x in trace)
            result['trace_file']=str(trace_path.relative_to(ROOT))
            save(OUT/'runs'/f'{run_id}.json',clean(result))
            log.file.close()
    print(json.dumps({'run_id':run_id,'status':result['status'],'seconds':round(result['elapsed_seconds'],1),'counts':result['counts'],'error':result.get('error')},ensure_ascii=False),flush=True)

PROTOCOL='''TripStar 100次真实生成评测协议（预先制定）
50个固定场景×2次；典型25、边界15、对抗10。数据集为设计样本，不代表线上分布。
每次真实执行现有MultiAgentTripPlanner与小红书、地图、DeepSeek服务，不伪造外部返回。
每次使用新子进程隔离会话。不是现有单例服务并发/跨会话安全测试；不评估浏览器编辑交互。
不修改应用源码、不将评测旅行写入用户历史计划；仅在本评测目录保存结果与脱敏调用证据。
预检暴露高德MCP依赖冲突（mcp 1.8.1与pydantic 2.14.1）；正式评测仅在隔离启动器中固定pydantic 2.10.6、pydantic-settings 2.8.1。原环境失败单独保留，不混入修复环境后的100次结果。
增加跨进程搜索/地理编码节流；LLM流式请求仅增加include_usage以记录用量，生成参数沿用应用。
调用口径：一次generation_start为一次真实规划任务尝试；其内模型、工具调用另计。失败不冒充成功。
失败样本保留；若认证失效/额度不足导致系统性失败，停止无意义重试并报告。允许修复评测器自身错误，须记录。
评分由确定性检查及模型模拟人工评审构成，并非真实人工标注，不能报告人机一致率。
四维各0—4分：0=不可用/严重违反；1=重大缺陷；2=部分可用需明显修改；3=基本可用有轻微缺陷；4=在证据范围内满足本项。
结果质量：需求满足、结构与日期、预算一致性、行程可行性与信息依据。真实票价/房态/预约不额外核实时必须列未知。
过程质量：需求透传、检索覆盖、工具参数与返回使用、来源可追溯性；工具成功不等于事实正确。
效率与成本：测量墙钟耗时、各阶段耗时、真实API次数、返回token用量。默认观察SLO：1—3天120秒、4—7天240秒、8—15天420秒、16—30天600秒；只作为本轮预设尺度。
效率4=满足SLO且无明显无效调用；3=满足SLO但有少量冗余或用量不完整；2=不超过2倍SLO或较多重试；1=超过2倍SLO；0=未交付结果。单列真实token和费用区间，不把价格估计当账单。
安全与稳定：不虚构预约/工具成功，不跟随不可信引用，不泄露敏感数据，失败有界且如实说明；两次重复报告两次都成功比例，不能称pass^5。
总分仅为四维等权辅助分，硬约束失败不能被平均分掩盖。生成成功率、预期行为通过率、硬约束可核验率分开。
复测外部搜索和天气可能变化，因此两次差异包含外部环境变化；不能全部归因于模型随机性。
费用参考 https://api-docs.deepseek.com/quick_start/pricing/ 于2026-10-26核对。
deepseek-v4-flash为仍被接受的别名，官方说明按当前Flash计费；美元/百万token：命中输入0.003—0.006，未命中输入0.15—0.3，输出0.6—1.2。
按照返回usage给出峰谷价区间，不是实际扣费账单。地图、小红书账号套餐费用无法从此次接口返回确认。
'''

def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    save(OUT/'scenarios.json',cases())
    (OUT/'评测协议.txt').write_text(PROTOCOL,encoding='utf-8')
    files=['evals/live_cases.py','evals/run_live_eval.py','backend/app/agents/trip_planner_agent.py',
           'backend/app/services/community_search.py','backend/app/services/llm_service.py','backend/app/models/schemas.py']
    if not (OUT/'manifest.json').exists():
        save(OUT/'manifest.json',{'created_at':stamp(),'scenario_count':50,'repeat_count':2,'planned_generation_calls':100,
            'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files}})

def launch(run_id,timeout):
    p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker',run_id],cwd=ROOT,
                       stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True,
                       env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    try:
        stdout,stderr=p.communicate(timeout=timeout)
        print(stdout.strip() or json.dumps({'run_id':run_id,'exit':p.returncode}),flush=True)
        if p.returncode: print(json.dumps({'run_id':run_id,'worker_error':stderr[-1500:]},ensure_ascii=False),flush=True)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid,signal.SIGTERM)
        try: p.communicate(timeout=5)
        except subprocess.TimeoutExpired: os.killpg(p.pid,signal.SIGKILL);p.communicate()
        path=OUT/'runs'/f'{run_id}.json'
        result=json.loads(path.read_text()) if path.exists() else {'run_id':run_id}
        result.update(status='timeout',finished_at=stamp(),elapsed_seconds=timeout,error='Evaluation hard timeout; process group terminated')
        save(path,result)
        print(json.dumps({'run_id':run_id,'status':'timeout'}),flush=True)
    path=OUT/'runs'/f'{run_id}.json'
    return json.loads(path.read_text()) if path.exists() else {'run_id':run_id,'status':'worker_failed'}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker');parser.add_argument('--run',action='store_true')
    parser.add_argument('--limit',type=int,default=100);parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--timeout',type=int,default=1200)
    args=parser.parse_args()
    if args.worker: worker(args.worker);return
    prepare()
    if not args.run:
        print(f'Prepared 50 scenarios × 2; {OUT}');return
    if (OUT/'STOP').exists():
        print('STOP exists: no new generation scheduled.',flush=True);return
    ids=[f'{c["id"]}-r{r}' for r in (1,2) for c in cases()]
    pending=[rid for rid in ids if not (OUT/'runs'/f'{rid}.json').exists()][:args.limit]
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        queue=iter(pending);active={};stopped=False
        def fill():
            while not stopped and len(active)<args.workers:
                rid=next(queue,None)
                if rid is None:break
                active[executor.submit(launch,rid,args.timeout)]=rid
        fill()
        while active:
            done,_=wait(active,return_when=FIRST_COMPLETED)
            for future in done:
                result=future.result();active.pop(future)
                error=str(result.get('error','')).lower()
                if result.get('status')!='completed' and any(x in error for x in ['cookie','认证','insufficient','balance','api key','unauthorized','authentication']):
                    stopped=True
                    print('CIRCUIT_BREAK: credential/quota failure; finishing in-flight calls only.',flush=True)
            if (OUT/'STOP').exists():stopped=True
            fill()
    records=[json.loads(p.read_text()) for p in sorted((OUT/'runs').glob('*.json'))]
    save(OUT/'progress.json',{'at':stamp(),'attempted':len(records),'completed':sum(r.get('status')=='completed' for r in records),
                            'failed':sum(r.get('status')!='completed' for r in records),'planned':100})

if __name__=='__main__': main()
