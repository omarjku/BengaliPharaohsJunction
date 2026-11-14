// Keep the mic quiet while the agent's scheduled audio can leak into it. A much louder chef voice still barges in.
export function shouldSendMicChunk(level: number, playbackLevel: number, playbackActive: boolean, muted: boolean): boolean {
  if (muted) return false
  return !playbackActive || level > Math.max(playbackLevel * 1.5, playbackLevel + 0.08)
}
