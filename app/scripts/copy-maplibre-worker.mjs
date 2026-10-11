// MapLibre 6 parses tiles in a module worker that the Next bundler does not
// emit. Copy the installed version's worker and its shared chunk to
// public/maplibre, where MapView points setWorkerUrl. Runs after npm install.
import { copyFileSync, mkdirSync } from "node:fs";

mkdirSync("public/maplibre", { recursive: true });
for (const f of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  copyFileSync(`node_modules/maplibre-gl/dist/${f}`, `public/maplibre/${f}`);
}
