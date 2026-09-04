"""Entry point so the loader is `python -m syntitude_backend.ingest`."""

from syntitude_backend.ingest.ingest_command_line import main

raise SystemExit(main())
