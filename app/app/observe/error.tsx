"use client";

import { useEffect } from "react";

/** Route-level boundary: a thrown render keeps the shell and the nav. */
export default function RouteErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[route]", error);
  }, [error]);

  return (
    <div className="mx-auto max-w-xl px-4 pb-24 pt-10">
      <h1 className="text-2xl font-semibold tracking-tight">This screen could not load</h1>
      <p className="mt-3 leading-relaxed text-mute">
        The forecast service returned something the app did not expect. Other screens still work.
      </p>
      <p className="mt-2 font-mono text-xs text-mute">{error.message}</p>
      <button
        onClick={reset}
        className="mt-6 rounded-lg bg-fire px-5 py-3 font-medium text-ink transition-transform active:scale-[0.98]"
      >
        Try again
      </button>
    </div>
  );
}
