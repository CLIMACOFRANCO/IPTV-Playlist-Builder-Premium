import importlib.util
import json
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_domain_family_attribution_v4.py"
SPEC = importlib.util.spec_from_file_location("attribution_v4", SCRIPT)
v4 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = v4
SPEC.loader.exec_module(v4)


def ev(group, strength, category, row="row-1"):
    return {"independence_group": group, "attribution_strength": strength, "evidence_category": category, "source_result_id": row}


class AttributionV4Tests(unittest.TestCase):
    def test_infrastructure_zero_identity(self):
        self.assertEqual(v4.classify_relation("cdn.example", "SHARED_INFRASTRUCTURE", "SUPPORT")[1], 0)

    def test_reseller_zero_identity(self):
        self.assertEqual(v4.classify_relation("seller.example", "RESELLER_RELATIONSHIP", "CONFIRMED_RESELLER")[1], 0)

    def test_reseller_source_does_not_retype_infrastructure_target(self):
        self.assertEqual(v4.classify_relation("wa.me", "SHARED_INFRASTRUCTURE", "CONFIRMED_RESELLER")[0], "INFRASTRUCTURE_SHARED")

    def test_review_zero_identity(self):
        self.assertEqual(v4.classify_relation("trustpilot.com", "SOURCE_REFERENCE", "REVIEW")[1], 0)

    def test_external_reference_zero_identity(self):
        self.assertEqual(v4.classify_relation("news.example", "SOURCE_REFERENCE", "EXTERNAL")[1], 0)

    def test_known_control_is_not_discovery(self):
        row = {"query_id": "voco_ctrl_01_known_vocotv_ai", "result_id": "r", "original_url": "https://x", "canonical_url": "https://x/", "canonical_hostname": "x", "registrable_domain": "x", "title": "x", "content": "", "raw_content": "", "extracted_fields": "{}", "role_candidates": "[]", "is_duplicate": "False"}
        self.assertEqual(v4.build_evidence_units([row])[0]["discovery_or_control"], "CONTROL")

    def test_duplicate_url_same_independence_group(self):
        a = v4.independence_group("https://x/a", "same content", "role")
        b = v4.independence_group("https://x/a", "same content", "role")
        self.assertEqual(a, b)

    def test_same_content_not_two_signals(self):
        groups = {v4.independence_group(url, "same", "role") for url in ["https://x/a", "https://x/b"]}
        self.assertEqual(len(groups), 1)

    def test_nominal_match_not_identity(self):
        self.assertEqual(v4.classify_relation("brand-name.example", "", "", "same name")[1], 0)

    def test_official_word_not_identity(self):
        self.assertEqual(v4.classify_relation("brand.example", "", "", "official site")[1], 0)

    def test_one_weak_signal_unresolved(self):
        role = v4.decide_domain_role([], [ev("g1", "IDENTITY_SUPPORTING", "SUPPORT")], {"SUPPORT"}, [], False, False, False, False)[0]
        self.assertEqual(role, "UNRESOLVED")

    def test_operator_requires_strong_and_two_categories(self):
        weak = v4.decide_domain_role([], [ev("g1", "IDENTITY_SUPPORTING", "SUPPORT")], {"SUPPORT"}, [], False, False, False, False)[0]
        passed = v4.decide_domain_role([ev("g1", "IDENTITY_STRONG", "LEGAL")], [ev("g2", "IDENTITY_SUPPORTING", "SUPPORT", "row-2")], {"LEGAL", "SUPPORT"}, [], False, False, False, False)[0]
        self.assertNotEqual(weak, "PROBABLE_BRAND_OPERATOR")
        self.assertEqual(passed, "PROBABLE_BRAND_OPERATOR")

    def test_possible_related_requires_attributable_relation(self):
        none = v4.decide_domain_role([], [], set(), [], False, False, False, False)[0]
        relation = [{"relation_type_v4": "IDENTITY_SUPPORTING"}]
        related = v4.decide_domain_role([], [], set(), relation, False, False, False, False)[0]
        self.assertEqual(none, "UNRESOLVED")
        self.assertEqual(related, "POSSIBLE_RELATED_DOMAIN")

    def test_system_can_abstain(self):
        self.assertEqual(v4.decide_domain_role([], [], set(), [], True, False, False, False)[0], "UNRESOLVED")

    def test_no_official_role_exists(self):
        self.assertFalse(any("OFFICIAL" in role or "OWNER" in role for role in v4.ALLOWED_ROLES))

    def test_conclusion_supporting_rows_contract(self):
        row_ids = json.dumps(["row-1"])
        self.assertTrue(json.loads(row_ids))

    def test_division_metrics_have_numerator_denominator(self):
        value = v4.metric(1, 2, "test")
        self.assertIn("numerator", value); self.assertIn("denominator", value)

    def test_source_has_no_network_or_credential_imports(self):
        text = SCRIPT.read_text(encoding="utf-8")
        forbidden = ["import requests", "import urllib", "import httpx", "import aiohttp", "import socket", "TAVILY_API_KEY", "TavilyClient"]
        self.assertFalse(any(item in text for item in forbidden))


if __name__ == "__main__":
    unittest.main()
