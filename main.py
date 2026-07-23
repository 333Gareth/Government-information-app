"""Entry point for the GOV.UK Policy Intelligence Workstation.

Run with:  python main.py
"""

from __future__ import annotations

import logging
import tkinter as tk

from gov_intel.ui.app import GovApp


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    root = tk.Tk()
    GovApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
