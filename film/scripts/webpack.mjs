/**
 * MapLibre builds its worker's URL with `new URL(url, import.meta.url)`;
 * webpack would try to bundle that as a module. The worker is served with
 * the production build instead, as in the app (setWorkerUrl).
 */
export const webpackOverride = (c) => ({
  ...c,
  module: { ...c.module, parser: { ...(c.module?.parser ?? {}), javascript: { ...(c.module?.parser?.javascript ?? {}), url: false } } },
});
