import { useEffect, useState } from "react";
import { getRules } from "./api";
import { Countdown } from "./components/Countdown";
import { useData } from "./hooks";
import { BestPicksView } from "./components/BestPicksView";
import { CaptaincyView } from "./components/CaptaincyView";
import { FixturesView } from "./components/FixturesView";
import { MyTeam } from "./components/MyTeam";
import { PlayersView } from "./components/PlayersView";

const TABS = [
  { id: "team", label: "My team" },
  { id: "players", label: "Players" },
  { id: "fixtures", label: "Fixtures" },
  { id: "captains", label: "Captains" },
  { id: "picks", label: "Best picks" },
] as const;
type TabId = (typeof TABS)[number]["id"];

function tabFromUrl(): TabId {
  const hash = window.location.hash.slice(1);
  return TABS.some((t) => t.id === hash) ? (hash as TabId) : "team";
}

export default function App() {
  const [tab, setTab] = useState<TabId>(tabFromUrl);

  useEffect(() => {
    const onHash = () => setTab(tabFromUrl());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const rules = useData(getRules, []);

  return (
    <div className="mx-auto max-w-[1240px] px-4 pb-10 lg:px-8">
      <header className="flex h-[60px] items-center gap-3">
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-accent" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 18 18">
            <rect x="2" y="2" width="14" height="14" rx="2" fill="none" stroke="#37003c" strokeWidth="1.6" />
            <path d="M2 9h14M9 2v14" stroke="#37003c" strokeWidth="1.6" />
            <circle cx="9" cy="9" r="2.6" fill="none" stroke="#37003c" strokeWidth="1.6" />
          </svg>
        </span>
        <div className="font-semibold leading-tight">
          FPL Assistant
          <small className="block text-xs font-normal text-faint">No login, no password</small>
        </div>
        {rules.data?.planning_deadline && (
          <div className="ml-auto text-right text-xs leading-4 text-faint">
            GW{rules.data.planning_gameweek} deadline
            <strong className="block text-sm font-semibold text-ink">
              <Countdown iso={rules.data.planning_deadline} />
            </strong>
          </div>
        )}
      </header>

      <h1 className="mt-3 text-[22px] font-bold leading-7">
        {rules.data?.planning_gameweek ? `Gameweek ${rules.data.planning_gameweek}` : "FPL Assistant"}
      </h1>
      <p className="mt-0.5 text-sm text-muted">Transfer, captain, bench and chip advice for your FPL team.</p>

      <nav className="-mx-4 my-5 overflow-x-auto px-4 [scrollbar-width:none]" aria-label="Sections">
        <ul className="flex gap-1.5">
          {TABS.map((t) => (
            <li key={t.id}>
              <a
                href={`#${t.id}`}
                aria-current={tab === t.id ? "page" : undefined}
                className={`block whitespace-nowrap rounded-full px-4 py-1.5 text-sm font-semibold transition-colors ${
                  tab === t.id ? "bg-accent text-accent-ink" : "bg-surface text-muted hover:bg-raised hover:text-ink"
                }`}
              >
                {t.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      {/* My team stays mounted so switching tabs doesn't refetch the squad and plans. */}
      <div hidden={tab !== "team"}>
        <MyTeam />
      </div>
      {tab === "players" && <PlayersView />}
      {tab === "fixtures" && <FixturesView />}
      {tab === "captains" && <CaptaincyView />}
      {tab === "picks" && <BestPicksView />}
    </div>
  );
}
