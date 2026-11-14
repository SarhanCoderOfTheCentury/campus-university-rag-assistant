import { useCurrentFrame } from 'remotion'

export type EducationVariant = 'campus' | 'courses' | 'policies' | 'support' | 'brand'
export type EducationSceneProps = { variant: EducationVariant; dark: boolean }
export const EDUCATION_DURATION = 240
export const EDUCATION_FPS = 30

const palettes = {
  light: { ink: '#343b35', soft: '#8b9489', line: '#d6ddd2', paper: '#fdfdfb', shade: '#f0f3ec', accent: '#77936a', tint: '#e3ebdb', warm: '#d9bb82' },
  dark: { ink: '#d7dfd1', soft: '#929e8a', line: '#434d3d', paper: '#20251e', shade: '#171c15', accent: '#a5be91', tint: '#303d29', warm: '#c6ad7a' },
}
type Palette = typeof palettes.light

/** The drawings below are decorative artwork, not new UI controls. All motion is
 * derived from the Remotion frame: no CSS animation, randomness, timers, or media. */
function OpenBook({ palette: p, turn = 0 }: { palette: Palette; turn?: number }) {
  return <g stroke={p.ink} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M-67 1 Q-34-9 0 4 Q34-9 67 1 L70 42 Q35 29 0 43 Q-35 29-70 42Z" fill={p.tint} />
    <path d="M-63-5 Q-32-17 0-3 L0 36 Q-31 23-65 35Z" fill={p.paper} />
    <g transform={`rotate(${turn} 0 0)`}>
      <path d="M0-3 Q32-17 63-5 L65 35 Q31 23 0 36Z" fill={p.paper} />
      {[5,14,23].map((y) => <path key={y} d={`M12 ${y} Q32 ${y-7} 50 ${y-3}`} fill="none" stroke={p.line} />)}
      <path d="M45-10 L45 7 L51 3 L57 6 L57-7" fill={p.warm} stroke="none" />
    </g>
    {[5,14,23].map((y) => <path key={y} d={`M-51 ${y-3} Q-32 ${y-7}-13 ${y}`} fill="none" stroke={p.line} />)}
    <path d="M0-3V42" stroke={p.accent} />
    <path d="M-60 39 Q-29 29-5 40 M5 40 Q29 29 60 39" fill="none" stroke={p.soft} strokeWidth=".8" />
  </g>
}

function Document({ palette: p, progress = 1 }: { palette: Palette; progress?: number }) {
  return <g stroke={p.ink} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="-26" y="-28" width="48" height="62" rx="5" fill={p.shade} stroke={p.line} transform="rotate(-8)" />
    <path d="M-21-31 H11 L25-17 V32 Q25 36 21 36 H-21 Q-25 36-25 32 V-27 Q-25-31-21-31Z" fill={p.paper} />
    <path d="M11-31 V-19 Q11-17 13-17 H25" fill={p.tint} />
    <path d="M-14-13H1 M-14-4H13 M-14 5H13" stroke={p.line} />
    <circle cx="13" cy="26" r="12" fill={p.tint} stroke={p.accent} />
    <path d="M7 26 L11 30 L19 21" fill="none" stroke={p.accent} strokeWidth="1.8" pathLength="1" strokeDasharray="1" strokeDashoffset={1-progress} />
  </g>
}

function Support({ palette: p, phase = 0 }: { palette: Palette; phase?: number }) {
  return <g strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M-13-12 H24 Q31-12 31-5 V19 Q31 26 24 26 H19 L19 35 L9 26 H-13 Q-20 26-20 19 V-5 Q-20-12-13-12Z" fill={p.tint} stroke={p.line} />
    <path d="M-27-28 H15 Q23-28 23-20 V3 Q23 11 15 11 H-7 L-18 21 V11 H-27 Q-35 11-35 3 V-20 Q-35-28-27-28Z" fill={p.paper} stroke={p.ink} />
    {[-20,-7,6].map((x,i) => <circle key={x} cx={x} cy={-8+Math.sin(phase-i*.8)*1.8} r="2.1" fill={p.accent} opacity={.6+.4*(Math.sin(phase-i*.8)+1)/2} />)}
    <path d="M-2 19H16 M4 25H16" stroke={p.accent} />
  </g>
}

function bezier(t: number, points: [number, number][]) {
  const a=1-t
  return { x: a*a*a*points[0][0]+3*a*a*t*points[1][0]+3*a*t*t*points[2][0]+t*t*t*points[3][0], y: a*a*a*points[0][1]+3*a*a*t*points[1][1]+3*a*t*t*points[2][1]+t*t*t*points[3][1] }
}

