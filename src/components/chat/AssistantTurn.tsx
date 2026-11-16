import { useState } from 'react'
import { Streamdown, type Components } from 'streamdown'
import { ArrowUpRightIcon, CheckIcon, CircleCheckIcon, CirclePauseIcon, CopyIcon, FileTextIcon, SearchIcon, SparklesIcon, TriangleAlertIcon } from 'lucide-react'
import { CodeBlock, CodeBlockActions, CodeBlockContent, CodeBlockCopyButton, CodeBlockHeader, CodeBlockTitle } from '@/components/ui/code-block'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card'
import { MessageFooter, MessageHeader } from '@/components/ui/message'
import { Spinner } from '@/components/ui/spinner'
import { InterfaceIcon } from '@/components/education/InterfaceIcon'
import { FlaticonIcon } from '@/components/education/FlaticonIcon'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Trace, TraceCollapsible, TraceCollapsibleContent, TraceCollapsibleTrigger, TraceDescription, TraceIcon, TraceLine, TraceTitle } from '@/components/ui/trace'
import { safeSourceUrl, type EvidenceSource } from '@/lib/rag/protocol'
import { isRunning, referencedSources, sourceLocation, sourceTitle, type RagRun } from '@/lib/rag/state'

// Generated answer text cannot introduce document links or remote images.
// Only structured backend evidence can create a clickable source citation.
const markdownComponents: Components = {
  a: ({ children }) => <span>{children}</span>,
  img: () => null,
  pre: ({ children }) => <>{children}</>,
  code: ({ children, className }) => {
    const value = String(children ?? '')
    if (!className?.startsWith('language-') && !value.includes('\n')) return <code className="rounded bg-muted px-1 py-0.5 text-xs">{children}</code>
    const language = className?.replace('language-', '')
    return <CodeBlock className="my-3"><CodeBlockHeader><CodeBlockTitle>{language ?? 'Code'}</CodeBlockTitle><CodeBlockActions><CodeBlockCopyButton value={value} /></CodeBlockActions></CodeBlockHeader><CodeBlockContent lineNumbers>{value.replace(/\n$/, '')}</CodeBlockContent></CodeBlock>
  },
}

type Props = {
  run: RagRun
  onOpenChange: (open: boolean) => void
  onInspect: (source: EvidenceSource) => void
}

/** Assembles the documented shadcn Reasoning, Chain of Thought, Sources and
 * Inline Citation patterns. No replacement UI primitives are implemented here. */
