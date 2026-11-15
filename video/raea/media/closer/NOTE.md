# Closer footage

Model: `gemini-omni-flash-preview` via the Google GenAI Interactions API (`/v1beta/interactions`). The model currently returns 720p for this preview model; the requested 16:9 clips were generated at 24 fps. The first probe returned 10 seconds without a duration field and was trimmed to the chosen 8-second source. `candidate-b`, `candidate-c`, and `candidate-d` returned 8 seconds with `duration: "8s"`.

Every prompt included this negative direction: no visible faces, no eyes, no identifiable people, no readable text, no subtitles, no UI copy, no logos, no brand marks, no packaging labels, no watermark, no gibberish lettering, no surreal anatomy, no extra fingers, no warped hands, no duplicated objects, no morphing phone, no jump cuts, no camera shake, no fantasy lighting, no staged commercial smile. Keep the phone screen blank or softly glowing so it can be composited later.

## Candidate A — chosen

> Cinematic live-action illustration matching a high-end documentary film: a busy professional kitchen in Lapland, Finland, stainless steel worktables, copper pans, steam, large windows, realistic Nordic morning atmosphere, naturalistic skin and fabric, shallow depth of field, restrained production design, cool blue dawn transitioning into warm sunrise, 16:9 landscape. Now it is later in the morning and calm. Start in a tight over-the-counter three-quarter close-up of a chef’s bare hand setting a modern black smartphone face-up on a brushed steel pass. The phone lands with quiet certainty beside a folded linen and a pot sending up a soft ribbon of steam. The camera makes a slow, deliberate push toward the phone, then eases its focus to the calm kitchen beyond: cooks’ backs only, measured movement, golden sunlight flooding the windows. The phone display is a clean dark glow with no legible content and enough stable flat surface for a graphic overlay. Mood: relief, control, the decision is complete.

Chosen source: `candidate-a-8s.mp4`, a clean 8-second trim of `candidate-a.mp4`. It has the strongest continuity: one believable hand-to-phone action, no visible face, a stable screen plane for the confirmation composite, and the clearest cool-to-golden sunrise progression. The scene uses the first four seconds of this clip before the pixel-door transition.

## Candidate B

> Cinematic live-action illustration matching a high-end documentary film: a busy professional kitchen in Lapland, Finland, stainless steel worktables, copper pans, steam, large windows, realistic Nordic morning atmosphere, naturalistic skin and fabric, shallow depth of field, restrained production design, cool blue dawn transitioning into warm sunrise, 16:9 landscape. Begin with a low, intimate macro shot of a smartphone resting face-up on the steel counter beside a chef’s folded towel, a warm reflection sliding across its blank glass. In one continuous slow pull-back and slight rise, reveal the whole kitchen working calmly at sunrise: cooks’ backs only, steam catching the light, an orderly pass, no rush. Keep the phone in the foreground for the first half, then let the sunrise and controlled rhythm take over. The camera never stops abruptly. Mood: the pressure has dissolved; the chef’s system is now running.

Rejected because the phone leaves the usable foreground too early for the UI payoff.

## Candidate C

> Cinematic live-action illustration matching a high-end documentary film: a busy professional kitchen in Lapland, Finland, stainless steel worktables, copper pans, steam, large windows, realistic Nordic morning atmosphere, naturalistic skin and fabric, shallow depth of field, restrained production design, cool blue dawn transitioning into warm sunrise, 16:9 landscape. At a kitchen back door at sunrise, compose a medium close shot of a gloved hand stacking two plain unbranded insulated milk crates and a few unmarked white cases onto a stainless receiving trolley. The heavy back door is already open, warm golden light pours through it into the blue kitchen, and a calm worker’s torso passes in the background with face fully out of frame. The camera makes a smooth lateral dolly from the crates toward the open doorway, ending on the warm threshold and the organized trolley. The delivery is ready, intentional, and under control. No text or labels anywhere.

Rejected because it lands the delivery metaphor well but has no phone surface for the confirmed-order UI.

## Candidate D

> Cinematic live-action illustration matching a high-end documentary film: a busy professional kitchen in Lapland, Finland, stainless steel worktables, copper pans, steam, large windows, realistic Nordic morning atmosphere, naturalistic skin and fabric, shallow depth of field, restrained production design, cool blue dawn transitioning into warm sunrise, 16:9 landscape. A chef’s hands finish a decision at the stainless pass: one hand places a black smartphone face-up beside a closed, unmarked order clipboard, the other hand gives the clipboard one calm final tap and withdraws. The camera begins over the shoulder with the head completely cropped out, then arcs gently around the pass as sunrise turns the steel from blue to honey. Steam rises, a timer light glows softly in the background, and cooks’ backs move with quiet confidence. Keep the phone screen as a stable blank pale glow for later compositing. End on the composed still life of phone, closed clipboard, and working kitchen. Mood: the chef has the final say.

Rejected after frame review: the phone briefly disappears and reappears during the camera move, creating a visible continuity/morph risk.

The footage carries the on-screen label `Illustration · AI-generated` in `Closer.tsx`.
