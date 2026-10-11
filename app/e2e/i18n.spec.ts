import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { reasonEs } from "../lib/i18n/reasons";
import { en } from "../lib/i18n/en";
import { es } from "../lib/i18n/es";

/** Spanish and screen-reader parity on the map, Place Card and Ember Score. None writes to the database. */

function bundleDir(): string {
  for (const d of ["../artifacts/ship/domains", "../demo/artifacts/ship/domains", "public/data/domains"]) {
    if (fs.existsSync(d)) return d;
  }
  throw new Error("no bundles found; run make ship or make demo-data");
}

test("every reason in the shipped bundles has a full Spanish translation", () => {
  const root = bundleDir();
  const reasons = new Set<string>();
  for (const dom of fs.readdirSync(root)) {
    const dir = path.join(root, dom);
    if (!fs.statSync(dir).isDirectory()) continue;
    for (const f of fs.readdirSync(dir).filter((x) => x.endsWith(".json"))) {
      const b = JSON.parse(fs.readFileSync(path.join(dir, f), "utf8"));
      for (const kind of ["targets", "horizons"]) {
        for (const [, reason] of Object.values(b.decisions?.[kind] ?? {}) as [string, string | null][]) {
          if (reason) reasons.add(reason);
        }
      }
    }
  }
  expect(reasons.size).toBeGreaterThan(0);
  const missing = [...reasons].filter((r) => reasonEs(r) === null);
  expect(missing).toEqual([]);
  // Numbers survive translation.
  for (const r of reasons) {
    const nums = (s: string) => (s.match(/\d+(?:\.\d+)?/g) ?? []).sort();
    expect(nums(reasonEs(r) as string)).toEqual(nums(r));
  }
});

test("the Spanish table fills every slot the English one has", () => {
  for (const k of Object.keys(en) as (keyof typeof en)[]) {
    const slots = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort();
    expect(slots(es[k]), k).toEqual(slots(en[k]));
    if (en[k]) expect(es[k], k).not.toEqual("");
  }
});

test("the map, Place Card and legend switch to Spanish and stay switched", async ({ page }) => {
  await page.goto("/?domain=denver");
  await expect(page.getByTestId("place-card")).toBeVisible({ timeout: 20_000 });
  await page.getByTestId("lang-es").click();
  await expect(page.locator("html")).toHaveAttribute("lang", "es");
  await expect(page.getByTestId("dryness-heading")).toHaveText(/Sequedad en \d semanas/);
  await expect(page.getByTestId("map-legend")).toContainText(/Sequedad|Probabilidad/);
  await expect(page.getByTestId("lang-notice")).toContainText("Borrador");
  await expect(page.getByTestId("adopt")).toHaveText(/Adoptar|Adoptada/);
  await page.getByRole("button", { name: /Mostrar|Por qué/ }).first().click();
  await expect(page.getByTestId("place-card")).not.toContainText("(en inglés)");
  await page.reload();
  await expect(page.getByTestId("dryness-heading")).toHaveText(/Sequedad/, { timeout: 20_000 });
  await page.getByTestId("lang-en").click();
  await expect(page.getByTestId("dryness-heading")).toHaveText(/Dryness in \d weeks/);
  await expect(page.getByTestId("lang-notice")).toHaveCount(0);
});

test("a ?lang=es link opens in Spanish, and untranslated pages say so", async ({ page }) => {
  await page.goto("/ember?lang=es");
  await expect(page.getByTestId("ember-title")).toHaveText(/Puntaje Ember/, { timeout: 20_000 });
  await expect(page.getByText("Todo lo demás")).toBeVisible();
  await expect(page.getByText("Nada de fuegos artificiales").or(page.getByText("Número de la casa visible desde la calle")).first()).toBeVisible();
  await page.goto("/about");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Cómo funciona");
});

test("every map cell can be reached from the list, and the choice is announced", async ({ page }) => {
  await page.goto("/?domain=dillon");
  await expect(page.getByTestId("place-card")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("map")).toHaveAttribute("aria-label", /Dillon/);
  const list = page.getByTestId("cell-list");
  await list.locator("summary").click();
  const items = list.getByTestId("cell-list-item");
  const n = await items.count();
  expect(n).toBeGreaterThan(10);
  const last = items.nth(n - 1);
  const id = await last.getAttribute("data-cell");
  await last.click();
  await expect(page).toHaveURL(new RegExp(`cell=${id}`));
  await expect(last).toHaveAttribute("aria-current", "true");
  const [lat, lon] = (id as string).split("_").map(Number);
  await expect(page.getByTestId("map-announce")).toHaveText(`Showing the forecast for the cell at ${lat.toFixed(3)}, ${lon.toFixed(3)}.`);
});

test("text translated from facts.json is still the text in facts.json", () => {
  const facts = JSON.parse(fs.readFileSync("lib/facts.json", "utf8"));
  const r = facts.interval_audit.retraction;
  expect(en["hind.retractionTitle"]).toBe(r.title);
  expect(en["hind.retractionSummary"]).toBe(r.summary);
  for (const [k, v] of Object.entries(facts.configuration)) {
    expect(en[`meth.cfgv.${k}` as keyof typeof en], k).toBe(v);
  }
});

for (const [path, heading] of [
  ["/beat", "Gánale al modelo"],
  ["/observe", "Rachas de observación"],
  ["/hindcast", "El año sellado, abierto una sola vez"],
  ["/scoreboard", "Registro de pronósticos"],
] as const) {
  test(`${path} is in Spanish`, async ({ page }) => {
    await page.goto(`${path}?lang=es`);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(heading, { timeout: 20_000 });
    await expect(page.getByTestId("lang-notice")).not.toContainText("todavía no está en español");
  });
}

test("the landing page is in Spanish", async ({ page }) => {
  await page.goto("/landing?lang=es");
  await expect(page.getByText("Colorado se seca semanas")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Luego guardamos un año bajo llave.")).toBeVisible();
});