export function AssistantTurn({ run, onOpenChange, onInspect }: Props) {
  const [copied, setCopied] = useState(false)
  const [copyError, setCopyError] = useState(false)
  const busy = isRunning(run)
  const failed = ['failed', 'interrupted', 'cancelled'].includes(run.status)
  const sources = referencedSources(run)
  const currentActivity = [...run.activities].reverse().find(a => a.status === 'running')
  const title = run.status === 'connecting' ? 'Connecting to university assistant' : run.status === 'cancelled' ? 'Stopped' : run.status === 'interrupted' ? 'Connection interrupted' : run.status === 'failed' ? 'Unable to complete request' : run.status === 'completed' ? 'Activity completed' : currentActivity?.label ?? (run.status === 'answering' ? 'Writing response' : 'Waiting for agent activity')

  async function copy() {
    const text = run.blocks.map(b => `${b.text}${b.sourceIds.map(id => ` [${run.sources[id].citation_number}]`).join('')}`).join('\n\n')
    const references = sources.map(s => `[${s.citation_number}] ${sourceTitle(s)}${sourceLocation(s) ? ` · ${sourceLocation(s)}` : ''}\n${s.excerpt}${safeSourceUrl(s.url) ? `\n${s.url}` : ''}`).join('\n\n')
    const notice = run.status !== 'completed' ? '[Incomplete response — generation did not complete]\n\n' : ''
    try { await navigator.clipboard.writeText(`${notice}${text}${references ? `\n\nSources\n${references}` : ''}`); setCopied(true); setCopyError(false) }
    catch { setCopyError(true) }
  }

  return <>
    <MessageHeader className="gap-2 px-0 text-xs text-foreground">Campus<Badge variant="secondary" className="rounded border-0 px-1.5 py-0 text-[9px] font-normal text-muted-foreground shadow-[inset_0_1px_rgba(255,255,255,.65)]">Assistant</Badge></MessageHeader>
    <Trace>
      <TraceCollapsible open={run.reasoningOpen} onOpenChange={onOpenChange}>
        <TraceCollapsibleTrigger aria-label={`${title}. ${run.reasoningOpen ? 'Collapse' : 'Expand'} activity`}>
          <TraceLine status={busy ? 'running' : failed ? 'error' : undefined}>
            <TraceIcon>{busy ? <Spinner aria-label="Request is active" /> : <InterfaceIcon icon={failed ? TriangleAlertIcon : CircleCheckIcon} size="xs" />}</TraceIcon>
            <TraceTitle className="text-xs">{title}</TraceTitle>
            {run.elapsedMs !== undefined && <TraceDescription className="text-[10px]">{(run.elapsedMs/1000).toFixed(1)}s</TraceDescription>}
          </TraceLine>
        </TraceCollapsibleTrigger>
        <TraceCollapsibleContent keepMounted className="text-xs">
          {!run.activities.length && <p className="py-1 leading-6">{run.status === 'connecting' ? 'Waiting for the backend connection. No retrieval activity has been reported.' : run.error?.message ?? 'The backend has not reported processing activity.'}</p>}
          <Trace className="gap-3">
            {run.activities.map(step => <TraceCollapsible key={step.id}>
              <TraceCollapsibleTrigger>
                <TraceLine status={step.status === 'running' ? 'running' : step.status === 'failed' ? 'error' : step.status === 'interrupted' ? 'pending' : undefined} className="flex-wrap gap-y-1">
                  <TraceIcon>{step.status === 'running' ? <Spinner /> : <InterfaceIcon icon={step.status === 'interrupted' ? CirclePauseIcon : step.status === 'failed' ? TriangleAlertIcon : step.kind === 'document' || step.kind === 'discovery' ? FileTextIcon : step.kind === 'retrieval' ? SearchIcon : SparklesIcon} size="xs" />}</TraceIcon>
                  <TraceTitle className="text-xs">{step.label}</TraceTitle>
                  <TraceDescription className="text-[10px]">{step.status === 'running' ? 'In progress' : step.status === 'completed' ? 'Completed' : step.status === 'failed' ? 'Failed' : 'Interrupted'}</TraceDescription>
                </TraceLine>
              </TraceCollapsibleTrigger>
              <TraceCollapsibleContent keepMounted className="space-y-2 text-xs leading-6">
                {step.detail && <p className="whitespace-pre-wrap">{step.detail}</p>}
                {step.sourceIds?.map(id => run.sources[id]).filter(Boolean).map(source => <Button key={source.source_id} variant="ghost" size="sm" className="h-auto max-w-full justify-start gap-2 whitespace-normal border-0 px-0 py-1 text-left text-[11px]" onClick={() => onInspect(source)}><InterfaceIcon icon={FileTextIcon} size="xs" /><span>[{source.citation_number}] {sourceTitle(source)}{sourceLocation(source) ? ` · ${sourceLocation(source)}` : ''}</span></Button>)}
                {!step.detail && !step.sourceIds?.length && <p>No additional detail was provided by the agent.</p>}
              </TraceCollapsibleContent>
            </TraceCollapsible>)}
          </Trace>
        </TraceCollapsibleContent>
      </TraceCollapsible>
    </Trace>
    <p className="sr-only" role="status" aria-live="polite">{title}</p>
    {run.blocks.map(block => <div key={block.id} className="mb-4 text-sm leading-7 break-words text-foreground/90" data-answer-block={block.id}>
      <Streamdown mode="static" parseIncompleteMarkdown={false} isAnimating={busy} skipHtml components={markdownComponents} className="rag-markdown min-w-0 space-y-3 [&_h2]:mt-4 [&_h2]:text-base [&_h2]:font-medium [&_h3]:mt-3 [&_h3]:text-sm [&_h3]:font-medium [&_ul]:list-disc [&_ul]:space-y-1.5 [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:space-y-1.5 [&_ol]:pl-5">{block.text}</Streamdown>
      {block.sourceIds.map(id => run.sources[id]).map(source => <HoverCard key={source.source_id}>
        <HoverCardTrigger delay={100} closeDelay={150} render={<Button variant="secondary" size="xs" className="mx-0.5 inline-flex h-5 px-1.5 align-middle text-[10px] font-normal" aria-label={`Source ${source.citation_number}: ${sourceTitle(source)}${sourceLocation(source) ? `, ${sourceLocation(source)}` : ''}`} onClick={() => onInspect(source)} />} >[{source.citation_number}]</HoverCardTrigger>
        <HoverCardContent className="flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2 p-4"><p className="text-xs font-medium">[{source.citation_number}] {sourceTitle(source)}</p>{sourceLocation(source) && <p className="text-[10px] text-muted-foreground">{sourceLocation(source)}</p>}<p className="text-xs leading-6 text-muted-foreground">{source.excerpt}</p>{safeSourceUrl(source.url) && <a href={safeSourceUrl(source.url)} target="_blank" rel="noopener noreferrer" className="text-[11px] underline underline-offset-4">Open original document<span className="sr-only"> (opens in a new tab)</span></a>}<p className="text-[10px] text-muted-foreground">Click the citation to inspect its evidence.</p></HoverCardContent>
      </HoverCard>)}
    </div>)}
    {run.error && run.activities.length > 0 && <p role="alert" className="text-xs leading-6 text-destructive">{run.error.message}</p>}
    {failed && run.blocks.length > 0 && <p className="text-[11px] text-muted-foreground">This is an incomplete response. The received text and evidence have been preserved.</p>}
    {sources.length > 0 ? <Trace><TraceCollapsible>
      <TraceCollapsibleTrigger><TraceLine><TraceIcon><FlaticonIcon name="sources" /></TraceIcon><TraceTitle className="text-xs">Sources · {sources.length}</TraceTitle></TraceLine></TraceCollapsibleTrigger>
      <TraceCollapsibleContent keepMounted><Trace className="gap-3">{sources.map(source => <TraceCollapsible key={source.source_id}>
        <TraceCollapsibleTrigger><TraceLine><TraceIcon><InterfaceIcon icon={FileTextIcon} size="xs" /></TraceIcon><TraceTitle className="text-xs">[{source.citation_number}] {sourceTitle(source)}</TraceTitle>{sourceLocation(source) && <TraceDescription className="max-w-40 truncate text-[10px]">{sourceLocation(source)}</TraceDescription>}</TraceLine></TraceCollapsibleTrigger>
        <TraceCollapsibleContent keepMounted className="space-y-2 text-xs leading-6"><p>{source.excerpt}</p>{sourceLocation(source) && <p className="text-[10px]">{sourceLocation(source)}</p>}<div className="flex flex-wrap items-center gap-3"><Button variant="link" size="sm" onClick={() => onInspect(source)} className="h-auto p-0 text-xs">Inspect evidence</Button>{safeSourceUrl(source.url) ? <a href={safeSourceUrl(source.url)} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs underline underline-offset-4">Open document<ArrowUpRightIcon className="size-3" /><span className="sr-only"> (opens in a new tab)</span></a> : <span className="text-[10px]">No document link was provided.</span>}</div></TraceCollapsibleContent>
      </TraceCollapsible>)}</Trace></TraceCollapsibleContent>
    </TraceCollapsible></Trace> : !busy && <p className="text-[11px] leading-5 text-muted-foreground">{run.outcome === 'no_evidence' ? 'No supporting document sources were found for this question.' : run.status === 'completed' ? 'No supporting document sources were cited for this response.' : 'No supporting document sources were received before this request stopped.'}</p>}
    {run.blocks.length > 0 && <MessageFooter className="gap-2 px-0"><TooltipProvider><Tooltip><TooltipTrigger render={<Button variant="ghost" size="icon-xs" aria-label={copied ? 'Answer copied' : 'Copy answer'} onClick={copy} />}>{copied ? <CheckIcon className="size-3.5" /> : <CopyIcon className="size-3.5" />}</TooltipTrigger><TooltipContent>{copied ? 'Copied' : 'Copy answer'}</TooltipContent></Tooltip></TooltipProvider><span className="text-[10px] font-normal text-muted-foreground" aria-live="polite">{copyError ? 'Copy is unavailable in this browser.' : copied ? 'Copied to clipboard' : busy ? 'Response streaming' : run.status === 'completed' ? 'Response completed' : 'Partial response'}</span></MessageFooter>}
  </>
}
