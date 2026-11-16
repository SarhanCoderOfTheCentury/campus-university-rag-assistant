import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { ArrowUpIcon, BookOpenIcon, ChevronRightIcon, GraduationCapIcon, MoonIcon, PauseIcon, PlayIcon, PlusIcon, SquareIcon, SunIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Bubble, BubbleContent } from '@/components/ui/bubble'
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty'
import { InputGroup, InputGroupAddon, InputGroupText, InputGroupTextarea } from '@/components/ui/input-group'
import { Item, ItemContent, ItemDescription, ItemMedia, ItemTitle } from '@/components/ui/item'
import { Kbd, KbdGroup } from '@/components/ui/kbd'
import { Message, MessageAvatar, MessageContent } from '@/components/ui/message'
import { MessageScroller, MessageScrollerButton, MessageScrollerContent, MessageScrollerItem, MessageScrollerProvider, MessageScrollerViewport } from '@/components/ui/message-scroller'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupContent, SidebarGroupLabel, SidebarHeader, SidebarInset, SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarProvider, SidebarTrigger, useSidebar } from '@/components/ui/sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'
import { starterQuestions } from '@/data/questions'
import { useRagChat } from '@/hooks/use-rag-chat'
import { Spinner } from '@/components/ui/spinner'
import { SourceInspector } from '@/components/chat/SourceInspector'
import { InterfaceIcon } from '@/components/education/InterfaceIcon'
import { FlaticonIcon } from '@/components/education/FlaticonIcon'
import { isRunning } from '@/lib/rag/state'
import type { EvidenceSource } from '@/lib/rag/protocol'
import type { AssistantMessage } from '@/lib/rag/session'

const loadAssistantTurn = () => import('@/components/chat/AssistantTurn').then(module => ({ default: module.AssistantTurn }))
const preloadAssistantTurn = () => { void loadAssistantTurn().catch(() => { /* Lazy loading can retry when the response mounts. */ }) }
const AssistantTurn = lazy(loadAssistantTurn)
const EducationalMotion = lazy(() => import('@/components/education/EducationalMotion'))

/** Page assembly only. Every UI primitive is fetched from the official shadcn registry. */
export default function App() {
  return <TooltipProvider><SidebarProvider className="app-shell h-dvh min-h-0 overflow-hidden" style={{ '--sidebar-width': '16rem' } as React.CSSProperties}><CampusAssistant /></SidebarProvider></TooltipProvider>
}

