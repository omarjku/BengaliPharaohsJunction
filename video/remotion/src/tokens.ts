import { loadFont } from "@remotion/google-fonts/Roboto";

const { fontFamily } = loadFont("normal", {
  weights: ["400", "500", "700", "900"],
  subsets: ["latin"],
});

export const FONT = `${fontFamily}, Roboto, Arial, sans-serif`;

export const C = {
  ink: "#1C1F23",
  paper: "#FFFFFF",
  wash: "#F5F6F8",
  blue: "#0B5CAD",
  amber: "#8A5A00",
  amberBg: "#FFF4DC",
  green: "#1E7A3C",
  greenBg: "#E8F5EC",
  red: "#B3261E",
  redBg: "#FDECEA",
  mute: "#5B636C",
  line: "#D5DAE0",
  cold: "#8EC0FF", // cold blue light for the night-kitchen look
  coldDeep: "#0B3A6E",
};

export type Tone = "amber" | "green" | "red" | "blue" | "ink";

export const TONES: Record<Tone, { fg: string; bg: string }> = {
  amber: { fg: C.amber, bg: C.amberBg },
  green: { fg: C.green, bg: C.greenBg },
  red: { fg: C.red, bg: C.redBg },
  blue: { fg: C.blue, bg: "#E6F0FA" },
  ink: { fg: C.ink, bg: C.wash },
};
