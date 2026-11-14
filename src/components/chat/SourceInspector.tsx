import { ArrowUpRightIcon, FileTextIcon, LibraryIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty'
import { Item, ItemContent, ItemDescription, ItemHeader, ItemMedia, ItemTitle } from '@/components/ui/item'
import { Separator } from '@/components/ui/separator'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { safeSourceUrl, type EvidenceSource } from '@/lib/rag/protocol'
import { sourceLocation, sourceTitle } from '@/lib/rag/state'

type Props = { open: boolean; onOpenChange: (open: boolean) => void; sources: EvidenceSource[]; selectedId: string | null }
export function SourceInspector({ open, onOpenChange, sources, selectedId }: Props) {
  return <Sheet open={open} onOpenChange={onOpenChange}><SheetContent className="w-full overflow-y-auto sm:max-w-[450px]">
    <SheetHeader className="border-b p-6 pb-5"><Badge variant="secondary" className="mb-2 self-start gap-1.5 text-[10px] font-normal"><LibraryIcon className="size-3" />Retrieved evidence</Badge><SheetTitle className="text-xl font-medium tracking-tight">Sources, in context.</SheetTitle><SheetDescription className="text-xs leading-6">Document metadata and passages come directly from the retrieval backend. Reference numbers belong to the selected answer.</SheetDescription></SheetHeader>
    <div className="space-y-4 p-6">{sources.length ? sources.map(source => <Item key={source.source_id} variant="outline" className={`flex-col items-stretch gap-4 rounded-xl p-4 ${selectedId === source.source_id ? 'ring-2 ring-ring/40' : ''}`}>
      <ItemHeader><ItemMedia variant="icon"><FileTextIcon className="size-4" /></ItemMedia><Badge variant="outline" className="text-[10px] font-normal">[{source.citation_number}]</Badge></ItemHeader><ItemContent className="gap-1"><ItemTitle className="text-sm">{sourceTitle(source)}</ItemTitle>{sourceLocation(source) && <ItemDescription className="text-xs">{sourceLocation(source)}</ItemDescription>}</ItemContent><Separator /><blockquote className="whitespace-pre-wrap text-xs leading-6 text-muted-foreground">{source.excerpt}</blockquote>
      {safeSourceUrl(source.url) ? <a href={safeSourceUrl(source.url)} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 self-start text-xs underline underline-offset-4">Open original document<ArrowUpRightIcon className="size-3" /><span className="sr-only"> (opens in a new tab)</span></a> : <p className="text-[10px] text-muted-foreground">No document link was provided by the backend.</p>}
    </Item>) : <Empty className="border-0 px-0 py-8"><EmptyHeader><EmptyMedia variant="icon"><LibraryIcon /></EmptyMedia><EmptyTitle>No document evidence yet</EmptyTitle><EmptyDescription className="text-xs leading-6">Retrieved sources will appear here when the connected university assistant uses them. Source titles, pages, excerpts, and links are never guessed.</EmptyDescription></EmptyHeader></Empty> }</div>
  </SheetContent></Sheet>
}
