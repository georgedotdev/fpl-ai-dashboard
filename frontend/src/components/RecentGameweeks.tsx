import type { GameweekResult } from "../api";
import { rank } from "../format";

export function RecentGameweeks({
  gameweeks,
  chipLabels,
}: {
  gameweeks: GameweekResult[];
  chipLabels: Record<string, string>;
}) {
  const recent = [...gameweeks].reverse().slice(0, 6);
  return (
    <div className="-mx-4 overflow-x-auto px-4">
      <table className="w-full min-w-[28rem] text-sm tabular-nums">
        <thead>
          <tr className="text-left text-xs text-slate-500 dark:text-slate-400">
            <th className="py-1 font-medium">GW</th>
            <th className="py-1 text-right font-medium">Points</th>
            <th className="py-1 text-right font-medium">Overall rank</th>
            <th className="py-1 text-right font-medium">Transfers</th>
            <th className="py-1 pl-4 font-medium">Chip</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {recent.map((gw) => (
            <tr key={gw.gameweek}>
              <td className="py-1.5">{gw.gameweek}</td>
              <td className="py-1.5 text-right font-medium">{gw.points}</td>
              <td className="py-1.5 text-right">{rank(gw.overall_rank)}</td>
              <td className="py-1.5 text-right">
                {gw.transfers}
                {gw.transfer_cost > 0 && <span className="text-red-600 dark:text-red-400"> (−{gw.transfer_cost})</span>}
              </td>
              <td className="py-1.5 pl-4 text-slate-500 dark:text-slate-400">{gw.chip ? (chipLabels[gw.chip] ?? gw.chip) : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
