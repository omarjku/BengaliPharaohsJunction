import { Composition, registerRoot } from "raea";
import { DoorTransition } from "./DoorTransition";

const FPS = 30;
const DURATION = Math.round(3.5 * FPS);

export default function DoorTransitionTest() {
  return <DoorTransition durationInFrames={DURATION} frameOffset={0} />;
}

registerRoot(() => (
  <Composition
    id="door-transition-test"
    component={DoorTransitionTest}
    width={1920}
    height={1080}
    fps={FPS}
    durationInFrames={DURATION}
  />
));
