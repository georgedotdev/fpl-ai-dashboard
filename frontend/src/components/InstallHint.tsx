import { useEffect, useState } from "react";
import { KEYS, load, save } from "../storage";

// Chrome and Edge (Android, desktop) fire this when the page can be installed as an app.
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
}

function isInstalled(): boolean {
  const iosStandalone = (navigator as Navigator & { standalone?: boolean }).standalone === true;
  return iosStandalone || window.matchMedia("(display-mode: standalone)").matches;
}

function isIos(): boolean {
  return /iphone|ipad|ipod/i.test(navigator.userAgent);
}

/** Suggests adding the page to the home screen, so it opens straight to your team like an app. */
export function InstallHint() {
  const [prompt, setPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [dismissed, setDismissed] = useState(() => load<boolean>(KEYS.installHintDismissed) === true);

  useEffect(() => {
    const onPrompt = (e: Event) => {
      e.preventDefault();
      setPrompt(e as BeforeInstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", onPrompt);
    return () => window.removeEventListener("beforeinstallprompt", onPrompt);
  }, []);

  if (dismissed || isInstalled() || (!prompt && !isIos())) return null;

  function dismiss() {
    save(KEYS.installHintDismissed, true);
    setDismissed(true);
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-violet-200 bg-violet-50 p-3 text-sm dark:border-violet-900 dark:bg-violet-950">
      <p className="text-violet-900 dark:text-violet-200">
        {prompt ? (
          <>Add FPL Assistant to your home screen: it'll open straight to your team.</>
        ) : (
          <>
            Add this to your home screen: tap <strong>Share</strong>, then <strong>Add to Home Screen</strong>. It'll open
            straight to your team.
          </>
        )}
      </p>
      <div className="flex gap-2">
        {prompt && (
          <button
            onClick={() => {
              void prompt.prompt().finally(() => setPrompt(null));
            }}
            className="rounded-md bg-violet-600 px-3 py-1.5 font-medium text-white hover:bg-violet-700"
          >
            Install
          </button>
        )}
        <button onClick={dismiss} className="px-2 py-1.5 text-violet-700 hover:underline dark:text-violet-300">
          Not now
        </button>
      </div>
    </div>
  );
}
