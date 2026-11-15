import {cn} from 'cn'

/** Two official Flaticon UIcons glyphs; no external font/CDN request. */
export function FlaticonIcon({name,size='sm',className}:{name:'conversation'|'sources';size?:'sm'|'md'|'lg';className?:string}) {
  return <span aria-hidden="true" data-flaticon={name} className={cn('campus-flaticon inline-grid shrink-0 place-items-center leading-none',size==='lg'?'size-7 text-[28px]':size==='md'?'size-6 text-[24px]':'size-4 text-[16px]',className)}>{name==='conversation'?'\uf4bc':'\uf28d'}</span>
}
