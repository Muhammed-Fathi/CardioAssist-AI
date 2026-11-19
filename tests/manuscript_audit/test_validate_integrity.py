import unittest
from research.manuscript_audit.validate_integrity import IntegrityError, validate_matrix

class MatrixValidatorTests(unittest.TestCase):
    def setUp(self):
        self.text = "\n".join(f"## FR-{i:02}. Chapter" for i in range(1, 18))
        self.coverage = {"report_chapters": [{"id": f"FR-{i:02}", "source_claim_ids": [f"CL-{min(i,28):03}"]} for i in range(1,18)],
                         "reviewer_actions": [{"id": f"REVIEW-{i:02}", "task": f"Action {i}", "status": "PENDING"} for i in range(1,11)]}
        self.index = {"claims": [{"id": f"CL-{i:03}", "statement": f"Claim {i}", "source_path": f"source/{i}.md", "source_blob_sha": f"{i:040x}", "source_section": f"§{i}"} for i in range(1,29)]}
        self.matrix = {"chapters": [{"id": f"FR-{i:02}", "line_span": f"{i}-{i}", "source_claim_ids": [f"CL-{min(i,28):03}"]} for i in range(1,18)],
          "claims": [], "reviewer_actions": [{"id": f"REVIEW-{i:02}", "task": f"Action {i}", "status": "PENDING", "audit_disposition": "UNCHANGED_PENDING"} for i in range(1,11)]}
        for i in range(1,29):
            fr=f"FR-{min(i,17):02}"
            self.matrix["claims"].append({"claim_id": f"CL-{i:03}", "indexed_claim": f"Claim {i}",
              "source": {"path": f"source/{i}.md", "pinned_blob_sha": f"{i:040x}", "actual_blob_sha_at_base": f"{i:040x}", "blob_match": True, "indexed_section": f"§{i}"},
              "content_check": {"status": "NOT_VERIFIABLE", "reason_or_specific_reviewer_task": "Synthetic fixture: meaning not assessed."},
              "manuscript_occurrences": [{"chapter": fr, "line_span": f"{min(i,17)}-{min(i,17)}", "matched_report_lines": []}]})
        self.resolver = lambda path: f"{int(path.split('/')[-1].split('.')[0]):040x}"

    def check(self):
        return validate_matrix(coverage=self.coverage, index=self.index, matrix=self.matrix,
                               manuscript_text=self.text, blob_resolver=self.resolver)

    def test_positive_complete_synthetic_matrix(self):
        result=self.check()
        self.assertEqual((result["status"], result["claims"], result["reviewer_actions_pending"]), ("PASS",28,10))

    def test_rejects_omitted_matrix_claim(self):
        self.matrix["claims"].pop()
        with self.assertRaisesRegex(IntegrityError, "exactly once"):
            self.check()

    def test_rejects_tampered_claim_and_wrong_source_mapping(self):
        self.matrix["claims"][0]["source"]["path"]="source/2.md"
        with self.assertRaisesRegex(IntegrityError, "source mapping mismatch"):
            self.check()

    def test_rejects_review_action_status_drift(self):
        self.matrix["reviewer_actions"][0]["status"]="COMPLETE"
        with self.assertRaisesRegex(IntegrityError, "status/task drift"):
            self.check()

    def test_rejects_mismatched_manuscript_excerpt_anchor(self):
        self.matrix["claims"][0]["manuscript_occurrences"][0]["matched_report_lines"]=[{"line":1,"text":"tampered"}]
        with self.assertRaisesRegex(IntegrityError, "excerpt anchor mismatch"):
            self.check()

if __name__ == "__main__": unittest.main()
