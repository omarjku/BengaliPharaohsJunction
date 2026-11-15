// Render the full video. Detects optional audio at render time (fs.existsSync) and passes it as input props.
// Usage: node scripts/render.mjs [outfile] [extra remotion render flags...]
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const out = process.argv[2] ?? "out/placeholder.mp4";
const extra = process.argv.slice(3);
const hasVo = existsSync(resolve(root, "public/vo.wav"));
const hasMusic = existsSync(resolve(root, "public/music.mp3"));
mkdirSync(resolve(root, "out"), { recursive: true });
writeFileSync(resolve(root, "out/props.json"), JSON.stringify({ hasVo, hasMusic }));
console.log(`HAS_VO=${hasVo} HAS_MUSIC=${hasMusic}`);
const r = spawnSync("npx", ["remotion", "render", "FrontDoor", out, "--props=out/props.json", ...extra], {
  cwd: root,
  stdio: "inherit",
  shell: true,
});
process.exit(r.status ?? 1);
