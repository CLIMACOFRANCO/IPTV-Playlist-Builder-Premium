import importlib.util
import json
import os
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPT=Path(__file__).resolve().parents[1]/"scripts/prioritize_domain_families_v4.py"
SPEC=importlib.util.spec_from_file_location("prioritize_v4",SCRIPT)
v4=importlib.util.module_from_spec(SPEC); sys.modules[SPEC.name]=v4; SPEC.loader.exec_module(v4)

def family(**overrides):
    base={"family_id":"f","brand_name":"Krooz TV","cluster_type":"DOMAIN_VARIANT","domains":["krooz.test"],"domain_count":1,
        "evidence_count":2,"unique_url_count":2,"first_party_evidence_count":2,"third_party_evidence_count":0,
        "legal_page_signal_count":0,"contact_signal_count":0,"application_signal_count":0,"payment_signal_count":0,"crosslink_count":0,
        "named_entities":[],"potential_entities":[],"jurisdictions":[],"potential_jurisdictions":[],"identity_strong_count":0,"identity_supporting_count":0,"conflicts":[],
        "independent_source_categories":["UNKNOWN"],"independent_query_category_count":1,"single_source_dependency":True,"noise_count":0,
        "duplicate_count":0,"duplicate_ratio":0.0,"supporting_row_ids":["r1","r2"],"known_urls":["https://krooz.test/"],"identity_gaps":["NAMED_LEGAL_ENTITY"]}
    base.update(overrides); return base

