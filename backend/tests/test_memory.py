import json,time
from types import SimpleNamespace
import boto3,pytest
from botocore.stub import Stubber,ANY
from backend.memory import DynamoMemory,MemoryConflict,Notes,TurnMemory,bounded_history,merge_notes,redact,forget_all
from backend.protocol import ChatRequest

def request(**kwargs):
    return ChatRequest(protocol_version=1,conversation_id='memory-fixture',request_id='request-1',message_id='answer-1',question='My name is Sarhan.',history=[],session_token='00000000-0000-4000-8000-000000000001',client_turn=1,**kwargs)

def client():return boto3.client('dynamodb',region_name='us-east-1',aws_access_key_id='test',aws_secret_access_key='test')

def test_tokens_and_conversations_are_separate_namespaces():
    store=DynamoMemory(client(),'test-table');a=request()
    assert store.key(a)!=store.key(a.model_copy(update={'conversation_id':'another-conversation'}))
    assert store.key(a)!=store.key(a.model_copy(update={'session_token':'00000000-0000-4000-8000-000000000002'}))
    assert a.session_token not in store.key(a)

def test_notes_keep_corrections_and_honour_explicit_forgetting():
    previous=Notes(preferred_name='Hamza',programme='BS Software Engineering')
    updated=merge_notes(previous,Notes(preferred_name='Sarhan'),'Actually my name is Sarhan.')
    assert updated.preferred_name=='Sarhan' and updated.programme==previous.programme
    assert merge_notes(updated,None,'Forget my name.').preferred_name is None
    assert merge_notes(updated,None,"Don't forget my name.").preferred_name=='Sarhan'
    assert merge_notes(updated,Notes(preferred_name='Someone'),'Forget everything.').model_dump()==Notes().model_dump()
    assert not forget_all('Do not forget everything.')

def test_recent_history_is_bounded_by_whole_pairs_and_redacts_credentials():
    messages=[]
    for i in range(12):messages.extend([{'role':'user','content':f'question-{i}'},{'role':'assistant','content':f'answer-{i}'}])
    result=bounded_history(messages)
    assert len(result)==8 and result[0]['content']=='question-8'
    assert bounded_history(messages,max_chars=1)==[]
    assert 'abcdef' not in redact('api_key=abcdef')

def test_expired_memory_is_not_loaded_even_before_dynamodb_ttl_deletion():
    db=client();store=DynamoMemory(db,'test-table')
    with Stubber(db) as stub:
        stub.add_response('update_item',{'Attributes':{'expires_at':{'N':'1'},'notes':{'S':Notes(preferred_name='Expired').model_dump_json()}}})
        assert store.begin(request()).notes.preferred_name is None

def test_newer_turn_prevents_a_stale_completion_from_overwriting_memory():
    db=client();store=DynamoMemory(db,'test-table')
    with Stubber(db) as stub:
        stub.add_client_error('update_item',service_error_code='ConditionalCheckFailedException')
        with pytest.raises(MemoryConflict):store.commit(request(),TurnMemory(),'obsolete answer')

def test_forgetting_removes_value_from_recent_user_and_assistant_context():
    db=client();store=DynamoMemory(db,'test-table');captured={}
    def capture(params,**_):captured.update(params)
    db.meta.events.register('before-parameter-build.dynamodb.UpdateItem',capture)
    state=TurnMemory(notes=Notes(preferred_name='Sarhan'),recent=[{'role':'user','content':'My name is Sarhan.'},{'role':'assistant','content':'Hello Sarhan.'}],next_notes=Notes())
    with Stubber(db) as stub:
        stub.add_response('update_item',{})
        store.commit(request().model_copy(update={'question':'Forget my name.'}),state,'I have cleared your name, Sarhan.')
    stored=captured['ExpressionAttributeValues'][':recent']['S']
    assert 'Sarhan' not in stored
    assert captured['ConditionExpression']=='last_turn=:turn AND active_request=:rid'
