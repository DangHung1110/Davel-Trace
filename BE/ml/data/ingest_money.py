"""Ingest money_answers.json into snapshot (lane A).

- P1 (band) yes -> band_verified=true (+note); no -> band from NOTE_BAND map.
- P3 (must-go) yes -> poi['must_go']=True; no -> False/absent.
Keys are poi_ids (unique across P1/P3 in this round).

Usage: python BE/ml/data/ingest_money.py --snapshot ... [--apply]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _REPO_ROOT) if _REPO_ROOT not in sys.path else None

# key -> (band, price_note) for v=no rows, from the user's own ranges
NOTE_BAND = {
    "ChIJN-vJNV8XQjERNccI4vX2rHY": ("medium", "user: Nén 150-300k"),
    "ChIJPYQKSAAXQjER0cga1BLD_MI": ("medium", "user: Muối Biển 100-200k, món đặc biệt 450k+, đồ uống tiền triệu"),
    "ChIJW_ilwg0XQjERQbqRXGggIFE": ("medium", "user: Cucina Luca 180-400k"),
    "ChIJYy-g38oQQjER2c931z_dDt4": ("medium", "user: Xanh 150k-1200k, vote medium"),
    "ChIJw-jjo3IXQjERjDCm-Yd0EAA": ("medium", "user: Le Comptoir từ 400k"),
    "ChIJxRB4CRgXQjER6zy0em0FyTk": ("medium", "user: Oppa Bar 200-700k"),
    "ChIJz0Od5IUXQjER_IUTHqI3gI8": ("medium", "user: My Casa từ 300k"),
    "manual:vinwonders-nam-hoi-an": ("medium", "user: VinWonders 650k, vote medium"),
}
TICKET_VND = {
    "ChIJyUQ4aw72QTERCXl5YV-4U1w": (1000000, "user: Bà Nà NL 1.000.000/NCT 800.000/TE 650-800k"),
}
BAND_KEYS = set(NOTE_BAND) | {
    "ChIJ28SKFJU9QjERBgIwBViBWD4", "ChIJ5aETx9oZQjERBE0f6BHAbyg",
    "ChIJFdFWDOQZQjERhEwTQhM7XII", "ChIJQydy2apx34oRnci64Kkdi4U",
    "ChIJdac9auQYQjERbldnY0G9R9c", "ChIJwRzh0c0ZQjERSqm3HPF_Gi4",
    "ChIJyUQ4aw72QTERCXl5YV-4U1w",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    path = os.path.join(args.snapshot, "pois.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    P = {p["poi_id"]: p for p in data["pois"]}
    ans = json.load(open(os.path.join(args.snapshot, "money_answers.json"),
                         encoding="utf-8"))
    mustgo, band_ok, band_fix, unknown = [], [], [], []
    for x in ans:
        pid, v, note = x["key"], x["v"], (x.get("note") or "").strip()
        p = P.get(pid)
        if not p:
            unknown.append(pid)
            continue
        if pid in BAND_KEYS or pid in NOTE_BAND:
            st = p.setdefault("smart_tags", {})
            if v == "yes":
                band_ok.append(pid)
                if args.apply:
                    st["band_verified"] = True
                    if note:
                        p["price_note"] = ((p.get("price_note") or "") + " | " if p.get("price_note") else "") + "user: " + note
            else:
                band_fix.append(pid)
                if args.apply and pid in NOTE_BAND:
                    st["price_band"] = NOTE_BAND[pid][0]
                    st["band_verified"] = True
                    p["price_note"] = NOTE_BAND[pid][1]
                    if pid in TICKET_VND:
                        p["ticket_vnd"] = TICKET_VND[pid][0]
                        p["ticket_note"] = TICKET_VND[pid][1]
                        st["ticket"] = True
        else:  # P3 must-go
            if v == "yes":
                mustgo.append(p["name"])
                if args.apply:
                    p["must_go"] = True
            elif args.apply:
                p.pop("must_go", None)
    print(f"band_ok={len(band_ok)} band_fix={len(band_fix)} "
          f"mustgo={len(mustgo)} unknown={unknown}")
    if args.apply:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        from BE.app.services.snapshot import load_snapshot
        load_snapshot(args.snapshot)
        print("snapshot valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
