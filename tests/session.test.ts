import { describe, expect, it } from 'vitest'
import { RagSession } from '../src/lib/rag/session'
import type { ChatRequest, RagEvent, RagTransport } from '../src/lib/rag/protocol'
import { event, happyEvents } from './fixtures'

function controlled() {
  const runs: {request:ChatRequest;signal:AbortSignal;emit:(e:RagEvent)=>void;finish:()=>void}[]=[]
  const transport:RagTransport={configured:true,stream(request,signal,emit){return new Promise<void>(resolve=>{
    runs.push({request,signal,emit,finish:resolve});signal.addEventListener('abort',()=>resolve(),{once:true})
  })}}
  let id=0
  return {runs,session:new RagSession(transport,()=>`test-id-${++id}`)}
}
const assistant=(session:RagSession,conversation='new-conversation')=>session.getSnapshot().conversations.find(c=>c.id===conversation)!.messages.filter(m=>m.role==='assistant')

describe('request isolation and lifecycle',()=>{
  it('replaces a rapid request in the same conversation and ignores its late events',async()=>{
    const {session,runs}=controlled()
    const first=session.send('new-conversation','[TEST] first question')
    runs[0].emit(event(1,{type:'started'},runs[0].request))
    const second=session.send('new-conversation','[TEST] second question')
    expect(runs[0].signal.aborted).toBe(true)
    runs[0].emit(event(2,{type:'answer_delta',block_id:'late',kind:'notice',delta:'LATE WRONG ANSWER',source_ids:[]},runs[0].request))
    happyEvents(runs[1].request).forEach(runs[1].emit);runs[1].finish()
    await Promise.all([first,second])
    const answers=assistant(session)
    expect(answers[0].run.status).toBe('cancelled');expect(answers[0].run.blocks).toHaveLength(0)
    expect(answers[1].run.status).toBe('completed');expect(answers[1].run.blocks[0].text).not.toContain('LATE')
  })
  it('keeps background conversations and citation catalogs independent',async()=>{
    const {session,runs}=controlled()
    const first=session.send('new-conversation','[TEST] first question')
    const other=session.newConversation()
    const second=session.send(other,'[TEST] other question')
    happyEvents(runs[1].request).forEach(runs[1].emit);runs[1].finish()
    expect(assistant(session)[0].run.status).toBe('connecting')
    happyEvents(runs[0].request).forEach(runs[0].emit);runs[0].finish()
    await Promise.all([first,second])
    expect(assistant(session)[0].run.status).toBe('completed');expect(assistant(session,other)[0].run.status).toBe('completed')
    expect(assistant(session)[0].run.request.request_id).not.toBe(assistant(session,other)[0].run.request.request_id)
  })
  it('preserves manual expansion while active and can reopen after automatic collapse',async()=>{
    const {session,runs}=controlled();const promise=session.send('new-conversation','[TEST] question')
    session.setReasoningOpen('new-conversation',runs[0].request.request_id,false)
    happyEvents(runs[0].request).slice(0,8).forEach(runs[0].emit)
    expect(assistant(session)[0].run.reasoningOpen).toBe(false)
    happyEvents(runs[0].request).slice(8).forEach(runs[0].emit);runs[0].finish();await promise
    expect(assistant(session)[0].run.reasoningOpen).toBe(false)
    session.setReasoningOpen('new-conversation',runs[0].request.request_id,true)
    expect(assistant(session)[0].run.reasoningOpen).toBe(true)
  })
  it('aborts active requests when disposed without overwriting finished messages',async()=>{
    const {session,runs}=controlled();const first=session.send('new-conversation','[TEST] first')
    happyEvents(runs[0].request).forEach(runs[0].emit);runs[0].finish();await first
    const pending=session.send('new-conversation','[TEST] pending')
    session.dispose();await pending
    expect(runs[1].signal.aborted).toBe(true)
    expect(assistant(session)[0].run.status).toBe('completed')
    expect(assistant(session)[1].run.status).toBe('interrupted')
  })
  it('sends history only from completed turns and includes the new question once',async()=>{
    const {session,runs}=controlled();const first=session.send('new-conversation','[TEST] first')
    happyEvents(runs[0].request).forEach(runs[0].emit);runs[0].finish();await first
    const interrupted=session.send('new-conversation','[TEST] interrupted');session.cancel('new-conversation');await interrupted
    const latest=session.send('new-conversation','[TEST] latest')
    expect(runs[2].request.history.map(m=>m.role)).toEqual(['user','assistant'])
    expect(runs[2].request.history[0].content).toBe('[TEST] first')
    expect(JSON.stringify(runs[2].request.history)).not.toContain('[TEST] latest')
    expect(JSON.stringify(runs[2].request.history)).not.toContain('[TEST] interrupted')
    session.cancel('new-conversation');await latest
  })
})
