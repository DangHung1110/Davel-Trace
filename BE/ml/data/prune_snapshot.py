"""Prune non-tourist POIs + unify categories (lane A, stdlib only).

- REMOVALS: {substring norm-name: reason}. Matched case/diacritic-insensitive;
  --check lists poi_id + reason first, --apply deletes (git keeps history).
- TYPE_FIX: {exact name: canonical} for audit-proven mislabels.
- Adds poi["cat"] = canonical enum for every kept POI (raw type untouched).

Usage: python BE/ml/data/prune_snapshot.py --snapshot ... --check|--apply
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _REPO_ROOT) if _REPO_ROOT not in sys.path else None

from BE.ml.patm.estimate_duration import canonical_category  # noqa: E402

REMOVALS = {
    # audit verdict LOẠI
    "cua hang dien nuoc huy hien": "audit LOẠI: không phải điểm du lịch",
    # wholesale / suppliers / admin (not visitable)
    "cho dau moi thuy san tho quang": "wholesale đầu mối, không tham quan",
    "gia vi cho nha hang": "supplier, không rating, không tham quan",
    "cho hai san da nang": "supplier (Người cung cấp thực phẩm)",
    "vat tu nong nghiep hung phuong": "supplier",
    "cho vat tu": "supplier",
    "ban quan ly cho quan ngu hanh son": "văn phòng BQL, không tham quan",
    "ban quan ly cho quan lien chieu": "văn phòng BQL, không tham quan",
    "van phong chinh quyen quan": "văn phòng chính quyền",
    # services / offices / civic (not attractions)
    "dia diem to chuc le cuoi": "venue cưới (tiệc cưới dạng nhà hàng thì giữ)",
    "trung tam thong tin du lich": "quầy info, không phải điểm tham quan",
    "trung tam xuc tien du lich": "cơ quan xúc tiến, không tham quan",
    "so du lich thanh pho": "cơ quan nhà nước",
    "hiep hoi/to chuc": "tổ chức, không tham quan",
    "dai ly du lich": "phòng vé/agency, không phải điểm đến",
    "truong sa tourist": "văn phòng điều hành tour, không tham quan",
    "dai ly du lich bang thuyen": "phòng vé/agency (tour đã có POI riêng)",
    "trung tam cham soc suc khoe": "cơ sở y tế",
    "trung tam y te": "cơ sở y tế",
    "benh vien": "bệnh viện",
    "cho thue xe may": "dịch vụ thuê xe",
    "nha dat lien chieu": "bất động sản",
    "khu cong nghiep lien chieu": "khu công nghiệp",
    # addresses / vague (not identifiable places)
    "79 tran hung dao son tra": "địa chỉ, không phải địa điểm",
    "so 10, khu tdc da son": "địa chỉ dân cư",
    "lien chieu": "TÊN QUẬN — placeholder, xem dưới",
    "ho thanh khe": "không định danh du lịch rõ ràng",
    "ngoi nha nho va bai co xanh": "nhà riêng, không định danh",
    # unidentifiable / out of scope
    "pnt international airport": "sai type, sân bay",
    "aarohi media training": "không tồn tại ở ĐN",
    "thi he": "không xác định được",
    "samdi": "không xác định (có thể là khách sạn)",
    # bbox leak
    "vinwonders nha trang": "ngoài Đà Nẵng (Nha Trang)",
}

# Short/generic keys: exact-match only (avoid "Hồ Thanh Khê" eating
# "Nhà thờ Tộc Hồ Thanh Khê", "Liên Chiểu" eating real POIs in that district)
EXACT_KEYS = {"ho thanh khe", "lien chieu"}

# poi_id removals (dedup resolutions: same-name dup with no data loses)
REMOVE_IDS = {
    "ChIJ28TlBIYXQjEREqSmOo2kQtU",  # Ban Quản lí Bán đảo Sơn Trà: admin office
    "ChIJ6xruBrT3cTER3emdI1jkITQ",  # Tiêm Chủng Long Châu: vaccination clinic
    "ChIJ3c1W2AAfQjERnRKZkrt0AjA",  # chợ Hòa Liên (unknown, dup of rated one)
}
TYPE_FIX = {
    "Du Thuyền Sông Hàn Mỹ Xuân 02": "attraction",
    "Dịch Vụ Thuyền Thúng Bến Dừa": "attraction",
    "Quán Hải sản Tân Trà Beach": "restaurant",
    "Bãi Biển Thiên Đường": "beach",
    "Bãi biển Sơn Trà": "beach",
    "Trà Quán Góc Nhà Tụi Mình": "cafe",
    "CỬA HÀNG ĐIỆN NƯỚC HUY HIỀN": "market",  # removed anyway; keep map total
    "Đà Sơn tâm linh": "landmark",
    "Di tích Đình Hồng Phước": "landmark",
    "Khu Căn cứ Cách mạng K20": "landmark",
    "Bảo tàng Điêu khắc Chăm Đà Nẵng": "museum",
    "Bảo Tàng Đà Nẵng": "museum",
    "Bảo tàng Hồ Chí Minh": "museum",
    "Chợ đêm Helio - B. Night Market": "market",
    "Chợ Đêm Sơn Trà": "market",
    "Chợ Đêm An Thượng": "market",
    "DD WONDERLAND": "attraction",
    "Trung Tâm Giải Trí Helio": "attraction",
    "Sân chơi trong nhà": "attraction",
    "KHU PHỐ DU LỊCH AN THƯỢNG": "attraction",
    "Khách sạn": "lodging",
    "Khách Sạn Smile": "lodging",
    "Nhà Hàng Tiệc Cưới Đại Hỷ": "restaurant",
    "Khách sạn nghỉ dưỡng": "lodging",
    "Lưu trú nhà dân": "lodging",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")


def plan(pois: list[dict]):
    drop, fix = [], []
    for p in pois:
        if p["poi_id"] in REMOVE_IDS:
            drop.append((p["poi_id"], p["name"], "poi_id denylist (dedup)"))
            continue
        n = _norm(p.get("name", ""))
        hit = next((k for k in REMOVALS
                    if (n == k if k in EXACT_KEYS else k in n)), None)
        if hit:
            drop.append((p["poi_id"], p["name"], REMOVALS[hit]))
        elif p.get("name") in TYPE_FIX:
            fix.append((p["poi_id"], p["name"], TYPE_FIX[p["name"]]))
    return drop, fix


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    path = os.path.join(args.snapshot, "pois.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    drop, fix = plan(data["pois"])
    print(f"pois={len(data['pois'])} drop={len(drop)} typefix={len(fix)}")
    for pid, name, why in drop:
        print(f"  DROP {pid[:8]} {name} -- {why}")
    for pid, name, cat in fix:
        print(f"  FIX {pid[:8]} {name} -> {cat}")
    if args.apply:
        drop_ids = {d[0] for d in drop}
        fix_map = {d[1]: d[2] for d in fix}
        kept = []
        for p in data["pois"]:
            if p["poi_id"] in drop_ids:
                continue
            p["cat"] = fix_map.get(p["name"],
                                   canonical_category(p.get("type", "")))
            kept.append(p)
        data["pois"] = kept
        data["count"] = len(kept)
        data["pruned_at"] = "2026-10-10"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"kept {len(kept)} -> {path}")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
