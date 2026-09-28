/**
 * Cells a reader has adopted, kept in this browser.
 *
 * Adopting a cell marks it as one you will report on; the Observe screen
 * offers adopted cells as quick picks. Stored as objects so a pick keeps its
 * area and position; the older format (a bare list of cell ids) is dropped
 * because it cannot say where a cell is.
 */
export type Adopted = { cell_id: string; domain: string; lat: number; lon: number };

const KEY = "cofire_adopted";

export function readAdopted(): Adopted[] {
  try {
    const raw = JSON.parse(window.localStorage.getItem(KEY) ?? "[]") as unknown;
    return Array.isArray(raw) ? raw.filter((a): a is Adopted => typeof a === "object" && a !== null && "cell_id" in a) : [];
  } catch {
    return [];
  }
}

export function toggleAdopted(a: Adopted): Adopted[] {
  const cur = readAdopted();
  const has = cur.some((x) => x.cell_id === a.cell_id && x.domain === a.domain);
  const next = has ? cur.filter((x) => !(x.cell_id === a.cell_id && x.domain === a.domain)) : [...cur, a];
  try {
    window.localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* storage blocked: the toggle still shows for this visit */
  }
  return next;
}
