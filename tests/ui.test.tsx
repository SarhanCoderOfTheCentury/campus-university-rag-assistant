import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { AssistantTurn } from '../src/components/chat/AssistantTurn'
import { applyEvent, createRun } from '../src/lib/rag/state'
import { happyEvents, request } from './fixtures'

describe('official component assembly',()=>{
  it('renders a numbered citation from structured evidence and an accessible collapsed timeline',()=>{
    const run=happyEvents().reduce(applyEvent,createRun(request))
    const markup=renderToStaticMarkup(<AssistantTurn run={run} onOpenChange={()=>{}} onInspect={()=>{}} />)
    expect(markup).toContain('Source 1: [TEST FIXTURE] Handbook, p. 2')
    expect(markup).toContain('Sources · 1')
    expect(markup).toContain('data-slot="trace-collapsible-trigger"')
    expect(markup).toContain('Activity completed. Expand activity')
    expect(markup).not.toContain('Student Handbook.pdf')
  })
  it('does not turn model-authored links, HTML or images into supporting sources',()=>{
    const run=happyEvents().reduce(applyEvent,createRun(request))
    run.blocks[0].text='[guessed document](https://fake.example/document) <script>alert(1)</script> ![track](https://fake.example/track.png)'
    const markup=renderToStaticMarkup(<AssistantTurn run={run} onOpenChange={()=>{}} onInspect={()=>{}} />)
    expect(markup).not.toContain('href="https://fake.example/document"')
    expect(markup).not.toContain('src="https://fake.example/track.png"')
    expect(markup).not.toContain('<script>')
  })
})
