/**
 * BlueTide descriptions are all caps ("WHITE SHRIMP 21/25 P&D TAIL-ON"). The spec asks for sentence
 * case (BUILD_PROMPT §9.1), so words are lower-cased, but anything that looks like a code or a size
 * keeps its letters: words with a digit or "&" (21/25, P&D) and words with no vowels (IQF).
 * "8OZ" becomes "8 oz". Display only: the item code is always shown next to the name.
 */
export function itemName(description: string): string {
  const words = description
    .trim()
    .split(/\s+/)
    .map((w) => {
      const sized = w.replace(
        /(\d)(OZ|LB|KG)$/i,
        (_, d: string, u: string) => `${d} ${u.toLowerCase()}`,
      );
      if (sized !== w) return sized;
      if (/[\d&]/.test(w) || !/[AEIOUY]/i.test(w)) return w;
      return w.toLowerCase();
    });
  const [first, ...rest] = words;
  if (first === undefined) return description;
  return [first.charAt(0).toUpperCase() + first.slice(1), ...rest].join(" ");
}
