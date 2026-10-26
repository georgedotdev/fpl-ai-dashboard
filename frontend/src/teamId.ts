/**
 * Pull an FPL team ID out of whatever the user pasted: the number itself, or any FPL link
 * that contains it (e.g. https://fantasy.premierleague.com/entry/1234567/event/9).
 * Returns null when there's no ID in it.
 */
export function parseTeamId(input: string): number | null {
  const text = input.trim();
  const fromLink = text.match(/entry\/(\d+)/i);
  const digits = fromLink ? fromLink[1] : /^\d+$/.test(text) ? text : null;
  if (!digits) return null;
  const id = Number(digits);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}
