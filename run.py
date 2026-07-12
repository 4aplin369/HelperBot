from __future__ import annotations

import os

from helper_bot.bot import main


if __name__ == "__main__":
    os.environ.setdefault("DATA_DIR", "/data")
    main()
