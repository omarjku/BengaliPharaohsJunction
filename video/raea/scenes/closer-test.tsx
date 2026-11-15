import { Composition, Mix, registerRoot } from "raea";
import { Closer } from "./Closer";

const FPS = 30;
const DURATION = 8 * FPS;

export default function CloserTest() {
  return (
    <>
      <Closer durationInFrames={DURATION} />
      <Mix lufs={-14} ceiling={-1.5} />
    </>
  );
}

registerRoot(() => (
  <Composition
    id="closer-test"
    component={CloserTest}
    width={1920}
    height={1080}
    fps={FPS}
    durationInFrames={DURATION}
  />
));
