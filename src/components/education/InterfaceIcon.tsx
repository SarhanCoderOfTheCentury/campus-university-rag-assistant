import type { LucideIcon } from 'lucide-react'
import { cn } from 'cn'

type Props = {
  icon: LucideIcon
  size?: 'xs' | 'sm' | 'md' | 'lg'
  className?: string
}

const sizes = {
  xs: 'size-4',
  sm: 'size-5',
  md: 'size-6',
  lg: 'size-7',
}

/** Decorative icon treatment only; interaction and semantics stay with shadcn. */
export function InterfaceIcon({ icon: Icon, size = 'sm', className }: Props) {
  return <Icon className={cn('shrink-0 text-current', sizes[size], className)} strokeWidth={1.75} aria-hidden="true" />
}
