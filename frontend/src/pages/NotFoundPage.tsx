/** What Dana sees on a mistyped link: a plain message and a way back. */
import { Link } from "react-router";

export function NotFoundPage() {
  return (
    <div>
      <h1 className="text-xl font-bold">We couldn't find that page.</h1>
      <Link to="/" className="mt-3 inline-block font-semibold text-ink underline">
        Go to the Monday screen
      </Link>
    </div>
  );
}
