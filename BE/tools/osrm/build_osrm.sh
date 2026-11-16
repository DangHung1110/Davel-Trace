#!/usr/bin/env bash
# Build the Da Nang MOTORBIKE OSRM graph (Phase 3). Reproducible, data outside
# the repo (*.osm.pbf / *.osrm* are gitignored and must never be committed).
#
#   BE/tools/osrm/build_osrm.sh <data_dir> [min_lon,min_lat,max_lon,max_lat]
#
# Steps: Geofabrik Vietnam extract (md5-checked) -> osmium bbox cut ->
# osrm-extract with motorbike.lua -> osrm-partition -> osrm-customize (MLD),
# then <data_dir>/osrm-meta.json records exactly what was built, for
# build_poi_matrix.py --osrm-meta. Needs: curl, python3, osmium, docker.
#
# Default bbox = every danang-v1 POI (lat 15.79-16.25, lon 107.94-108.52)
# plus ~10 km, so routes near the edge are not cut short.
set -euo pipefail

DATA="${1:?usage: build_osrm.sh <data_dir> [bbox]}"
BBOX="${2:-107.80,15.65,108.65,16.35}"
IMAGE="ghcr.io/project-osrm/osrm-backend:v5.27.1"
PBF_URL="https://download.geofabrik.de/asia/vietnam-latest.osm.pbf"
PROFILE="$(cd "$(dirname "$0")" && pwd)/motorbike.lua"

mkdir -p "$DATA"
DATA="$(cd "$DATA" && pwd)"
cd "$DATA"

md5_of() { python3 -c 'import hashlib,sys;h=hashlib.md5();f=open(sys.argv[1],"rb")
for b in iter(lambda:f.read(1<<20),b""): h.update(b)
print(h.hexdigest())' "$1"; }

if [ ! -f vietnam-latest.osm.pbf ]; then
  curl -fL -o vietnam-latest.osm.pbf "$PBF_URL"
fi
EXPECTED="$(curl -fsS "$PBF_URL.md5" | cut -d' ' -f1)"
ACTUAL="$(md5_of vietnam-latest.osm.pbf)"
if [ "$EXPECTED" != "$ACTUAL" ]; then
  echo "md5 mismatch: local $ACTUAL != Geofabrik $EXPECTED (stale or corrupt;" \
       "delete vietnam-latest.osm.pbf and rerun)" >&2
  exit 1
fi

osmium extract -b "$BBOX" -s complete_ways --overwrite \
  -o danang.osm.pbf vietnam-latest.osm.pbf

# The profile runs from /opt so `require('lib/...')` resolves to the libs of
# the SAME OSRM release it was derived from.
docker run --rm -v "$DATA:/data" -v "$PROFILE:/opt/motorbike.lua:ro" "$IMAGE" \
  osrm-extract -p /opt/motorbike.lua /data/danang.osm.pbf
docker run --rm -v "$DATA:/data" "$IMAGE" osrm-partition /data/danang.osrm
docker run --rm -v "$DATA:/data" "$IMAGE" osrm-customize /data/danang.osrm

OSM_TS="$(osmium fileinfo -g header.option.timestamp vietnam-latest.osm.pbf)"
PROFILE_SHA="$(shasum -a 256 "$PROFILE" | cut -d' ' -f1)"
python3 - "$IMAGE" "$BBOX" "$ACTUAL" "$OSM_TS" "$PROFILE_SHA" <<'PY'
import json, sys
from datetime import datetime, timezone
image, bbox, md5, osm_ts, profile_sha = sys.argv[1:6]
meta = {
    "mode": "motorbike",
    "osrm_image": image,
    "algorithm": "mld",
    "profile": "BE/tools/osrm/motorbike.lua",
    "profile_sha256": profile_sha,
    "extract": "vietnam-latest.osm.pbf (Geofabrik)",
    "extract_md5": md5,
    "osm_timestamp": osm_ts,
    "bbox": [float(v) for v in bbox.split(",")],
    "graph_built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
}
with open("osrm-meta.json", "w", encoding="utf-8") as f:
    json.dump(meta, f, indent=1)
print(json.dumps(meta, indent=1))
PY

# macOS: AirPlay Receiver listens on *:5000, so OSRM_PORT=5001 there.
PORT="${OSRM_PORT:-5000}"
cat <<EOF
built $DATA/danang.osrm. Serve it (max-table-size covers 742 x 742 in one go):
  docker run -d --name osrm-motorbike -p 127.0.0.1:$PORT:5000 -v "$DATA:/data" \\
    $IMAGE osrm-routed --algorithm mld --max-table-size 1000 /data/danang.osrm
EOF
