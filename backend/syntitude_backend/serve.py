"""``python -m syntitude_backend.serve`` — the development server.

Production is gunicorn against ``syntitude_backend.application_factory:create_application()``;
this exists so that a fresh clone can be run with one command and no WSGI knowledge.
"""

from __future__ import annotations

import argparse

from syntitude_backend.application_factory import create_application


def main() -> None:
    """CLI entry: run the development server."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    arguments = parser.parse_args()
    create_application().run(host=arguments.host, port=arguments.port, debug=arguments.debug)


if __name__ == "__main__":
    main()
