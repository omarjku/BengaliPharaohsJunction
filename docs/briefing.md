# Junction 2026: opening-ceremony briefing (Omar + Fathia)

Sources: two phone recordings (R1 19:15:28–19:19:43 photo-verified; R2 ≈19:20–19:32, start time **inference**), 42 photos (18:16–19:18), and the platform's challenge list (PDF saved 20:07). Speaker labels match [roster.md](roster.md).
**Coverage gap:** no audio exists before 19:15. The opening words, practicalities, "How to win?", the DeepMind keynote and the MLH segment come **from the photos only**.

## 1. Rules, deadlines, submission requirements
| What | Detail | Source |
|---|---|---|
| Preliminary (draft) submission | **Tonight before midnight.** The slide says **23:55**. The guidebook says 23:59. Aim for 23:30. | Speaker 10 (host A), R2 11:13; IMG_6771–6773 |
| Submissions open on the platform | Sat 12:00 | IMG_6774 |
| Final submission | **Sun 10:00**, on the Junction Platform | Speaker 10, R2 11:13; IMG_6775 |
| Face-to-face peer review | Sun 10:30, at your own tables. "Stay for the face-to-face review." (The guidebook says absence costs eligibility for the main prize.) | Speaker 10; IMG_6775 |
| Submission page fields shown | Demo link, Source code link, Video (YouTube; the example player shows 2:00), Presentation (file upload) | IMG_6776 |
| Space | "More builders than we initially expected": use shared tables and squeeze in. | Speaker 14 (host B), R2 08:44 |
| Tech challenges | Side challenges "for what you built with particular tools". Do them **alongside** your main challenge, and check each one's eligibility and submission requirements on the platform. | Speaker 14, R2 08:44 |

## 2. Judging criteria and weights
- **The event-level criteria are not covered in the audio.** The "03 How to win?" section (ToC, IMG_6764–6770) happened before the recordings started.
- The guidebook lists **Innovation, Impact, Implementation**. **No weights are stated anywhere** (unknown).
- **Partner challenges publish weighted criteria.** All 38 pages are saved in [challenges/](challenges/INDEX.md), with an index of prizes, weights and resources. The ones that matter for our shortlist:
  - **Valio Aimo, Trusted Trade Agents:**
    - Working end-to-end demo (request → lookup → order/approval): **30%**
    - Matching the buyer's need: 20%
    - Autonomy & controls (guardrails, human sign-off, audit log): 20%
    - Exceptions (partial availability, substitution): 15%
    - Open standards + production path: 15%
    - Mock APIs, synthetic catalogue and resource portal at junction26.valioaimo.fi. The portal password and a shared API key are on the challenge page.
  - **AfterQuery, Break the Agent:** the gap 30, meaningful difficulty 30, reward integrity 25, craft 15. Harbor + OpenCode harness over MCP, plus model credits.
  - **Cala, Make Unicorns Real:** real need, execution, originality, use of Cala, 25% each.
  - **Best Use of Gemini API:** no weights. The page asks you to explain the problem, how Gemini is integrated, what's innovative, and why Gemini matters ("beyond simply adding an LLM"). **18+ only.** Credits for up to 400 teams via AI Studio.
  - **Hostinger, Decode the Noise:** detection 40%, deployment **on Hostinger** 25%, originality 20%, demo 15%.

## 3. Prizes, tracks and sponsor challenges
Event: "2,000 builders, 100,000 in prizes, 48 hours" (Speaker 14, R2 11:26). Host B said "six main track challenges" before the tech challenges (R2 08:44). **Inference:** this means six tracks, not six challenges, because the platform lists 19.

