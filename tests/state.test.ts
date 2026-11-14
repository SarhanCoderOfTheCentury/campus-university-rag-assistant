import { describe, expect, it } from 'vitest'
import { applyEvent, createRun, referencedSources, stopRun } from '../src/lib/rag/state'
import { parseEvent, safeSourceUrl } from '../src/lib/rag/protocol'
import { event, happyEvents, request, source } from './fixtures'

describe('authoritative event state', () => {
  it('tracks genuine steps, streams a claim, deduplicates sources and collapses only at completion', () => {
    let run = createRun(request)
    expect(run.activities).toEqual([])
    expect(run.reasoningOpen).toBe(true)
    const events = happyEvents()
    for (const update of events.slice(0,-1)) run = applyEvent(run, update)
    expect(run.status).toBe('answering')
    expect(run.reasoningOpen).toBe(true)
    expect(run.blocks[0].text).toBe(source.excerpt)
    expect(referencedSources(run)).toEqual([source])
    run = applyEvent(run, events.at(-1)!)
    expect(run.status).toBe('completed')
    expect(run.reasoningOpen).toBe(false)
    expect(run.activities.every(a => a.status === 'completed')).toBe(true)
    expect(run.elapsedMs).toBe(173)
  })
  it('does not infer retrieval or processing from local request initiation', () => {
    const run = createRun(request)
    expect(run.status).toBe('connecting'); expect(run.activities).toHaveLength(0); expect(Object.keys(run.sources)).toHaveLength(0)
  })
  it('ignores replayed events without duplicating answer text', () => {
    let run = createRun(request)
    for (const update of happyEvents().slice(0,8)) { run = applyEvent(run, update); run = applyEvent(run, update) }
    expect(run.blocks[0].text).toBe('[TEST FIXTURE] The library ')
  })
  it.each(['request_id','conversation_id','message_id'] as const)('rejects events belonging to another %s', field => {
    expect(() => applyEvent(createRun(request), { ...event(1,{type:'started'}), [field]: 'other' })).toThrow('different request')
  })
  it('rejects missing, out-of-order, and mismatched run events', () => {
    expect(() => applyEvent(createRun(request), event(2,{type:'started'}))).toThrow('out of order')
    const run = applyEvent(createRun(request), event(1,{type:'started'}))
    expect(() => applyEvent(run, {...event(2,{type:'sources',sources:[],final:false}),run_id:'another'})).toThrow('different agent run')
    expect(() => applyEvent(createRun(request), event(1,{type:'answer_delta',block_id:'b',delta:'hello',source_ids:[],kind:'notice'}))).toThrow('started event')
  })
  it.each(['unknown', '__proto__', 'constructor'])('never treats unknown source %s as supporting evidence', id => {
    const run = applyEvent(createRun(request), event(1,{type:'started'}))
    expect(() => applyEvent(run,event(2,{type:'answer_delta',block_id:'b',kind:'grounded',delta:'claim',source_ids:[id]}))).toThrow('unknown')
  })
  it('requires citations on grounded blocks and immutable source metadata', () => {
    let run = createRun(request)
    for (const update of happyEvents().slice(0,3)) run = applyEvent(run, update)
    expect(() => applyEvent(run,event(4,{type:'answer_delta',block_id:'b',kind:'grounded',delta:'claim',source_ids:[]}))).toThrow('no source')
    expect(() => applyEvent(run,event(4,{type:'document_found',retrieval_id:'retrieval-1',source:{...source,title:'Invented change'}}))).toThrow('changed')
    expect(() => applyEvent(run,event(4,{type:'document_found',retrieval_id:'retrieval-1',source:{...source,source_id:'duplicate',citation_number:2}}))).toThrow('duplicate')
  })
  it('preserves two page/chunk references from the same document', () => {
    let run = createRun(request)
    for (const update of happyEvents().slice(0,3)) run=applyEvent(run,update)
    const second={...source,source_id:'fixture-source-2',chunk_id:'chunk-2',citation_number:2,page_start:3}
    run=applyEvent(run,event(4,{type:'document_found',retrieval_id:'retrieval-1',source:second}))
    expect(Object.keys(run.sources)).toHaveLength(2)
  })
  it('rejects reuse of a reading activity ID for different document evidence', () => {
    let run=createRun(request)
    for(const update of happyEvents().slice(0,3))run=applyEvent(run,update)
    const second={...source,source_id:'fixture-source-2',document_id:'another-document',chunk_id:'another-chunk',citation_number:2}
    run=applyEvent(run,event(4,{type:'document_found',retrieval_id:'retrieval-1',source:second}))
    run=applyEvent(run,event(5,{type:'document_reading',activity_id:'same-reading',document_id:source.document_id,source_ids:[source.source_id]}))
    expect(()=>applyEvent(run,event(6,{type:'document_reading',activity_id:'same-reading',document_id:second.document_id,source_ids:[second.source_id]}))).toThrow('identity')
  })
  it('marks unfinished operations interrupted, retains partial answer and ignores late events', () => {
    let run = createRun(request)
    for (const update of happyEvents().slice(0,8)) run=applyEvent(run,update)
    run=stopRun(run,'cancelled','cancelled','Stopped by student')
    expect(run.blocks[0].text).toBe('[TEST FIXTURE] The library ')
    expect(run.activities.at(-1)?.status).toBe('interrupted')
    expect(run.reasoningOpen).toBe(true)
    expect(applyEvent(run,happyEvents()[8])).toEqual(run)
  })
  it('rejects a final source list that contradicts inline citations', () => {
    let run=createRun(request)
    for(const update of happyEvents().slice(0,10))run=applyEvent(run,update)
    run=applyEvent(run,event(11,{type:'sources',sources:[],final:true}))
    expect(()=>applyEvent(run,event(12,{type:'completed',outcome:'answered'}))).toThrow('did not match')
  })
  it('supports a truthful no-evidence outcome', () => {
    let run=createRun(request)
    const payloads=[{type:'started'},{type:'answer_delta',block_id:'notice',kind:'notice',delta:'No relevant documents were found.',source_ids:[]},{type:'sources',sources:[],final:true},{type:'completed',outcome:'no_evidence'}]
    payloads.forEach((p,i)=>{run=applyEvent(run,event(i+1,p))})
    expect(run.outcome).toBe('no_evidence');expect(referencedSources(run)).toHaveLength(0)
  })
  it('validates backend payloads at runtime',()=>{
    expect(()=>parseEvent('{invalid')).toThrow('invalid activity')
    expect(()=>parseEvent(JSON.stringify({...event(1,{type:'started'}),protocol_version:2}))).toThrow()
    expect(()=>event(1,{type:'sources',sources:[{...source,page_start:0}],final:true})).toThrow()
  })
  it.each(['javascript:alert(1)','data:text/html,test','//evil.example/doc','/\\evil/doc','https://user:secret@example.com/doc',' https://example.com/doc'])('does not make unsafe source URL clickable: %s',url=>expect(safeSourceUrl(url)).toBeUndefined())
  it('uses provided safe URLs unchanged; never reconstructs a missing URL',()=>{
    expect(safeSourceUrl('/documents/real-id?page=2')).toBe('/documents/real-id?page=2')
    expect(safeSourceUrl('https://university.example/document.pdf#page=2')).toBe('https://university.example/document.pdf#page=2')
    expect(safeSourceUrl()).toBeUndefined()
  })
})
