"""Two raters' exports -> labels and agreement (BE/eval/human/ingest_plan_pairs.py)."""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from BE.eval.human import ingest_plan_pairs as ing  # noqa: E402


def key_pair(rid, first, second, a_is_first):
    f, s = f"{rid}/{first}", f"{rid}/{second}"
    return {"request_id": rid, "first": f, "second": s, "A": f if a_is_first else s, "B": s if a_is_first else f,
            "variants": {f: first, s: second}}


KEY = {"schema": "plan-pairs-v1-key", "dataset": "plan-pairs-v1-test", "label_convention": "+1 = first",
       "pairs": {"P001": key_pair("r1", "savings", "balanced", True),
                 "P002": key_pair("r2", "savings", "experience", False),
                 "P003": key_pair("r3", "balanced", "experience", True),
                 "P004": key_pair("r4", "savings", "balanced", False)}}


def export(rater, answers, dataset="plan-pairs-v1-test"):
    return {"schema": "plan-pairs-ratings-v1", "dataset": dataset, "rater": rater,
            "answers": {pid: {"tags": {"A": [], "B": []}, "comment": "", "secs": 40, "at": "2026-11-25T10:00:00Z", **a}
                        for pid, a in answers.items()}}


class TestSides(unittest.TestCase):
    def test_side_label_both_orientations(self):
        p1, p2 = KEY["pairs"]["P001"], KEY["pairs"]["P002"]       # P001 shows first as A, P002 as B
        self.assertEqual([ing.side_label(c, p1) for c in ("A", "B", "tie", None)], [1, -1, 0, None])
        self.assertEqual([ing.side_label(c, p2) for c in ("A", "B", "tie")], [-1, 1, 0])

    def test_tags_follow_the_plan(self):
        p2 = KEY["pairs"]["P002"]
        self.assertEqual(ing.side_tags({"A": ["travel"], "B": ["wish"]}, p2), {"first": ["wish"], "second": ["travel"]})
        self.assertEqual(ing.side_tags(None, p2), {"first": [], "second": []})


class TestStatistics(unittest.TestCase):
    def test_cohen_kappa_textbook(self):
        # 50 items, yes/yes 20, yes/no 5, no/yes 10, no/no 15: po 0.7, pe 0.5, kappa 0.4
        x = [1] * 20 + [1] * 5 + [-1] * 10 + [-1] * 15
        y = [1] * 20 + [-1] * 5 + [1] * 10 + [-1] * 15
        self.assertAlmostEqual(ing.cohen_kappa(x, y), 0.4)
        self.assertAlmostEqual(ing.cohen_kappa([1, 0, -1, 1], [1, 0, -1, 1]), 1.0)
        self.assertIsNone(ing.cohen_kappa([1, 1], [1, 1]))        # one category only: undefined
        self.assertIsNone(ing.cohen_kappa([], []))
        self.assertLess(ing.cohen_kappa([1, -1, 1, -1], [-1, 1, -1, 1]), 0)

    def test_wilson_matches_the_planned_sample_sizes(self):
        # 70% agreement: about +-16 points on 30 pairs, +-9 on 100, +-6 on 200
        half = {n: (lambda lo_hi: (lo_hi[1] - lo_hi[0]) / 2)(ing.wilson(round(0.7 * n), n)) for n in (30, 100, 200)}
        self.assertAlmostEqual(half[30], 0.156, places=3)
        self.assertAlmostEqual(half[100], 0.088, places=3)
        self.assertAlmostEqual(half[200], 0.063, places=3)
        self.assertIsNone(ing.wilson(0, 0))
        self.assertAlmostEqual(ing.wilson(0, 10)[0], 0.0)

    def test_agreement_counts(self):
        a = ing.agreement({"p1": 1, "p2": -1, "p3": 0, "p4": 1, "only": 1}, {"p1": 1, "p2": 1, "p3": 0, "p4": 0})
        self.assertEqual((a["n"], a["agree"], a["decisive_n"], a["decisive_agree"], a["opposite"]), (4, 2, 2, 1, 1))
        self.assertEqual(a["pct"], 0.5)
        self.assertEqual(a["confusion"], {"-1|1": 1, "0|0": 1, "1|0": 1, "1|1": 1})


