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
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-raised p-3 text-sm">
      <p className="text-muted">
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
            className="rounded-full bg-accent px-4 py-1.5 font-bold text-accent-ink hover:brightness-110"
          >
            Install
          </button>
        )}
        <button onClick={dismiss} className="px-2 py-1.5 text-accent hover:underline">
          Not now
        </button>
      </div>
    </div>
  );
}
