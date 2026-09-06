# test_week6.py — Automated Unit Test Suite for Week 6 Evaluation Infrastructure

import os
import sys
import json
import unittest
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from week6.assertions import (
    policy_section_reference_present,
    policy_section_reference_resolves,
    handbook_version_present,
    numeric_policy_value_present,
    out_of_jurisdiction_refusal,
    run_all_assertions,
    VALID_HANDBOOK_SECTIONS,
    DETERMINISTIC_ASSERTION_COUNT,
    JUDGE_CRITERION_COUNT
)
from week6.judge import parse_judge_output
from week6.eval_week6 import (
    load_eval_cases,
    load_labels,
    validate_cases,
    compute_mode_statistics,
    WEEK5_TAXONOMY_MODES
)


class TestWeek6Evaluation(unittest.TestCase):
    """Automated test suite verifying the complete Week 6 Task Set C specification."""

    def setUp(self):
        self.cases_path = "week6/eval_cases_25.json"
        self.labels_path = "week6/labels_25.json"

    def test_eval_cases_dataset_integrity(self):
        """Verify that eval_cases_25.json exists, contains >= 25 cases with valid schema."""
        cases = load_eval_cases(self.cases_path)
        self.assertGreaterEqual(len(cases), 25, "Must have at least 25 evaluation cases")
        
        required_keys = [
            "case_id", "trace_id", "question", "answer", "retrieved_context",
            "handbook_version", "section_info", "taxonomy_mode",
            "source_trace_ref", "regression", "out_of_jurisdiction"
        ]

        for case in cases:
            for k in required_keys:
                self.assertIn(k, case, f"Case {case.get('case_id')} missing required key '{k}'")
            self.assertTrue(bool(case["question"].strip()), "Question must not be empty")
            self.assertTrue(bool(case["answer"].strip()), "Answer must not be empty")

    def test_taxonomy_mode_coverage(self):
        """Verify that every case is tagged with an official Week 5 taxonomy mode."""
        cases = load_eval_cases(self.cases_path)
        modes_present = set()
        for case in cases:
            mode = case["taxonomy_mode"]
            self.assertIn(mode, WEEK5_TAXONOMY_MODES, f"Invalid taxonomy mode '{mode}' in case {case['case_id']}")
            modes_present.add(mode)
        
        self.assertEqual(len(modes_present), 5, "All 5 Week-5 taxonomy modes must be represented")

    def test_regression_cases_present_and_bound(self):
        """Verify that at least 2 regression cases exist with real trace IDs."""
        cases = load_eval_cases(self.cases_path)
        regression_count = validate_cases(cases)
        self.assertGreaterEqual(regression_count, 2, "Must contain at least 2 verbatim regression cases")
        
        for case in cases:
            if case.get("regression"):
                self.assertTrue(len(case["trace_id"]) >= 8, f"Regression case {case['case_id']} missing valid trace_id")

    def test_blind_human_labels_integrity(self):
        """Verify that blind human labels exist for all cases and are binary 0 or 1."""
        cases = load_eval_cases(self.cases_path)
        labels = load_labels(self.labels_path)
        
        self.assertEqual(len(labels), len(cases), "Labels count must match evaluation cases count")
        for case in cases:
            cid = case["case_id"]
            self.assertIn(cid, labels, f"Missing human label for case {cid}")
            self.assertIn(labels[cid], [0, 1], f"Label for {cid} must be binary 0 or 1")

    def test_deterministic_assertion_section_present(self):
        """Verify policy_section_reference_present regex recognition."""
        self.assertTrue(policy_section_reference_present("According to section 5.3.2 of the policy"))
        self.assertTrue(policy_section_reference_present("As stated in Section: 2.2.2"))
        self.assertTrue(policy_section_reference_present("Sec 9.1.1 provides the grievance timeline"))
        self.assertFalse(policy_section_reference_present("Employees receive 28 days of leave [1]."))

    def test_deterministic_assertion_section_resolves(self):
        """Verify policy_section_reference_resolves validates against real handbook sections."""
        self.assertTrue(policy_section_reference_resolves("According to section 5.3.2"))
        self.assertTrue(policy_section_reference_resolves("As per section 2.2.3 and section 9.1"))
        self.assertFalse(policy_section_reference_resolves("According to section 99.88.77"))
        self.assertTrue(policy_section_reference_resolves("Employees receive leave without section citations."))

    def test_deterministic_assertion_version_present(self):
        """Verify handbook_version_present checks for edition / manual markers."""
        self.assertTrue(handbook_version_present("According to the 2018 HR Policy Manual"))
        self.assertTrue(handbook_version_present("Citing HRPolicy.pdf (page 11)"))
        self.assertTrue(handbook_version_present("Per HRPPM rules"))
        self.assertFalse(handbook_version_present("You get 28 days of vacation."))

    def test_deterministic_assertion_numeric_value(self):
        """Verify numeric_policy_value_present checks required numbers and words."""
        self.assertTrue(numeric_policy_value_present("Entitlement is sixteen (16) weeks", "sixteen (16) weeks"))
        self.assertTrue(numeric_policy_value_present("You get 5 days of leave", "5 days"))
        self.assertTrue(numeric_policy_value_present("Working hours are 9.00 am to 5:30 pm", "9.00 am to 5:30 pm"))
        self.assertTrue(numeric_policy_value_present("No number needed", None))
        self.assertFalse(numeric_policy_value_present("You get several days of leave", "5 days"))

    def test_deterministic_assertion_refusal_behavior(self):
        """Verify out_of_jurisdiction_refusal validates unstated policy refusal paths."""
        self.assertTrue(out_of_jurisdiction_refusal("I don't know.", is_out_of_jurisdiction=True))
        self.assertTrue(out_of_jurisdiction_refusal("The documents do not mention overtime.", is_out_of_jurisdiction=True))
        self.assertFalse(out_of_jurisdiction_refusal("Overtime is paid at 1.5x.", is_out_of_jurisdiction=True))
        self.assertTrue(out_of_jurisdiction_refusal("Probation is 6 months.", is_out_of_jurisdiction=False))

    def test_assertion_counts_constant(self):
        """Verify the ratio of deterministic assertions to LLM judge criteria."""
        self.assertEqual(DETERMINISTIC_ASSERTION_COUNT, 5, "Must have 5 deterministic assertions")
        self.assertEqual(JUDGE_CRITERION_COUNT, 1, "Must have 1 binary judge criterion")

    def test_judge_output_parser(self):
        """Verify parse_judge_output handles binary tokens, markdown, and whitespace."""
        self.assertEqual(parse_judge_output("1"), 1)
        self.assertEqual(parse_judge_output("0"), 0)
        self.assertEqual(parse_judge_output("Output: 1"), 1)
        self.assertEqual(parse_judge_output("The answer is 0."), 0)
        self.assertEqual(parse_judge_output("  1  \n"), 1)

    def test_mode_aggregation_math(self):
        """Verify compute_mode_statistics calculates pass rates per taxonomy mode."""
        cases = load_eval_cases(self.cases_path)
        labels = load_labels(self.labels_path)
        dummy_v1 = [{"case_id": c["case_id"], "judge_label": 1} for c in cases]
        dummy_v2 = [{"case_id": c["case_id"], "judge_label": 0} for c in cases]
        
        stats = compute_mode_statistics(cases, labels, dummy_v1, dummy_v2)
        self.assertEqual(len(stats), 5)
        for mode, s in stats.items():
            self.assertGreater(s["total"], 0)
            self.assertEqual(s["v1_pass"], s["total"])
            self.assertEqual(s["v2_pass"], 0)


if __name__ == "__main__":
    unittest.main()
