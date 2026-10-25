import { useState } from "react";
import { getFixtures } from "../api";
import { useData } from "../hooks";
import { Card } from "./Card";
import { ErrorBox, Loading, Select, Toolbar, fdrClass, horizonOptions } from "./ui";

export function FixturesView() {
  const [horizon, setHorizon] = useState(6);
  const { data, error, loading } = useData(() => getFixtures(horizon), [horizon]);

  return (
    <Card title="Fixture difficulty">
      <Toolbar>
        <Select label="Horizon" value={horizon} options={horizonOptions()} onChange={setHorizon} />
        <div className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
          <span>Easy</span>
          {[1, 2, 3, 4, 5].map((d) => (
            <span key={d} className={`rounded px-1.5 py-0.5 ${fdrClass(d)}`}>
              {d}
            </span>
          ))}
          <span>Hard</span>
        </div>
      </Toolbar>
      {error && <ErrorBox message={error} />}
      {loading && !data && <Loading />}
      {data && (
        <div className="-mx-4 overflow-x-auto px-4">
          <table className="w-full min-w-[36rem] border-separate border-spacing-1 text-xs">
            <thead>
              <tr className="text-slate-500 dark:text-slate-400">
                <th className="text-left font-medium">Team</th>
                {data.gameweeks.map((gw) => (
                  <th key={gw} className="font-medium">
                    GW{gw}
                  </th>
                ))}
                <th className="text-right font-medium" title="Average difficulty of the fixtures shown">
                  Avg
                </th>
              </tr>
            </thead>
            <tbody>
              {data.teams.map((team) => (
                <tr key={team.team_id}>
                  <td className="pr-2 font-medium" title={team.name}>
                    {team.short_name}
                  </td>
                  {team.gameweeks.map((cells, i) => (
                    <td key={i} className="p-0">
                      {cells.length === 0 ? (
                        <div className="rounded border border-dashed border-slate-300 py-1.5 text-center text-slate-400 dark:border-slate-700">
                          blank
                        </div>
                      ) : (
                        <div className="flex gap-0.5">
                          {cells.map((c, j) => (
                            <div
                              key={j}
                              className={`flex-1 rounded py-1.5 text-center font-medium ${fdrClass(c.difficulty)}`}
                              title={`${c.home ? "Home" : "Away"} vs ${c.opponent}, difficulty ${c.difficulty}`}
                            >
                              {c.home ? c.opponent : c.opponent.toLowerCase()}
                            </div>
                          ))}
                        </div>
                      )}
                    </td>
                  ))}
                  <td className="text-right tabular-nums">{team.average_difficulty?.toFixed(2) ?? "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
            FPL's fixture difficulty ratings. Home fixtures in capitals, away in lower case. Teams with the easiest run come first;
            a double gameweek shows two fixtures in one cell.
          </p>
        </div>
      )}
    </Card>
  );
}
