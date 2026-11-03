"""Offline baseline audit; never opens a database connection."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
DDL = (ROOT / "alembic/sql/initial_schema.sql").read_text(encoding="utf-8")
EVIDENCE = json.loads((ROOT / "migrations/inspecoes/20261029/estrutura.json").read_text(encoding="utf-8"))


class BaselineIndexConstraintAudit(unittest.TestCase):
    def test_index_names_are_unique_and_match_evidence(self):
        ddl_names = re.findall(r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF NOT EXISTS\s+)?(?:public\.)?([\w]+)", DDL, re.I)
        self.assertEqual(len(ddl_names), len(set(ddl_names)), "duplicate explicit index names in baseline")
        evidence_names = {str(i.get("indexname", i.get("name", ""))) for i in EVIDENCE["indexes"]}
        # PRIMARY KEY/UNIQUE backing indexes are implicit; compare only explicit indexes.
        evidence_names = {n for n in evidence_names if not (n.endswith("_pkey") or n.endswith("_key") or n == "uq_meta_mes")}
        self.assertTrue(evidence_names, "index evidence is missing names")
        self.assertEqual(set(ddl_names), evidence_names, "index names differ from inspected evidence")

    def test_no_duplicate_constraint_declarations(self):
        names = re.findall(r"CONSTRAINT\s+([\w]+)", DDL, re.I)
        duplicates = sorted({n for n in names if names.count(n) > 1})
        self.assertEqual(duplicates, [], f"duplicate constraint names: {duplicates}")

    def test_expected_inventory_counts(self):
        self.assertEqual(len(EVIDENCE["columns"]), 92)
        self.assertEqual(len(EVIDENCE["constraints"]), 113)
        self.assertEqual(len(EVIDENCE["indexes"]), 23)
        self.assertEqual(len(EVIDENCE["triggers"]), 5)
        self.assertEqual(len(EVIDENCE["sequences"]), 9)


if __name__ == "__main__":
    unittest.main()
