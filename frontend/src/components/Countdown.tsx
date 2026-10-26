import { useEffect, useState } from "react";

function left(deadline: number): string {
  let s = Math.max(0, Math.floor((deadline - Date.now()) / 1000));
  const d = Math.floor(s / 86400);
  s -= d * 86400;
  const h = Math.floor(s / 3600);
  s -= h * 3600;
  const m = Math.floor(s / 60);
  s -= m * 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  if (d > 0) return `${d}d ${pad(h)}h ${pad(m)}m`;
  return `${h}h ${pad(m)}m ${pad(s)}s`;
}

/** Live time left until a deadline, ticking every second. */
export function Countdown({ iso }: { iso: string }) {
  const deadline = new Date(iso).getTime();
  const [text, setText] = useState(() => left(deadline));
  useEffect(() => {
    const t = setInterval(() => setText(left(deadline)), 1000);
    return () => clearInterval(t);
  }, [deadline]);
  return <span className="num">{text}</span>;
}
