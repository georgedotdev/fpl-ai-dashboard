/** Step-by-step help for finding an FPL team ID, written for phones first. */
export function FindTeamId({ onEnterByHand }: { onEnterByHand: () => void }) {
  return (
    <details className="mb-6 rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-800">
      <summary className="cursor-pointer font-medium text-violet-700 dark:text-violet-400">
        Where do I find my team ID?
      </summary>
      <div className="mt-3 space-y-3 text-slate-700 dark:text-slate-300">
        <p>
          The official FPL app doesn't show it, so use the FPL <strong>website</strong> once. After that, this page remembers
          your team on this device.
        </p>
        <div>
          <h3 className="font-medium text-slate-900 dark:text-slate-100">On your phone</h3>
          <ol className="mt-1 list-decimal space-y-1 pl-5">
            <li>
              Open{" "}
              <a
                href="https://fantasy.premierleague.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-violet-700 underline dark:text-violet-400"
              >
                fantasy.premierleague.com
              </a>{" "}
              in Safari or Chrome and sign in. If the link opens the FPL app instead, type the address into your browser.
            </li>
            <li>
              Tap <strong>Points</strong>.
            </li>
            <li>
              Tap the address bar and copy the whole address. It looks like …/entry/<strong>1234567</strong>/event/9.
            </li>
            <li>Paste it into the box above. We'll pick the team ID out of the link for you.</li>
          </ol>
        </div>
        <div>
          <h3 className="font-medium text-slate-900 dark:text-slate-100">On a computer</h3>
          <p className="mt-1">
            Sign in at fantasy.premierleague.com, click <strong>Points</strong>, and copy the address (or just the number after
            /entry/).
          </p>
        </div>
        <p>
          Don't want to? <button onClick={onEnterByHand} className="font-medium text-violet-700 underline dark:text-violet-400">
            Enter your squad by hand
          </button>{" "}
          instead: no team ID needed.
        </p>
      </div>
    </details>
  );
}
