"""Entry point so the loader is `python -m bacatlas_backend.ingest`."""

from bacatlas_backend.ingest.ingest_command_line import main

raise SystemExit(main())
