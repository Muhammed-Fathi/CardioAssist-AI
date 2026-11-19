import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research.manuscript_audit.validate_integrity import IntegrityError, validate

class IntegrityValidatorTests(unittest.TestCase):
    def test_rejects_wrong_claim_count_before_git(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "docs/research/next_phase").mkdir(parents=True)
            (root / "docs/research/next_phase/AI12_2_GRADUATION_RESEARCH_MANUSCRIPT_DRAFT_2026_11_19.md").write_text("FR-01")
            (root / "docs/research/next_phase/AI12_2_MANUSCRIPT_COVERAGE_2026_11_19.json").write_text('{"report_chapters": []}')
            (root / "docs/research/next_phase/RH01_CLAIM_EVIDENCE_INDEX_2026_11_19.json").write_text('{"claims": []}')
            with self.assertRaisesRegex(IntegrityError, "FR-01 through FR-17"):
                validate(root)

    def test_rejects_bad_pinned_sha(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "docs/research/next_phase").mkdir(parents=True)
            (root / "docs/research/next_phase/AI12_2_GRADUATION_RESEARCH_MANUSCRIPT_DRAFT_2026_11_19.md").write_text(" ".join(f"FR-{i:02}" for i in range(1,18)))
            chapters = [{"id": f"FR-{i:02}"} for i in range(1,18)]
            claims = [{"id": f"CL-{i:03}", "source_path": "src.md", "source_blob_sha": "a"*40} for i in range(1,29)]
            d=root/"docs/research/next_phase"
            (d/"AI12_2_MANUSCRIPT_COVERAGE_2026_11_19.json").write_text(__import__('json').dumps({"report_chapters":chapters}))
            (d/"RH01_CLAIM_EVIDENCE_INDEX_2026_11_19.json").write_text(__import__('json').dumps({"claims":claims}))
            with patch("research.manuscript_audit.validate_integrity._blob_sha", return_value="b"*40):
                with self.assertRaisesRegex(IntegrityError, "pinned blob mismatch"):
                    validate(root)

if __name__ == "__main__": unittest.main()
