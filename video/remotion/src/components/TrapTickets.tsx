import React from "react";
import { C } from "../tokens";
import { Trap } from "../types";
import { Arrow } from "./Icons";
import { Stamp } from "./Stamp";
import { TicketCard } from "./TicketCard";

/** Three trap tickets, each ending in an ASK stamp. Tickets reveal one at a time. */
export const TrapTickets: React.FC<{ items: Trap[]; at?: number; interval?: number; width?: number }> = ({
  items,
  at = 0,
  interval = 52,
  width = 1700,
}) => {
  const gap = 40;
  const cardW = (width - gap * (items.length - 1)) / items.length;
  const tilts = [-1.6, 1.2, -0.8];
  return (
    <div style={{ display: "flex", gap, width, alignItems: "stretch" }}>
      {items.map((it, i) => {
        const start = at + i * interval;
        return (
          <TicketCard key={it.lines.join("|")} title="TRAP" width={cardW} tilt={tilts[i % tilts.length]} at={start}>
            <div style={{ minHeight: 190, display: "flex", flexDirection: "column", justifyContent: "center", gap: 6 }}>
              {it.lines.map((l) => (
                <div key={l} style={{ fontSize: 44, fontWeight: 900, letterSpacing: "0.03em", lineHeight: 1.15 }}>
                  {l}
                </div>
              ))}
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                borderTop: `3px dashed ${C.line}`,
                paddingTop: 22,
                minHeight: 120,
              }}
            >
              <Arrow size={32} length={36} color={C.mute} />
              {it.via && (
                <>
                  <span
                    style={{
                      fontSize: 28,
                      fontWeight: 900,
                      letterSpacing: "0.04em",
                      color: C.amber,
                      background: C.amberBg,
                      padding: "6px 12px",
                      borderRadius: 10,
                    }}
                  >
                    {it.via}
                  </span>
                  <Arrow size={32} length={36} color={C.mute} />
                </>
              )}
              <Stamp label={it.stamp} tone="amber" size={50} at={start + 20} rotate={-7} />
            </div>
          </TicketCard>
        );
      })}
    </div>
  );
};
