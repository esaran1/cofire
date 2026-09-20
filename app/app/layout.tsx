import type { Metadata } from "next";
import "./globals.css";
import { BottomNav } from "@/components/BottomNav";

export const metadata: Metadata = {
  title: "COFIRE",
  description:
    "Colorado drought and fire-spread condition forecasts, 2 to 8 weeks ahead.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-dvh bg-ink text-paper antialiased">
        <main className="pb-20">{children}</main>
        <BottomNav />
      </body>
    </html>
  );
}
