/**
 * A laptop and a phone, drawn in code from plain shapes. Generic on purpose:
 * no maker's shape language, no logo, no brand mark.
 */
import { T } from "../theme";

/** The laptop's screen is 16:9 to match the desktop captures. `screenW` sets its size. */
export function laptopGeometry(screenW: number) {
  const screenH = (screenW * 9) / 16;
  const bezel = screenW * 0.022;
  const lidW = screenW + 2 * bezel, lidH = screenH + bezel * 2.4;
  const baseW = lidW * 1.16, baseH = screenW * 0.034;
  return { screenW, screenH, bezel, lidW, lidH, baseW, baseH, totalH: lidH + baseH };
}

export const Laptop: React.FC<{ screenW: number; children: React.ReactNode }> = ({ screenW, children }) => {
  const g = laptopGeometry(screenW);
  return (
    <div style={{ position: "relative", width: g.baseW, height: g.totalH }}>
      <div style={{ position: "absolute", left: (g.baseW - g.lidW) / 2, top: 0, width: g.lidW, height: g.lidH, borderRadius: g.bezel * 1.1, background: "linear-gradient(180deg,#2b2d33,#1c1d21)", boxShadow: "0 40px 90px rgba(0,0,0,0.55), inset 0 0 0 1px rgba(255,255,255,0.06)" }}>
        <div style={{ position: "absolute", left: g.bezel, top: g.bezel * 1.2, width: g.screenW, height: g.screenH, overflow: "hidden", borderRadius: 3, background: "#000" }}>
          {children}
        </div>
      </div>
      <div style={{ position: "absolute", left: 0, top: g.lidH - 2, width: g.baseW, height: g.baseH, borderRadius: `2px 2px ${g.baseH}px ${g.baseH}px`, background: "linear-gradient(180deg,#4a4d55 0%,#34363c 45%,#1f2024 100%)", boxShadow: "0 18px 30px rgba(0,0,0,0.5)" }}>
        <div style={{ position: "absolute", left: "50%", top: 0, width: g.baseW * 0.14, height: g.baseH * 0.32, transform: "translateX(-50%)", borderRadius: `0 0 ${g.baseH}px ${g.baseH}px`, background: "#2a2c31" }} />
      </div>
    </div>
  );
};

/** A phone with a 390:844 screen (the phone captures). */
export function phoneGeometry(screenW: number) {
  const screenH = (screenW * 844) / 390;
  const bezel = screenW * 0.045;
  return { screenW, screenH, bezel, w: screenW + 2 * bezel, h: screenH + 2 * bezel, r: screenW * 0.16 };
}

export const Phone: React.FC<{ screenW: number; children: React.ReactNode }> = ({ screenW, children }) => {
  const g = phoneGeometry(screenW);
  return (
    <div style={{ position: "relative", width: g.w, height: g.h }}>
      <div style={{ position: "absolute", inset: 0, borderRadius: g.r, background: "linear-gradient(160deg,#30323a,#15161a)", boxShadow: "0 50px 100px rgba(0,0,0,0.6), inset 0 0 0 1.5px rgba(255,255,255,0.08)" }} />
      {/* side buttons */}
      <div style={{ position: "absolute", right: -g.bezel * 0.22, top: g.h * 0.24, width: g.bezel * 0.3, height: g.h * 0.09, borderRadius: 3, background: "#26282e" }} />
      <div style={{ position: "absolute", left: -g.bezel * 0.22, top: g.h * 0.2, width: g.bezel * 0.3, height: g.h * 0.06, borderRadius: 3, background: "#26282e" }} />
      <div style={{ position: "absolute", left: g.bezel, top: g.bezel, width: g.screenW, height: g.screenH, borderRadius: g.r - g.bezel, overflow: "hidden", background: T.paper }}>
        {children}
        {/* a camera cut-out, a plain pill */}
        <div style={{ position: "absolute", left: "50%", top: g.screenW * 0.03, width: g.screenW * 0.26, height: g.screenW * 0.07, transform: "translateX(-50%)", borderRadius: 999, background: "#0b0b0d" }} />
      </div>
    </div>
  );
};
