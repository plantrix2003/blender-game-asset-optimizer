"""Static tests that do not require Blender to be installed."""
import ast
import unittest
from pathlib import Path


ADDON_FILE = (
    Path(__file__).resolve().parents[1]
    / "blender_game_asset_optimizer"
    / "__init__.py"
)


class AddonMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ADDON_FILE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_source_is_valid_python(self):
        self.assertIsNotNone(self.tree)

    def test_bl_info_declares_addon_name_and_version(self):
        info = next(
            node for node in self.tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "bl_info"
                    for target in node.targets)
        )
        metadata = ast.literal_eval(info.value)
        self.assertEqual(metadata["name"], "Game Asset Optimizer")
        self.assertEqual(metadata["version"], (0, 1, 0))

    def test_expected_operator_classes_exist(self):
        class_names = {
            node.name for node in self.tree.body if isinstance(node, ast.ClassDef)
        }
        self.assertTrue({
            "GAO_OT_report",
            "GAO_OT_apply_transforms",
            "GAO_OT_make_decimated_copy",
            "GAO_OT_export_fbx",
            "GAO_PT_panel",
        }.issubset(class_names))


if __name__ == "__main__":
    unittest.main()
