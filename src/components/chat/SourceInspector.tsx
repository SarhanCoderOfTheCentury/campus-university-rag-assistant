import { ArrowUpRightIcon, FileTextIcon, LibraryIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty'
import { Item, ItemContent, ItemDescription, ItemHeader, ItemMedia, ItemTitle } from '@/components/ui/item'
import { Separator } from '@/components/ui/separator'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { safeSourceUrl, type EvidenceSource } from '@/lib/rag/protocol'
import { sourceLocation, sourceTitle } from '@/lib/rag/state'
import { DimensionalIcon } from '@/components/education/DimensionalIcon'

type Props = { open: boolean; onOpenChange: (open: boolean) => void; sources: EvidenceSource[]; selectedId: string | null }
export function SourceInspector({ open, onOpenChange, sources, selectedId }: Props) {
  return <Sheet open={open} onOpenChange={onOpenChange}><SheetContent className="w-full overflow-y-auto sm:max-w-[450px]">
    <SheetHeader className="border-0 bg-muted/20 p-6 pb-5"><Badge variant="secondary" className="mb-2 self-start gap-1.5 border-0 text-[10px] font-normal shadow-[inset_0_1px_rgba(255,255,255,.7)]"><DimensionalIcon icon={LibraryIcon} size="xs" tone="gold" />Retrieved evidence</Badge><SheetTitle className="text-xl font-medium tracking-tight">Sources, in context.</SheetTitle><SheetDescription className="text-xs leading-6">Document metadata and passages come directly from the retrieval backend. Reference numbers belong to the selected answer.</SheetDescription></SheetHeader>
    <div className="space-y-4 p-6">{sources.length ? sources.map(source => <Item key={source.source_id} className={`flex-col items-stretch gap-4 rounded-2xl border-0 p-4 shadow-[0_18px_40px_-30px_rgba(15,23,42,.7),inset_0_1px_rgba(255,255,255,.8)] ${selectedId === source.source_id ? 'bg-muted/70 -translate-y-0.5' : 'bg-muted/35'}`}>
      <ItemHeader><ItemMedia><DimensionalIcon icon={FileTextIcon} size="md" tone="gold" /></ItemMedia><Badge variant="secondary" className="border-0 text-[10px] font-normal shadow-inner">[{source.citation_number}]</Badge></ItemHeader><ItemContent className="gap-1"><ItemTitle className="text-sm">{sourceTitle(source)}</ItemTitle>{sourceLocation(source) && <ItemDescription className="text-xs">{sourceLocation(source)}</ItemDescription>}</ItemContent><Separator className="opacity-40" /><blockquote className="whitespace-pre-wrap text-xs leading-6 text-muted-foreground">{source.excerpt}</blockquote>
      {safeSourceUrl(source.url) ? <a href={safeSourceUrl(source.url)} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 self-start text-xs underline underline-offset-4">Open original document<ArrowUpRightIcon className="size-3" /><span className="sr-only"> (opens in a new tab)</span></a> : <p className="text-[10px] text-muted-foreground">No document link was provided by the backend.</p>}
    </Item>) : <Empty className="border-0 px-0 py-8"><EmptyHeader><EmptyMedia><DimensionalIcon icon={LibraryIcon} size="lg" tone="gold" /></EmptyMedia><EmptyTitle>No document evidence yet</EmptyTitle><EmptyDescription className="text-xs leading-6">Retrieved sources will appear here when the connected university assistant uses them. Source titles, pages, excerpts, and links are never guessed.</EmptyDescription></EmptyHeader></Empty> }</div>
  </SheetContent></Sheet>
}
