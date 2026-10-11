import type { Metadata } from "next";
import { IBM_Plex_Mono, Newsreader, Outfit } from "next/font/google";
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
const serif = Newsreader({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-serif",
  weight: ["300", "400", "500"],
  style: ["normal", "italic"],
});

const sans = Outfit({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans",
  weight: ["300", "400", "500", "600"],
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-mono",
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "COFIRE - Colorado drought and fire-spread conditions",
  description:
    "Drought and fire-spread condition forecasts for Colorado, 2 to 8 weeks ahead, with an uncertainty layer that says when it cannot be trusted.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${serif.variable} ${sans.variable} ${mono.variable}`}>
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
