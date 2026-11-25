/** What Dana sees on a mistyped link: a plain message and a way back. */
import { Link } from "react-router";

export function NotFoundPage() {
  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
      <h1 className="text-xl font-bold">We couldn't find that page.</h1>
      <Link to="/" className="mt-3 inline-block font-semibold text-soon underline">
        Go to the Monday screen
      </Link>
    </main>
  );
}
