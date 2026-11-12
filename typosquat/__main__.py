"""Allow ``python -m typosquat`` in addition to the cli module entry point."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
