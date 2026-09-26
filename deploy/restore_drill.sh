#!/usr/bin/env bash
# The restore drill — the S3 exit criterion, as one command the owner runs unaided.
#
#   deploy/restore_drill.sh --yes-delete-the-database
#
# It DELETES the running database volume, restores it from the dump, times that, then checks the
# stack end to end THROUGH THE PUBLISHED PORT — the path a reader's browser takes — and prints one
# PASS/FAIL line per check and a summary. Exit status 0 means every check passed.
#
# ⛔ Destructive by design: `docker compose down -v` is how a new dump is loaded (the postgres image
# restores only into an EMPTY volume), so the drill IS the upgrade procedure. It refuses to run
# without the flag above, and it refuses before deleting anything if the dump is missing — a drill
# that deletes the live database and then finds no dump has made an outage out of a rehearsal.
#
# Needs: Docker Engine 25+ with Compose v2, curl, and `.env` beside compose.yaml (see .env.example).
# ⚠ Nothing else on the host — no Python: JSON is read with the api container's own interpreter.
set -Eeuo pipefail

cd "$(dirname "$0")/.."

if [ "${1:-}" != "--yes-delete-the-database" ]; then
  echo "usage: deploy/restore_drill.sh --yes-delete-the-database"
  echo "  deletes the database volume, restores it from the dump, and checks the stack end to end."
  exit 2
fi

failures=0
pass() { printf '  PASS  %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1"; failures=$((failures + 1)); }

# ── preflight: nothing is deleted until all of this holds ─────────────────────────────────────────
[ -f .env ] || { echo "no .env beside compose.yaml — copy .env.example and fill it in"; exit 2; }
set -a; . ./.env; set +a
dump_dir="${BACATLAS_HOST_DUMP_DIR:-./deploy/dump}"
dump="$dump_dir/bacatlas.dump"
[ -f "$dump" ] || { echo "no dump at $dump — refusing to delete a database it cannot replace"; exit 2; }
command -v curl >/dev/null || { echo "curl is required"; exit 2; }
docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 is required"; exit 2; }
engine=$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo 0)
[ "${engine%%.*}" -ge 25 ] 2>/dev/null || { echo "Docker Engine 25+ is required (found $engine)"; exit 2; }

base="${BACATLAS_PUBLIC_BASE:-/}"
host="${BACATLAS_HTTP_BIND:-127.0.0.1}"
[ "$host" = "0.0.0.0" ] && host=127.0.0.1
url="http://$host:${BACATLAS_HTTP_PORT:-8080}${base}"
api="${url}api/v1"

echo "BacAtlas restore drill — $(date -u +%FT%TZ)"
checksum=$( (sha256sum "$dump" 2>/dev/null || shasum -a 256 "$dump") | cut -c1-16)
echo "  dump    $dump ($(du -h "$dump" | cut -f1), sha256 ${checksum}…)"
echo "  serves  $url"
echo "  engine  Docker $engine"
echo

# ── the drill ─────────────────────────────────────────────────────────────────────────────────────
echo "deleting the database volume and restoring from the dump…"
docker compose down -v --remove-orphans >/dev/null 2>&1
started=$(date +%s)
if docker compose up -d --wait >/dev/null 2>&1; then
  elapsed=$(( $(date +%s) - started ))
  pass "stack healthy ${elapsed} s after the volume was deleted"
else
  elapsed=$(( $(date +%s) - started ))
  fail "stack did not come up healthy (${elapsed} s) — docker compose ps; docker compose logs db"
  docker compose ps
  exit 1
fi
restore_line=$(docker compose logs db 2>/dev/null | grep -o 'restore + ANALYZE finished in [0-9]* s' | tail -1 || true)
[ -n "$restore_line" ] && pass "$restore_line (inside the db container)" || fail "no restore line in the db log — did the dump restore?"

# ── end to end, through the published port ────────────────────────────────────────────────────────
get() { curl -fsS --max-time 20 "$1"; }
status() { curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$@"; }
json() { docker compose exec -T api python -c "import json,sys; d=json.load(sys.stdin); print($1)"; }

health=$(get "$api/health" || true)
if echo "$health" | json 'd.get("schema_present") is True' 2>/dev/null | grep -q True; then
  pass "health: database reachable, schema present"
else
  fail "health: $health"
fi

species=$(get "$api/species" | json '" ".join(s["key"] for s in d["species"] if s["published"])' 2>/dev/null || true)
[ -n "$species" ] && pass "published species: $species" || fail "no published species in the restored database"

[ "$(status "$url")" = "200" ] && pass "the page itself: 200" || fail "the page itself: $(status "$url")"

for key in $species; do
  catalogue=$(get "$api/species/$key" || true)
  landing=$(echo "$catalogue" | json 'd["landing_locus"]' 2>/dev/null || true)
  loci=$(echo "$catalogue" | json 'd["pangenome"]["locus_count"]' 2>/dev/null || true)
  [ -n "$landing" ] && pass "$key: catalogue of $loci loci, landing locus $landing" || { fail "$key: no catalogue"; continue; }

  [ "$(status "$api/species/$key/loci/$landing")" = "200" ] && pass "$key: landing locus 200" \
    || fail "$key: landing locus $(status "$api/species/$key/loci/$landing")"

  digest=$(echo "$catalogue" | json '[p["scatter_sprite"]["content_digest"] for p in d["map_projections"] if p["scatter_sprite"]][0]' 2>/dev/null || true)
  rep=$(echo "$catalogue" | json '[p["representation"] for p in d["map_projections"] if p["scatter_sprite"]][0]' 2>/dev/null || true)
  if [ -n "$digest" ]; then
    sprite="$api/species/$key/map/$rep/scatter.png?v=$digest"
    [ "$(status "$sprite")" = "200" ] && pass "$key: catalogue sprite 200" || fail "$key: catalogue sprite"
    # The ETag must survive the proxy, or every map view re-downloads the picture.
    [ "$(status -H "If-None-Match: \"$digest\"" "$sprite")" = "304" ] && pass "$key: sprite revalidates (304)" \
      || fail "$key: sprite did not answer 304 to its own ETag"
  else
    fail "$key: no catalogue sprite described"
  fi

  genome=$(get "$api/species/$key/genomes?limit=1" | json 'd["genomes"][0]["sample_id"]' 2>/dev/null || true)
  [ -n "$genome" ] && pass "$key: genome list answers ($genome first)" || fail "$key: genome list"

  if [ -n "${BACATLAS_HOST_GFF_DIR:-}" ] && [ -n "$genome" ]; then
    code=$(status "$api/species/$key/genomes/$genome/loci/$landing/sequence")
    [ "$code" = "200" ] && pass "$key: sequence read from the GFF tree" \
      || fail "$key: sequence endpoint $code — is the GFF tree readable by uid 10001?"
  fi
done

echo
if [ "$failures" -eq 0 ]; then
  echo "DRILL PASSED — restored and serving in ${elapsed} s."
else
  echo "DRILL FAILED — $failures check(s) failed. The stack is left running for inspection."
  exit 1
fi
