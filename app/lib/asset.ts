/**
 * A public file's URL under the deployment's base path.
 *
 * Served from the root in development and from `/cofire/` on GitHub Pages;
 * a root-absolute "/img/..." would 404 there.
 */
export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

export function asset(path: string): string {
  return `${BASE_PATH}${path}`;
}
