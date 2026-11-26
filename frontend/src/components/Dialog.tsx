/**
 * A simple accessible dialog (native <dialog>): used for "Mark as handled" and "Who's using this?".
 * Escape or the Cancel button closes it.
 */
import { useEffect, useRef, type ReactNode } from "react";

interface DialogProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}

export function Dialog({ open, title, onClose, children }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="dialog-title"
      className="m-auto w-[min(32rem,calc(100%-2rem))] rounded-lg border border-rope bg-hull p-0 text-ink backdrop:bg-ink/40"
    >
      <div className="p-5">
        <h2 id="dialog-title" className="text-lg font-bold">
          {title}
        </h2>
        <div className="mt-3">{children}</div>
      </div>
    </dialog>
  );
}
