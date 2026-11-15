// Audio hooks. Defaults are false so the placeholder render is silent.
// scripts/render.mjs checks fs.existsSync(public/vo.wav) and fs.existsSync(public/music.mp3)
// at bundle/render time and passes hasVo / hasMusic as input props that override these defaults.
// To force them on without the script, flip the constants below.
export const HAS_VO = false; // public/vo.wav
export const HAS_MUSIC = false; // public/music.mp3 (played ducked under the voice)

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

// Shown on the end card. Replace if the submission repo URL differs.
export const REPO_URL = "github.com/omarjku/BengaliPharaohsJunction";
export const DISCLAIMER = "Valio challenge mock. No real orders or payments.";
export const AUTHORS = "Omar + Zoha";
