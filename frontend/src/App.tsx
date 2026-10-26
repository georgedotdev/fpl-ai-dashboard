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

function TabIcon({ id }: { id: TabId }) {
  const paths: Record<TabId, string> = {
    team: "M3 8l7-5 7 5v8.5H12.5V12h-5v4.5H3z",
    players: "M10 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM4 17c.6-3.4 3-5 6-5s5.4 1.6 6 5",
    fixtures: "M3.5 5h13v11.5h-13zM3.5 8.5h13M7 3v3M13 3v3",
    captains: "M10 3.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zM12.4 7.6a3 3 0 1 0 0 4.8",
    picks: "M10 3l2 4.3 4.7.6-3.4 3.2.9 4.6L10 13.4 5.8 15.7l.9-4.6L3.3 7.9 8 7.3z",
  };
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
      <path d={paths[id]} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

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
    <div className="w-full px-4 pb-24 md:pb-10 lg:px-8 2xl:px-12">
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

      <nav className="-mx-4 my-5 hidden overflow-x-auto px-4 [scrollbar-width:none] md:block" aria-label="Sections">
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

      {/* On a phone the sections move to a bottom tab bar, within reach of a thumb. */}
      <nav
        className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-5 bg-surface pb-[env(safe-area-inset-bottom)] md:hidden"
        aria-label="Sections"
      >
        {TABS.map((t) => (
          <a
            key={t.id}
            href={`#${t.id}`}
            aria-current={tab === t.id ? "page" : undefined}
            className={`flex flex-col items-center gap-0.5 pb-2.5 pt-2 text-[11px] font-semibold transition-colors ${
              tab === t.id ? "text-accent" : "text-faint"
            }`}
          >
            <TabIcon id={t.id} />
            {t.label}
          </a>
        ))}
      </nav>
    </div>
  );
}
