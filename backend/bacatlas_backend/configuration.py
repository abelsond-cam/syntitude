"""Environment-driven settings — the only place a path or a URL is read from the outside.

Two deployment profiles, and the difference between them is entirely *where the files are*:
the Mac has the cluster artifacts under ``~/developer/nuna/data``, the med school server has
whatever its sysadmin gave us. Nothing else in the package reads ``os.environ``, so a wrong
path is one exception at start-up rather than a 404 on one endpoint three weeks later.

⛔ ``artifact_roots`` is a MAP, not a single path. Every ``artifact_pointer`` row stores a root
KEY plus a relative path, so moving the store is a config change and not a database migration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

#: Root keys an artifact_pointer row may name. Adding one is a schema decision, not a config
#: convenience, so the set is closed here and validated at start-up.
ARTIFACT_ROOT_KEYS = ("gff", "assemblies", "embeddings", "analysis")


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. The API refuses to start without it rather than failing on the "
            f"first request that needs it — see syntitude_backend/configuration.py."
        )
    return value


@dataclass(frozen=True)
class Configuration:
    """Everything the application needs from its environment, resolved once."""

    database_url: str
    artifact_roots: dict[str, Path] = field(default_factory=dict)
    deployment_profile: str = "development"
    sql_echo: bool = False

    @classmethod
    def from_environment(cls) -> Configuration:
        """Build from ``SYNTITUDE_*`` variables. Raises on anything missing or unreadable."""
        roots: dict[str, Path] = {}
        for key in ARTIFACT_ROOT_KEYS:
            raw = os.environ.get(f"SYNTITUDE_ROOT_{key.upper()}")
            if raw:
                roots[key] = Path(raw).expanduser()
        return cls(
            database_url=_require("SYNTITUDE_DATABASE_URL"),
            artifact_roots=roots,
            deployment_profile=os.environ.get("SYNTITUDE_PROFILE", "development"),
            sql_echo=os.environ.get("SYNTITUDE_SQL_ECHO", "").lower() in {"1", "true", "yes"},
        )

    def resolve_artifact(self, root_key: str, relative_path: str) -> Path:
        """``(root_key, relative_path)`` → an absolute path, or a named failure.

        ⚠ The error names the root key AND the configured roots, because the failure this
        actually produces in practice is a profile that was never given the root at all —
        which is indistinguishable from a missing file unless the message says so.
        """
        if root_key not in self.artifact_roots:
            raise KeyError(
                f"artifact root {root_key!r} is not configured for profile "
                f"{self.deployment_profile!r} (have: {sorted(self.artifact_roots) or 'none'}). "
                f"Set SYNTITUDE_ROOT_{root_key.upper()}."
            )
        return self.artifact_roots[root_key] / relative_path
