#!/usr/bin/env python3
"""Backward-compatible entry point. Prefer ``python -m ddp2json``."""

from ddp2json.engine.cli import main

if __name__ == "__main__":
    main()
