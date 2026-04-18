#!/usr/bin/env python3
"""Standalone entry point for PyInstaller builds.

Converts relative imports to absolute so the frozen binary works.
"""

import sys
import os

# When running as a PyInstaller bundle, adjust the path
if getattr(sys, "frozen", False):
    # Running as compiled
    bundle_dir = sys._MEIPASS  # type: ignore[attr-defined]
    sys.path.insert(0, bundle_dir)

from copilot_confirm.install import main

if __name__ == "__main__":
    sys.exit(main())
