"""Entry point: `uv run app.py` locally, or run automatically on Hugging Face Spaces."""

import sys
from pathlib import Path

# The package lives in src/ (uv layout). Spaces doesn't install it, so add it to the path.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from voice_agent import main  # noqa: E402

if __name__ == "__main__":
    main()
