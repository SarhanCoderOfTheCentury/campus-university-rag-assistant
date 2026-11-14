import { useEffect, useRef } from 'react'
import { Player, type PlayerRef } from '@remotion/player'
import { EDUCATION_DURATION, EDUCATION_FPS, EducationScene, type EducationVariant } from './EducationScene'

type Props = { variant: EducationVariant; dark: boolean; paused: boolean; className?: string }

/** Remotion is isolated to decorative SVGs; it never owns or changes chat state. */
export default function EducationalMotion({ variant, dark, paused, className }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const player = useRef<PlayerRef>(null)

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    let inViewport = false
    const syncPlayback = () => {
      if (!paused && !media.matches && document.visibilityState === 'visible' && inViewport) {
        void player.current?.play()
      } else {
        player.current?.pause()
      }
    }
    const observer = new IntersectionObserver(([entry]) => {
      inViewport = entry.isIntersecting
      syncPlayback()
    }, { threshold: 0.05 })
    if (container.current) observer.observe(container.current)
    media.addEventListener('change', syncPlayback)
    document.addEventListener('visibilitychange', syncPlayback)
    syncPlayback()
    return () => {
      observer.disconnect()
      media.removeEventListener('change', syncPlayback)
      document.removeEventListener('visibilitychange', syncPlayback)
      player.current?.pause()
    }
  }, [paused])

  return <div ref={container} className={className} data-motion-variant={variant} aria-hidden="true" inert>
    <Player
      ref={player}
      component={EducationScene}
      inputProps={{ variant, dark }}
      compositionWidth={variant === 'campus' ? 640 : variant === 'brand' ? 64 : 80}
      compositionHeight={variant === 'campus' ? 200 : variant === 'brand' ? 64 : 76}
      durationInFrames={EDUCATION_DURATION}
      fps={EDUCATION_FPS}
      loop
      autoPlay={false}
      controls={false}
      initiallyMuted
      numberOfSharedAudioTags={0}
      clickToPlay={false}
      doubleClickToFullscreen={false}
      spaceKeyToPlayOrPause={false}
      style={{ width: '100%', pointerEvents: 'none' }}
    />
  </div>
}
