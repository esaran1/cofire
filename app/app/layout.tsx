import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { SiteNav } from "@/components/SiteNav";
import { ConditionalFooter } from "@/components/SiteChrome";
import { LangNotice } from "@/components/LangSwitch";
import { OfflineSupport } from "@/components/Offline";
import { LangProvider } from "@/lib/i18n";

/**
 * Type system, three roles, no more.
 *
 * Newsreader (serif)   display statements. The page argues in serif, which is
 *                      what makes a scientific claim read as a claim rather
 *                      than as marketing.
 * Outfit (sans)        UI and body. Geometric, quiet, wide language coverage.
 * IBM Plex Mono        every measurement. A number in this app is always mono
 *                      and always tabular, so columns of figures line up and a
 *                      reading is visually distinct from prose.
 */
// Self-hosted (app/fonts, SIL OFL 1.1, see app/fonts/OFL.txt): the build
// fetches nothing, so a change at Google Fonts cannot break it. These are the
// latin-subset files next/font/google served before, byte for byte.
const Newsreader = localFont({
  src: [
    { path: "../fonts/Newsreader-latin.woff2", weight: "300 500", style: "normal" },
    { path: "../fonts/Newsreader-Italic-latin.woff2", weight: "300 500", style: "italic" },
  ],
  display: "swap",
  variable: "--font-serif",
});

const Outfit = localFont({
  src: [{ path: "../fonts/Outfit-latin.woff2", weight: "300 600", style: "normal" }],
  display: "swap",
  variable: "--font-sans",
});

const IBMPlexMono = localFont({
  src: [
    { path: "../fonts/IBMPlexMono-Regular-latin.woff2", weight: "400", style: "normal" },
    { path: "../fonts/IBMPlexMono-Medium-latin.woff2", weight: "500", style: "normal" },
  ],
  display: "swap",
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "COFIRE - Colorado drought and fire-spread conditions",
  description:
    "Drought and fire-spread condition forecasts for Colorado, 2 to 8 weeks ahead, with an uncertainty layer that says when it cannot be trusted.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${Newsreader.variable} ${Outfit.variable} ${IBMPlexMono.variable}`}>
      <body className="min-h-dvh bg-paper font-sans text-ink antialiased">
        <LangProvider>
          <SiteNav />
          <OfflineSupport />
          <LangNotice />
          <main id="main">{children}</main>
          <ConditionalFooter />
        </LangProvider>
      </body>
    </html>
  );
}
