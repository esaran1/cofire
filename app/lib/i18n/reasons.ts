/**
 * Spanish for the reason strings the export attaches to every number.
 *
 * The reasons are generated from a fixed set of clauses with numbers in them
 * (`cofire/ship/export.py` reading the pre-registered decisions), so each
 * clause is matched and rebuilt with its numbers. A reason containing any
 * clause not listed here comes back as null, and the caller shows the English
 * with a note, rather than a half-translated sentence. A test runs every
 * reason in the shipped bundles through this table.
 */

type Rule = [RegExp, (m: RegExpMatchArray) => string];

const N = "(\\d+(?:\\.\\d+)?)";

const CLAUSES: Rule[] = [
  [new RegExp(`^only ${N} weeks with the event in ${N} to ${N} validation, fewer than the ${N} needed to check a per-cell probability`),
    (m) => `solo ${m[1]} semanas con el evento en la validación de ${m[2]} a ${m[3]}, menos de las ${m[4]} necesarias para comprobar una probabilidad por celda`],
  [new RegExp(`^stated probabilities did not match observed frequencies on the ${N} holdout: reliability ${N}, needed ${N} or less`),
    (m) => `las probabilidades indicadas no coincidieron con las frecuencias observadas en el año reservado ${m[1]}: confiabilidad ${m[2]}, se necesitaba ${m[3]} o menos`],
  [new RegExp(`^stated probabilities did not match observed frequencies in ${N} to ${N} validation: reliability ${N}, needed ${N} or less`),
    (m) => `las probabilidades indicadas no coincidieron con las frecuencias observadas en la validación de ${m[1]} a ${m[2]}: confiabilidad ${m[3]}, se necesitaba ${m[4]} o menos`],
  [new RegExp(`^the event did not happen in this area in ${N} or ${N}, so a per-cell probability cannot be checked`),
    (m) => `el evento no ocurrió en esta zona en ${m[1]} ni en ${m[2]}, así que no se puede comprobar una probabilidad por celda`],
  [new RegExp(`^the forecast does not separate events from non-events: resolution ${N}, so every cell would show the same number`),
    (m) => `el pronóstico no distingue los casos con evento de los casos sin evento: resolución ${m[1]}, así que todas las celdas mostrarían la misma cifra`],
  [new RegExp(`^calibrated on ${N} to ${N} validation \\(reliability ${N}\\) and beats its baseline there$`),
    (m) => `calibrado con la validación de ${m[1]} a ${m[2]} (confiabilidad ${m[3]}) y supera allí a su referencia`],
  [new RegExp(`^calibrated on ${N} to ${N} validation \\(reliability ${N}\\); it does not beat its baseline, so it is shown as a probability with no claim of skill$`),
    (m) => `calibrado con la validación de ${m[1]} a ${m[2]} (confiabilidad ${m[3]}); no supera a su referencia, así que se muestra como probabilidad sin afirmar que tenga capacidad predictiva`],
  [new RegExp(`^calibrated on the ${N} holdout and beats its baseline on ${N} to ${N} validation$`),
    (m) => `calibrado con el año reservado ${m[1]} y supera a su referencia en la validación de ${m[2]} a ${m[3]}`],
  [new RegExp(`^calibrated on the ${N} holdout; it does not beat its baseline, so it is shown as a probability with its historical basis and no claim of skill$`),
    (m) => `calibrado con el año reservado ${m[1]}; no supera a su referencia, así que se muestra como probabilidad con su base histórica y sin afirmar que tenga capacidad predictiva`],
  [/^No interval method passes the delayed-feedback check, so no band is drawn\. The point forecast is shown with the historical range for the week\.$/,
    () => "Ningún método de intervalos pasa la prueba de retroalimentación con retraso, así que no se dibuja ninguna banda. Se muestra el pronóstico puntual con el rango histórico de la semana."],
  [/^The interval tests were run with same-week updates a real-time forecaster cannot make\. With the honest lag the controller is unstable, so no calibrated interval can be shown\.$/,
    () => "Las pruebas de intervalos se hicieron con actualizaciones de la misma semana que un pronóstico en tiempo real no puede hacer. Con el retraso real, el controlador es inestable, así que no se puede mostrar un intervalo calibrado."],
];

const TAILS: Rule[] = [
  [/^[;,] (?:so )?no number is shown: a historical rate beside the model's other drought odds could contradict them on the same card$/,
    () => "; no se muestra ninguna cifra: una tasa histórica junto a las otras probabilidades de sequía del modelo podría contradecirlas en la misma tarjeta"],
  [/^[;,] (?:so )?the historical rate for this area at this time of year is shown instead$/,
    () => "; en su lugar se muestra la tasa histórica de esta zona en esta época del año"],
  [/^$/, () => ""],
];

/** The Spanish for an export reason, or null when any part is unknown. */
export function reasonEs(text: string | null | undefined): string | null {
  if (!text) return "";
  for (const [re, make] of CLAUSES) {
    const m = text.match(re);
    if (!m) continue;
    const rest = text.slice(m[0].length);
    for (const [tre, tmake] of TAILS) {
      const tm = rest.match(tre);
      if (tm) return make(m) + tmake(tm);
    }
    return null;
  }
  return null;
}
