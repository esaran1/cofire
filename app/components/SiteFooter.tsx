import Link from "next/link";

/**
 * Footer. Repeats the IA and carries the provenance line, because a judge
 * reading this needs to know what it is and what it does not claim.
 */
export function SiteFooter() {
  return (
    <footer className="border-t border-rule bg-paper-sunk">
      <div className="measure px-6 py-12">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <span className="display text-lg">
              CO<span className="text-ember">FIRE</span>
            </span>
            <p className="mt-2 max-w-[34ch] text-sm leading-relaxed text-mute">
              Drought and fire-spread conditions for Colorado, 2 to 8 weeks ahead.
            </p>
          </div>

          <nav aria-label="Forecast">
            <h2 className="text-sm font-medium">Forecast</h2>
            <ul className="mt-3 space-y-2 text-sm text-mute">
              <li><Link href="/" className="hover:text-ink">Map</Link></li>
              <li><Link href="/beat" className="hover:text-ink">Predict</Link></li>
              <li><Link href="/observe" className="hover:text-ink">Observe</Link></li>
              <li><Link href="/ember" className="hover:text-ink">Harden</Link></li>
            </ul>
          </nav>

          <nav aria-label="Evidence">
            <h2 className="text-sm font-medium">Evidence</h2>
            <ul className="mt-3 space-y-2 text-sm text-mute">
              <li><Link href="/hindcast" className="hover:text-ink">2026 hindcast</Link></li>
              <li><Link href="/about" className="hover:text-ink">Method and provenance</Link></li>
              <li><Link href="/landing" className="hover:text-ink">How it works</Link></li>
            </ul>
          </nav>

          <div>
            <h2 className="text-sm font-medium">What this is not</h2>
            <p className="mt-3 max-w-[32ch] text-sm leading-relaxed text-mute">
              Not a forecast of ignitions or of where a fire will start. It forecasts the conditions
              that let fire spread, and says how much to trust each number.
            </p>
          </div>
        </div>

        <p className="mt-10 border-t border-rule pt-6 text-xs text-mute">
          2026 Congressional App Challenge. Data from gridMET, the US Drought Monitor, NRCS SNOTEL,
          USGS 3DEP and NIFC. Basemap by OpenStreetMap contributors.
        </p>
      </div>
    </footer>
  );
}