**Main challenges.** Prizes come from the platform PDF. The "Said on stage" column is from the recordings.
| Challenge (partner) | 1st prize | Said on stage: deliverable / support offered |
|---|---|---|
| Decode the Noise (Hostinger) | €2,000 (2nd €1,000) + 1 yr hosting + domain | Working detection tool (API, classifier or dashboard) **deployed live on Hostinger with a public URL**; explainable, handles false positives. Dedicated cloud environments, model credits, on-site mentors. (Speaker 5) |
| The Internet Butler (Exa) | $2,500 + $5k credits | Agent that takes tedious tasks off people's hands (rent questions, missed benefits, special occasions); functional prototype. Full API access, platform credits, on-site engineers. (Speaker 6) |
| Spread (Bahn Express) | €2,000 | Pricing software for a simulated week of car transport in Finland. Make the most money while delivering [~90%?] of cars; competitor prices and driver asks are hidden. Test as many times as you like; final round uses the same unseen week for everyone. (Speaker 7) |
| Break the Agent (AfterQuery) | **€3,000 + work trial** | RL environment that exposes where frontier agents fail. Action space, goals, reward functions that resist reward hacking. Reproducible environment + evaluation vs a reference run. Model credits, open-source agent harness, mentors. (Speaker 8) |
| Earned Trust in AI Code (Tieto) | €2,000 | AI-assisted code review: a PR explains what and why, with confidence and evidence, and the human stays accountable. Team on site for sparring. (Speaker 9) |
| Trusted Trade Agents (Valio Aimo) | **€4,000** (2nd €2,000) | Autonomous purchasing agents for a food-service wholesaler, without exposing real systems or confidential data (platform). Audio too noisy to quote reliably. (Speaker 4) |
| Make Unicorns Real (Cala) | **€5,000 to attend any hackathon** + €1k credits ("Cala Comet") | Product for founders or investors on Cala's company / people / funding-round data. (Speaker 3; IMG_6806–6808) |
| Wikipedia Through Time (MariaDB) | €1,000 + €1k UpCloud credits + certifications | Make Wikipedia better for editors or readers with MariaDB vector search (RAG) and **system-versioned tables** ("what did Wikipedia say in 2015?"). Datasets prepared. (Speaker 11) |
| Rethinking Recruitment (City of Espoo) | €1,500 | Matchmaking concept or prototype for recruitment events: real skills over AI-generated applications, no automated screening. Business advisors on site. (Speaker 12) |
| The Web Is Your Real-Time Database (Context.dev) | €2,000 + swag | Product that reacts to the live web (websites, companies, news → structured data via one API). API credits, engineers on site all weekend. (Speaker 13) |
| Personal Economic Trainer (S-Pankki) | €2,000 Airbnb card | AI financial coach from banking data. (Speaker 1, audio garbled) |
| Not in the recordings (platform only) | | Arduino Green European Renaissance (Ventuno Q per member); Meta AI Glasses (Ray-Ban Meta per member); Intel Physical AI (**€5,000**); Rokoko Robot Teleoperation (≈€4,990 kit); Aalto Aaltonomous Humanoid (€2,000 + live run on a Unitree G1 for the top ~5); AstraZeneca Equal Care Across Finland (€1,000; **insights at their stand Fri 20:00**); Aalto Beyond the Clinic (prizes TBA); Stoa Make Blueprints Talk (€1,000 + work trial) |

**Tech challenges** (platform "Tech Challenges" tab, PDF saved ~20:10). You enter these **alongside** a main challenge (Speaker 14). Sorted by value:
| Tech challenge | Prize | What it takes (platform text) |
|---|---|---|
| **Best Use of Gemini API** (Google DeepMind) | **€4,000 + $1,000 Google Cloud credits per member**; 2nd €2,000; 3rd €1,000 | Open innovation: any agent, tool or app built on Gemini |
| Best Use of Gemma (Google DeepMind) | €1,000 each for the top 3 (unranked) | Gemma open models |
| Verda Compute Track | $10,000 Verda credits; 2nd/3rd $2,500 | Run on Verda compute |
| Best Use of Codex (OpenAI) | $10,000 / $5,000 / $2,500 API credits | Use Codex in your development process |
| Best use of Modal | **$2,000 cash** + $3,000 credits | Take the project from laptop to a production GPU endpoint |
| Best Use of Aiven | €1,000 / €750 / €500 | Use Aiven managed data services |
| Best agentic use of Oxylabs Web API | €1,000 Apple voucher + $500 credits per member | Agent verified by live search/scraping |
| Best Use of Context.dev | €750 / €250 + swag | Plug the Context.dev API into whatever you build |
| Best use of CRACI | LEGO set per member / Red Bull / CRACI x OpenAI lunch at Slush | Run your GitHub Actions CI on `runs-on: craci`; any project qualifies |
| Best Use of Nemotron (NVIDIA) | RTX 5080 for each of the 2 best teams | Nemotron for reasoning / tool use, any track |
| Best Use of Cloudinary | $500 Amazon gift card per member | One of four tools at cld.media/hackathons |
| Atech Real World Challenge | Pro Atech kit; Copenhagen visit for top teams | Hardware modules + browser-flashed firmware |
| Best use of Arduino UNO Q | UNO Q + Plug and Make kit per member | Use UNO Q + Modulino sensors in any project |
| MLH: MongoDB Atlas / Vultr / Tiger Data / Solana / Entire / ElevenLabs | Hardware prizes (M5Stack kit, monitor, Stream Deck Mini, wallets, projector, earbuds) | Use the sponsor tool |

