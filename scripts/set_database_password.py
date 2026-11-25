"""Put the Supabase database password into backend/.env safely.

Why this exists
    The password goes *inside* the DATABASE_URL line (between "postgres.<ref>:" and "@aws-0-..."),
    which is easy to miss, and characters like @ : / # in a password silently break the URL unless
    they are URL-encoded. This script does both for you, and never prints the password.

Run it in your own Terminal from the repo root (it needs a real keyboard for the hidden prompt):
    python3 scripts/set_database_password.py

It reads backend/.env, asks for the password (nothing shows as you type), URL-encodes it, and
replaces the password part of DATABASE_URL (the [YOUR-DATABASE-PASSWORD] placeholder, or an old
password). Running it again just replaces the password again. Uses only the standard library.
"""

from __future__ import annotations

import getpass
import re
import sys
from pathlib import Path
from urllib.parse import quote

DEFAULT_ENV = Path(__file__).resolve().parents[1] / "backend" / ".env"
_LINE = re.compile(r"^DATABASE_URL=(?P<url>.*)$", re.MULTILINE)


def with_password(url: str, password: str) -> str:
    """Return `url` with its password replaced by the URL-encoded `password`.

    Example: with_password("postgresql://u:[X]@host:5432/db", "p@ss") -> "postgresql://u:p%40ss@host:5432/db"
    The password is everything between the first ":" after the user name and the LAST "@".
    """
    scheme, sep, rest = url.partition("://")
    if not sep:
        raise ValueError("DATABASE_URL should start with postgresql://")
    credentials, at, host_part = rest.rpartition("@")
    if not at:
        raise ValueError("DATABASE_URL has no '@host' part")
    user = credentials.split(":", 1)[0]
    if not user:
        raise ValueError("DATABASE_URL has no user name")
    return f"{scheme}://{user}:{quote(password, safe='')}@{host_part}"


def main(env_path: Path = DEFAULT_ENV) -> int:
    if not env_path.exists():
        print(f"Can't find {env_path}. Copy backend/.env.example to backend/.env first.")
        return 1
    text = env_path.read_text()
    match = _LINE.search(text)
    if not match or not match.group("url").strip():
        print("backend/.env has no DATABASE_URL value. Paste the Supabase session pooler string first.")
        return 1

    password = getpass.getpass("Supabase database password (hidden while you type): ")
    if not password:
        print("No password entered. Nothing changed.")
        return 1

    try:
        new_url = with_password(match.group("url").strip(), password)
    except ValueError as problem:
        print(f"Couldn't update DATABASE_URL: {problem}")
        return 1

    env_path.write_text(text[: match.start("url")] + new_url + text[match.end("url") :])
    host = new_url.rpartition("@")[2].split("/")[0]
    print(f"Saved. DATABASE_URL now uses your password (not shown) for {host}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ENV))
