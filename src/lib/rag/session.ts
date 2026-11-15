import { createRun, applyEvent, isRunning, stopRun, type RagRun } from './state'
import { RagError, type ChatRequest, type RagTransport } from './protocol'
import {restoreSession,saveSession} from './persistence'

export type UserMessage = { id: string; role: 'user'; text: string }
export type AssistantMessage = { id: string; role: 'assistant'; run: RagRun }
export type ChatMessage = UserMessage | AssistantMessage
export type Conversation = { id: string; title: string; messages: ChatMessage[]; memoryToken:string; lastTurn:number }
type Snapshot = { conversations: Conversation[]; activeConversationId:string }
type Pending = { requestId: string; controller: AbortController }

/** A synchronous store keeps rapid submissions ordered even before React rerenders. */
export class RagSession {
  private snapshot: Snapshot
  private listeners = new Set<() => void>()
  private pending = new Map<string, Pending>()
  private persistenceTimer:ReturnType<typeof setTimeout>|undefined
  constructor(readonly transport: RagTransport, private newId: () => string = () => crypto.randomUUID(),private storage?:Storage) {
    this.snapshot=restoreSession(storage)??{conversations:[{id:'new-conversation',title:'New conversation',messages:[],memoryToken:crypto.randomUUID(),lastTurn:0}],activeConversationId:'new-conversation'}
  }
  getSnapshot = () => this.snapshot
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener) } }
  flush=()=>{clearTimeout(this.persistenceTimer);saveSession(this.storage,this.snapshot.conversations,this.snapshot.activeConversationId)}
  private publish(conversations: Conversation[]) {
    this.snapshot = { ...this.snapshot,conversations };this.listeners.forEach(l=>l())
    if(this.storage){clearTimeout(this.persistenceTimer);this.persistenceTimer=setTimeout(this.flush,150)}
  }
  setActiveConversation=(id:string)=>{if(this.snapshot.conversations.some(c=>c.id===id)){this.snapshot={...this.snapshot,activeConversationId:id};this.publish(this.snapshot.conversations);this.flush()}}
  private updateRun(conversationId: string, requestId: string, update: (run: RagRun) => RagRun) {
    this.publish(this.snapshot.conversations.map(c => c.id !== conversationId ? c : { ...c, messages: c.messages.map(m => m.role === 'assistant' && m.run.request.request_id === requestId ? { ...m, run: update(m.run) } : m) }))
  }
  newConversation = (): string => {
    const empty = this.snapshot.conversations.find(c => !c.messages.length)
    if (empty) return empty.id
    const id = this.newId()
    this.publish([...this.snapshot.conversations, { id, title: 'New conversation', messages: [],memoryToken:crypto.randomUUID(),lastTurn:0 }])
    this.flush()
    return id
  }
  setReasoningOpen = (conversationId: string, requestId: string, open: boolean) => this.updateRun(conversationId, requestId, run => ({ ...run, reasoningOpen: open }))
  cancel = (conversationId: string, reason = 'Generation stopped by you.') => {
    const active = this.pending.get(conversationId)
    if (!active) return
    this.pending.delete(conversationId) // Invalidate callbacks before aborting the network.
    this.updateRun(conversationId, active.requestId, run => stopRun(run, 'cancelled', 'cancelled', reason))
    active.controller.abort()
  }
  dispose = () => {
    for (const [conversationId, active] of this.pending) {
      this.pending.delete(conversationId)
      this.updateRun(conversationId, active.requestId, run => stopRun(run, 'interrupted', 'unmounted', 'The interface was closed before the response completed.'))
      active.controller.abort()
    }
    this.flush()
  }
  async send(conversationId: string, question: string): Promise<void> {
    question = question.trim()
    if (!question || question.length > 8000) return
    const before = this.snapshot.conversations.find(c => c.id === conversationId)
    if (!before) return
    this.cancel(conversationId, 'Replaced by a newer question in this conversation.')
    // Only completed question/answer pairs enter history; interrupted partial answers never become evidence.
    const history: ChatRequest['history'] = []
    before.messages.forEach((m, index) => {
      const previous = before.messages[index-1]
      if (m.role === 'assistant' && m.run.status === 'completed' && previous?.role === 'user' && m.run.blocks.reduce((size,block) => size+block.text.length+2,0) <= 100000) {
        history.push({ role: 'user', content: previous.text }, { role: 'assistant', content: m.run.blocks.map(b => b.text).join('\n\n') })
      }
    })
    // Whole pairs only, bounded so even long Unicode chats fit the API body limit.
    const recent:ChatRequest['history']=[];let budget=0
    for(let i=history.length-2;i>=0;i-=2){const pair=history.slice(i,i+2);const size=new TextEncoder().encode(JSON.stringify(pair)).length;if(budget+size>48000)break;recent.unshift(...pair);budget+=size;if(recent.length>=40)break}
    const clientTurn=Math.max(Date.now(),before.lastTurn+1)
    const request: ChatRequest = { protocol_version: 1, conversation_id: conversationId, request_id: this.newId(), message_id: this.newId(), question, history:recent,session_token:before.memoryToken,client_turn:clientTurn }
    const pending: Pending = { requestId: request.request_id, controller: new AbortController() }
    this.pending.set(conversationId, pending)
    this.publish(this.snapshot.conversations.map(c => c.id !== conversationId ? c : {
      ...c, lastTurn:clientTurn,title: c.messages.length ? c.title : question.slice(0, 48),
      messages: [...c.messages, { id: this.newId(), role: 'user', text: question }, { id: request.message_id, role: 'assistant', run: createRun(request) }],
    }))
    this.flush()
    try {
      await this.transport.stream(request, pending.controller.signal, event => {
        if (this.pending.get(conversationId) !== pending || pending.controller.signal.aborted) return
        this.updateRun(conversationId, request.request_id, run => applyEvent(run, event))
      })
      if (this.pending.get(conversationId) === pending) this.updateRun(conversationId, request.request_id, run => isRunning(run) ? stopRun(run, 'interrupted', 'interrupted', 'The stream ended before a completion event arrived.') : run)
    } catch (error) {
      if (this.pending.get(conversationId) !== pending) return
      const known = error instanceof RagError ? error : new RagError('interrupted', 'The agent connection was interrupted.')
      const status = known.code === 'cancelled' ? 'cancelled' : ['interrupted', 'timeout', 'protocol_error'].includes(known.code) ? 'interrupted' : 'failed'
      this.updateRun(conversationId, request.request_id, run => stopRun(run, status, known.code, known.message))
    } finally {
      if (this.pending.get(conversationId) === pending) this.pending.delete(conversationId)
      this.flush()
    }
  }
}
