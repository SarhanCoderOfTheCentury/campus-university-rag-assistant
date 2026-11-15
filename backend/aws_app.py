"""Public-document service with shared request budgets and explicit Lambda cancellation."""
import asyncio,hashlib,json,os,time
from functools import lru_cache
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException,Request
from fastapi.responses import JSONResponse
from .main import create_app
from .protocol import ChatRequest,Identifier,StrictModel
from .university import UniversityAgent
from .memory import DynamoMemory

ddb=boto3.client('dynamodb')
TABLE=os.getenv('RAG_LIMIT_TABLE','campus-rag-limits')
memory_store=DynamoMemory(ddb,TABLE)
ORIGINS=[x.strip() for x in os.getenv('RAG_ALLOWED_ORIGINS','').split(',') if x.strip()]

def validate_origin(request):
    if request.headers.get('origin') not in ORIGINS:raise HTTPException(403,'This origin is not enabled for the university assistant.')

def increment(key,limit,expiry):
    try:
        ddb.update_item(TableName=TABLE,Key={'pk':{'S':key}},UpdateExpression='SET expires_at=:ttl ADD used :one',ConditionExpression='attribute_not_exists(used) OR used < :limit',ExpressionAttributeValues={':ttl':{'N':str(expiry)},':one':{'N':'1'},':limit':{'N':str(limit)}})
    except ClientError as e:
        if e.response['Error']['Code']=='ConditionalCheckFailedException':raise HTTPException(429,'The request limit has been reached. Please try again later.') from None
        raise HTTPException(503,'The university assistant is temporarily unavailable.') from None

async def authorize(request:Request):
    validate_origin(request)
    now=int(time.time());address=request.client.host if request.client else 'unknown'
    ip=hashlib.sha256(address.encode()).hexdigest()[:24]
    await asyncio.to_thread(increment,f'global-day:{now//86400}',int(os.getenv('RAG_DAILY_LIMIT','100')),now+172800)
    await asyncio.to_thread(increment,f'ip-day:{ip}:{now//86400}',20,now+172800)
    await asyncio.to_thread(increment,f'ip-minute:{ip}:{now//60}',6,now+180)
    return {'scope':'public-university-documents'}

def cancel_key(request):
    values='|'.join([request.conversation_id,request.request_id,request.message_id])
    return 'cancel:'+hashlib.sha256(values.encode()).hexdigest()

async def cancelled(request):
    result=await asyncio.to_thread(ddb.get_item,TableName=TABLE,Key={'pk':{'S':cancel_key(request)}},ConsistentRead=True,ProjectionExpression='cancelled')
    explicit=result.get('Item',{}).get('cancelled',{}).get('BOOL',False)
    return explicit or (request.session_token is not None and not await asyncio.to_thread(memory_store.current,request))

@lru_cache(maxsize=1)
def agent():
    value=boto3.client('secretsmanager').get_secret_value(SecretId=os.getenv('RAG_PROVIDER_SECRET','campus-rag/gemini'))
    return UniversityAgent(json.loads(value['SecretString'])['GEMINI_API_KEY'],cancelled=cancelled,memory_store=memory_store)

async def factory(principal):return await asyncio.to_thread(agent)

app=create_app(service_factory=factory,authorize=authorize)

@app.middleware('http')
async def size_limit(request:Request,call_next):
    # Validate actual bytes as well as the header before Pydantic/history parsing.
    if request.method=='POST':
        body=await request.body()
        if len(body)>131072:return JSONResponse({'detail':'Request body is too large.'},status_code=413)
    return await call_next(request)

@app.get('/health')
async def health():
    manifest=json.loads((Path(__file__).parent/'data/manifest.json').read_text())
    return {'status':'ok','service':'campus-rag','protocol_version':1,'indexed_chunks':manifest['chunks'],'embedding_model':manifest['embedding_model'],'model':os.getenv('GEMINI_MODEL','gemini-3.5-flash-lite'),'release':os.getenv('RAG_RELEASE','unknown'),'memory':'isolated-conversation-context','memory_idle_ttl_seconds':86400}

class CancelRequest(StrictModel):
    conversation_id:Identifier
    request_id:Identifier
    message_id:Identifier

@app.post('/api/chat/cancel',status_code=202)
async def cancel(body:CancelRequest,request:Request):
    validate_origin(request)
    now=int(time.time())
    await asyncio.to_thread(increment,f'cancel-day:{now//86400}',500,now+172800)
    await asyncio.to_thread(ddb.put_item,TableName=TABLE,Item={'pk':{'S':cancel_key(body)},'cancelled':{'BOOL':True},'expires_at':{'N':str(int(time.time())+600)}})
    return {'status':'cancellation_requested'}