function CampusAssistant() {
  // Fetch the Markdown/activity renderer while the student reads or types, so a
  // first question can show actual backend progress without waiting for its chunk.
  useEffect(() => {const timer=setTimeout(preloadAssistantTurn,1000);return ()=>clearTimeout(timer)},[])
  const { setOpen, setOpenMobile } = useSidebar()
  const { conversations, session, backendConfigured, activeConversationId:activeId } = useRagChat()
  const setActiveId=session.setActiveConversation
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [sourcesOpen, setSourcesOpen] = useState(false)
  const [selectedSource, setSelectedSource] = useState<string | null>(null)
  const [inspectorRequestId, setInspectorRequestId] = useState<string | null>(null)
  const [dark, setDark] = useState(false)
  const [motionPaused, setMotionPaused] = useState(false)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const active = conversations.find((chat) => chat.id === activeId) ?? conversations[0]
  const draft = drafts[activeId] ?? ''
  const latestAssistant = [...active.messages].reverse().find((message): message is AssistantMessage => message.role === 'assistant')
  const busy = latestAssistant ? isRunning(latestAssistant.run) : false
  const inspectedMessage = conversations.flatMap(chat => chat.messages).find((message): message is AssistantMessage => message.role === 'assistant' && message.run.request.request_id === inspectorRequestId)
  const inspectorSources = inspectedMessage ? Object.values(inspectedMessage.run.sources).sort((a, b) => a.citation_number - b.citation_number) : []

  function selectConversation(conversationId: string) {
    setActiveId(conversationId)
    setOpen(false)
    setOpenMobile(false)
  }

  function newChat() { selectConversation(session.newConversation()) }

  function inspectSource(source: EvidenceSource, requestId: string) {
    setInspectorRequestId(requestId); setSelectedSource(source.source_id); setSourcesOpen(true)
  }

  function openSources() {
    setInspectorRequestId(latestAssistant?.run.request.request_id ?? null)
    setSelectedSource(null); setSourcesOpen(true)
  }

  function fillPrompt(question: string) {
    setDrafts((previous) => ({ ...previous, [activeId]: question }))
    inputRef.current?.focus()
  }

  function submit() {
    const text = draft.trim()
    if (!text) return
    setDrafts(previous => ({ ...previous, [activeId]: '' }))
    void session.send(activeId, text)
  }

  return (
    <>
        <Sidebar collapsible="icon" className="border-r border-border/70">
          <SidebarHeader className="px-4 pt-5 pb-4 group-data-[collapsible=icon]:px-2">
            <div className="flex min-w-0 items-center gap-2 group-data-[collapsible=icon]:flex-col">
              <SidebarMenu className="min-w-0 flex-1 group-data-[collapsible=icon]:flex-none">
                <SidebarMenuItem>
                  <SidebarMenuButton size="lg" aria-label="Campus — new conversation" tooltip="Campus — new conversation" onClick={newChat} className="h-11 gap-2.5 p-0 hover:bg-transparent group-data-[collapsible=icon]:size-8!">
                    <Suspense fallback={<Skeleton className="size-10 shrink-0 rounded-xl group-data-[collapsible=icon]:size-8" />}><EducationalMotion variant="brand" dark={dark} paused={motionPaused} className="size-10 shrink-0 select-none group-data-[collapsible=icon]:size-8 [&_svg]:size-full!" /></Suspense>
                    <span className="flex min-w-0 flex-col gap-0.5 group-data-[collapsible=icon]:hidden"><span className="text-lg font-semibold tracking-tight">Campus</span><span className="truncate text-[10px] font-normal text-muted-foreground">Your university, made clearer</span></span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              </SidebarMenu>
              <SidebarTrigger className="shrink-0 text-muted-foreground" />
            </div>
            <SidebarMenu className="mt-5 group-data-[collapsible=icon]:mt-3"><SidebarMenuItem><SidebarMenuButton aria-label="New conversation" onClick={newChat} tooltip="New conversation" className="h-10 gap-2.5 border-0 bg-background font-normal shadow-none"><InterfaceIcon icon={PlusIcon} size="xs" /><span>New conversation</span></SidebarMenuButton></SidebarMenuItem></SidebarMenu>
          </SidebarHeader>
          <SidebarContent className="gap-6 px-2 group-data-[collapsible=icon]:px-0">
            <SidebarGroup>
              <SidebarGroupLabel className="mb-2 text-[10px] font-medium tracking-[0.14em] uppercase">Workspace</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem><SidebarMenuButton aria-label="Conversations" tooltip="Conversations" isActive onClick={() => selectConversation(active.id)}><FlaticonIcon name="conversation" /><span>Conversations</span></SidebarMenuButton></SidebarMenuItem>
                  <SidebarMenuItem><SidebarMenuButton aria-label="Source documents" tooltip="Source documents" onClick={openSources}><FlaticonIcon name="sources" /><span>Source documents</span></SidebarMenuButton></SidebarMenuItem>
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
            <SidebarGroup>
              <SidebarGroupLabel className="mb-2 text-[10px] font-medium tracking-[0.14em] uppercase">Conversations</SidebarGroupLabel>
              <SidebarGroupContent><SidebarMenu>
                {conversations.map((chat) => <SidebarMenuItem key={chat.id}><SidebarMenuButton aria-label={chat.title} tooltip={chat.title} onClick={() => selectConversation(chat.id)} isActive={chat.id === activeId} className="h-auto min-h-9 items-start py-2 text-xs"><FlaticonIcon name="conversation" className="mt-0.5" /><span className="line-clamp-2 whitespace-normal leading-5 group-data-[collapsible=icon]:hidden">{chat.title}</span></SidebarMenuButton></SidebarMenuItem>)}
              </SidebarMenu></SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
          <SidebarFooter className="gap-3 p-4 group-data-[collapsible=icon]:px-2">
            <SidebarMenu>
              <SidebarMenuItem><SidebarMenuButton tooltip={dark ? 'Light appearance' : 'Dark appearance'} aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'} onClick={() => { document.documentElement.classList.toggle('dark', !dark); setDark(!dark) }}>
                <InterfaceIcon icon={dark ? SunIcon : MoonIcon} size="xs" /><span>{dark ? 'Light appearance' : 'Dark appearance'}</span>
              </SidebarMenuButton></SidebarMenuItem>
              <SidebarMenuItem className="motion-reduce:hidden"><SidebarMenuButton tooltip={motionPaused ? 'Play animations' : 'Pause animations'} aria-label={motionPaused ? 'Play educational illustrations' : 'Pause educational illustrations'} onClick={() => setMotionPaused(!motionPaused)}>
                <InterfaceIcon icon={motionPaused ? PlayIcon : PauseIcon} size="xs" /><span>{motionPaused ? 'Play animations' : 'Pause animations'}</span>
              </SidebarMenuButton></SidebarMenuItem>
            </SidebarMenu>
            <Separator />
            <Item size="sm" className="gap-2.5 p-0 pt-1"><ItemMedia className="shrink-0"><InterfaceIcon icon={GraduationCapIcon} size="md" /></ItemMedia><ItemContent className="gap-0.5 group-data-[collapsible=icon]:hidden"><ItemTitle className="text-xs">Campus workspace</ItemTitle><ItemDescription className="text-[10px]">{backendConfigured ? 'Document-grounded answers' : 'Knowledge base not connected'}</ItemDescription></ItemContent></Item>
            <a href="https://www.flaticon.com/uicons" target="_blank" rel="noopener noreferrer" className="text-[9px] text-muted-foreground group-data-[collapsible=icon]:hidden">UIcons by Flaticon</a>
          </SidebarFooter>
        </Sidebar>

        <div className="fixed top-3 left-3 z-30 md:hidden"><SidebarTrigger aria-label="Open sidebar" className="border-0 bg-sidebar shadow-none" /></div>
        <SidebarInset aria-label="University assistant" className="h-dvh min-w-0 overflow-hidden bg-background">


          {active.messages.length === 0 ? (
            <section className="welcome-viewport relative flex min-h-0 flex-1 items-center justify-center overflow-hidden px-5 py-4 sm:px-10" aria-label="Welcome">
              <div className="welcome-content mx-auto flex w-full max-w-[710px] flex-col gap-7">
                <Empty className="flex-none gap-0 border-0 p-0"><EmptyHeader className="welcome-header w-full max-w-md gap-3">
                  <div className="welcome-art mb-1 w-full max-w-[420px]"><Suspense fallback={<Skeleton className="aspect-[16/5] w-full rounded-xl opacity-20" />}><EducationalMotion variant="campus" dark={dark} paused={motionPaused} className="w-full select-none" /></Suspense></div>
                  <Badge variant="secondary" className="welcome-eyebrow mb-1 border-0 px-2.5 py-1 text-[10px] font-normal tracking-wide shadow-none">THE UNIVERSITY ASSISTANT</Badge>
                  <EmptyTitle role="heading" aria-level={1} className="welcome-title text-3xl leading-tight font-medium tracking-tight sm:text-[38px]">A little clarity for<br />university life.</EmptyTitle>
                  <EmptyDescription className="welcome-description mt-1 max-w-sm text-sm leading-6">Ask about courses, policies, and campus support.{' '}<br className="hidden sm:block" />Your answers will start with university documents.</EmptyDescription>
                </EmptyHeader></Empty>
                <div className="grid grid-cols-3 gap-2 sm:gap-2.5">{starterQuestions.map((question) => <Button key={question.title} variant="outline" onClick={() => fillPrompt(question.question)} className="welcome-topic h-auto min-w-0 flex-col items-start justify-start gap-2 rounded-xl p-2 text-left shadow-none hover:shadow-none sm:p-3">
                  <span className="welcome-topic-top flex w-full flex-col items-center gap-1.5 sm:flex-row sm:gap-2.5"><Suspense fallback={<Skeleton className="welcome-topic-art h-10 w-11 shrink-0 rounded-md opacity-20" />}><EducationalMotion variant={question.icon === 'book' ? 'courses' : question.icon === 'file' ? 'policies' : 'support'} dark={dark} paused={motionPaused} className="welcome-topic-art w-9 shrink-0 select-none sm:w-11" /></Suspense><span className="whitespace-normal text-center text-[11px] leading-4 font-medium sm:text-left sm:text-xs">{question.title}</span><ChevronRightIcon className="ml-auto hidden size-3.5 shrink-0 text-muted-foreground sm:block" /></span>
                  <span className="welcome-topic-description hidden px-1 pb-1 whitespace-normal text-[11px] font-normal text-muted-foreground sm:inline">{question.description}</span>
                </Button>)}</div>
                <Button variant="link" onClick={openSources} className="welcome-example self-center text-xs font-normal text-muted-foreground">How sources support answers<ChevronRightIcon className="size-3" /></Button>
              </div>
            </section>
          ) : (
            <MessageScrollerProvider key={activeId} autoScroll defaultScrollPosition="last-anchor">
              <MessageScroller className="flex-1"><MessageScrollerViewport><MessageScrollerContent className="mx-auto max-w-[790px] gap-8 px-5 pt-14 pb-10 sm:px-10 sm:pt-10">
                {active.messages.map(message => <MessageScrollerItem key={message.id} messageId={message.id} scrollAnchor={message.role === 'user'}>
                  <Message align={message.role === 'user' ? 'end' : 'start'} className="gap-3">
                    {message.role === 'assistant' && <MessageAvatar className="mt-0.5 size-9 min-w-9 self-start overflow-visible rounded-none bg-transparent shadow-none group-has-data-[slot=message-footer]/message:translate-y-0"><InterfaceIcon icon={GraduationCapIcon} size="md" /></MessageAvatar>}
                    <MessageContent className="gap-5">
                      {message.role === 'user' ? <Bubble align="end" variant="muted" className="max-w-[94%] rounded-2xl rounded-br-md px-1 py-0.5 sm:max-w-[85%]"><BubbleContent className="text-sm leading-6 whitespace-pre-wrap">{message.text}</BubbleContent></Bubble> : <Suspense fallback={<Spinner aria-label="Loading response interface" />}><AssistantTurn run={message.run} onOpenChange={open => session.setReasoningOpen(activeId, message.run.request.request_id, open)} onInspect={source => inspectSource(source, message.run.request.request_id)} /></Suspense>}
                    </MessageContent>
                  </Message>
                </MessageScrollerItem>)}
              </MessageScrollerContent></MessageScrollerViewport><MessageScrollerButton aria-label="Scroll to latest message" /></MessageScroller>
            </MessageScrollerProvider>
          )}

          <footer className="z-10 shrink-0 bg-background px-5 pt-2 pb-4 sm:px-10 sm:pb-5">
            <div className="mx-auto max-w-[710px]">
              <form onSubmit={(event) => { event.preventDefault(); void submit() }}>
                <InputGroup className="prompt-surface rounded-2xl border-0 bg-background shadow-none has-[[data-slot=input-group-control]:focus-visible]:border-0 has-[[data-slot=input-group-control]:focus-visible]:ring-0">
                  <InputGroupTextarea ref={inputRef} aria-label="Ask the university assistant" aria-describedby="prompt-help" value={draft} onChange={(event) => setDrafts((previous) => ({ ...previous, [activeId]: event.target.value }))} onKeyDown={(event) => { if (event.key === 'Escape' && busy && !event.nativeEvent.isComposing) { event.preventDefault(); session.cancel(activeId); return } if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void submit() } }} placeholder="Ask about your university…" className="min-h-[66px] max-h-40 resize-none px-4 pt-4 pb-2 text-sm" maxLength={8000}  />
                  <InputGroupAddon align="block-end" className="justify-between gap-3 px-4 pb-3">
                    <InputGroupText className="gap-1.5 text-[10px]" title="Answers use the supplied fictional classroom dataset, not official university records."><InterfaceIcon icon={BookOpenIcon} size="xs" />Classroom dataset · Not official</InputGroupText>
                    <div className="ml-auto flex items-center gap-3">
                      <InputGroupText id="prompt-help" className="hidden gap-1.5 text-[10px] sm:flex"><Kbd className="h-4.5 border-0 px-1 text-[9px] shadow-inner">↵</Kbd>to ask<span className="mx-1">·</span><KbdGroup><Kbd className="h-4.5 border-0 px-1 text-[9px] shadow-inner">Shift</Kbd><Kbd className="h-4.5 border-0 px-1 text-[9px] shadow-inner">↵</Kbd></KbdGroup>new line</InputGroupText>
                      {busy ? <Button type="button" size="icon-lg" className="rounded-full border-0" aria-label="Stop generating" title="Stop generating" onClick={() => session.cancel(activeId)}><SquareIcon className="size-3.5 fill-current" /></Button> : <Button type="submit" size="icon-lg" className="rounded-full border-0" aria-label="Send message" title="Send message" disabled={!draft.trim()}><ArrowUpIcon className="size-4" /></Button>}
                    </div>
                  </InputGroupAddon>
                </InputGroup>
              </form>
              <p className="mt-3 text-center text-[10px] leading-4 text-muted-foreground">{backendConfigured ? 'Answers are grounded in the uploaded documents. Inspect citations for details.' : 'Knowledge base not connected. Questions cannot be answered yet.'}</p>
            </div>
          </footer>
        </SidebarInset>

        <SourceInspector open={sourcesOpen} onOpenChange={setSourcesOpen} sources={inspectorSources} selectedId={selectedSource} />
    </>
  )
}
