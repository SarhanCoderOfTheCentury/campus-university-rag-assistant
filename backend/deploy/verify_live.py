"""Exercise the deployed HTTPS service; records real events, never demo answers."""
import argparse,json,time,uuid
from pathlib import Path
import httpx
from backend.protocol import wire_event_adapter

p=argparse.ArgumentParser();p.add_argument('endpoint');p.add_argument('--origin',required=True);p.add_argument('--question',default='What degree programmes does DSU offer?');p.add_argument('--output',default='.deploy/live-check.json');args=p.parse_args()
request={'protocol_version':1,'conversation_id':str(uuid.uuid4()),'request_id':str(uuid.uuid4()),'message_id':str(uuid.uuid4()),'question':args.question,'history':[]}
start=time.monotonic();events=[];first_answer=None;envelope=None
with httpx.stream('POST',args.endpoint,json=request,headers={'Origin':args.origin,'Accept':'text/event-stream'},timeout=170) as response:
    print('HTTP',response.status_code,response.headers.get('content-type'),flush=True)
    response.raise_for_status()
    for line in response.iter_lines():
        if line.startswith('data: '):
            event=wire_event_adapter.validate_json(line[6:]).model_dump(exclude_none=True)
            assert event['request_id']==request['request_id'] and event['conversation_id']==request['conversation_id']
            assert event['sequence']==len(events)+1
            events.append(event)
            if event['type']=='answer_delta':
                first_answer=first_answer or round(time.monotonic()-start,3)
                print(event['delta'],flush=True)
            elif event['type'] in ['retrieval_completed','completed','error']:print(event['type'],event.get('message',event.get('outcome','')),flush=True)
answer='\n\n'.join(e['delta'] for e in events if e['type']=='answer_delta')
sources={e['source']['source_id']:e['source'] for e in events if e['type']=='document_found'}
for e in events:
    if e['type']=='answer_delta':assert all(sid in sources for sid in e['source_ids'])
result={'endpoint':args.endpoint,'question':args.question,'seconds':round(time.monotonic()-start,3),'first_answer_seconds':first_answer,'event_count':len(events),'terminal':events[-1] if events else None,'answer':answer,'events':events}
Path(args.output).parent.mkdir(parents=True,exist_ok=True);Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2))
assert events and events[-1]['type']=='completed','The deployed response did not complete successfully'
print('Live validated events:',len(events),'first answer seconds:',first_answer)
