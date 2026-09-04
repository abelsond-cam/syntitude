"""``GET /health`` — liveness, and whether the database behind it is actually usable.

⚠ A health check that only proves the process is running is worse than none: it goes green
while every request 500s on a database that is unreachable, or reachable and empty. This one
reports the connection, the server version and whether the schema has been migrated, and it
says which of those failed rather than returning a bare 503.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

health_blueprint = Blueprint("health", __name__)

#: Present once the first migration has run. Until then the API is up and has nothing to serve,
#: which is a distinct state from "the database is down" and must read as one.
_SCHEMA_PROBE = text("SELECT to_regclass('public.pangenome') IS NOT NULL AS schema_present")


@health_blueprint.get("/health")
def report_health():
    """Report process liveness and database reachability. 200 healthy, 503 otherwise."""
    database = current_app.extensions["syntitude_database"]
    report: dict[str, object] = {
        "service": "syntitude-backend",
        "deployment_profile": current_app.config["SYNTITUDE"].deployment_profile,
        "database_reachable": False,
        "schema_present": False,
    }
    try:
        with database.session() as session:
            report["database_server_version"] = session.execute(text("SHOW server_version")).scalar_one()
            report["database_reachable"] = True
            report["schema_present"] = bool(session.execute(_SCHEMA_PROBE).scalar_one())
    except SQLAlchemyError as error:
        # The class name and message, not a traceback: this endpoint is public.
        report["database_error"] = f"{type(error).__name__}: {error}"
        return jsonify(report), 503

    if not report["schema_present"]:
        report["note"] = "database reachable but not migrated — run `alembic upgrade head`"
    return jsonify(report), 200
