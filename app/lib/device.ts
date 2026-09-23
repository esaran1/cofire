const KEY = "cofire_device_id";

/** Session fallback when storage is unavailable, so the id is stable per tab. */
let memoryId: string | null = null;

/**
 * An anonymous per-browser id for streaks and the leaderboard.
 *
 * `localStorage` throws in some private windows and when site data is blocked,
 * and an uncaught throw here takes down Predict and Observe. Falling back to an
 * in-memory id keeps both pages working; the only cost is that the streak does
 * not survive a reload in that browser.
 */
export function deviceId(): string {
  if (typeof window === "undefined") return "ssr";
  try {
    let id = window.localStorage.getItem(KEY);
    if (!id) {
      id = crypto.randomUUID();
      window.localStorage.setItem(KEY, id);
    }
    return id;
  } catch {
    memoryId ??= crypto.randomUUID();
    return memoryId;
  }
}
