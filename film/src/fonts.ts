/**
 * Load the app's fonts before any frame renders, so no frame is captured in a
 * fallback face. delayRender holds the render until every face is ready.
 */
import { continueRender, delayRender, staticFile } from "remotion";

const FACES: [string, string, FontFaceDescriptors][] = [
  ["Newsreader", "fonts/Newsreader-latin.woff2", { weight: "300 500", style: "normal" }],
  ["Newsreader", "fonts/Newsreader-Italic-latin.woff2", { weight: "300 500", style: "italic" }],
  ["Outfit", "fonts/Outfit-latin.woff2", { weight: "300 600" }],
  ["IBMPlexMono", "fonts/IBMPlexMono-Regular-latin.woff2", { weight: "400" }],
  ["IBMPlexMono", "fonts/IBMPlexMono-Medium-latin.woff2", { weight: "500" }],
];

let started = false;
export function loadFonts(): void {
  if (started || typeof document === "undefined") return;
  started = true;
  const handle = delayRender("fonts");
  Promise.all(
    FACES.map(async ([family, file, desc]) => {
      const face = new FontFace(family, `url(${staticFile(file)}) format("woff2")`, desc);
      await face.load();
      (document.fonts as unknown as { add: (f: FontFace) => void }).add(face);
    }),
  )
    .then(() => continueRender(handle))
    .catch((e) => {
      throw new Error(`fonts failed to load: ${e}`);
    });
}
