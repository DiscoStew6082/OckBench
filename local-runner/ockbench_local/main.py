"""Register local providers, then delegate to OckBench's pinned CLI."""

from main import main

from . import lmstudio_native_provider  # noqa: F401

if __name__ == "__main__":
    raise SystemExit(main())
