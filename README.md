# City Camera Network Tracker

This project tracks vehicles by plate across a city-wide camera network, uses appearance and timing as a fallback identity signal when a plate can't be read, and learns normal transit patterns between cameras to flag journeys that deviate from them.

## Setup Decisions

- Virtual Environment: Created Python 3.10 virtual environment (`backend/venv`) for binary compatibility with PyTorch, TorchVision, and OpenCV on Windows.
- Dependency Pinning: Standardized and pinned exact resolved package versions to `backend/requirements.txt`.
- Data Isolation: SQLite databases and video clips isolated under `backend/data/` and excluded from git tracking.
- Design Rules: Locked design rules codified in `DESIGN.md` across color palette, typography, layout, and copy tone.

## Build Log

- Stage 1 completed: Project directory tree, git configuration, virtual environment with pinned dependencies, locked DESIGN.md contract, and FastAPI health probe verified.