**Also said or shown on stage**
- **Oxylabs** (Speaker 15, R2 09:54): connect an AI agent to the **live web** through Oxylabs instead of static training data. The deliverable is **a working feature inside your main-challenge project** that uses live web data and cites its sources. Instant API access and setup provided.
- **MLH** (photos IMG_6793–6805): "everything you need this weekend" at **mlh.link/junction-26** (partly hidden; inference, high). Side prizes: Best use of **ElevenLabs** (Beats), **Solana**, **Tiger Data** (Postgres; Stream Deck), **MongoDB Atlas** (M5GO kits), **Vultr**; **DEV Writing Challenge** ($100); "I Demoed" stickers on Sunday.
- **Google DeepMind keynote** (photos only, Genevieve Huskens): the **Gemini 4** lineup is Carbon (hardest, long-horizon), [Argon] (complex workflows) and Hydrogen (everyday coding / agentic). The new **Gemini Decisions API** (*Gemini Decision 1*) gives fast yes/no, choice and rubric scores with **calibrated confidence**, 150–250 ms, $0.10 per 1M input tokens. Also Stitch (UI generation) and `npx skills add google-gemini/gemini-skills --skill gemini-api-dev --global`.
- **NVIDIA** (photo only): Nemotron 3.5 Super VL slide.

## 4. Schedule and logistics (from slides)
- **Fri:**
  - 19:30 hacking + dinner (2nd & 3rd floor).
  - 20:00 Build with Google DeepMind workshop (2nd floor cafe).
  - 20:30 Verda workshop (2nd floor cafe).
  - 20:30 Arduino workshop (5th floor).
  - 21:00 [hidden] (2nd floor cafe).
  - 22:00 [hidden] (2nd floor).
  - 23:55 preliminary submission.
  - AstraZeneca stand briefing 20:00 (platform).
- **Sat:**
  - 11:00 Cala workshops (2nd floor cafe).
  - 12:00 submissions open; Intel workshop (5th floor).
  - Lunch (time partly hidden).
  - 13:00 Hostinger keynote (main stage).
  - 13:30 Modal workshop.
  - 14:30 Kiuas workshop (2nd floor cafe).
  - Dinner [18:00?] (2nd & 3rd floor).
- **Sun:**
  - 10:00 final submissions.
  - 10:30 peer review at your own tables.
  - 14:00 final ceremony (3rd floor).
  - 17:00 event ends.
  - 18:00 doors close.

**Partner booths** (platform Guide → Venue Map, checked 20:55 Fri):
- **Floor 3**: booths are numbered 1–8 along the right-hand wall of the hacking area, 1 at the top. 1 Valio Aimo · 2 Hostinger · 3 **Google DeepMind** · 4 AstraZeneca · 5 MariaDB · 6 Verda · 7 Stoa · 8 Cala.
- **Floor 5**: 1 Exa · 2 Meta · 3 Aiven · 4 Modal · 5 Bahn Express · 6 S-Pankki · 7 City of Espoo · 8 Cloudinary · 9 AfterQuery · 10 Ignite Next x Intel · 11 Aalto University · 12 Tieto · 13 Context.dev.
- The announcements put the Fri workshops (DeepMind, Verda, MLH x GitHub) in the **Registration room, 2nd floor**. That contradicts both the slides (2nd floor cafe) and the guidebook (Loft).

## 5. Names, contacts, links
| Item | Value | Attributed to |
|---|---|---|
| Safe Space Guardians | **Oula Karinen +358 44 3389744**; [Lo]tta H[äm]äläinen, number partly hidden, ends **…2095** (the guidebook gives +358 44 2222095) | IMG_6777 (slide) |
| Google DeepMind DevRel | Genevieve Huskens, x.com/genevieve__h | IMG_6779 (slide) |
| MLH hub | mlh.link/junction-26 (partly obscured) | IMG_6793 (slide) |
| Partner booths | Hostinger, Exa, AfterQuery, MariaDB, Context.dev, Tieto, City of Espoo, Oxylabs: all said they're on site all weekend | Speakers 5, 6, 8, 9, 11, 12, 13, 15 |
| Opening slide name | "SARI MULTALA" (role not shown) | IMG_6762 |
| Discord / QR codes / Slack / Devpost | **None mentioned in the recordings or visible in the photos.** The guidebook says Discord + Junction Platform. | — |