class PrioritizeDomainFamiliesV4Tests(unittest.TestCase):
    def test_module_has_no_network_or_tavily_execution_api(self):
        source=SCRIPT.read_text(encoding="utf-8")
        for token in ("urllib.request","requests","httpx","TavilyClient","os.getenv","socket."):
            self.assertNotIn(token,source)

    def test_zero_network_and_zero_credential_read_for_pure_scoring(self):
        with mock.patch.object(socket,"create_connection",side_effect=AssertionError("network")), mock.patch.object(os,"getenv",side_effect=AssertionError("credential")):
            self.assertGreaterEqual(v4.score_family(family())["priority_score"],0)

    def test_voco_is_excluded(self):
        self.assertEqual(v4.exclusion_reason("Voco TV","vocotviptv.com",[]),"CLOSED_VOCO_FAMILY")

    def test_technical_domains_are_excluded(self):
        self.assertEqual(v4.exclusion_reason("Krooz TV","x.azurefd.net",[]),"TECHNICAL_INFRASTRUCTURE_ONLY")

    def test_nominal_similarity_alone_does_not_create_strong_family(self):
        scored=v4.score_family(family(evidence_count=1,unique_url_count=1,first_party_evidence_count=1))
        self.assertEqual(scored["penalties"]["nominal_only"],-20); self.assertNotEqual(scored["priority_class"],"HIGH_VALUE")

    def test_www_groups_with_base_domain(self):
        self.assertEqual(v4.normalize_hostname("www.KroozTV.com."),"krooztv.com")

    def test_malformed_ipv6_like_url_is_ignored_not_fatal(self):
        self.assertEqual(v4.canonical_url("https://[invalid/path"),"")

    def test_supporting_rows_are_preserved(self):
        scored=v4.score_family(family()); self.assertEqual(scored["supporting_row_ids"],["r1","r2"])

    def test_utf8_bom_inventory_id_is_normalized(self):
        source=Path(__file__).resolve().parents[1]/"research/output/best_iptv_2026/domain_inventory_v2_existing_results/run_20260714_062112/domain_inventory_detail.csv"
        row=v4.read_csv(source)[0]; self.assertIn("inventory_id",row); self.assertTrue(row["inventory_id"])

    def test_duplicates_do_not_inflate_score(self):
        clean=v4.score_family(family(contact_signal_count=2))
        duplicate=v4.score_family(family(contact_signal_count=2,evidence_count=20,duplicate_count=18,duplicate_ratio=.9))
        self.assertLess(duplicate["priority_score"],clean["priority_score"])

    def test_independent_sources_are_counted(self):
        one=v4.score_family(family(independent_source_categories=["A"]))
        two=v4.score_family(family(independent_source_categories=["A","B"]))
        self.assertGreater(two["positive_components"]["independent_sources"],one["positive_components"]["independent_sources"])

    def test_review_only_is_not_first_party_and_is_do_not_investigate(self):
        scored=v4.score_family(family(first_party_evidence_count=0,third_party_evidence_count=2))
        self.assertEqual(scored["priority_class"],"DO_NOT_INVESTIGATE")

    def test_named_entity_has_more_weight(self):
        plain=v4.score_family(family()); named=v4.score_family(family(named_entities=["Example Ltd"],potential_entities=["Example Ltd"],identity_strong_count=1))
        self.assertGreater(named["priority_score"],plain["priority_score"])

    def test_conflicts_penalize(self):
        plain=v4.score_family(family(contact_signal_count=2)); conflict=v4.score_family(family(contact_signal_count=2,conflicts=["A","B"]))
        self.assertLess(conflict["priority_score"],plain["priority_score"])

    def test_scoring_is_clamped_zero_to_one_hundred(self):
        self.assertEqual(v4.score_family(family(noise_count=100,conflicts=list("abcdefghij"),first_party_evidence_count=0,third_party_evidence_count=1))["priority_score"],0)
        high=v4.score_family(family(domain_count=50,unique_url_count=50,legal_page_signal_count=50,contact_signal_count=50,application_signal_count=50,payment_signal_count=50,crosslink_count=50,named_entities=["X"],potential_entities=["X"],jurisdictions=["Y"],potential_jurisdictions=["Y"],independent_source_categories=list("abcdefghij")))
        self.assertLessEqual(high["priority_score"],100)

    def test_do_not_investigate_works(self):
        self.assertEqual(v4.score_family(family(evidence_count=1,first_party_evidence_count=0,third_party_evidence_count=1))["priority_class"],"DO_NOT_INVESTIGATE")

    def test_ranking_is_deterministic(self):
        items=[v4.score_family(family(family_id="b")),v4.score_family(family(family_id="a"))]
        self.assertEqual(v4.rank_families(items),v4.rank_families(list(reversed(items))))

    def test_tie_break_is_family_id(self):
        items=[v4.score_family(family(family_id="b")),v4.score_family(family(family_id="a"))]
        self.assertEqual([x["family_id"] for x in v4.rank_families(items)],["a","b"])

    def test_unique_primary_recommendation(self):
        common={"legal_page_signal_count":4,"contact_signal_count":3,"payment_signal_count":2,"crosslink_count":2,"independent_source_categories":["A","B"]}
        ranked=v4.rank_families([v4.score_family(family(family_id="a",**common)),v4.score_family(family(family_id="b",application_signal_count=1,**common))])
        primary,reserve=v4.choose_recommendations(ranked); self.assertNotEqual(primary["family_id"],reserve["family_id"])

    def test_low_value_family_can_be_explicit_reserve(self):
        primary=v4.score_family(family(family_id="primary",domain_count=3,unique_url_count=8,legal_page_signal_count=4,contact_signal_count=4,application_signal_count=2,payment_signal_count=4,crosslink_count=3,named_entities=["Example Ltd"],potential_entities=["Example Ltd"],jurisdictions=["Exampleland"],potential_jurisdictions=["Exampleland"],independent_source_categories=["A","B","C"]))
        reserve=v4.score_family(family(family_id="reserve",legal_page_signal_count=2,contact_signal_count=2,payment_signal_count=1,independent_source_categories=["A","B"]))
        chosen,backup=v4.choose_recommendations(v4.rank_families([primary,reserve])); self.assertEqual((chosen["family_id"],backup["family_id"]),("primary","reserve"))

    def test_crawl_and_research_are_blocked(self):
        item=v4.rank_families([v4.score_family(family(legal_page_signal_count=4))])[0]
        plan=v4.skill_plan(item,set()); self.assertEqual(plan["crawl"]["default"],"BLOCKED"); self.assertEqual(plan["research"]["default"],"BLOCKED")

    def test_historical_query_hash_control(self):
        item=v4.rank_families([v4.score_family(family(legal_page_signal_count=4))])[0]
        plan=v4.skill_plan(item,set()); self.assertTrue(all(len(x["query_sha256"])==64 and not x["historical_duplicate"] for x in plan["search"]["queries"]))

    def test_map_seed_prefers_highest_known_url_coverage(self):
        item=v4.rank_families([v4.score_family(family(legal_page_signal_count=4,domains=["a.test","b.test"],domain_count=2,known_urls=["https://a.test/","https://b.test/one","https://b.test/two"]))])[0]
        self.assertEqual(v4.skill_plan(item,set())["map"]["initial_domain"],"b.test")

    def test_source_hash_function_is_stable_and_read_only(self):
        root=Path(__file__).resolve().parents[1]/"research/output/best_iptv_2026/domain_inventory_v2_existing_results/run_20260714_062112"
        before=v4.recursive_fingerprint(root); after=v4.recursive_fingerprint(root)
        self.assertEqual(before["aggregate_sha256"],after["aggregate_sha256"])

    def test_official_roles_remain_prohibited(self):
        self.assertEqual(v4.PROHIBITED_ROLES,{"OFFICIAL_DOMAIN","CONFIRMED_OFFICIAL_DOMAIN","VERIFIED_OWNER"})
        self.assertFalse(v4.PROHIBITED_ROLES & v4.ALLOWED_CLUSTER_TYPES)

    def test_output_contract_has_nineteen_artifacts(self):
        self.assertEqual(len(v4.OUTPUT_NAMES),19); self.assertEqual(len(v4.OUTPUT_NAMES),len(set(v4.OUTPUT_NAMES)))

if __name__=="__main__": unittest.main()
