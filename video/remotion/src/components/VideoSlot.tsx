import React, { useEffect, useState } from "react";
import { OffthreadVideo, continueRender, delayRender, staticFile } from "remotion";
import { C } from "../tokens";

// Does public/<src> exist? Probed once per file with a HEAD request against the static server.
const probes = new Map<string, Promise<boolean>>();
const probe = (src: string): Promise<boolean> => {
  let p = probes.get(src);
  if (!p) {
    p = fetch(staticFile(src), { method: "HEAD" })
      .then((r) => r.ok && /^(video|application\/octet-stream)/.test(r.headers.get("content-type") ?? ""))
      .catch(() => false);
    probes.set(src, p);
  }
  return p;
};

const useFootage = (src: string): boolean | null => {
  const [exists, setExists] = useState<boolean | null>(null);
  const [handle] = useState(() => delayRender(`probe ${src}`));
  useEffect(() => {
    let live = true;
    probe(src).then((ok) => {
      if (live) setExists(ok);
      continueRender(handle);
    });
    return () => {
      live = false;
    };
  }, [src, handle]);
  return exists;
};

const Placeholder: React.FC<{ name: string; src: string; dark?: boolean; corner?: boolean }> = ({ name, src, dark, corner }) => (
  <div
    style={{
      position: "absolute",
      inset: 0,
      display: "flex",
      flexDirection: "column",
      alignItems: corner ? "flex-start" : "center",
      justifyContent: corner ? "flex-start" : "center",
      gap: 12,
      textAlign: corner ? "left" : "center",
      padding: corner ? "40px 56px" : 24,
      color: dark ? C.cold : C.blue,
      background: dark
        ? "repeating-linear-gradient(135deg, rgba(142,192,255,0.07) 0 22px, rgba(142,192,255,0.02) 22px 44px)"
        : "repeating-linear-gradient(135deg, #E9EEF5 0 22px, #F2F5F9 22px 44px)",
      border: `4px dashed ${dark ? "rgba(142,192,255,0.5)" : C.blue}`,
      boxSizing: "border-box",
    }}
  >
    <div style={{ fontSize: 34, fontWeight: 900, letterSpacing: "0.08em" }}>FOOTAGE: {name}</div>
    <div style={{ fontSize: 24, fontWeight: 500, opacity: 0.8 }}>public/{src}</div>
  </div>
);

/**
 * A screen recording. variant "phone": phone frame with rounded corners. variant "bleed": full-bleed fill.
 * If the file is missing, a labelled placeholder card is shown instead ("FOOTAGE: <name>").
 * `startFrom` is in frames.
 */
export const VideoSlot: React.FC<{
  src: string;
  startFrom?: number;
  name?: string;
  variant?: "phone" | "bleed";
  width?: number;
  height?: number;
  dark?: boolean;
}> = ({ src, startFrom = 0, name, variant = "phone", width = 396, height = 830, dark }) => {
  const exists = useFootage(src);
  const label = name ?? src.split("/").pop() ?? src;
  const media =
    exists === true ? (
      <OffthreadVideo
        src={staticFile(src)}
        startFrom={startFrom}
        volume={0}
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }}
      />
    ) : (
      <Placeholder name={label} src={src} dark={dark ?? variant === "bleed"} corner={variant === "bleed"} />
    );

  if (variant === "bleed") {
    return <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>{media}</div>;
  }

  return (
    <div
      style={{
        width,
        height,
        borderRadius: 58,
        background: C.ink,
        padding: 12,
        boxSizing: "border-box",
        boxShadow: "0 24px 48px rgba(28,31,35,0.28)",
        flex: "none",
      }}
    >
      <div style={{ position: "relative", width: "100%", height: "100%", borderRadius: 46, overflow: "hidden", background: C.paper }}>
        {media}
        <div
          style={{
            position: "absolute",
            top: 12,
            left: "50%",
            transform: "translateX(-50%)",
            width: 96,
            height: 26,
            borderRadius: 14,
            background: C.ink,
          }}
        />
      </div>
    </div>
  );
};
