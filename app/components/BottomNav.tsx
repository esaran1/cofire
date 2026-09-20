"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ITEMS = [
  { href: "/", label: "Map" },
  { href: "/hindcast", label: "Hindcast" },
  { href: "/beat", label: "Predict" },
  { href: "/observe", label: "Observe" },
  { href: "/ember", label: "Ember" },
  { href: "/about", label: "About" },
];

export function BottomNav() {
  const path = usePathname();
  return (
    <nav className="fixed bottom-0 inset-x-0 z-40 border-t border-white/10 bg-ink/95 backdrop-blur">
      <ul className="grid grid-cols-6 text-[11px] uppercase tracking-wide">
        {ITEMS.map((it) => {
          const on = path === it.href;
          return (
            <li key={it.href}>
              <Link
                href={it.href}
                className={`block py-3 text-center ${on ? "text-paper" : "text-mute"}`}
              >
                {it.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
