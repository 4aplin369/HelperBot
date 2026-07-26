from __future__ import annotations

import os

from helper_bot.bot import main


if __name__ == "__main__":
    if os.getenv("DATA_DIR") in {None, "", "/app/data"}:
        os.environ["DATA_DIR"] = "/data"
    main()
