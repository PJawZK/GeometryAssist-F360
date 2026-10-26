"""Offline selection-state tests against the production Fusion class AST.

These tests use a fake SelectionCommandInput. They verify data flow and
API lifecycle boundaries, NOT live Fusion UI behavior.
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
        self.clear_calls = 0
        self.add_calls = 0

    @property
    def selectionCount(self):
        return len(self.faces)

    def selection(self, index):
        return types.SimpleNamespace(entity=self.faces[index])

    def clearSelection(self):
        self.clear_calls += 1
        self.faces.clear()

    def addSelection(self, face):
        self.add_calls += 1
        self.faces.append(face)
        return True


def read_class(name):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    return next(n for n in tree.body
                if isinstance(n, ast.ClassDef) and n.name == name)


def load_state_class():
    node = read_class("_FeatureRebuildState")
    code = compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec")
    adsk = types.SimpleNamespace(
        fusion=types.SimpleNamespace(BRepFace=types.SimpleNamespace(cast=lambda value: value))
    )
    environment = {
        "_load_settings": lambda: {},
        "_face_live_key": lambda face: (face.body.entityToken, face.tempId),
        "adsk": adsk,
    }
    exec(code, environment)
    return environment["_FeatureRebuildState"]


class MultiSelectionTests(unittest.TestCase):
    def setUp(self):
        self.body = types.SimpleNamespace(entityToken="source")
        self.a = Face(self.body, "a", "A")
        self.a_shoulder = Face(self.body, "a-shoulder", "A")
        self.b = Face(self.body, "b", "B")
        self.b_second = Face(self.body, "b-second", "B")
        self.unrelated = Face(self.body, "unrelated", "none")
        self.families = {"A": [self.a, self.a_shoulder], "B": [self.b, self.b_second]}
        self.selection = SelectionInput()
        self.mode = types.SimpleNamespace(value=True)
        self.info = types.SimpleNamespace(text="")
        self.state = load_state_class()(None, self.selection, self.info, None, self.mode)

        def analyze(face):
            if face is self.unrelated or face is self.a_shoulder:
                return {"valid": False}, [], None
            return {"valid": True, "title": face.group}, self.families[face.group], face.entityToken

        self.state.analyze_face = analyze

    def test_two_live_selections_produce_two_targets_without_rewriting_input(self):
        self.selection.faces = [self.a, self.b]
        self.assertEqual(len(self.state.current_analyses()), 2)
        self.assertEqual(self.selection.faces, [self.a, self.b])
        self.assertEqual(self.selection.clear_calls, 0)
        self.assertEqual(self.selection.add_calls, 0)

    def test_ctrl_deselect_is_immediately_authoritative(self):
        self.selection.faces = [self.a, self.b]
        self.assertEqual(len(self.state.current_analyses()), 2)
        self.selection.faces.remove(self.a)
        self.assertEqual([a["title"] for a in self.state.current_analyses()], ["B"])
        self.assertEqual(self.selection.clear_calls, 0)

    def test_second_face_of_same_recognized_feature_counts_once(self):
        self.selection.faces = [self.a, self.b, self.b_second]
        self.assertEqual(len(self.state.current_analyses()), 2)
        self.assertEqual(self.selection.selectionCount, 3)

    def test_initial_normalization_runs_once_after_activation(self):
        # Inherited Fusion selections may contain preview shoulders/floors.
        self.selection.faces = [self.a_shoulder, self.a, self.b, self.b_second]
        self.state.show_current_selection = lambda: None
        self.state.normalize_initial_selection()
        self.assertEqual(self.selection.faces, [self.a, self.b])
        self.assertEqual(self.selection.clear_calls, 1)
        self.assertEqual(self.selection.add_calls, 2)
        # Subsequent activation (e.g. returning from Pan/Orbit) must not
        # restore already Ctrl-deselected items.
        self.selection.faces = [self.b]
        self.state.normalize_initial_selection()
        self.assertEqual(self.selection.faces, [self.b])

    def test_unrecognized_only_selection_cannot_be_a_valid_target(self):
        self.selection.faces = [self.unrelated]
        self.assertEqual(self.state.current_analyses(), [])

    def test_legacy_single_mode_keeps_pruned_group_preview(self):
        self.mode.value = False
        self.selection.faces = [self.a, self.a_shoulder]
        self.state.pending_face = self.a
        self.state.reconcile_visible_selection()
        self.assertEqual(self.selection.faces, [self.a])
        self.assertEqual(len(self.state.current_analyses()), 1)


class FusionLifecycleContractTests(unittest.TestCase):
    def test_created_handler_does_not_mutate_selection_with_addselection(self):
        node = read_class("_FeatureRebuildCreatedHandler")
        methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
        notify = next(n for n in methods if n.name == "notify")
        calls = [n.func.attr for n in ast.walk(notify)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
        self.assertNotIn("addSelection", calls)
        self.assertNotIn("clearSelection", calls)
        self.assertIn("setSelectionLimits", calls)
        self.assertIn("add", calls)  # command.activate.add(ah)

    def test_activate_handler_initializes_selection_after_command_created(self):
        node = read_class("_FeatureRebuildActivateHandler")
        names = [n.func.attr for n in ast.walk(node)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
        self.assertIn("normalize_initial_selection", names)

    def test_multi_mode_selection_event_returns_before_adding_preview_faces(self):
        node = read_class("_FeatureRebuildSelectionHandler")
        notify = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "notify")
        source = ast.get_source_segment(SOURCE.read_text(encoding="utf-8"), notify)
        self.assertIn("if self.state.multi_mode_input.value:", source)
        self.assertIn("args.additionalEntities = additional", source)
        self.assertLess(source.index("if self.state.multi_mode_input.value:"),
                        source.index("args.additionalEntities = additional"))

    def test_manifest_identifies_new_candidate(self):
        import json
        manifest = json.loads(
            (SOURCE.parent / "GeometryAssist.manifest").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["version"], "0.14.15")


if __name__ == "__main__":
    unittest.main()
