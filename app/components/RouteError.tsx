"use client";

import { Component, ReactNode } from "react";

/**
 * Per-route error boundary. One bad field degrades a component, not a page.
 *
 * This exists because `why[].value` was null on a SHAP cache miss and
 * `.toFixed()` on it took down the entire Place Card, leaving a blank screen
 * with a 200 response behind it. Schema parsing now catches the shape, and this
 * catches anything that still throws during render.
 */
export class RouteError extends Component<
  { children: ReactNode; what?: string },
  { error: Error | null }
> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error("[route]", this.props.what ?? "component", error);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="rounded-lg border border-fire/40 bg-fire/10 p-4">
        <p className="text-sm font-medium text-fire">
          {this.props.what ? `${this.props.what} could not be shown.` : "This section could not be shown."}
        </p>
        <p className="mt-1 text-xs leading-relaxed text-mute">
          The rest of the page still works. If this keeps happening, the forecast service is
          returning a shape the app does not expect.
        </p>
        <button
          onClick={() => this.setState({ error: null })}
          className="mt-3 text-xs text-paper underline underline-offset-4"
        >
          Try again
        </button>
      </div>
    );
  }
}
