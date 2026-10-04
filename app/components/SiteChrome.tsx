"use client";

import { usePathname } from "next/navigation";
import { SiteFooter } from "./SiteFooter";

/**
 * The map route fills the viewport by design, so a footer beneath it would add
 * a scrollbar to a view that is not meant to scroll. Every other route wants
 * the footer.
 */
export function ConditionalFooter() {
  const path = usePathname();
  if (path === "/") return null;
  return (
    <div className="print:hidden">
      <SiteFooter />
    </div>
  );
}
