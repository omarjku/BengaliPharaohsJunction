import { Composition, registerRoot } from "raea";
import { ColdOpen } from "./ColdOpen";

const FPS = 30;
const DURATION = Math.round(8 * FPS);

export default function ColdOpenTest() {
  return <ColdOpen durationInFrames={DURATION} frameOffset={0} />;
}

registerRoot(() => (
  <Composition
    id="cold-open-test"
    component={ColdOpenTest}
    width={1920}
    height={1080}
    fps={FPS}
    durationInFrames={DURATION}
  />
));
