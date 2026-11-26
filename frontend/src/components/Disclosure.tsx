/**
 * A section Dana can open and close ("Handled (2)", "Everything else looks fine (21 items)").
 * Native <details>, so it works with the keyboard and screen readers for free.
 */
import type { ReactNode } from "react";

interface DisclosureProps {
  title: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}

export function Disclosure({ title, defaultOpen = false, children }: DisclosureProps) {
  return (
    <details open={defaultOpen} className="group rounded-lg border border-rope bg-hull">
      <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 font-semibold">
        <span>{title}</span>
        <span aria-hidden="true" className="text-fog transition-transform group-open:rotate-90">
          ›
        </span>
      </summary>
      <div className="border-t border-rope px-4 py-3">{children}</div>
    </details>
  );
}
