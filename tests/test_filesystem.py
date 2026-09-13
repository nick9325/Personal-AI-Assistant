from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

module_path = Path(__file__).parents[1] / "mcp_servers" / "filesystem-mcp" / "app" / "tools.py"
module_spec = importlib.util.spec_from_file_location("filesystem_tools", module_path)
filesystem_module = importlib.util.module_from_spec(module_spec)
assert module_spec and module_spec.loader
sys.modules[module_spec.name] = filesystem_module
module_spec.loader.exec_module(filesystem_module)
FilesystemPolicy = filesystem_module.FilesystemPolicy
FilesystemPolicyError = filesystem_module.FilesystemPolicyError
FilesystemService = filesystem_module.FilesystemService


class FilesystemServiceTests(unittest.TestCase):
    def test_root_sandbox_and_text_operations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = FilesystemService(FilesystemPolicy((root,)))
            service.create_directory("project")
            (root / "project" / "main.py").write_text("print('ok')", encoding="utf-8")
            self.assertEqual(service.read("project/main.py"), "print('ok')")
            self.assertEqual(len(service.search(".", "*.py", True, 10)), 1)
            with self.assertRaises(FilesystemPolicyError):
                service.read("../outside.txt")


if __name__ == "__main__":
    unittest.main()