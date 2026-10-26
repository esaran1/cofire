# COFIRE Demo Film v2: Script

Target length 2:55, hard cap 2:58. Four speakers, P1 to P4, plus ALL.

**Speakers and titles.** Professional titles only, shown as clean lower thirds (name, title). Fill in names, and adjust the three supporting titles to what each person actually did.

| Speaker | Title |
|---|---|
| P1 | Lead Developer (the teammate who did most of the CS work) |
| P2 | Data and Research Lead |
| P3 | Product Designer |
| P4 | Outreach and Accessibility Lead |

**Rules for this script**
- Every bracketed number is verified against a source or `facts.json` before render, and cut if it can't be verified.
- Light humor lives only in the team intro and the timer gag. Nothing light near fire damage, homes, or deaths.
- Spoken words total about 400. If the voice read runs long, cut in this order: the timer line at 2:36, the second demo line from P2, the Slide 2 narration down to its first sentence. Never cut a required item.

**Through-line.** The film opens and closes on a kitchen tap. Everything in between answers one question: where did that water come from, and what's coming for it?

**Running gag.** A small 3:00 countdown timer, styled like the app's UI, appears when the team introduces itself and counts down to the end card. Two scripted glances.

---

## 0:00 to 0:12 | Cold open: the tap

No logo, no title. Sound first.

| Visual | Sound | Speaker | Line |
|---|---|---|---|
| Black. A single water drop, rendered in the app's palette, forms and falls. Small text: *Denver, Colorado* | Tap running, close and quiet | P2 (V.O.) | Turn on a tap in Denver. |
| The camera follows the drop backward: up the pipe, out of the city, west across the map, along the glowing Roberts Tunnel line under the Continental Divide, up into a mountain watershed | A low rising tone | P2 (V.O.) | About half of that water starts here, on the other side of the mountains. |
| The watershed on the map shifts from green to drought orange, spreading cell by cell | The tone cuts out | P3 (V.O.) | This year, here looked like this. |

Small source line at the bottom for the water claim (Denver Water).

---

## 0:12 to 0:22 | The numbers

Numbers slam onto the map one at a time, huge, in the app's display face, each with a low hit and a small source line.

| On screen | Speaker | Line |
|---|---|---|
| **[94%]** | P1 (V.O.) | [Ninety-four] percent of Colorado in drought. |
| **[235,000] acres** | P1 (V.O.) | [Two hundred thirty-five thousand] acres burned. |
| **1,000,000+ cubic yards** | P1 (V.O.) | And after two past fires, more than a million cubic yards of mud ended up in the reservoir that feeds those taps. |
| The numbers fade; only the orange watershed remains | P4 (V.O.) | And from Denver, almost nobody can see it coming. |

---

## 0:22 to 0:38 | The team

Hard cut from dark to bright. The timer appears in the corner reading about 2:38 and starts counting down. Each person gets a clean lower third, about 3 seconds each, quick cuts.

| Lower third | Speaker | Line |
|---|---|---|
| **[Name]** / Lead Developer | P1 | So four of us built something. I'm [Name], lead developer. |
| **[Name]** / Data and Research Lead | P2 | I'm [Name], data and research. |
| **[Name]** / Product Designer | P3 | I'm [Name], design. |
| **[Name]** / Outreach and Accessibility Lead | P4 | And I'm [Name], outreach and Spanish. |
| All four glance at the timer. Logo lands. | ALL | This is COFIRE. |
| Beat | P1 | And we have about two and a half minutes. Let's go. |

---

## 0:38 to 0:55 | Purpose and audience

The logo becomes the app's map. On screen, verbatim, centered, held long enough to read:

> **COFIRE gives Denver residents plain-language odds of drought and fire danger, for their neighborhood and for the watersheds their water comes from.**

**P1:** COFIRE gives Denver residents plain-language odds of drought and fire danger, for their neighborhood and for the watersheds their water comes from.

