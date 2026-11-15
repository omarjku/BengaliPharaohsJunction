import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const projectDir = resolve(new URL(".", import.meta.url).pathname);
const timeline = readFileSync(resolve(projectDir, "timeline.ts"), "utf8");
const number = (name) => Number(timeline.match(new RegExp(`export const ${name} = (\\d+)`))?.[1]);
const captionBandTop = number("CAPTION_BAND_TOP");
const contentSafeBottom = number("CONTENT_SAFE_BOTTOM");

if (captionBandTop !== 900 || contentSafeBottom !== 880 || contentSafeBottom >= captionBandTop) {
  throw new Error(`Caption layout constants invalid: contentSafeBottom=${contentSafeBottom}, captionBandTop=${captionBandTop}`);
}

// These are the authored bottom edges of information-bearing regions. The check is intentionally explicit: a new
// card, callout or end-card lockup must declare its bottom edge here before it can drift into the caption band.
const regions = [
  ["cold-open phone after punch", 876],
  ["door silhouette", 875],
  ["explanation steps", 676],
  ["demo callouts", 800],
  ["track-card facts", 850],
  ["closer confirmation screen", 864],
  ["closer lockup and footer", 870],
];
for (const [name, bottom] of regions) {
  if (bottom > contentSafeBottom) throw new Error(`${name} reaches y=${bottom}; caption band starts at y=${captionBandTop}`);
}

const outDir = resolve(projectDir, "out/v6-stills");
mkdirSync(outDir, { recursive: true });
const totalSeconds = 115;
const at = Array.from({ length: totalSeconds + 1 }, (_, second) => second * 30).join(",");
execFileSync("raea", ["render", "frontdoor.tsx", "--at", at, "-o", outDir], { cwd: projectDir, stdio: "inherit" });
console.log(`Caption band layout passed. Rendered ${totalSeconds + 1} stills to ${outDir}. Inspect the contact sheet at the shipping size; no information region may enter y >= ${captionBandTop}.`);
