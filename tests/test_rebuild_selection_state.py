"""Adsk-free selection reducer tests using the actual Fusion state-class source.

Mocks approximate selectionInput and additionalEntities behavior; Fusion still
must verify the real event order and native UI interactions.
"""
import ast
import types
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "GeometryAssist" / "GeometryAssist.py"


class Face:
    def __init__(self, body, token, group):
        self.body = body
        self.entityToken = token
        self.tempId = hash(token)
        self.group = group


class SelectionInput:
    def __init__(self, faces=()):
        self.faces = list(faces)

    @property
    def selectionCount(self):
        return len(self.faces)

    def selection(self, index):
        return types.SimpleNamespace(entity=self.faces[index])

    def clearSelection(self):
        self.faces.clear()

    def addSelection(self, face):
        self.faces.append(face)
        return True


def load_state_class():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    node = next(n for n in tree.body
                if isinstance(n, ast.ClassDef) and n.name == "_FeatureRebuildState")
    code = compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec")
    adsk = types.SimpleNamespace(
        fusion=types.SimpleNamespace(
            BRepFace=types.SimpleNamespace(cast=lambda value: value)
        )
    )
    environment = {
        "_load_settings": lambda: {},
        "_face_live_key": lambda face: (face.body.entityToken, face.tempId),
        "adsk": adsk,
    }
    exec(code, environment)
    return environment["_FeatureRebuildState"]


class SelectionReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.body = types.SimpleNamespace(entityToken="original-body")
        self.hole_a = Face(self.body, "a", "hole-a")
        self.shoulder_a = Face(self.body, "a-shoulder", "hole-a")
        self.hole_b = Face(self.body, "b", "hole-b")
        self.floor_b = Face(self.body, "b-floor", "hole-b")
        self.second_face_b = Face(self.body, "b-second", "hole-b")
        self.families = {
            "hole-a": [self.hole_a, self.shoulder_a],
            "hole-b": [self.hole_b, self.floor_b, self.second_face_b],
        }
        state_class = load_state_class()
        self.selection_input = SelectionInput()
        self.state = state_class(None, self.selection_input, None, None)
        self.state.analyze_face = lambda face: (
            {"valid": True}, self.families[face.group], face.entityToken
        )

    def test_preview_faces_collapse_to_one_seed(self):
        self.selection_input.faces = [self.hole_a, self.shoulder_a]
        self.state.pending_face = self.hole_a
        self.state.reconcile_visible_selection()
        self.assertEqual(self.selection_input.faces, [self.hole_a])
        self.assertEqual(self.state.seed_faces, [self.hole_a])

    def test_second_independent_seed_is_retained(self):
        self.selection_input.faces = [self.hole_a, self.shoulder_a]
        self.state.pending_face = self.hole_a
        self.state.reconcile_visible_selection()
        self.selection_input.faces += [self.hole_b, self.floor_b]
        self.state.pending_face = self.hole_b
        self.state.reconcile_visible_selection()
        self.assertEqual(self.state.seed_faces, [self.hole_a, self.hole_b])
        self.assertEqual(self.selection_input.faces, [self.hole_a, self.hole_b])

    def test_ctrl_deselect_removes_only_one_target(self):
        self.selection_input.faces = [self.hole_a, self.shoulder_a]
        self.state.pending_face = self.hole_a
        self.state.reconcile_visible_selection()
        self.selection_input.faces += [self.hole_b, self.floor_b]
        self.state.pending_face = self.hole_b
        self.state.reconcile_visible_selection()
        self.selection_input.faces = [self.hole_b]
        self.state.reconcile_visible_selection()
        self.assertEqual(self.state.seed_faces, [self.hole_b])

    def test_second_face_of_same_feature_does_not_duplicate_target(self):
        self.selection_input.faces = [self.hole_b, self.floor_b]
        self.state.pending_face = self.hole_b
        self.state.reconcile_visible_selection()
        self.selection_input.faces += [self.second_face_b]
        self.state.pending_face = self.second_face_b
        self.state.reconcile_visible_selection()
        self.assertEqual(self.state.seed_faces, [self.hole_b])
        self.assertEqual(self.selection_input.faces, [self.hole_b])

    def test_multiple_preselected_features_are_imported(self):
        self.selection_input.faces = [
            self.shoulder_a, self.hole_a, self.hole_b, self.floor_b
        ]
        # Planar preview families are unsupported as independent seed inputs.
        def analyze(face):
            if face is self.shoulder_a or face is self.floor_b:
                return {"valid": False}, [], None
            return {"valid": True}, self.families[face.group], face.entityToken
        self.state.analyze_face = analyze
        self.state.reconcile_visible_selection()
        self.assertEqual(self.state.seed_faces, [self.hole_a, self.hole_b])


if __name__ == "__main__":
    unittest.main()