## 6. What the photos add that the transcript lacks
- The whole schedule. There's no audio for that part.
- Workshop **locations** (2nd floor cafe), which contradict the guidebook.
- Safe-space contacts.
- The submission form layout.
- The DeepMind keynote, including the Decisions API pricing.
- The MLH side prizes and link.
- The Cala prize ("Cala Comet: travel to [3?] hackathons, flights and accommodation covered").

## 7. Contradictions, unclear points, unreadable items
| Issue | Detail | Confidence |
|---|---|---|
| Preliminary deadline | Slide 23:55, guidebook 23:59, host said "before midnight" | Slide reading high. **Use 23:55.** |
| Workshop locations | Slides: 2nd floor cafe. Guidebook: Loft, 4th floor. | High that they differ; which is right is unknown. Ask. |
| "Six main track challenges" | Platform lists 19 main challenges across ~6 tracks | Inference: tracks |
| Fri 21:00 and 22:00 items | Hidden behind people in every photo (guidebook: 21:00 MLH x GitHub workshop) | Unreadable |
| Recording timestamps | Both files claim creation 19:54:01 (after all photos). Real start of R1 is 19:15:28, from 2 photo/caption matches. R2 start is inferred. | R1 high; R2 low-medium |
| Bahn delivery target | "delivering 90% of every cars of the time" | Inference: ~90% on-time delivery. Low; check the brief. |
| Speaker names | ASR spellings of Isaiah, Dugan, Vayne, Toni, Robert are approximate | See roster |
| Recording 1 audio | Noisy; off-stage chatter overlaps. The Valio Aimo and S-Pankki pitches are only partly intelligible. | — |
| Cala prize text | "travel to [3?] hackathons" partly hidden. The platform says "5,000€ to attend any hackathon". | Medium |

## 8. The 5 decisions to make first (tonight)
1. **Main challenge, by ~21:00.** The top candidates by prize and fit:
   - **Valio Aimo** (€4,000, our plan A; agents + trust).
   - **AfterQuery** (€3,000 + work trial; judge Daksh's own company).
   - **Cala** (€5,000 hackathon travel).
   - Intel (€5,000) is hardware-heavy.
   Use the GAME_PLAN scoring rule.
2. **Which tech challenges to stack.** Build on **Gemini** regardless: **Best Use of Gemini API is €4,000 + credits**, as much as Valio's 1st prize. The **Gemini Decisions API** (calibrated yes/no with confidence) fits Valio's "right approval" step almost exactly. Cheap add-ons on top:
   - **Verda** or **Modal** for hosting (Modal pays $2,000 cash).
   - **CRACI** (one CI line).
   - **Oxylabs** (one live-web feature).
   - **Codex**, if you use it while building anyway.
   Don't chase hardware or MLH prizes.
3. **Who submits the draft before 23:55 tonight**, and what goes in it (name, challenge, one-line punchline).
4. **Roles for Sat/Sun.** Who builds, and who owns the 2-min video (**made with RAEA, per our plan**), the deck and the demo. Both of you must be at the peer review Sun 10:30.
5. **Stack and hosting.** Gemini 4 Hydrogen vs Carbon for the agent; deploy on Hostinger or Verda credits so the demo link is live. A Hostinger deploy is required only if you enter Decode the Noise.

## 9. Questions for the organizers / partners
- Is the preliminary deadline 23:55 or 23:59? What exactly must the draft contain?
- Are workshops in the 2nd-floor cafe or the 4th-floor Loft?
- What were the Fri 21:00 and 22:00 items?
- How are Innovation / Impact / Implementation weighted, if at all?
- Can one project enter one main challenge plus several tech challenges? (Host B implied yes; confirm on the platform.)
- Valio Aimo: is there a sandbox API or mock catalogue, and how is "trusted" judged?
- AfterQuery: which harness and models are provided, and what does a "reference run" need to show?
