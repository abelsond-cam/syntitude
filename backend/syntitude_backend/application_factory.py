"""``create_application(configuration) -> Flask`` — registers blueprints and nothing else.

The factory decides nothing. Which endpoints exist is the blueprint list below; what they
return is the services layer; where the data is, is `Configuration`. Keeping it that thin is
what lets a test build an app against a throwaway database in two lines.
"""

from __future__ import annotations

from flask import Flask

from syntitude_backend.api.blueprint_health import health_blueprint
from syntitude_backend.api.blueprint_species import species_blueprint
from syntitude_backend.configuration import Configuration
from syntitude_backend.database import Database

#: Every blueprint the application serves, in registration order. One line per resource.
BLUEPRINTS = (health_blueprint, species_blueprint)

#: All API routes live under this prefix. The version is in the path rather than a header so a
#: breaking change can run alongside its predecessor instead of replacing it.
API_PREFIX = "/api/v1"


def create_application(configuration: Configuration | None = None) -> Flask:
    """Build the app. Pass a `Configuration` in tests; omit it to read the environment."""
    configuration = configuration or Configuration.from_environment()
    application = Flask(__name__)
    application.config["SYNTITUDE"] = configuration
    application.extensions["syntitude_database"] = Database(configuration)

    for blueprint in BLUEPRINTS:
        application.register_blueprint(blueprint, url_prefix=API_PREFIX)

    # Read-only service, immutable responses: JSON key order carries no meaning and sorting it
    # makes two responses byte-comparable, which the parity suites rely on.
    application.json.sort_keys = True
    return application