class TestIngest(unittest.TestCase):
    def test_merge_map_and_consensus(self):
        an_old = export("an", {"P001": {"choice": "B", "at": "2026-11-25T09:00:00Z"}})
        an = export("an", {"P001": {"choice": "A", "tags": {"A": ["wish"], "B": ["travel"]}},
                           "P002": {"choice": "A"}, "P003": {"choice": "tie"}, "P004": {"choice": None}})
        binh = export("binh", {"P001": {"choice": "A"}, "P002": {"choice": "B", "comment": "B đỡ mệt"},
                               "P003": {"choice": "tie"}})
        result = ing.ingest(KEY, [an, an_old, binh])
        pairs = {p["pair_id"]: p for p in result["pairs"]}
        self.assertEqual(sorted(pairs), ["P001", "P002", "P003"])                  # P004 has no choice
        self.assertEqual(pairs["P001"]["labels"], {"an": 1, "binh": 1})           # the later export won
        self.assertEqual(pairs["P001"]["label"], 1)
        self.assertEqual(pairs["P001"]["tags"]["an"], {"first": ["wish"], "second": ["travel"]})
        self.assertEqual(pairs["P002"]["labels"], {"an": -1, "binh": 1})          # A is the second plan here
        self.assertIsNone(pairs["P002"]["label"])
        self.assertEqual(pairs["P002"]["comments"], {"binh": "B đỡ mệt"})
        self.assertEqual((pairs["P002"]["first_id"], pairs["P002"]["first_variant"]), ("r2/savings", "savings"))
        self.assertEqual(pairs["P003"]["label"], 0)
        rep = result["report"]
        both = rep["pairs_of_raters"]["an|binh"]
        self.assertEqual((both["n"], both["agree"], both["opposite"]), (3, 2, 1))
        self.assertEqual(rep["consensus_n"], 2)
        self.assertEqual(rep["raters"]["an"]["A"], 2)
        self.assertEqual(rep["wins"]["consensus"], {"balanced|experience": {"first": 0, "tie": 1, "second": 0},
                                                    "savings|balanced": {"first": 1, "tie": 0, "second": 0}})
        self.assertEqual(rep["tags"], {"preferred": {"wish": 1}, "other": {"travel": 1}})
        self.assertIn("kappa", ing.format_report(result))

    def test_other_dataset_is_refused(self):
        with self.assertRaises(ing.IngestError):
            ing.ingest(KEY, [export("an", {"P001": {"choice": "A"}}, dataset="plan-pairs-v1-other")])
        with self.assertRaises(ing.IngestError):
            ing.check_export({"schema": "review_v21", "answers": {}}, KEY["dataset"], "x.json")

    def test_unknown_pairs_are_counted(self):
        result = ing.ingest(KEY, [export("an", {"P001": {"choice": "A"}, "P999": {"choice": "A"}})])
        self.assertEqual(result["report"]["unknown_pairs"], {"an": 1})
        self.assertEqual([p["pair_id"] for p in result["pairs"]], ["P001"])


