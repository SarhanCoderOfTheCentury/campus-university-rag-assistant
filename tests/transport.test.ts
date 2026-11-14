import { describe, expect, it, vi } from 'vitest'
import { createRagTransport } from '../src/lib/rag/transport'
import { RagError, type RagEvent } from '../src/lib/rag/protocol'
import { encode, event, happyEvents, request } from './fixtures'

function response(body: string, size=7) {
  const bytes=new TextEncoder().encode(body);let offset=0
  return new Response(new ReadableStream({pull(controller){if(offset>=bytes.length){controller.close();return}controller.enqueue(bytes.slice(offset,offset+=size))}}),{headers:{'content-type':'text/event-stream; charset=utf-8'}})
}
const fetchReturning=(result: Response)=>vi.fn(async()=>result) as unknown as typeof fetch

describe('POST SSE integration',()=>{
  it('parses split UTF-8, BOM, CRLF and heartbeat comments without fabricating events',async()=>{
    const events=happyEvents();events[1]={...events[1],label:'[TEST] Searching کتاب 📚'} as RagEvent
    const received:RagEvent[]=[]
    const fetcher=fetchReturning(response('\ufeff: ping\r\nx-vendor: ignored\r\n\r\n'+encode(events,'\r\n'),1))
    await createRagTransport({endpoint:'/api/chat/stream',fetcher}).stream(request,new AbortController().signal,e=>received.push(e))
    expect(received).toEqual(events)
    expect(fetcher).toHaveBeenCalledTimes(1)
    const options=vi.mocked(fetcher).mock.calls[0][1]!
    expect(options.method).toBe('POST');expect(JSON.parse(options.body as string)).toEqual(request)
  })
  it('does not contact any guessed backend when unconfigured',async()=>{
    const fetcher=vi.fn() as unknown as typeof fetch
    const transport=createRagTransport({fetcher})
    await expect(transport.stream(request,new AbortController().signal,()=>{})).rejects.toMatchObject({code:'not_configured'})
    expect(fetcher).not.toHaveBeenCalled()
  })
  it('fails on EOF without completed and retains delivered deltas for the store',async()=>{
    const received:RagEvent[]=[]
    await expect(createRagTransport({endpoint:'/stream',fetcher:fetchReturning(response(encode(happyEvents().slice(0,8))))}).stream(request,new AbortController().signal,e=>received.push(e))).rejects.toMatchObject({code:'interrupted'})
    expect(received.at(-1)?.type).toBe('answer_delta')
  })
  it.each([
    ['wrong content type',new Response('<html>no</html>',{headers:{'content-type':'text/html'}}),'protocol_error'],
    ['authorization failure',new Response('',{status:401}),'http_401'],
    ['unavailable backend',new Response('',{status:503}),'http_503'],
  ])('handles %s without retrying',async(_name,res,code)=>{
    const fetcher=fetchReturning(res as Response)
    await expect(createRagTransport({endpoint:'/stream',fetcher}).stream(request,new AbortController().signal,()=>{})).rejects.toMatchObject({code})
    expect(fetcher).toHaveBeenCalledTimes(1)
  })
  it('rejects an event for a different request before updating state',async()=>{
    const received=vi.fn()
    const wrong={...event(1,{type:'started'}),conversation_id:'other'}
    await expect(createRagTransport({endpoint:'/stream',fetcher:fetchReturning(response(encode([wrong])))}).stream(request,new AbortController().signal,received)).rejects.toMatchObject({code:'protocol_error'})
    expect(received).not.toHaveBeenCalled()
  })
  it('rejects malformed event identity and never treats a truncated completion as success',async()=>{
    for(const body of [encode(happyEvents()).replace('event: started','event: completed'),encode(happyEvents()).slice(0,-2)]){
      await expect(createRagTransport({endpoint:'/stream',fetcher:fetchReturning(response(body))}).stream(request,new AbortController().signal,()=>{})).rejects.toBeInstanceOf(RagError)
    }
  })
  it('cancels the stream reader after the terminal event',async()=>{
    const cancel=vi.fn()
    const body=new ReadableStream({start(c){c.enqueue(new TextEncoder().encode(encode(happyEvents())))},cancel})
    await createRagTransport({endpoint:'/stream',fetcher:fetchReturning(new Response(body,{headers:{'content-type':'text/event-stream'}}))}).stream(request,new AbortController().signal,()=>{})
    expect(cancel).toHaveBeenCalled()
  })
  it('cleans up on abort and on idle timeout',async()=>{
    vi.useFakeTimers()
    try {
      const fetcher=vi.fn(async(_url:unknown,options:RequestInit|undefined)=>new Response(new ReadableStream({start(c){options?.signal?.addEventListener('abort',()=>c.error(options.signal?.reason),{once:true})}}),{headers:{'content-type':'text/event-stream'}})) as unknown as typeof fetch
      const external=new AbortController()
      const stopped=createRagTransport({endpoint:'/stream',fetcher}).stream(request,external.signal,()=>{}).catch(e=>e)
      await Promise.resolve();external.abort();expect((await stopped).code).toBe('cancelled')
      const timed=createRagTransport({endpoint:'/stream',fetcher,idleTimeoutMs:1000}).stream(request,new AbortController().signal,()=>{}).catch(e=>e)
      await vi.advanceTimersByTimeAsync(1001);expect((await timed).code).toBe('timeout')
      expect(vi.getTimerCount()).toBe(0)
    } finally { vi.useRealTimers() }
  })
})
