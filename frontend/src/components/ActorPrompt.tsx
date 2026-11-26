/**
 * "Who's using this?": asked once, remembered on this device (BUILD_PROMPT §8.5). The name goes
 * in the X-Actor header, so the audit log says who changed what. There is no login in v1 (ADR-011).
 * Opens on first visit, or when Dana clicks "change" in the header.
 */
import { useState, type FormEvent } from "react";
import { DEFAULT_ACTOR, getActor, hasChosenActor, setActor } from "../lib/actor";
import { Dialog } from "./Dialog";

interface ActorPromptProps {
  open: boolean;
  onDone: (name: string) => void;
}

export function ActorPrompt({ open, onDone }: ActorPromptProps) {
  const [name, setName] = useState(hasChosenActor() ? getActor() : DEFAULT_ACTOR);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const chosen = name.trim() || DEFAULT_ACTOR;
    setActor(chosen);
    onDone(chosen);
  };
  return (
    <Dialog open={open} title="Who's using this?" onClose={() => onDone(getActor())}>
      <form onSubmit={submit} className="space-y-3">
        <p className="text-fog">
          Your name goes next to any change you make, so everyone can see who changed what.
        </p>
        <label className="block">
          <span className="text-sm font-semibold">Your name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={80}
            className="mt-1 w-full rounded-md border border-rope px-3 py-2"
          />
        </label>
        <button type="submit" className="rounded-md bg-ink px-4 py-2 font-semibold text-hull">
          Continue
        </button>
      </form>
    </Dialog>
  );
}
