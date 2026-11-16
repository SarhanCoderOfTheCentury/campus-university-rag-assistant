"""Opt-in real-model regression checks; uses AWS credentials or GEMINI_API_KEY."""
import argparse,asyncio,json,os,re,time,uuid
from pathlib import Path
import boto3
from backend.university import UniversityAgent
from backend.protocol import ChatRequest

CASES=[
 ('catalogue','List all degree programmes with their duration and per-semester tuition in a table.',['Computer Science','Software Engineering','Artificial Intelligence','Electrical Engineering','Civil Engineering','Computer Engineering','Business Administration','MS','MBA','185,000','140,000']),
 ('attendance','Explain the current attendance rule, lab exception, and medical certificate deadline.',['75%','85%','5 working days']),
 ('comparison','Compare the current and previous attendance, add/drop, late fee and refund policies in tables.',['75%','80%','85%','3,000','500','12,000','10,000','75%','50%']),
 ('library_conflict','What is the library overdue fine?',['20','25']),
 ('admissions','Explain the complete admission process including required documents, test details and payment deadline.',['100','90','50','7 working days','10 calendar days','CNIC','4']),
 ('refund','What are the current withdrawal refunds and are one-time fees refundable?',['100%','75%','50%','30','security']),
 ('missing','What is the hostel room price per month?',[]),
]

async def main():
 p=argparse.ArgumentParser();p.add_argument('--case',choices=[c[0] for c in CASES]);args=p.parse_args()
 key=os.getenv('GEMINI_API_KEY') or json.loads(boto3.client('secretsmanager').get_secret_value(SecretId='campus-rag/gemini')['SecretString'])['GEMINI_API_KEY']
 agent=UniversityAgent(key);results=[];output=Path('.deploy/corpus-'+args.case+'-validation.json') if args.case else Path('.deploy/corpus-validation.json')
 for name,question,expected in CASES:
  if args.case and name!=args.case:continue
  started=time.monotonic();events=[]
  try:
   request=ChatRequest(protocol_version=1,conversation_id='corpus-check-'+str(uuid.uuid4()),request_id=str(uuid.uuid4()),message_id=str(uuid.uuid4()),question=question,history=[])
   async for event in agent.events(request):events.append(event)
   answer='\n\n'.join(e['delta'] for e in events if e['type']=='answer_delta')
   missing=[text for text in expected if text.lower() not in answer.lower()]
   assert events[-1]['type']=='completed',events[-1]
   assert not missing,'Missing expected details: '+str(missing)
   if name in ['catalogue','comparison']:assert re.search(r'(?m)^\|\s*:?-{3,}',answer),'Missing Markdown table'
   if name=='missing':assert events[-1]['outcome']=='no_evidence'
   assert not any(s in answer.lower() for s in ['fictional','demo data','classroom dataset'])
   final=next(e for e in events if e['type']=='sources' and e['final'])
   cited={sid for e in events if e['type']=='answer_delta' for sid in e['source_ids']}
   assert cited=={s['source_id'] for s in final['sources']}
   if name!='comparison':assert all('archived' not in s.get('section','') for s in final['sources'])
   row={'case':name,'passed':True,'answer':answer,'source_count':len(cited),'seconds':round(time.monotonic()-started,1)}
  except Exception as exc:row={'case':name,'passed':False,'error':type(exc).__name__+': '+str(exc)[:250]}
  results.append(row);output.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
  print(json.dumps(row,ensure_ascii=False),flush=True)
 assert all(r['passed'] for r in results),'Some checks failed; see .deploy/corpus-validation.json'
 print('All real-model corpus checks passed',flush=True)

if __name__=='__main__':asyncio.run(main())
