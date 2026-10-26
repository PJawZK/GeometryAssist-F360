"""Offline, adsk-free tests for the multi-target preflight planner.

The planner is extracted from the production source AST so these cases exercise
the actual function body without running any Autodesk Fusion API calls. These
checks do not certify native reconstruction or Fusion selection events.
"""
import ast
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "GeometryAssist" / "GeometryAssist.py"


class SourceBody:
    def __init__(self, name):
        self.entityToken = "test-body:" + name


def analysis(body, *, tokens=("face-1",), valid=True, kind=None, reason=None):
    result = {
        "valid": valid,
        "source_body": body,
        "feature_tokens": tokens,
        "rebuild_kind": kind,
    }
    if reason:
        result["reason"] = reason
    return result


def load_production_planner():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    function = next(n for n in tree.body
                    if isinstance(n, ast.FunctionDef)
                    and n.name == "_feature_rebuild_batch_plan")
    code = compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), "exec")
    environment = {"_native_body": lambda obj: obj}
    exec(code, environment)
    return environment["_feature_rebuild_batch_plan"]


class RebuildBatchPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = staticmethod(load_production_planner())

    def test_no_selection_fails(self):
        self.assertFalse(self.plan([])["valid"])

    def test_one_recognized_hole_keeps_single_path(self):
        result = self.plan([analysis(SourceBody("a"))])
        self.assertTrue(result["valid"])
        self.assertEqual(result["groups"][0]["mode"], "single")

    def test_disjoint_same_body_holes_use_one_reconstruction(self):
        body = SourceBody("a")
        result = self.plan([analysis(body, tokens=("a", "b")),
                            analysis(body, tokens=("c", "d"))])
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["groups"]), 1)
        self.assertEqual(result["groups"][0]["mode"], "sequential_native_holes")
        self.assertEqual(result["target_count"], 2)

    def test_separate_bodies_remain_independent(self):
        result = self.plan([analysis(SourceBody("a")), analysis(SourceBody("b"))])
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["groups"]), 2)
        self.assertTrue(all(g["mode"] == "single" for g in result["groups"]))

    def test_same_group_twice_is_rejected_if_faces_overlap(self):
        body = SourceBody("a")
        result = self.plan([analysis(body, tokens=("a", "b")),
                            analysis(body, tokens=("b", "c"))])
        self.assertFalse(result["valid"])
        self.assertIn("overlapping", result["reason"])

    def test_missing_membership_cannot_be_batched(self):
        body = SourceBody("a")
        result = self.plan([analysis(body, tokens=()),
                            analysis(body, tokens=("a",))])
        self.assertFalse(result["valid"])

    def test_intersecting_cut_group_is_atomic_on_same_body(self):
        body = SourceBody("a")
        result = self.plan([
            analysis(body, kind="intersecting_cylindrical_group"),
            analysis(body, tokens=("hole",)),
        ])
        self.assertFalse(result["valid"])
        self.assertIn("not yet validated", result["reason"])

    def test_group_on_different_body_is_allowed(self):
        result = self.plan([
            analysis(SourceBody("a"), kind="intersecting_cylindrical_group"),
            analysis(SourceBody("b"), tokens=("hole",)),
        ])
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["groups"]), 2)

    def test_invalid_target_prevents_any_execution(self):
        result = self.plan([
            analysis(SourceBody("a")),
            analysis(SourceBody("b"), valid=False, reason="Unsupported cut"),
        ])
        self.assertFalse(result["valid"])
        self.assertIn("Target 2", result["reason"])

    def test_aliases_to_same_entity_token_use_one_body_group(self):
        first, second = SourceBody("a"), SourceBody("a")
        result = self.plan([analysis(first, tokens=("a",)),
                            analysis(second, tokens=("b",))])
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["groups"]), 1)


if __name__ == "__main__":
    unittest.main()