class TestLlmLabels(unittest.TestCase):
    def test_every_record_form(self):
        records = [
            {"pair_id": "P001", "choice": "A"},                                         # first shown as A: +1
            {"pair_id": "P002", "winner": "a"},                                         # A is second: -1
            {"pair_id": "P003", "label": -1},                                           # canonical already
            {"first_id": "r4/balanced", "second_id": "r4/savings", "label": 1},        # PATM, reversed
            {"pair_id": "P009", "choice": "A"},                                         # not in the key
            {"pair_id": "P001", "first_id": "r1/x", "second_id": "r1/y", "label": 1},  # ids do not match
            {"pair_id": "P003", "choice": "maybe"},
        ]
        labels, skipped = ing.llm_labels(records, KEY["pairs"])
        self.assertEqual(labels, {"P001": 1, "P002": -1, "P003": -1, "P004": -1})
        self.assertEqual(skipped, {"pair not in the key": 1, "plan ids do not match the key": 1,
                                   "unreadable choice": 1})

    def test_repeated_judgements_take_the_majority(self):
        labels, skipped = ing.llm_labels([{"pair_id": "P001", "choice": "A"}, {"pair_id": "P001", "choice": "B"},
                                          {"pair_id": "P001", "choice": "A"}, {"pair_id": "P002", "choice": "A"},
                                          {"pair_id": "P002", "choice": "B"}], KEY["pairs"])
        self.assertEqual(labels, {"P001": 1, "P002": 0})
        self.assertEqual(skipped["inconsistent pairs (kept, majority)"], 2)

    def test_read_records_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            lines, wrapped = Path(tmp, "a.jsonl"), Path(tmp, "b.json")
            lines.write_text('{"pair_id": "P001", "choice": "A"}\n\n{"pair_id": "P002", "choice": "tie"}\n', "utf-8")
            wrapped.write_text(json.dumps({"labels": [{"pair_id": "P001", "label": 1}]}), "utf-8")
            self.assertEqual(len(ing.read_records(lines)), 2)
            self.assertEqual(ing.read_records(wrapped), [{"pair_id": "P001", "label": 1}])

    def test_judge_in_the_report(self):
        an = export("an", {"P001": {"choice": "A"}, "P002": {"choice": "A"}, "P003": {"choice": "B"}})
        binh = export("binh", {"P001": {"choice": "A"}, "P002": {"choice": "A"}, "P003": {"choice": "A"}})
        judge = [{"pair_id": "P001", "choice": "B"}, {"pair_id": "P002", "choice": "A"}]
        rep = ing.ingest(KEY, [an, binh], {"llm": judge})["report"]["judges"]["llm"]
        self.assertEqual(rep["labelled"], 2)
        self.assertEqual((rep["vs"]["an"]["n"], rep["vs"]["an"]["agree"]), (2, 1))
        self.assertEqual((rep["vs"]["consensus"]["n"], rep["vs"]["consensus"]["agree"]), (2, 1))
        self.assertEqual(rep["wins"]["savings|balanced"], {"first": 0, "tie": 0, "second": 1})


class TestCommand(unittest.TestCase):
    def test_writes_only_with_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "key.json").write_text(json.dumps(KEY), "utf-8")
            (tmp / "an.json").write_text(json.dumps(export("an", {"P001": {"choice": "A"}})), "utf-8")
            (tmp / "binh.json").write_text(json.dumps(export("binh", {"P001": {"choice": "tie"}})), "utf-8")
            args = [str(tmp / "an.json"), str(tmp / "binh.json"), "--key", str(tmp / "key.json")]
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(ing.main(args), 0)
            self.assertIn("an và binh cùng chấm", out.getvalue())
            self.assertEqual(sorted(p.name for p in tmp.iterdir()), ["an.json", "binh.json", "key.json"])
            with redirect_stdout(io.StringIO()):
                self.assertEqual(ing.main(args + ["--out", str(tmp / "labels.json")]), 0)
            labels = json.loads((tmp / "labels.json").read_text("utf-8"))
            self.assertEqual((labels["schema"], labels["pairs"][0]["labels"]), ("plan-pairs-v1-labels", {"an": 1, "binh": 0}))
            (tmp / "other.json").write_text(json.dumps(export("c", {}, dataset="x")), "utf-8")
            with redirect_stdout(io.StringIO()), mock.patch("sys.stderr", io.StringIO()):
                self.assertEqual(ing.main([str(tmp / "other.json"), "--key", str(tmp / "key.json")]), 2)


if __name__ == "__main__":
    unittest.main()
