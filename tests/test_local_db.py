from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from connections.local_db import LocalCollection


class LocalCollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "database.json"
        self.collection = LocalCollection(self.path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_crud_and_persistence(self):
        self.collection.insert_one({"_id": "alpha", "value": 1})
        self.assertEqual(self.collection.find_one({"_id": "alpha"})["value"], 1)

        result = self.collection.replace_one(
            {"_id": "alpha"}, {"_id": "alpha", "value": 2}, upsert=True
        )
        self.assertEqual(result.matched_count, 1)
        self.assertEqual(LocalCollection(self.path).find_one({"_id": "alpha"})["value"], 2)

        deleted = self.collection.delete_one({"_id": "alpha"})
        self.assertEqual(deleted.deleted_count, 1)
        self.assertIsNone(self.collection.find_one({"_id": "alpha"}))

    def test_queries_projection_and_update(self):
        self.collection.insert_one({"_id": "a", "group": "x", "score": 10})
        self.collection.insert_one({"_id": "b", "group": "y", "score": 20})
        self.collection.insert_one({"_id": "c", "group": "x", "score": 30})

        rows = self.collection.find({"group": "x", "score": {"$gte": 20}}, {"_id": 1})
        self.assertEqual(rows, [{"_id": "c"}])

        self.collection.update_one({"_id": "a"}, {"$inc": {"score": 5}, "$set": {"ok": True}})
        self.assertEqual(self.collection.find_one({"_id": "a"})["score"], 15)
        self.assertTrue(self.collection.find_one({"_id": "a"})["ok"])

        deleted = self.collection.delete_many({"group": {"$in": ["x"]}})
        self.assertEqual(deleted.deleted_count, 2)
        self.assertEqual(self.collection.count_documents({}), 1)

    def test_atomic_file_is_valid_json(self):
        self.collection.replace_one(
            {"_id": "settings"}, {"_id": "settings", "enabled": True}, upsert=True
        )
        raw = self.path.read_text(encoding="utf-8")
        self.assertIn('"documents"', raw)
        self.assertFalse(any(self.path.parent.glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()
