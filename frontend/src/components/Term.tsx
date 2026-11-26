/**
 * A word with a plain-English explanation on hover or keyboard focus (BUILD_PROMPT §9.3), e.g.
 * "to arrive", "cushion", "promised to customers". Tap on a phone also focuses it.
 * The definitions live in one place (GLOSSARY) so every page says the same thing.
 * Only the word's own hover or keyboard focus opens its bubble (named group "term", see below).
 * The bubble ignores the mouse (pointer-events-none): otherwise it can open over a button above the
 * word and swallow the click (found in the Phase 5 click-through: "Set real date" under "on hold").
 */
import { useId, type ReactNode } from "react";

// eslint-disable-next-line react-refresh/only-export-components
export const GLOSSARY = {
  arrive: "Time to arrive means from placing the order to having it in our building.",
  cushion: "Cushion means extra stock for when ships slip.",
  promised: "Promised to customers means open orders not yet shipped.",
  onHold: "On hold means waiting on paperwork or a temperature check. Not counted until it passes.",
  sixMonth:
    "Inside the six-month line means less than six months left before it expires. Customers won't take it, so it needs discounting or moving now.",
  harbor: "Harbor Cold Storage is overflow storage we pay for by the pallet, every month.",
  late: "A late PO is one whose arrival date has passed with nothing received. It isn't counted until you set a real date.",
} as const;

interface TermProps {
  explain: keyof typeof GLOSSARY;
  children: ReactNode;
}

export function Term({ explain, children }: TermProps) {
  const id = useId();
  return (
    // A NAMED group ("term"): a plain "group" would also match the dropdown row around it (<details
    // className="group">), so opening or hovering a row showed every bubble inside it (Ishan, 2026-11-26).
    <span className="group/term relative inline-block">
      <span
        tabIndex={0}
        aria-describedby={id}
        className="cursor-help underline decoration-fog decoration-dotted underline-offset-4"
      >
        {children}
      </span>
      <span
        id={id}
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-0 z-20 mb-1 hidden w-64 max-w-[calc(100vw-2rem)] rounded-md bg-ink px-3 py-2 text-sm font-normal text-hull shadow-md group-focus-within/term:block group-hover/term:block"
      >
        {GLOSSARY[explain]}
      </span>
    </span>
  );
}
