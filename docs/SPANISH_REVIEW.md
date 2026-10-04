# Spanish review, before release

The Spanish was written by the AI agent and has not been checked by a fluent
reader. Until it is, the app shows "Borrador: esta traducción todavía no ha
sido revisada por una persona" on every Spanish screen.

## What to review

| File | What it holds |
|---|---|
| `app/lib/i18n/es.ts` | Every label and sentence on the map, the Place Card, the legend, the map controls, the neighborhoods layer, the weekly brief, the staleness notice and the Ember page, beside the English keys in `en.ts` |
| `app/lib/links.ts` | The Spanish name of each outside link |
| `app/lib/i18n/ember_es.json` | Both Ember checklists, item by item |
| `app/lib/i18n/reasons.ts` | The sentences that explain each number ("Why" on the Place Card), built from templates with the numbers filled in |

Terms chosen, worth a second opinion:

- **ERC** is left as "ERC" and described as "sequedad del combustible
  vegetal".
- **Fire-spread conditions** is "condiciones de propagación de incendios".
- **The sealed 2026 test** is "la prueba sellada de 2026", and the holdout
  year is "el año reservado".
- **The Ember Score** keeps "Ember" as a name: "Puntaje Ember".
- **Red Flag days** is "días de Bandera Roja".
- **Usted** throughout.
- **Source names** in the Ember lists stay in English, because they name real
  documents.

## When it is reviewed

1. Correct the files above.
2. Set `REVIEWED = true` in `app/lib/i18n/es.ts`. The draft notice then
   disappears from translated screens.
3. Run `cd app && npx playwright test e2e/i18n.spec.ts`. It checks that every
   reason in the shipped bundles has a full translation that keeps its
   numbers, and that every `{slot}` in English is also in Spanish.

## Not yet in Spanish

Predict, Observe, Hindcast, Method and the landing page. In Spanish mode
they show "Esta página todavía no está en español" rather than mixing the
two languages.
