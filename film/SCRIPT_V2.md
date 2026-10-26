# COFIRE Demo Film v2: Script

Target length 2:55, hard cap 2:58. Four speakers: P1, P2, P3, P4, plus ALL.
Roles below are placeholders; replace each with what that person actually did.
Every bracketed number is verified against a source or `facts.json` before render, and cut if it cannot be verified.
Humor stays in intros and transitions only. Nothing light near fire damage, homes, or deaths.

Running gag: a small 3:00 countdown timer sits in a corner from the first intro to the end card. Two scripted glances.

---

## 0:00 to 0:10 | Cold open

Black screen. Huge numbers slam in one at a time with a low bass hit, then shrink into the Colorado map.

| On screen | Speaker | Line |
|---|---|---|
| **[94%]** | P1 (V.O.) | [Ninety-four percent] of Colorado. In drought. |
| **[235,000] acres** | P2 (V.O.) | [Two hundred thirty-five thousand] acres burned this year. |
| **1,000,000+ cubic yards** | P3 (V.O.) | And more than a million cubic yards of mud, after two fires, inside the reservoir that feeds Denver's taps. |
| Beat. Timer appears and starts counting down. | P4 | ...okay, that was intense. Hi. |

Source lines appear small at the bottom of each number.

---

## 0:10 to 0:32 | Team intros

Trailer-style title cards, about 5 seconds each, fast cuts. Name large, role underneath, gag as subtitle.

| Card | Speaker | Line |
|---|---|---|
| **[NAME] / THE DATA WRANGLER** | P1 | I'm [Name]. I built the data pipeline. I have read more drought reports than any teenager should. |
| **[NAME] / THE PROBABILITY PERSON** | P2 | I'm [Name]. I built the forecasting model. I have strong opinions about base rates. Don't ask. |
| **[NAME] / THE PIXEL PUSHER** | P3 | I'm [Name]. I designed the app. Dark mode, because fire is already bright enough. |
| **[NAME] / THE TRANSLATOR** | P4 | And I'm [Name]. I did the Spanish version and accessibility, so our app works for more of Denver than our group chat does. |
| All four glance at the timer. Logo lands. | ALL | We are COFIRE. |

---

## 0:32 to 1:00 | Stakes, purpose, audience

The map pulls back from Denver over the Continental Divide to the two source watersheds. The Roberts Tunnel traces under the Divide.

**P1:** Here's the thing. Denver feels far from wildfire. But about half of Denver's water comes from the other side of the Continental Divide, from forests that can burn.

**P2:** So we built COFIRE.

On screen, verbatim, centered, held long enough to read:

> **COFIRE gives Denver residents plain-language odds of drought and fire danger, for their neighborhood and for the watersheds their water comes from.**

**P3:** It's for Denver residents, in English and Spanish, and for the people who serve them: neighborhood groups, gardeners, teachers, and city staff.

---

## 1:00 to 1:58 | Demo

Real app captures only. Synthetic cursor, eased zooms, no static shot over 2 seconds, no loading states.

| Visual | Speaker | Line |
|---|---|---|
| Map flies into Denver; a cell is tapped | P3 | Pick your spot. |
| Icon array fills in | P3 | You get odds, not jargon. In 100 weeks like this one, [N] got worse within a month. |
| "Weeks like this one" opens | P2 | And it shows its work. These are the actual past years that started exactly like today, and what happened next. |
| Watershed panel | P1 | Then the part nobody else shows you: where your water comes from. Fire danger upstream, east and west of the Divide. |
| Spanish toggle flips the card | P4 | One tap, and the whole thing is in Spanish. |
| Weekly brief slides in | P4 | And every week, it prints a one-page brief, in both languages, for anyone who isn't going to open an app. |
| Forecast record page with timestamps | P1 | It updates itself every week. Every forecast is time-stamped before we know the outcome, so it can be checked later. |

---

## 1:58 to 2:40 | Tech slides

Four slides, about 10 seconds each. Voice carries the explanation; slides hold only a few words. Content in `SLIDES_V2.md`.

**Slide 1, How it's built**
**P1:** Here's what's under the hood. Python for the data and models. TypeScript, React, and Next.js for the app. MapLibre for the map. GitHub Actions runs the weekly update. We used AI coding tools for parts of the build, and we documented exactly where in our repo.

**Slide 2, The data**
**P1:** Nineteen years of the U.S. Drought Monitor and fire-danger data, across [five] areas and [1,245] map cells. Every download is checked before we trust it.

**Slide 3, Simple beat complex**
**P2:** We tried [four] neural-network models. The simple one won: for every week like today since 2007, count what happened next. It beat the fancy ones, and you can explain it in one sentence.

**Slide 4, How we know it works**
**P2:** We locked away all of 2026 before testing, and scored it once. We checked every result against shuffled data. [N] forecasts beat their baselines.
**P3:** And when we found a bug in our own best result, we took it out of the app and said why.

Timer glance.

**P4:** [Thirty] seconds. We're fine.

---

## 2:40 to 2:55 | Close

The live map breathing, then the end card.

**P4:** Next, we want to cover the rest of the Front Range, and get the brief to every neighborhood that needs it.

**P1:** COFIRE. Free, open source, updated every week.

**ALL:** Each says their own name, with names on screen: [Name], [Name], [Name], [Name].

End card: COFIRE, four names, and a URL. Use the deployed URL only if it returns 200 at render time; otherwise the public repo URL. Timer stops at about 0:03.

---

## Required items checklist (2026 CAC rules)

| Requirement | Where |
|---|---|
| Name of every participant | 0:10 to 0:32 intros, again at close |
| Name of the app | "We are COFIRE," logo, end card |
| Purpose in one clear sentence | 0:32 to 1:00, spoken and on screen verbatim |
| Target audience | 0:32 to 1:00, P3 |
| Tools and coding languages | Slide 1 |
| Functionality | 1:00 to 1:58 demo |
| AI usage disclosed | Slide 1, spoken and on screen |
| Length 1 to 3 minutes | Target 2:55, cap 2:58 |
