"""Allow ``python -m ddp2json`` (delegates to ``engine.cli.main``)."""

from .engine.cli import main

if __name__ == "__main__":
    main()
