"""Measure actual HTTPS SSE stage latency. Explicitly consumes live model quota."""
import argparse,json,time,uuid
from pathlib import Path
import httpx

ENDPOINT='https://vrn7rkajt4fke7okwkdrjj5jpq0zhfws.lambda-url.us-east-1.on.aws/api/chat/stream'
QUESTIONS=['What is the current attendance rule, lab exception and medical certificate deadline?', 'List all degree programmes with their duration and per-semester tuition in a table.']

def main():
 p=argparse.ArgumentParser();p.add_argument('--label',required=True);p.add_argument('--endpoint',default=ENDPOINT);args=p.parse_args();rows=[]
 for question in QUESTIONS:
  started=time.monotonic();marks={};events=[]
  body={'protocol_version':1,'conversation_id':str(uuid.uuid4()),'request_id':str(uuid.uuid4()),'message_id':str(uuid.uuid4()),'question':question,'history':[],'session_token':str(uuid.uuid4()),'client_turn':int(time.time()*1000)}
  with httpx.stream('POST',args.endpoint,json=body,headers={'Origin':'https://campus-university-rag-assistant-dqa.vercel.app','Accept':'text/event-stream'},timeout=170) as response:
   response.raise_for_status()
   for line in response.iter_lines():
    if not line.startswith('data: '):continue
    event=json.loads(line[6:]);events.append(event);marks.setdefault(event['type'],round(time.monotonic()-started,3))
  assert events and events[-1]['type']=='completed',events[-1] if events else 'No events'
  row={'question':question,'timings_seconds':marks,'server_elapsed_seconds':events[-1].get('elapsed_ms',0)/1000,'event_count':len(events),'answer':'\n\n'.join(e['delta'] for e in events if e['type']=='answer_delta'),'source_count':len(next(e for e in events if e['type']=='sources')['sources'])}
  rows.append(row);print(json.dumps({k:v for k,v in row.items() if k!='answer'}),flush=True)
  Path('.deploy').mkdir(exist_ok=True);Path('.deploy/latency-'+args.label+'.json').write_text(json.dumps(rows,indent=2)+'\n')

if __name__=='__main__':main()
