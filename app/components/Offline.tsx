"use client";

import { useEffect, useState } from "react";
import { asset } from "@/lib/asset";
import { useT } from "@/lib/i18n";

/**
 * Registers the service worker in production builds, so the newest forecast
 * and brief stay readable offline, and says so when the connection drops.
 * Development builds skip registration, which would fight hot reloading.
 */
export function OfflineSupport() {
  const { t } = useT();
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    if (process.env.NODE_ENV === "production" && "serviceWorker" in navigator) {
      navigator.serviceWorker.register(asset("/sw.js"), { scope: asset("/") }).catch(() => undefined);
    }
    const update = () => setOffline(!navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  if (!offline) return null;
  return (
    <div role="status" data-testid="offline-banner" className="border-b border-ochre/40 bg-ochre-soft px-6 py-1.5 text-center text-xs text-ochre print:hidden">
      {t("offline.banner")}
    </div>
  );
}
