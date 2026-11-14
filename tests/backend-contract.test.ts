import { readFileSync } from 'node:fs'
import { expect, it } from 'vitest'
import { eventSchema } from '../src/lib/rag/protocol'
import { applyEvent, createRun } from '../src/lib/rag/state'

it('accepts genuine FastAPI/LangChain fixture output with the frontend wire schema and state machine',()=>{
  const wire=JSON.parse(readFileSync(new URL('./backend-wire.generated.json',import.meta.url),'utf8')) as unknown[]
  const events=wire.map(value=>eventSchema.parse(value))
  const first=events[0]
  const request={protocol_version:1 as const,conversation_id:first.conversation_id,request_id:first.request_id,message_id:first.message_id,question:'[TEST] Contract verification',history:[]}
  const run=events.reduce(applyEvent,createRun(request))
  expect(run.status).toBe('completed')
  expect(run.blocks[0].text).toBe('[TEST FIXTURE] The library opens at 09:00.')
  expect(run.sources['fixture-source-1'].page_start).toBe(2)
})
