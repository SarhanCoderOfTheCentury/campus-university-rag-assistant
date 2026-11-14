import type { LucideIcon } from 'lucide-react'
import { cn } from 'cn'

type Props = {
  icon: LucideIcon
  size?: 'xs' | 'sm' | 'md' | 'lg'
  tone?: 'sage' | 'gold' | 'ink' | 'rose'
  className?: string
}

const sizes = {
  xs: 'size-5 rounded-[7px] [&_svg]:size-3',
  sm: 'size-7 rounded-[9px] [&_svg]:size-3.5',
  md: 'size-9 rounded-[11px] [&_svg]:size-[18px]',
  lg: 'size-12 rounded-[14px] [&_svg]:size-6',
}

/** Decorative icon treatment only; interaction and semantics stay with shadcn. */
export function DimensionalIcon({ icon: Icon, size = 'sm', tone = 'sage', className }: Props) {
  return <span className={cn('dimensional-icon', sizes[size], className)} data-tone={tone} aria-hidden="true">
    <span className="dimensional-icon__shine" />
    <Icon className="dimensional-icon__glyph" strokeWidth={1.8} />
  </span>
}