export function EducationScene({ variant, dark }: EducationSceneProps) {
  const frame = useCurrentFrame()
  const phase = frame / EDUCATION_DURATION * Math.PI * 2
  const p = palettes[dark ? 'dark' : 'light']
  const float = Math.sin(phase)*2.5

  if (variant === 'brand') {
    const ink = dark ? '#20251e' : '#f7faf4'
    const background = dark ? '#f4f6f0' : '#111510'
    const accent = dark ? '#6c875e' : '#c8d8bc'
    return <svg className="size-full" xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64" aria-hidden="true" data-education-frame={frame}>
      <rect x="1" y="1" width="62" height="62" rx="19" fill={background} />
      <g transform={`translate(32 ${30+Math.sin(phase)*.65})`} stroke={ink} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" fill="none">
        <path d="M-17-3L0-10L17-3L0 4Z" fill={background} />
        <path d="M-10 1V9Q0 15 10 9V1" />
        <path d={`M17-3V8L${15.5+Math.sin(phase)*1.4} 12`} stroke={accent} />
        <path d="M-9 18Q0 15 9 18" stroke={accent} strokeWidth="1.2" opacity={.55+.2*Math.sin(phase)} />
      </g>
      <g transform={`translate(${46+Math.sin(phase)*.5} ${16+Math.cos(phase)*.5})`} stroke={accent} strokeWidth="1" strokeLinecap="round" opacity={.55+.2*Math.sin(phase)}><path d="M0-2V2M-2 0H2" /></g>
    </svg>
  }

  if (variant !== 'campus') {
    return <svg className="size-full" xmlns="http://www.w3.org/2000/svg" width="80" height="76" viewBox="0 0 80 76" aria-hidden="true" data-education-frame={frame}>
      <ellipse cx="40" cy="67" rx="25" ry="2" fill={p.shade} />
      <g transform={`translate(40 ${38+float*.45})`}>
        {variant === 'courses' ? <g transform="translate(0 -3) scale(.46)"><OpenBook palette={p} turn={Math.sin(phase)*2} /><path d="M-28-34 L0-45 L28-34 L0-23Z" fill={p.ink} /><path d="M-17-28 V-18 Q0-10 17-18 V-28" fill={p.tint} stroke={p.ink} strokeWidth="2" /></g> : variant === 'policies' ? <g transform="scale(.72)"><Document palette={p} progress={.9+.1*Math.sin(phase)} /></g> : <g transform="scale(.72)"><Support palette={p} phase={phase} /></g>}
      </g>
      <path d="M66 13V19 M63 16H69" stroke={p.accent} strokeWidth="1.2" strokeLinecap="round" opacity={.55+.25*Math.sin(phase)} />
    </svg>
  }

  const dot = bezier((frame/EDUCATION_DURATION+.2)%1,[[158,113],[212,42],[261,51],[285,91]])
  const dot2 = bezier((frame/EDUCATION_DURATION+.65)%1,[[365,91],[406,44],[447,36],[482,79]])
  // Dots fade at path endpoints so the loop has no visible jump.
  const fade = (t: number) => Math.min(1,t*8,(1-t)*8)
  return <svg className="size-full" xmlns="http://www.w3.org/2000/svg" width="640" height="200" viewBox="0 0 640 200" fill="none" aria-hidden="true" data-education-frame={frame}>
    <ellipse cx="320" cy="170" rx="99" ry="5" fill={p.shade} />
    <path d="M107 174H533" stroke={p.line} strokeWidth="1" strokeDasharray="1 8" strokeLinecap="round" />
    <path d="M158 113 C212 42 261 51 285 91 M365 91 C406 44 447 36 482 79" stroke={p.line} strokeWidth="1.3" strokeDasharray="3 6" strokeLinecap="round" />
    <circle cx={dot.x} cy={dot.y} r="3" fill={p.accent} opacity={fade((frame/EDUCATION_DURATION+.2)%1)} />
    <circle cx={dot2.x} cy={dot2.y} r="3" fill={p.warm} opacity={fade((frame/EDUCATION_DURATION+.65)%1)} />

    {/* A small, generic campus building — no real university building is implied. */}
    <g transform={`translate(94 ${93+float*.4})`} stroke={p.ink} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      <path d="M0 73 H104 L100 79 H4Z" fill={p.tint} stroke={p.line} />
      <path d="M8 31 H95 V73 H8Z" fill={p.paper} />
      <path d="M3 29 L51 5 L100 29Z" fill={p.shade} />
      <path d="M18 29 L51 13 L85 29" stroke={p.line} />
      <path d="M12 36H92 M12 68H92" stroke={p.line} />
      {[22,42,62,82].map(x => <g key={x}><path d={`M${x} 40V64`} stroke={p.soft} strokeWidth="3" /><path d={`M${x-4} 39H${x+4} M${x-4} 65H${x+4}`} stroke={p.soft} /></g>)}
      <path d="M51 4V-12 M51-12H68L62-7L68-2H51" stroke={p.accent} fill={p.tint} />
      <path d="M-9 74V56 M-9 63C-25 57-17 44-9 56 M-9 68C6 62-1 50-9 62" stroke={p.accent} />
    </g>

    <g transform={`translate(321 ${125+float*.35})`}><OpenBook palette={p} turn={Math.sin(phase)*1.5} /></g>
    <g transform={`translate(320 ${61-float}) rotate(${Math.sin(phase)*2})`} stroke={p.ink} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M-31 0L0-13L31 0L0 14Z" fill={p.ink} />
      <path d="M-20 6V20Q0 31 20 20V6" fill={p.tint} />
      <path d="M-31 0L0-13L31 0L0 14Z" fill={p.ink} />
      <path d="M0 0L27 2V24" stroke={p.warm} />
      <path d={`M27 24L${25+Math.sin(phase)} 30H${29+Math.sin(phase)}Z`} fill={p.warm} stroke={p.warm} />
    </g>

    <g transform={`translate(488 ${121-float*.6}) rotate(${4+Math.sin(phase)*1.2})`}><Document palette={p} />
      <g transform="translate(35 -15)" stroke={p.accent} strokeWidth="2" strokeLinecap="round"><circle r="13" fill={p.paper} /><path d="M9 9L20 20" /><path d="M-5 0H5 M0-5V5" strokeWidth="1.2" /></g>
    </g>
    <g stroke={p.accent} strokeWidth="1.4" strokeLinecap="round" opacity={.55+.2*Math.sin(phase)}>
      <path d="M222 54V66 M216 60H228" />
      <path d="M414 144V152 M410 148H418" />
      <circle cx="552" cy="90" r="2.5" stroke={p.warm} />
      <circle cx="77" cy="103" r="2" fill={p.tint} />
    </g>
  </svg>
}
