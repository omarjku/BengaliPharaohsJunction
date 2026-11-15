// Render key frames to out/stills/*.png. Bundles once (the slow part), then renders every still.
// Usage: node scripts/stills.mjs [name-filter ...]   or   node scripts/stills.mjs --frame=1234 --name=custom
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
mkdirSync(resolve(root, "out/stills"), { recursive: true });

const STILLS = {
  "01-opening": 135, // 4.5 s
  "02-held-stamp": 975, // 32.5 s
  "03-confidence-bar": 2070, // 69 s
  "04-evidence-cards": 2370, // 79 s
  "05-trap-tickets": 2620, // 87.3 s
  "06-end-card": 3420, // 114 s
};
// Extra frames for review (not part of the six): node scripts/stills.mjs --all
const EXTRA = {
  "x02-intake": 270,
  "x03-reads": 480,
  "x04-checks": 700,
  "x06-strip": 1250,
  "x07-cannot": 1450,
  "x08-ordered": 1680,
  "x09-verify": 1900,
  "x13-fallback": 2800,
  "x14-agents": 3000,
  "x15-codex": 3200,
};

const args = process.argv.slice(2);
const all = args.includes("--all");
const filters = args.filter((a) => !a.startsWith("--"));
const set = all ? { ...STILLS, ...EXTRA } : STILLS;

const serveUrl = await bundle({ entryPoint: resolve(root, "src/index.ts"), onProgress: () => {} });
const props = { hasVo: false, hasMusic: false };
const composition = await selectComposition({ serveUrl, id: "FrontDoor", inputProps: props });
for (const [name, frame] of Object.entries(set)) {
  if (filters.length && !filters.some((f) => name.includes(f))) continue;
  await renderStill({
    composition,
    serveUrl,
    frame,
    output: resolve(root, `out/stills/${name}.png`),
    inputProps: props,
    timeoutInMilliseconds: 120000,
  });
  console.log("still", name, "frame", frame);
}
