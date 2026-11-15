# Front Door: demo-take checklist

## Write this list

Use one clean white sheet. Write large, dark, and by hand. Keep the Finnish accents. Do not add instructions to the agent on the sheet. The photo reader treats instruction-like text as untrusted data and removes it from the order (`backend/app/vision.py`).

```text
TILAUS MAANANTAILLE · 500 ASIAKASTA
1000 l Valio Eila 3 % maitojuomaa, laktoositon
25 kg perunoita
15 kg suolatonta voita
30 kg mozzarellaa
10 kg vehnäjauhoja
3 kg Valio Viola -tuorejuustoa, laktoositon
20 l vispikermaa, laktoositon
```

The seven item lines use product terms already present in the project’s Valio catalogue, evaluation, or test fixtures: lactose-free milk drink, potatoes, unsalted butter, mozzarella, wheat flour, lactose-free cream cheese, and whipping cream. The take still has to show the app selecting a real catalogue product for each line. Do not write **Arla**; it is not a Valio product. If a fresh catalogue search cannot match a line, replace that line before recording and record the replacement in the take notes.

The `1000 l` milk line is the intended hold trigger. The current evidence shows the milk line at **€1,560**, above the seeded kitchen’s **€1,500 auto-approval limit**, but the challenge mock can change. Show the number only if the live card shows it. If the live card holds for stock, cut-off, unknown stock, or another real reason, use that reason instead.

## Exact Talk change

After the pending card is visible, tap **Talk** and say this once, in English:

> Change the potatoes to 30 kilograms.

Wait for the transcript and the updated pending card. Do not say “approve”, “place the order”, or “go ahead” as the change command. The live voice path supports English and Finnish, shares `change_order` with text chat, and cannot approve an order (`backend/app/live.py`).

## Backend truth to check before recording

- `backend/app/vision.py` accepts JPEG, PNG, WEBP, HEIC, and HEIF. The image must be at most 8 MB. It returns structured text and items; the UI then sends the checked request to the agent. The photo endpoint does not place an order on its own.
- The photo schema preserves the Finnish language (`language: "fi"`) and the amount/unit as written. The downstream quantity parser recognizes common units such as `kg`, `l`, `kpl`, `kiloa`, and `litraa`; keep this take to the simple `kg` and `l` units above. Do not add `ltk` unless a preflight test proves the deployed UI handles it end to end.
- Photo text is untrusted. Do not write `AGENT:`, approval instructions, budget instructions, or a planted prompt on the list. Such text is reported and ignored.
- `backend/app/chat_agent.py` supports `propose_order` for the photo request and `change_order` for a pending order. A confirmed order cannot be changed.
- `backend/app/live.py` uses the same catalogue, order, assumption, and change tools. Every voice-originated order or change carries a voice hold. There is no voice approval tool.
- The catalogue is a static searchable index followed by live Valio mock price and availability quotes. Do not promise that every requested quantity is in stock or that a particular substitute will appear. Show the returned status.
- A Valio availability value of `999999` is treated as unknown stock by the backend. If it appears, say **unknown stock**; do not call it “full stock”.

## Recording setup

### Before the take

- Use the seeded **`lapland-kitchen`** buyer. The capture scripts and demo fixtures use this kitchen for the milk and Finnish demos. Use its agent key for the phone and its approver key for the approval view. Keep keys in the app or local `.env`; never show or say them.
- Reset only this buyer before the take. Use the app’s demo reset/admin control if available; otherwise use the existing admin demo-reset path. Confirm that the reset archives the old order and leaves a fresh audit trail. Do not reset another buyer.
- Confirm the seeded kitchen still has the **€1,500 auto-approval limit**. If the limit or buyer changes, update the expected hold reason before recording.
- Warm `https://valio-front-door.onrender.com` and run one disposable photo flow. Confirm the selected products, date, quotes, exception reason, Talk control, approval control, signed result, and audit entry.
- Verify the CRACI endpoint separately. Do not put a live SBOM claim in the video unless `/.well-known/front-door-build.json` returns `status: ok` and a non-empty `sbom_sha256`.
- Put the phone in **Do Not Disturb**. Turn off banners, calls, keyboard suggestions, and personal notifications. Keep the Mac in Do Not Disturb too.
- Close unrelated Mac windows. Hide secrets, API keys, terminal paths, and private messages.

### Capture

- Mirror the iPhone to the Mac with **macOS iPhone Mirroring**. Use the native mirrored resolution. Do not enlarge a low-resolution crop.
- Record the Mac screen with macOS Screen Recording or QuickTime. Capture the complete mirrored-phone window and enough surrounding frame for the `LIVE · one take` label.
- Keep the phone in one chronological run: photograph the list, inspect the seven read items, send the request, wait for the card, use Talk for the quantity change, show the hold, tap approval, then show the signed result and audit entry.
- Keep Omar’s finger taps visible. Keep the Talk transcript visible. Do not record a voice approval attempt as if it succeeded.
- Do not pause and replace a screen. If a wait is too long, record it honestly and retime only the waiting frames in the edit with a visible `×2` or `×4` badge.
- Record the voiceover after the picture. Keep Omar and Zoha’s captions separate and readable. Do not use AI voices.

## Pass/fail gate

### Pass only if all are true

- [ ] The final frame is native-resolution iPhone Mirroring footage with no notification or secret visible.
- [ ] The photo is the Finnish sheet above, and Gemini returns the intended seven item lines or a documented, visible correction.
- [ ] The app shows a real product match, live mock price, stock/availability, delivery date, and pack size for the selected lines.
- [ ] The intended hold is visible with its real reason. The €1,500 limit and €1,560 milk line appear only if the current card actually shows those values.
- [ ] The exact Talk sentence is transcribed. The potatoes quantity changes to 30 kg on the pending card.
- [ ] Talk does not approve, confirm, or place the order. The order remains pending until the approver tap.
- [ ] The approver view changes the same pending card to `Ordered` and exposes the signed result and audit entry.
- [ ] The video contains no splice, pasted card, made-up substitute, fabricated price, or fabricated CRACI status.
- [ ] The screen recording, voiceover, burned-in captions, and `.srt` fit inside the 1:58 plan.

### Fail and reset if any are true

- The list is read as English noise, fewer than six useful lines, or a different order with no visible correction.
- A line is silently changed to another product, or the app claims a price or stock value not shown by the mock.
- The live exception is absent, invented, or described with a number that is not visible.
- The Talk change creates a confirmed order, changes a confirmed order, or the agent claims it approved.
- The approver tap does not produce the signed and audited result.
- A notification, key, private message, or unrelated buyer appears.
- The only usable result is a pre-recorded card. That is a rehearsal failure, not a live take.

## Take notes

Record these after a passing take so the edit can stay truthful:

```text
Take ID:
Date/time:
Buyer: lapland-kitchen
Photo result: [items / unreadable / ignored instructions]
Selected products:
Delivery date shown:
Hold reason shown:
Displayed total or line price:
Talk transcript:
Changed line and quantity:
Approver result:
Audit/signature visible: yes / no
CRACI endpoint: status / sbom_sha256 present or omitted
Retimed waits: none / ×2 / ×4 at [timestamps]
Pass: yes / no
```

