# Cold open candidates

Illustration, AI-generated. Generated with Gemini Omni Flash Preview through the Gemini API Interactions REST endpoint.

Model: `gemini-omni-flash-preview`

The selected clip is `candidate-a.mp4`: a single over-the-shoulder shot with the phone held in the centre, a blank dark screen, no visible face, and a stable screen plane for the notification composite. `candidate-b.mp4` was rejected because it introduced stray generated text in the lower-left corner. `candidate-c.mp4` was rejected as the alternative kitchen push-in because it did not provide a clean, front-facing phone screen for the required notification.

Prompts:

- `candidate-a.mp4`: “In a single continuous 8-second cinematic shot, over-the-shoulder POV from behind a professional chef at 06:00 in a dark Lapland kitchen. No face visible. The chef's hands hold a modern smartphone with the screen facing the camera, held fairly steady in the centre foreground; keep the screen mostly plain dark charcoal with no readable text, no logos, no app UI, so it can be composited later. Behind the phone is a busy professional kitchen in soft focus: cooks moving, steam rising, pans and stainless steel, cold blue dawn light through windows. Shallow depth of field, restrained handheld breathing, realistic documentary food-service cinematography, cool steel and blue palette, no cuts, no titles, no watermarks, no readable text.”
- `candidate-b.mp4`: “One unbroken 8-second cinematic shot, camera positioned behind the phone and chef's shoulder, looking over the shoulder at the chef's hands. The chef holds a smartphone upright in the exact centre and the glass screen faces camera, stays fairly steady and blank dark so a notification can be added in post. Never show the person's face. A dark professional Lapland kitchen wakes at 06:00 behind them: soft-focus cooks crossing, steam, pans, stainless prep tables, cold blue dawn through windows. Slow subtle push toward the phone, shallow depth of field, natural cool-blue light, grounded high-end food documentary realism, no cuts, no readable text, no logos, no graphic overlays, no watermarks.”
- `candidate-c.mp4`: “A single continuous 8-second cinematic dawn kitchen shot with a slow forward push through a bustling professional kitchen in Lapland at 06:00. Cold blue dawn light through windows, steam, stainless steel, pans, cooks moving with purposeful quiet urgency. Keep the central path clear and the foreground phone on a counter or in a chef's hand only as an out-of-focus anchor; no face, no readable text, no logos, no titles, no watermarks. Soft focus transitions toward the work, realistic documentary food-service cinematography, restrained camera movement, cool steel and blue palette, no cuts.”

Fallback: `../../media/coldopen-b.mp4` remains available if the selected generated clip is unavailable. It has the same dark Lapland kitchen look, but its phone geometry is less suitable for a stable notification plane.

Composite: the `ColdOpen` scene uses an 8-point keyframed 2D phone plane measured from extracted stills. Position, scale, and rotation are interpolated from the candidate-A phone corners; the iOS-style notification is nested inside that plane, so it follows the glass. It enters at 1.5 s with a 15-frame settle and a quiet local chime, then the camera punches toward the banner over the last 1.4 s.
