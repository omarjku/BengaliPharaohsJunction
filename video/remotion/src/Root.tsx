import React from "react";
import { Composition } from "remotion";
import { FPS, HEIGHT, WIDTH } from "./config";
import { FrontDoor, frontDoorDefaults } from "./FrontDoor";
import { TOTAL_SECONDS } from "./timeline";

export const Root: React.FC = () => (
  <Composition
    id="FrontDoor"
    component={FrontDoor}
    durationInFrames={TOTAL_SECONDS * FPS}
    fps={FPS}
    width={WIDTH}
    height={HEIGHT}
    defaultProps={frontDoorDefaults}
  />
);
