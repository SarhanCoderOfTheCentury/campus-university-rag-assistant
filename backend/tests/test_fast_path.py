import asyncio
from types import SimpleNamespace
import pytest
from backend.fast_path import direct_intent,BoundedTTL
from backend.university import UniversityAgent

def test_only_self_contained_topics_bypass_contextual_planning():
    assert direct_intent('What is the attendance requirement?')=='focused'
    assert direct_intent('List all degree programmes and fees')=='catalogue'
    assert direct_intent('List all postgraduate programmes')=='focused'
    assert direct_intent('Compare previous and current refund policies')=='historical'
    for question in ['What about that programme?','My name is TestReader.','Forget my name.','I prefer Urdu.','What is my fee?']:
        assert direct_intent(question) is None

def test_cache_is_bounded_and_expiring(monkeypatch):
    now=[10.0];monkeypatch.setattr('backend.fast_path.time.monotonic',lambda:now[0])
    cache=BoundedTTL(limit=2,ttl=1)
    cache.put('a',False);assert cache.get('a') is False
    cache.put('b',2);cache.put('c',3);assert cache.get('a') is None
    now[0]=12;assert cache.get('c') is None

@pytest.mark.asyncio
async def test_cancellation_checks_coalesce_but_forced_completion_check_is_fresh():
    agent=object.__new__(UniversityAgent);agent.cancel_cache=BoundedTTL(ttl=1);calls=[]
    async def check(_):calls.append(1);return len(calls)>1
    agent.cancelled=check
    request=SimpleNamespace(conversation_id='a',request_id='r',session_token='token')
    for _ in range(20):await agent.check_cancelled(request)
    assert len(calls)==1
    with pytest.raises(asyncio.CancelledError):await agent.check_cancelled(request,force=True)