**P3:** It's built for Denver residents, in English and Spanish, and for the people who look out for them: neighbors, community gardeners, teachers, and city staff.

---

## 0:55 to 1:55 | Demo: one person, one minute

Real app captures only. Synthetic cursor, eased zooms, no static shot over 2 seconds, no loading states. The demo follows one hypothetical user so every feature answers a question she'd actually have.

| Visual | Speaker | Line |
|---|---|---|
| Map flies into Denver | P3 | Say you run a community garden in Denver. You open COFIRE. |
| A cell is tapped; the Place Card resolves and the icon array fills in | P3 | No jargon. Just odds. In 100 weeks like this one, [N] reached severe drought within a month. |
| "Weeks like this one" opens | P2 | And you can see why. These are the real past weeks that started just like today, and what happened next. |
| Watershed panel; camera pans across the Divide | P1 | Then the part most drought maps don't show you: your water. Fire danger upstream, on both sides of the Divide. |
| Spanish toggle flips the whole card | P4 | Your neighbor speaks Spanish? One tap. |
| The weekly brief slides in, then prints | P4 | Not on a phone at all? Every week, COFIRE makes a one-page brief, in both languages, for the bulletin board. |
| Forecast record page with timestamps | P1 | And it keeps itself honest. Every forecast is time-stamped before the outcome exists, so anyone can check it later. |

---

## 1:55 to 2:38 | Under the hood, and the moment we got it wrong

Four slides, then the climax. Slide content is in `SLIDES_V2.md`. The voice explains; the slides hold keywords.

**Slide 1, How it's built**
**P1:** Under the hood: Python for the data pipeline and models. TypeScript, React, and Next.js for the app. MapLibre for the map. GitHub Actions refreshes everything every week. We used AI coding tools for parts of the build, and our repo documents exactly where.

**Slide 2, The data**
**P2:** Nineteen years of Drought Monitor and fire-danger data, [1,245] map cells, and every download checked before we trust it.

**Slide 3, Simple beat complex**
**P2:** We tried [four] machine-learning models. The simplest one won: look at every week like today since 2007, and count what happened next. It's calibrated, and you can explain it in one sentence.

**Slide 4, How we know it works**
**P2:** Then we locked away all of 2026 and tested on it exactly once. [N] forecasts beat their baselines.

**The turn.** Music drops out. The slide dims to a single line on black.

**P3:** One of our results looked perfect. That's what worried us.

**P1:** We dug in, found a flaw in how we'd tested it, and pulled it from the app. Now COFIRE says plainly when it can't back up a number.

Music returns.

**P4:** *(glancing at the timer)* Twenty seconds. We're fine.

---

## 2:38 to 2:56 | Close: back to the tap

The live map, breathing. Then the camera follows a drop forward this time: down from the mountains, under the Divide, into the city, back to the tap.

**P4:** Next, we want to cover the whole Front Range, and get the brief into every neighborhood that needs it.

**P2:** So the next time you turn on the tap...

**P1:** ...you'll know where it's been, and what's coming.

**ALL:** We're COFIRE.

End card: COFIRE, the four names and titles, and a URL. Use the deployed URL only if it returns 200 at render time; otherwise the public repo URL. The timer stops at about 0:02.

---

## Required items checklist (2026 CAC rules)

| Requirement | Where |
|---|---|
| Name of every participant | 0:22 to 0:38 lower thirds and lines; end card |
| Name of the app | "This is COFIRE," logo, close, end card |
| Purpose in one clear sentence | 0:38 to 0:55, spoken and on screen verbatim |
| Target audience | 0:38 to 0:55, P3 |
| Tools and coding languages | Slide 1, spoken and on screen |
| Functionality | 0:55 to 1:55 demo |
| AI usage disclosed | Slide 1, spoken and on screen |
| Length 1 to 3 minutes | Target 2:55, cap 2:58 |
