import { useState } from "react";
import { getFixtures, type FixturesResponse } from "../api";
import { useData } from "../hooks";
import { Card } from "./Card";
import { ErrorBox, Loading, Select, Toolbar, fdrClass, horizonOptions } from "./ui";

/** The fixture ticker in FPL's difficulty colours, teams with the easiest run first. */
export function FdrGrid({ data }: { data: FixturesResponse }) {
  return (
    <div className="-mx-1 overflow-x-auto px-1">
      <table className="w-full min-w-[22rem] border-separate border-spacing-1 text-xs">
        <thead>
          <tr className="text-faint">
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
              <td className="pr-2 font-semibold" title={team.name}>
                {team.short_name}
              </td>
              {team.gameweeks.map((cells, i) => (
                <td key={i} className="p-0">
                  {cells.length === 0 ? (
                    <div className="rounded border border-dashed border-line py-1.5 text-center text-faint">blank</div>
                  ) : (
                    <div className="flex gap-0.5">
                      {cells.map((c, j) => (
                        <div
                          key={j}
                          className={`flex-1 rounded py-1.5 text-center font-semibold ${fdrClass(c.difficulty)}`}
                          title={`${c.home ? "Home" : "Away"} vs ${c.opponent}, difficulty ${c.difficulty}`}
                        >
                          {c.home ? c.opponent : c.opponent.toLowerCase()}
                        </div>
                      ))}
                    </div>
                  )}
                </td>
              ))}
              <td className="num text-right">{team.average_difficulty?.toFixed(2) ?? "–"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-faint">
        FPL's difficulty ratings. Home fixtures in capitals, away in lower case; a double gameweek shows two fixtures in one cell.
      </p>
    </div>
  );
}

export function FixturesView() {
  const [horizon, setHorizon] = useState(6);
  const { data, error, loading } = useData(() => getFixtures(horizon), [horizon]);

  return (
    <Card title="Fixture difficulty">
      <Toolbar>
        <Select label="Horizon" value={horizon} options={horizonOptions()} onChange={setHorizon} />
        <div className="flex items-center gap-1 text-xs text-faint">
          <span>Easy</span>
          {[1, 2, 3, 4, 5].map((d) => (
            <span key={d} className={`rounded px-1.5 py-0.5 font-semibold ${fdrClass(d)}`}>
              {d}
            </span>
          ))}
          <span>Hard</span>
        </div>
      </Toolbar>
      {error && <ErrorBox message={error} />}
      {loading && !data && <Loading />}
      {data && <FdrGrid data={data} />}
    </Card>
  );
}
