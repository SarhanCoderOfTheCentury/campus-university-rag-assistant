import {z} from 'zod'
import {chatRequestSchema,sourceSchema} from './protocol'
import {isRunning,stopRun} from './state'
import type {Conversation} from './session'

export const SESSION_KEY='campus-chat-session-v1'
const TTL=24*60*60*1000
const activity=z.object({id:z.string(),kind:z.enum(['retrieval','document','discovery','summary']),label:z.string(),status:z.enum(['running','completed','failed','interrupted']),detail:z.string().optional(),documentId:z.string().optional(),sourceIds:z.array(z.string()).optional()})
const run=z.object({request:chatRequestSchema,runId:z.string().optional(),sequence:z.number().int().nonnegative(),status:z.enum(['connecting','processing','answering','completed','failed','interrupted','cancelled']),activities:z.array(activity),sources:z.record(z.string(),sourceSchema),blocks:z.array(z.object({id:z.string(),text:z.string(),sourceIds:z.array(z.string()),kind:z.enum(['grounded','notice'])})),selectedSourceIds:z.array(z.string()),sourcesFinal:z.boolean(),reasoningOpen:z.boolean(),outcome:z.enum(['answered','no_evidence','clarification']).optional(),elapsedMs:z.number().optional(),error:z.object({code:z.string(),message:z.string()}).optional()})
const conversation=z.object({id:z.string().min(1).max(200),title:z.string().max(200),memoryToken:z.string().uuid(),lastTurn:z.number().int().nonnegative(),messages:z.array(z.discriminatedUnion('role',[
  z.object({id:z.string(),role:z.literal('user'),text:z.string().max(8000)}),
  z.object({id:z.string(),role:z.literal('assistant'),run}),
])).max(200)})
const stored=z.object({version:z.literal(1),savedAt:z.number(),activeConversationId:z.string(),conversations:z.array(conversation).min(1).max(20)})

export function restoreSession(storage:Storage|undefined):{conversations:Conversation[];activeConversationId:string}|undefined {
  if(!storage)return
  try {
    const raw=storage.getItem(SESSION_KEY)
    if(!raw)return
    if(raw.length>1600000)throw new Error('Oversized tab session')
    const value=stored.parse(JSON.parse(raw))
    if(Date.now()-value.savedAt>TTL)throw new Error('Expired tab session')
    if(new Set(value.conversations.map(c=>c.id)).size!==value.conversations.length)throw new Error('Duplicate conversation')
    const conversations=value.conversations.map(c=>({...c,messages:c.messages.map(m=>m.role==='assistant'&&isRunning(m.run)?{...m,run:stopRun(m.run,'interrupted','page_reloaded','The page was refreshed before this response completed.')}:m)}))
    return {conversations,activeConversationId:conversations.some(c=>c.id===value.activeConversationId)?value.activeConversationId:conversations[0].id}
  } catch {try{storage.removeItem(SESSION_KEY)}catch{/* Browser storage may be disabled. */}}
}

export function saveSession(storage:Storage|undefined,conversations:Conversation[],activeConversationId:string) {
  if(!storage)return
  try {
    // Do not recursively duplicate prior history in each persisted assistant request.
    const allCompact:Conversation[]=conversations.map(c=>({...c,messages:c.messages.slice(-80).map(m=>m.role==='assistant'?{...m,run:{...m.run,request:{...m.run.request,history:[]}}}:m)}))
    let compact=allCompact.filter(c=>c.id===activeConversationId||c.messages.length).slice(-20)
    if(!compact.some(c=>c.id===activeConversationId)){
      const active=allCompact.find(c=>c.id===activeConversationId)
      if(active)compact=[...compact.slice(-19),active]
    }
    const encode=()=>JSON.stringify({version:1,savedAt:Date.now(),activeConversationId,conversations:compact})
    let json=encode()
    while(json.length>1500000){
      const candidate=compact.find(c=>c.id!==activeConversationId&&c.messages.length>2)??compact.find(c=>c.messages.length>2)
      if(candidate)candidate.messages=candidate.messages.slice(2)
      else if(compact.length>1)compact=compact.filter(c=>c.id===activeConversationId)
      else return // Keep the in-memory session if one turn alone exceeds storage budget.
      json=encode()
    }
    storage.setItem(SESSION_KEY,json)
  }catch{/* Keep the active in-memory session when browser storage is unavailable. */}
}

export function tabStorage():Storage|undefined{try{return window.sessionStorage}catch{return undefined}}
