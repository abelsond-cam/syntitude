"""Every error under `/api/` is JSON — including the ones no route chose to raise.

A missing route answered with Flask's HTML 404 and an unmigrated database with its HTML 500, and the
front end reported "Unexpected token '<'" instead of the status. These need no database at all.
"""

from __future__ import annotations

from syntitude_backend.application_factory import create_application
from syntitude_backend.configuration import Configuration

#: Never connected to: nothing here reaches a route that opens a session.
UNREACHABLE = "postgresql+psycopg://nobody@127.0.0.1:1/none"


def _client():
    application = create_application(Configuration(database_url=UNREACHABLE))
    # ⚠ As a server runs, not as a test runs: under TESTING Flask re-raises instead of answering.
    application.config["PROPAGATE_EXCEPTIONS"] = False
    return application


def test_an_unknown_api_route_is_a_JSON_404_with_the_same_shape_as_a_named_one():
    reply = _client().test_client().get("/api/v1/no/such/route")
    assert reply.status_code == 404
    assert reply.is_json
    assert reply.get_json()["error"] == "not_found"


def test_an_unhandled_error_is_a_JSON_500_that_leaks_NOTHING_about_the_server():
    application = _client()

    @application.get("/api/v1/boom")
    def boom():
        raise RuntimeError('relation "locus" does not exist at /srv/secret/path')

    reply = application.test_client().get("/api/v1/boom")
    assert reply.status_code == 500
    assert reply.is_json
    body = reply.get_json()
    assert body["error"] == "server_error"
    assert "locus" not in body["detail"] and "/srv" not in body["detail"]


def test_outside_the_api_errors_are_left_to_the_framework():
    reply = _client().test_client().get("/not-the-api")
    assert reply.status_code == 404
    assert not reply.is_json
