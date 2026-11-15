"""Capability-scoped, bounded, expiring conversation context; never document evidence."""
import hashlib,json,re,time
from dataclasses import dataclass,field
from pydantic import BaseModel,Field
from botocore.exceptions import ClientError

TTL=86400
PROFILE_FIELDS=['preferred_name','programme','campus','study_level','language','answer_style']

class Notes(BaseModel):
    preferred_name:str|None=Field(default=None,max_length=120)
    programme:str|None=Field(default=None,max_length=160)
    campus:str|None=Field(default=None,max_length=100)
    study_level:str|None=Field(default=None,max_length=100)
    language:str|None=Field(default=None,max_length=80)
    answer_style:str|None=Field(default=None,max_length=200)
    current_topic:str|None=Field(default=None,max_length=240)

class MemoryConflict(Exception):pass

def redact(text):
    text=re.sub(r'gh[pousr]_[A-Za-z0-9_]+|AKIA[A-Z0-9]{16}|AIza[\w-]{25,}|AQ\.Ab8[\w-]{20,}','[credential removed]',text)
    return re.sub(r'(?i)\b(password|secret[_ -]?key|api[_ -]?key)\s*[:=]\s*\S+',r'\1=[credential removed]',text)

def forget_requested(question):
    if re.search(r"(?i)\b(don't|do not|never)\s+(forget|clear|reset|remove)\b",question):return False
    return bool(re.search(r'(?i)\b(forget|remove|clear|reset|stop remembering)\b',question))

def forget_all(question):
    return forget_requested(question) and bool(re.search(r'(?i)\b(forget (everything|all)|clear (the |my )?(memory|context)|reset (the |my )?(memory|context))\b',question))

def merge_notes(previous,proposed,question):
    if forget_all(question):return Notes()
    values=previous.model_dump()
    if proposed:
        for key,value in proposed.model_dump().items():
            if value and redact(value)==value:values[key]=value
    if forget_requested(question):
        names={'preferred_name':r'\bname\b','programme':r'\b(programme|program|degree|interest)\b','campus':r'\bcampus\b','language':r'\blanguage\b','study_level':r'\b(year|semester|level)\b','answer_style':r'\b(style|format|preference)\b'}
        for key,pattern in names.items():
            if re.search(pattern,question,re.I):values[key]=None
    return Notes(**values)

def bounded_history(messages,max_chars=16000):
    pairs=[];size=0
    for i in range(len(messages)-2,-1,-2):
        pair=messages[i:i+2]
        if len(pair)!=2 or pair[0]['role']!='user' or pair[1]['role']!='assistant':continue
        safe=[{'role':m['role'],'content':redact(m['content'])} for m in pair]
        cost=sum(len(m['content']) for m in safe)
        if size+cost>max_chars:break
        pairs.insert(0,safe);size+=cost
        if len(pairs)>=4:break
    return [m for pair in pairs for m in pair]

@dataclass
class TurnMemory:
    notes:Notes=field(default_factory=Notes)
    recent:list=field(default_factory=list)
    next_notes:Notes|None=None

class DynamoMemory:
    def __init__(self,client,table):self.client=client;self.table=table
    def key(self,request):
        return 'memory:'+hashlib.sha256((request.session_token+'|'+request.conversation_id).encode()).hexdigest()
    def begin(self,request):
        if not request.session_token:return TurnMemory(recent=bounded_history([m.model_dump() for m in request.history]))
        try:
            result=self.client.update_item(TableName=self.table,Key={'pk':{'S':self.key(request)}},
                UpdateExpression='SET last_turn=:turn, active_request=:rid, expires_at=:ttl',
                ConditionExpression='attribute_not_exists(last_turn) OR last_turn < :turn OR expires_at < :now',
                ExpressionAttributeValues={':turn':{'N':str(request.client_turn)},':rid':{'S':request.request_id},':ttl':{'N':str(int(time.time())+TTL)},':now':{'N':str(int(time.time()))}},ReturnValues='ALL_OLD')
        except ClientError as exc:
            if exc.response['Error']['Code']=='ConditionalCheckFailedException':raise MemoryConflict('A newer turn already owns this conversation') from None
            raise
        old=result.get('Attributes',{})
        if int(old.get('expires_at',{}).get('N','0'))<=time.time():return TurnMemory()
        return TurnMemory(notes=Notes.model_validate_json(old.get('notes',{}).get('S','{}')),recent=bounded_history(json.loads(old.get('recent',{}).get('S','[]'))))
    def current(self,request):
        if not request.session_token:return True
        result=self.client.get_item(TableName=self.table,Key={'pk':{'S':self.key(request)}},ProjectionExpression='active_request',ConsistentRead=True)
        return result.get('Item',{}).get('active_request',{}).get('S')==request.request_id
    def commit(self,request,state,answer):
        if not request.session_token:return
        notes=state.next_notes or state.notes
        history=[] if forget_all(request.question) else state.recent
        # Explicitly forgotten values must not be reintroduced by recent transcripts.
        history=[] if forget_all(request.question) else history+[{'role':'user','content':request.question},{'role':'assistant','content':answer}]
        for key in PROFILE_FIELDS:
            old=getattr(state.notes,key)
            if old and getattr(notes,key) is None:
                history=[{**m,'content':re.sub(re.escape(old),'[forgotten preference]',m['content'],flags=re.I)} for m in history]
        recent=bounded_history(history)
        try:
            self.client.update_item(TableName=self.table,Key={'pk':{'S':self.key(request)}},
                UpdateExpression='SET notes=:notes, recent=:recent, expires_at=:ttl ADD committed_turns :one',
                ConditionExpression='last_turn=:turn AND active_request=:rid',
                ExpressionAttributeValues={':notes':{'S':notes.model_dump_json()},':recent':{'S':json.dumps(recent,ensure_ascii=False)},':ttl':{'N':str(int(time.time())+TTL)},':one':{'N':'1'},':turn':{'N':str(request.client_turn)},':rid':{'S':request.request_id}})
        except ClientError as exc:
            if exc.response['Error']['Code']=='ConditionalCheckFailedException':raise MemoryConflict('This turn was superseded') from None
            raise
