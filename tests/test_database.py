from __future__ import annotations

import tempfile
import unittest
import importlib.util
from pathlib import Path

module_path = Path(__file__).parents[1] / "mcp_servers" / "database-mcp" / "app" / "database.py"
module_spec = importlib.util.spec_from_file_location("database_service", module_path)
database_module = importlib.util.module_from_spec(module_spec)
assert module_spec and module_spec.loader
module_spec.loader.exec_module(database_module)
DatabaseService = database_module.DatabaseService
DatabaseValidationError = database_module.DatabaseValidationError


class DatabaseServiceTests(unittest.TestCase):
    def test_crud_and_schema_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = DatabaseService(Path(temp_dir) / "assistant.db")
            record_id = service.create_record("tasks", {"title": "Prepare demo"})
            self.assertEqual(
                service.get_records("tasks", ["id", "title"], {"id": str(record_id)}, 10)[0]["title"],
                "Prepare demo",
            )
            self.assertEqual(service.update_records("tasks", {"status": "done"}, {"id": str(record_id)}), 1)
            self.assertEqual(service.delete_records("tasks", {"id": str(record_id)}), 1)
            with self.assertRaises(DatabaseValidationError):
                service.get_records("tasks", ["missing"], {}, 10)


if __name__ == "__main__":
    unittest.main()
