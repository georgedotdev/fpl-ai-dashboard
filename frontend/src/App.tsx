import { useEffect, useState } from "react";
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

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:py-10">
      <header className="mb-4">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">FPL Assistant</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Transfer, captain, bench and chip advice for your FPL team. No login, no password.
        </p>
      </header>

      <nav className="-mx-4 mb-6 overflow-x-auto border-b border-slate-200 px-4 dark:border-slate-800" aria-label="Sections">
        <ul className="flex gap-1">
          {TABS.map((t) => (
            <li key={t.id}>
              <a
                href={`#${t.id}`}
                aria-current={tab === t.id ? "page" : undefined}
                className={`block whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium ${
                  tab === t.id
                    ? "border-violet-600 text-violet-700 dark:text-violet-400"
                    : "border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
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
