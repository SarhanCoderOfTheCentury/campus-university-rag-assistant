import {describe,it,expect} from 'vitest'
import {RagSession} from '../src/lib/rag/session'
import {restoreSession,SESSION_KEY} from '../src/lib/rag/persistence'
import type {ChatRequest,RagTransport} from '../src/lib/rag/protocol'
import {happyEvents} from './fixtures'

function storage():Storage{
  const items=new Map<string,string>()
  return {getItem:k=>items.get(k)??null,setItem:(k,v)=>{items.set(k,v)},removeItem:k=>{items.delete(k)},clear:()=>items.clear(),key:i=>[...items.keys()][i]??null,get length(){return items.size}}
}
function transport(requests:ChatRequest[]):RagTransport{return{configured:true,async stream(r,_signal,emit){requests.push(r);happyEvents(r).forEach(emit)}}}

describe('tab session memory',()=>{
  it('restores the active conversation and preserves its private token across refresh',async()=>{
    const saved=storage(),requests:ChatRequest[]=[]
    const first=new RagSession(transport(requests),undefined,saved)
    await first.send('new-conversation','My name is Sarhan.')
    const other=first.newConversation();first.setActiveConversation(other)
    await first.send(other,'I prefer English.')
    const restored=new RagSession(transport(requests),undefined,saved)
    expect(restored.getSnapshot().activeConversationId).toBe(other)
    expect(restored.getSnapshot().conversations[0].messages).toHaveLength(2)
    await restored.send(other,'What language do I prefer?')
    expect(requests[1].session_token).toBe(requests[2].session_token)
    expect(requests[0].session_token).not.toBe(requests[1].session_token)
    expect(requests[2].client_turn).toBeGreaterThan(requests[1].client_turn!)
    expect(requests[2].history[0].content).toBe('I prefer English.')
  })
  it('restores interrupted streams as interrupted, never completed history',async()=>{
    const saved=storage()
    const pending:RagTransport={configured:true,stream:()=>new Promise(()=>{})}
    const first=new RagSession(pending,undefined,saved)
    void first.send('new-conversation','Pending question')
    const restored=restoreSession(saved)!
    const last=restored.conversations[0].messages[1]
    expect(last.role==='assistant'&&last.run.status).toBe('interrupted')
    first.dispose()
  })
  it('rejects malformed or expired storage without breaking a new chat',()=>{
    const saved=storage();saved.setItem(SESSION_KEY,'{invalid')
    expect(restoreSession(saved)).toBeUndefined()
    const first=new RagSession(transport([]),undefined,saved);first.flush()
    const value=JSON.parse(saved.getItem(SESSION_KEY)!);value.savedAt=1;saved.setItem(SESSION_KEY,JSON.stringify(value))
    expect(restoreSession(saved)).toBeUndefined()
  })
  it('continues safely when browser storage is disabled',async()=>{
    const saved=storage();saved.setItem=()=>{throw new Error('quota denied')}
    const session=new RagSession(transport([]),undefined,saved)
    await session.send('new-conversation','Hello')
    expect(session.getSnapshot().conversations[0].messages).toHaveLength(2)
  })
})
