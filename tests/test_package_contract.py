"""Repository-level contracts for the Fusion add-in.

These checks intentionally parse source without importing Autodesk's `adsk`
module. They cannot validate ShapeManager Booleans, native feature creation,
timeline editability, or live Fusion command behavior.
"""

import ast
import json
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ADDIN = REPO_ROOT / "GeometryAssist"
SOURCE = ADDIN / "GeometryAssist.py"
MANIFEST = ADDIN / "GeometryAssist.manifest"
SETTINGS = ADDIN / "settings.json"
RESOURCES = ADDIN / "Resources"

# Public Fusion command IDs are compatibility-sensitive. Refactoring these
# requires an explicit migration decision, not a casual tidy-up.
STABLE_COMMAND_IDS = {
    "SELECT_COMMAND_ID": "JZ_SelectSimilarEdges",
    "SMART_SELECT_COMMAND_ID": "JZ_SmartSelect",
    "FACE_REGION_COMMAND_ID": "JZ_FaceRegionSelect",
    "FEATURE_RECOGNITION_COMMAND_ID": "JZ_FeatureRecognition",
    "FEATURE_REBUILD_COMMAND_ID": "JZ_FeatureRebuild",
    "MOVE_REGION_COMMAND_ID": "JZ_MoveRegion",
    "OFFSET_REGION_COMMAND_ID": "JZ_OffsetRegion",
    "DELETE_HEAL_COMMAND_ID": "JZ_DeleteHealRegion",
    "FILLET_COMMAND_ID": "JZ_SmartFilletSimilar",
    "CHAMFER_COMMAND_ID": "JZ_SmartChamferSimilar",
    "SETTINGS_COMMAND_ID": "JZ_SmartSelectionSettings",
    "DIAGNOSTICS_COMMAND_ID": "JZ_FeatureRebuildDiagnostics",
    "GEOMETRY_ASSIST_MENU_ID": "JZ_GeometryAssistMenu",
}

# These names mark the existing rebuild/rollback architecture. This is not
# proof that those paths work on every model: see docs/REGRESSION_MATRIX.md.
REBUILD_ENTRY_POINTS = {
    "_intersecting_group_rebuild_analysis",
    "_prepare_intersecting_group_stock_transient",
    "_create_native_intersecting_cut_group",
    "_rebuild_intersecting_cylindrical_group",
    "_make_independent_rebuild_copy",
    "_geometry_match_result",
    "_discard_rebuild_occurrence",
}


class PackageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_text = SOURCE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source_text, filename=str(SOURCE))
        cls.assignments = {}
        cls.functions = set()
        for statement in cls.tree.body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                cls.functions.add(statement.name)
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        cls.assignments[target.id] = statement.value

    def test_required_package_files_exist(self):
        for path in (SOURCE, MANIFEST, SETTINGS, ADDIN / "README.md"):
            with self.subTest(path=path.relative_to(REPO_ROOT)):
                self.assertTrue(path.is_file())

    def test_manifest_and_source_versions_agree(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["autodeskProduct"], "Fusion360")
        self.assertEqual(manifest["type"], "addin")
        self.assertTrue(manifest["runOnStartup"])
        self.assertEqual(manifest["supportedOS"], "windows|mac")
        version = manifest["version"]
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        self.assertIn("Geometry Assist v" + version, ast.get_docstring(self.tree) or "")
        self.assertIn("Geometry Assist v" + version,
                      (ADDIN / "README.md").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["id"].split("-")), 5)

    def test_fusion_source_compiles_without_importing_adsk(self):
        # Compiling does not execute APP = adsk.core.Application.get().
        compile(self.source_text, str(SOURCE), "exec")

    def test_settings_keys_and_types_match_defaults(self):
        defaults = ast.literal_eval(self.assignments["DEFAULT_SETTINGS"])
        shipped = json.loads(SETTINGS.read_text(encoding="utf-8"))
        self.assertEqual(set(defaults), set(shipped))
        for key, expected in defaults.items():
            with self.subTest(setting=key):
                self.assertIs(type(shipped[key]), type(expected))

    def test_fusion_command_ids_remain_stable(self):
        for variable, expected in STABLE_COMMAND_IDS.items():
            with self.subTest(command=variable):
                self.assertEqual(ast.literal_eval(self.assignments[variable]), expected)
        actual_ids = list(STABLE_COMMAND_IDS.values())
        self.assertEqual(len(actual_ids), len(set(actual_ids)))

    def test_all_declared_toolbar_resource_folders_have_both_icons(self):
        mapped = {}
        for variable, value in self.assignments.items():
            if not variable.endswith("RESOURCE_DIR"):
                continue
            if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Attribute):
                continue
            if value.func.attr != "join" or len(value.args) != 2:
                continue
            if not isinstance(value.args[0], ast.Name) or value.args[0].id != "RESOURCE_ROOT":
                continue
            mapped[variable] = ast.literal_eval(value.args[1])
        self.assertGreaterEqual(len(mapped), 10)
        for variable, folder in mapped.items():
            for icon_name in ("16x16.svg", "32x32.svg"):
                path = RESOURCES / folder / icon_name
                with self.subTest(mapping=variable, icon=icon_name):
                    self.assertTrue(path.is_file(), str(path))
                    root = ET.parse(path).getroot()
                    self.assertEqual(root.tag.split("}")[-1], "svg")
        # Catch lost assets that no longer correspond to an active mapping.
        self.assertEqual({p.name for p in RESOURCES.iterdir() if p.is_dir()},
                         set(mapped.values()))

    def test_rebuild_safety_entry_points_are_still_present(self):
        self.assertFalse(REBUILD_ENTRY_POINTS - self.functions,
                         "Missing rebuild/validation/rollback entry points: "
                         + repr(sorted(REBUILD_ENTRY_POINTS - self.functions)))

    def test_diagnostic_artifacts_are_ignored(self):
        ignores = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("GeometryAssist-last-rebuild-failure.txt", ignores)
        self.assertIn("__pycache__/", ignores)
        self.assertIn("*.py[cod]", ignores)

    def test_handoff_and_manual_regression_matrix_exist(self):
        self.assertTrue((REPO_ROOT / "docs" / "HANDOFF.md").is_file())
        self.assertTrue((REPO_ROOT / "docs" / "REGRESSION_MATRIX.md").is_file())


if __name__ == "__main__":
    unittest.main()
