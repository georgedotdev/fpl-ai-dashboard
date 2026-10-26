import { useId } from "react";

// Club kits as flat colours: body, sleeves, and an optional stripe colour. No crests or logos.
const KITS: Record<string, [string, string, string?]> = {
  ARS: ["#e2231a", "#ffffff"], AVL: ["#670e36", "#95bfe5"], BOU: ["#d8231c", "#111111", "#111111"],
  BRE: ["#e30613", "#ffffff", "#ffffff"], BHA: ["#0057b8", "#0057b8", "#ffffff"], BUR: ["#6c1d45", "#99d6ea"],
  CHE: ["#034694", "#034694"], COV: ["#62b5e5", "#ffffff"], CRY: ["#1b458f", "#c4122e", "#c4122e"],
  EVE: ["#003399", "#003399"], FUL: ["#ffffff", "#111111"], HUL: ["#f18a01", "#111111", "#111111"],
  IPS: ["#3a64a3", "#ffffff"], LEE: ["#ffffff", "#1d428a"], LEI: ["#003090", "#003090"], LIV: ["#c8102e", "#c8102e"],
  MCI: ["#6cabdd", "#6cabdd"], MUN: ["#da291c", "#da291c"], NEW: ["#ffffff", "#111111", "#111111"],
  NFO: ["#dd0000", "#ffffff"], SOU: ["#d71920", "#ffffff", "#ffffff"], SUN: ["#eb172b", "#eb172b", "#ffffff"],
  TOT: ["#ffffff", "#132257"], WHU: ["#7a263a", "#1bb1e7"], WOL: ["#fdb913", "#231f20"],
};

/** A simple shirt in the club's colours, from its three-letter short name. */
export function Shirt({ team, size = 34, className = "" }: { team: string; size?: number; className?: string }) {
  const clip = useId();
  const [body, sleeve, stripe] = KITS[team] ?? ["#888888", "#666666"];
  const edge = body === "#ffffff" ? "#cfcfcf" : "rgba(0,0,0,.18)";
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <path
        d="M14 6l-10 7 4 9 6-3v23h20V19l6 3 4-9-10-7c-1.5 3-4 4.5-10 4.5S15.5 9 14 6z"
        fill={body}
        stroke={edge}
        strokeWidth="1"
      />
      <path d="M14 6l-10 7 4 9 6-3zM34 6l10 7-4 9-6-3z" fill={sleeve} />
      {stripe && (
        <>
          <clipPath id={clip}>
            <path d="M14 8h20v34H14z" />
          </clipPath>
          <g clipPath={`url(#${clip})`}>
            {[16.5, 24, 31.5].map((x) => (
              <rect key={x} x={x - 2} y="8" width="4" height="34" fill={stripe} />
            ))}
          </g>
        </>
      )}
    </svg>
  );
}
