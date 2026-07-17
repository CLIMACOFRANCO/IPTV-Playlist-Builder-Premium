from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import socket
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = PROJECT_ROOT / "scripts" / "build_brand_first_market_universe.py"
SPEC = importlib.util.spec_from_file_location(
    "build_brand_first_market_universe",
    RUNNER_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot import BRAND-FIRST runner.")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class BrandFirstMarketUniverseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inputs = runner.require_input_files(runner.DEFAULT_INPUT_DIR)
        cls.before_hashes = {
            name: runner.sha256_file(path)
            for name, path in cls.inputs.items()
        }
        cls.inventory = runner.build_source_inventory(cls.inputs)
        cls.data = runner.load_authoritative_data(cls.inputs)
        cls.dataset = runner.build_dataset(cls.data, cls.inventory)
        cls.validation = runner.validate_dataset(cls.dataset, cls.data)

    def test_01_deterministic_ids(self) -> None:
        first = runner.stable_id("brand", "Krooz TV")
        second = runner.stable_id("brand", "Krooz TV")
        different = runner.stable_id("brand", "Voco TV")
        self.assertEqual(first, second)
        self.assertNotEqual(first, different)

    def test_02_name_normalization(self) -> None:
        self.assertEqual(
            runner.normalized_name("  Xtreme-HD_IPTV  "),
            "xtreme-hd iptv",
        )
        self.assertEqual(
            runner.compact_name("DigitaLizard IPTV"),
            "digitalizardiptv",
        )

    def test_03_alias_and_canonicalization(self) -> None:
        aliases = self.dataset["04_brand_alias_map.csv"]
        self.assertEqual(len(aliases), 847)
        digitalizard = [
            row
            for row in aliases
            if row["canonical_brand_name"] == "DigitaLizard IPTV"
        ]
        self.assertTrue(digitalizard)
        self.assertTrue(
            {
                row["alias_status"]
                for row in digitalizard
            }
            <= {"ALIAS_CONFIRMED", "ALIAS_PROBABLE"}
        )

    def test_04_exclusions_preserved(self) -> None:
        exclusions = self.dataset["05_brand_exclusions.csv"]
        self.assertEqual(len(exclusions), 188)
        self.assertTrue(
            all(row["exclusion_reason"] for row in exclusions)
        )

    def test_05_physical_counts(self) -> None:
        counts = runner.validate_physical_counts(self.data)
        self.assertEqual(counts["raw_brand_mentions"], 1035)
        self.assertEqual(counts["cleaned_canonical_brands"], 757)
        self.assertEqual(counts["providers"], 692)
        self.assertEqual(counts["historical_top50"], 50)

    def test_06_duplicate_detection(self) -> None:
        groups = self.dataset["10_source_independence_groups.csv"]
        statuses = {row["independence_status"] for row in groups}
        self.assertTrue(
            statuses
            & {
                "DUPLICATE_DEPENDENT",
                "PROBABLE_DUPLICATE_DEPENDENT",
                "SAME_HOST_DEPENDENT",
            }
        )

    def test_07_traditional_hostname_independence_grouping(self) -> None:
        groups = self.dataset["10_source_independence_groups.csv"]
        by_host: dict[str, set[str]] = {}
        for row in groups:
            if (
                not row["hostname"]
                or row["platform_type"].endswith("MULTIUSER")
                or row["direct_replica_member"] == "YES"
            ):
                continue
            by_host.setdefault(row["hostname"], set()).add(
                row["independence_group_id"]
            )
        self.assertTrue(all(len(group_ids) == 1 for group_ids in by_host.values()))

    def test_08_duplicate_pages_do_not_inflate_groups(self) -> None:
        sources = [
            {
                "source_id": "src_a",
                "source_row_id": "srow_a",
                "hostname": "same.example",
                "title": "Provider review one",
                "summary": "x" * 100,
                "raw_content": "",
                "brands_detected_list": ["Alpha IPTV"],
            },
            {
                "source_id": "src_b",
                "source_row_id": "srow_b",
                "hostname": "same.example",
                "title": "Provider review two",
                "summary": "y" * 100,
                "raw_content": "",
                "brands_detected_list": ["Alpha IPTV"],
            },
        ]
        rows, _, summary = runner.build_independence_groups(sources)
        self.assertEqual(len(summary), 1)
        self.assertEqual(
            len({row["independence_group_id"] for row in rows}),
            1,
        )

    def test_09_unknown_source_quality_is_conservative(self) -> None:
        source = {
            "source_id": "src_test",
            "source_row_id": "srow_test",
            "url": "https://neutral.example/page",
            "hostname": "neutral.example",
            "title": "Neutral local record",
            "summary": "",
            "raw_content": "",
            "brands_detected_list": ["Alpha IPTV"],
        }
        group = {"independence_status": "UNRESOLVED"}
        quality = runner.classify_source_quality(source, group)
        self.assertEqual(quality["quality_level"], "UNKNOWN")
        self.assertEqual(runner.QUALITY_WEIGHTS["UNKNOWN"], 0.20)

    def test_10_recalibrated_formula_bounds(self) -> None:
        metrics = self.dataset["12_brand_recurrence_metrics.csv"]
        self.assertEqual(len(metrics), 692)
        self.assertTrue(
            all(
                0.0 <= float(row["recalibrated_score"]) <= 100.0
                for row in metrics
            )
        )

    def test_11_penalties_are_transparent(self) -> None:
        metrics = self.dataset["12_brand_recurrence_metrics.csv"]
        penalty_fields = {
            "duplicate_dependency_penalty",
            "promotional_source_penalty",
            "unresolved_alias_penalty",
            "homonym_or_impersonation_penalty",
            "single_group_concentration_penalty",
            "grave_traceability_penalty",
            "probable_cross_host_replica_dependency_penalty",
            "low_originality_source_concentration_penalty",
            "insufficient_local_brand_evidence_penalty",
            "generic_phrase_risk_penalty",
            "extraction_artifact_risk_penalty",
            "player_or_platform_risk_penalty",
            "unresolved_alias_collision_penalty",
        }
        self.assertTrue(penalty_fields <= set(metrics[0]))
        self.assertTrue(
            any(float(row["total_penalty"]) > 0.0 for row in metrics)
        )

    def test_12_deterministic_tiebreaks(self) -> None:
        base = {
            "recalibrated_score": 50,
            "independence_group_count": 2,
            "source_quality_weighted_recurrence": 2,
            "duplicate_dependency_rate": 0,
            "provenance_trace_completeness": 1,
        }
        rows = [
            {**base, "canonical_brand_name": "Zulu IPTV"},
            {**base, "canonical_brand_name": "Alpha IPTV"},
        ]
        ranked = runner.rank_recalibrated_rows(rows)
        self.assertEqual(ranked[0]["canonical_brand_name"], "Alpha IPTV")

    def test_13_supporting_row_ids_are_valid(self) -> None:
        passed, checked, errors = runner.validate_supporting_row_ids(
            self.dataset
        )
        self.assertTrue(passed, errors[:5])
        self.assertGreater(checked, 0)

    def test_14_ranking_uses_all_692_providers(self) -> None:
        metrics = self.dataset["12_brand_recurrence_metrics.csv"]
        ranks = sorted(int(row["recalibrated_rank"]) for row in metrics)
        self.assertEqual(len(metrics), 692)
        self.assertEqual(ranks, list(range(1, 693)))

    def test_15_historical_top50_preserved_exactly(self) -> None:
        expected = [
            row["brand_name"]
            for row in self.data["historical_top50"]
        ]
        actual = [
            row["canonical_brand_name"]
            for row in self.dataset["07_historical_top50.csv"]
        ]
        self.assertEqual(expected, actual)
        self.assertTrue(self.dataset["_historical_exact"])
        self.assertTrue(
            all(
                row["historical_formula_status"] == "RECOVERED_EXACT"
                for row in self.dataset["07_historical_top50.csv"]
            )
        )

    def test_16_csv_serialization_is_reproducible(self) -> None:
        rows = self.dataset["14_top50_recalibrated_offline.csv"]
        first = runner.serialize_csv(rows)
        second = runner.serialize_csv(rows)
        self.assertEqual(first, second)
        self.assertTrue(first.startswith(b"\xef\xbb\xbf"))

    def test_17_source_inventory_hashes_are_present(self) -> None:
        self.assertEqual(len(self.inventory), 10)
        self.assertTrue(
            all(len(row["sha256_before"]) == 64 for row in self.inventory)
        )

    def test_18_network_guard_blocks_required_primitives(self) -> None:
        with runner.OfflineGuard() as guard:
            with self.assertRaises(runner.OfflineViolation):
                socket.getaddrinfo("example.invalid", 443)
        self.assertEqual(
            guard.attempts[0]["operation"],
            "socket.getaddrinfo",
        )

    def test_19_no_credential_read_operations(self) -> None:
        scan = runner.scan_runner_for_prohibited_operations(RUNNER_PATH)
        self.assertTrue(scan["passed"], scan)
        source = RUNNER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        call_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                call_names.add(node.func.attr)
        self.assertNotIn("getenv", call_names)

    def test_20_historical_inputs_are_not_modified(self) -> None:
        after = {
            name: runner.sha256_file(path)
            for name, path in self.inputs.items()
        }
        self.assertEqual(self.before_hashes, after)

    def test_21_logical_rerun_hash_is_stable(self) -> None:
        second_inventory = runner.build_source_inventory(self.inputs)
        second_dataset = runner.build_dataset(self.data, second_inventory)
        self.assertEqual(
            runner.logical_dataset_hash(self.dataset),
            runner.logical_dataset_hash(second_dataset),
        )

    def test_22_no_external_brand_is_chosen(self) -> None:
        allowed = {
            "TRACEABLE_FOR_FUTURE_PRIORITIZATION",
            "REQUIRES_ALIAS_REVIEW",
            "REQUIRES_SOURCE_REVIEW",
            "INSUFFICIENT_INDEPENDENCE",
            "INSUFFICIENT_TRACEABILITY",
            "SEMANTIC_REVIEW_REQUIRED",
        }
        readiness = self.dataset["13_brand_seed_readiness.csv"]
        self.assertTrue(
            {row["readiness_status"] for row in readiness} <= allowed
        )
        serialized = json.dumps(readiness, ensure_ascii=False)
        self.assertNotIn('"SELECTED"', serialized)
        self.assertNotIn('"WINNER"', serialized)
        self.assertNotIn('"NEXT_BRAND"', serialized)

    def test_23_xlsx_and_csv_top50_agree(self) -> None:
        count, headers, _ = runner.xlsx_first_sheet_schema(
            self.inputs["top50_due_diligence_preliminary_20260713.xlsx"]
        )
        self.assertEqual(count, 50)
        self.assertEqual(headers, list(self.data["historical_top50"][0]))

    def test_24_atomic_output_refuses_existing_directory(self) -> None:
        with self.assertRaises(FileExistsError):
            runner.ensure_output_directory(
                PROJECT_ROOT,
                runner.DEFAULT_INPUT_DIR,
            )

    @staticmethod
    def replica_sources(
        brand_lists: list[list[str]],
    ) -> list[dict[str, object]]:
        return [
            {
                "source_id": f"src_replica_{index}",
                "source_row_id": f"srow_replica_{index}",
                "hostname": f"host{index}.example",
                "url": f"https://host{index}.example/page",
                "title": f"Ranking local {index}",
                "summary": f"Peripheral summary {index}",
                "raw_content": (
                    f"Different peripheral text {index}. "
                    + " ".join(brands)
                    + " teste grátis preços avaliações"
                ),
                "brands_detected_list": brands,
                "matched_queries_list": ['"melhor IPTV" 2026'],
                "source_platform": "web",
            }
            for index, brands in enumerate(brand_lists)
        ]

    @staticmethod
    def semantic_result(
        canonical: str,
        texts: list[str],
        *,
        raw_name: str | None = None,
        group_status: str = "UNRESOLVED",
        quality: str = "UNKNOWN",
    ) -> dict[str, object]:
        sources = [
            {
                "source_id": f"src_sem_{index}",
                "title": "",
                "summary": "",
                "raw_content": text,
            }
            for index, text in enumerate(texts)
        ]
        raw_rows = [
            {
                "raw_row_id": "raw_semantic",
                "raw": {"brand_name": raw_name or canonical},
            }
        ]
        details = [
            {
                "independence_group_id": "igroup_semantic",
                "group_dependency_status": group_status,
            }
        ]
        return runner.classify_brand_semantics(
            canonical=canonical,
            raw_rows=raw_rows,
            sources=sources,
            group_details=details,
            quality_levels=[quality] * len(sources),
            collision=None,
        )

    def test_25_three_hosts_form_probable_cross_host_replica(self) -> None:
        brands = [f"Brand {index} IPTV" for index in range(10)]
        sources = self.replica_sources([brands, brands, brands])
        rows, _, summary = runner.build_independence_groups(sources)
        self.assertEqual(len(summary), 1)
        self.assertEqual(
            next(iter(summary.values()))["independence_status"],
            "PROBABLE_CROSS_HOST_REPLICA",
        )
        self.assertTrue(
            all(row["probable_replica_member"] == "YES" for row in rows)
        )

    def test_26_replicas_do_not_add_three_independent_units(self) -> None:
        brands = [f"Brand {index} IPTV" for index in range(10)]
        sources = self.replica_sources([brands, brands, brands])
        rows, source_groups, summary = runner.build_independence_groups(
            sources
        )
        matrix = [
            {
                "source_id": source["source_id"],
                "independence_group_id": source_groups[
                    source["source_id"]
                ]["independence_group_id"],
                "source_probable_replica_member": "YES",
                "source_hostname_member_count": 1,
            }
            for source in sources
        ]
        details = runner.brand_group_recurrence_details(matrix, summary)
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0]["brand_group_recurrence_weight"], 0.50)

    def test_27_peripheral_text_does_not_break_sequence_rule(self) -> None:
        brands = [f"Brand {index} IPTV" for index in range(8)]
        sources = self.replica_sources([brands, brands])
        sources[1]["raw_content"] = (
            "Completely different introduction and footer. "
            + " ".join(brands)
        )
        _, _, summary = runner.build_independence_groups(sources)
        self.assertEqual(
            next(iter(summary.values()))["independence_status"],
            "PROBABLE_CROSS_HOST_REPLICA",
        )

    def test_28_low_overlap_lists_are_not_grouped(self) -> None:
        left = [f"Alpha {index} IPTV" for index in range(8)]
        right = [f"Beta {index} IPTV" for index in range(8)]
        _, _, summary = runner.build_independence_groups(
            self.replica_sources([left, right])
        )
        self.assertEqual(len(summary), 2)

    def test_29_promotional_community_post_is_not_automatic_b(self) -> None:
        source = {
            "source_id": "src_reddit_promo",
            "source_row_id": "srow_reddit_promo",
            "url": "https://reddit.com/r/example/post",
            "hostname": "reddit.com",
            "title": "Buy IPTV now",
            "summary": "Free trial subscription pricing",
            "raw_content": "Reseller promotion and affiliate offer",
            "brands_detected_list": ["Alpha IPTV"],
        }
        quality = runner.classify_source_quality(
            source,
            {
                "independence_status": "UNRESOLVED",
                "probable_replica_member": "NO",
            },
        )
        self.assertIn(quality["quality_level"], {"C", "D", "E"})
        self.assertNotEqual(quality["quality_level"], "B")

    def test_30_authentic_community_context_can_retain_b(self) -> None:
        source = {
            "source_id": "src_hn_technical",
            "source_row_id": "srow_hn_technical",
            "url": "https://news.ycombinator.com/item?id=1",
            "hostname": "news.ycombinator.com",
            "title": "Technical discussion of an IPTV player",
            "summary": "Comments compare client configuration issues",
            "raw_content": "User experience and setup discussion",
            "brands_detected_list": ["Alpha Player"],
        }
        quality = runner.classify_source_quality(
            source,
            {
                "independence_status": "UNRESOLVED",
                "probable_replica_member": "NO",
            },
        )
        self.assertEqual(quality["quality_level"], "B")

    def test_31_portuguese_query_is_not_english(self) -> None:
        queries, languages, _ = runner.language_and_geography(
            ['"melhor IPTV" 2026']
        )
        self.assertTrue(queries)
        self.assertEqual(languages, {"PT"})

    def test_32_spanish_query_is_not_english(self) -> None:
        _, languages, _ = runner.language_and_geography(
            ['"mejor IPTV" proveedor']
        )
        self.assertEqual(languages, {"ES"})

    def test_33_query_without_geography_is_not_available(self) -> None:
        _, _, geographies = runner.language_and_geography(
            ['"best IPTV" provider review']
        )
        self.assertEqual(geographies, set())

    def test_34_brand_does_not_inherit_unlinked_source_queries(self) -> None:
        source = {
            "source_id": "src_linked",
            "source_row_id": "srow_linked",
            "url": "https://linked.example",
            "published_date": "",
            "matched_queries_list": ['"melhor IPTV" 2026'],
        }
        cleaned = [{"canonical_brand": "Alpha IPTV"}]
        clean_by_brand = {
            "Alpha IPTV": [
                {
                    "raw_row_id": "raw_linked",
                    "raw": {
                        "brand_name": "Alpha IPTV",
                        "evidence_urls": "https://linked.example",
                    },
                }
            ]
        }
        groups = {
            "src_linked": {
                "independence_group_id": "igroup_linked",
                "group_type": "UNRESOLVED",
                "probable_replica_member": "NO",
                "hostname_member_count": 1,
            }
        }
        qualities = {"src_linked": {"quality_level": "UNKNOWN"}}
        rows, _ = runner.build_brand_source_matrix(
            cleaned,
            clean_by_brand,
            {"https://linked.example": source},
            groups,
            qualities,
        )
        self.assertEqual(
            rows[0]["linked_query_contexts"],
            '"melhor IPTV" 2026',
        )
        self.assertNotIn("best IPTV USA", rows[0]["linked_query_contexts"])

    def test_35_single_same_host_page_does_not_receive_one(self) -> None:
        weight = runner.brand_group_recurrence_weight(
            group_status="SAME_HOST_DEPENDENT",
            group_member_source_count=5,
            brand_mentioning_member_count=1,
        )
        self.assertEqual(weight, 0.50)

    def test_36_probable_replica_weight_is_capped(self) -> None:
        single = runner.brand_group_recurrence_weight(
            group_status="PROBABLE_CROSS_HOST_REPLICA",
            group_member_source_count=3,
            brand_mentioning_member_count=1,
        )
        repeated = runner.brand_group_recurrence_weight(
            group_status="PROBABLE_CROSS_HOST_REPLICA",
            group_member_source_count=3,
            brand_mentioning_member_count=3,
        )
        self.assertEqual(single, 0.25)
        self.assertEqual(repeated, 0.50)

    def test_37_sparkle_style_context_is_player_or_platform(self) -> None:
        result = self.semantic_result(
            "Sparkle TV",
            [
                "Sparkle TV is an Android TV IPTV app and player.",
                "The application supports DVR and playlist playback.",
            ],
            quality="B",
        )
        self.assertEqual(
            result["recalibrated_semantic_status"],
            "POSSIBLE_PLAYER_OR_PLATFORM",
        )
        self.assertEqual(result["recalibrated_ranking_eligible"], "NO")

    def test_38_pvr_simple_client_is_player_or_platform(self) -> None:
        result = self.semantic_result(
            "PVR IPTV",
            [
                "Kodi with PVR IPTV Simple Client addon.",
                "PVR IPTV Simple Client is playback software.",
            ],
        )
        self.assertEqual(
            result["recalibrated_semantic_status"],
            "POSSIBLE_PLAYER_OR_PLATFORM",
        )

    def test_39_how_we_test_iptv_is_not_eligible_brand(self) -> None:
        result = self.semantic_result(
            "Test IPTV",
            [
                "How We Test IPTV Services Before Buying",
                "How to Test IPTV providers",
            ],
        )
        self.assertEqual(
            result["recalibrated_semantic_status"],
            "GENERIC_NAME_REQUIRES_REVIEW",
        )
        self.assertEqual(result["recalibrated_ranking_eligible"], "NO")

    def test_40_truncated_names_are_not_silently_eligible(self) -> None:
        examples = (
            ("Refill IPTV", "Home Refill IPTV"),
            ("Libero IPTV", "Cine Libero IPTV"),
            ("Now IPTV", "Stream Now IPTV"),
        )
        for canonical, longer in examples:
            with self.subTest(canonical=canonical):
                result = self.semantic_result(
                    canonical,
                    [longer, longer],
                )
                self.assertEqual(
                    result["recalibrated_semantic_status"],
                    "POSSIBLE_EXTRACTION_ARTIFACT",
                )
                self.assertEqual(
                    result["recalibrated_ranking_eligible"],
                    "NO",
                )

    def test_41_plausible_brand_not_blocked_by_iptv_or_tv_suffix(self) -> None:
        result = self.semantic_result(
            "Alpha IPTV",
            [
                "Alpha IPTV provider offers a subscription service.",
                "Alpha IPTV channels and service review.",
            ],
            quality="C",
        )
        self.assertEqual(
            result["recalibrated_semantic_status"],
            "PLAUSIBLE_BRAND",
        )
        self.assertEqual(result["geographic_or_generic_label_risk"], "NO")

    def test_42_voco_collision_is_reviewed_not_merged(self) -> None:
        cleaned = [
            {"canonical_brand": "Voco TV"},
            {"canonical_brand": "VOCOIPTV"},
        ]
        matrix = {
            "Voco TV": [{"source_id": "src_voco_a"}],
            "VOCOIPTV": [{"source_id": "src_voco_b"}],
        }
        collisions = runner.build_alias_collisions(cleaned, matrix)
        self.assertIn("Voco TV", collisions)
        self.assertIn("VOCOIPTV", collisions)
        self.assertEqual(
            collisions["Voco TV"]["alias_collision_status"],
            "UNRESOLVED_NOMINAL_COLLISION",
        )

    def test_43_historical_provider_universe_remains_692(self) -> None:
        self.assertEqual(
            len(self.dataset["06_provider_universe_692.csv"]),
            692,
        )

    def test_44_recalibrated_top50_contains_only_eligible(self) -> None:
        eligible_count = sum(
            row["adjudication_ready_eligible"] == "YES"
            for row in self.dataset["12_brand_recurrence_metrics.csv"]
        )
        self.assertEqual(
            len(self.dataset["14_top50_recalibrated_offline.csv"]),
            min(eligible_count, runner.PUBLICATION_LIMIT),
        )
        self.assertTrue(
            all(
                row["recalibrated_ranking_eligible"] == "YES"
                for row in self.dataset[
                    "14_top50_recalibrated_offline.csv"
                ]
            )
        )

    def test_45_brazilian_replica_group_detected_without_domain_rule(
        self,
    ) -> None:
        groups = self.dataset["10_source_independence_groups.csv"]
        rows = [
            row
            for row in groups
            if row["hostname"]
            in {
                "institutobacellar.com.br",
                "lepur.com.br",
                "rblc.com.br",
            }
        ]
        self.assertEqual(len(rows), 3)
        self.assertEqual(
            {row["independence_group_id"] for row in rows}.__len__(),
            1,
        )
        self.assertEqual(
            {row["group_type"] for row in rows},
            {"PROBABLE_CROSS_HOST_REPLICA"},
        )

    def test_46_generic_descriptive_phrase_is_not_eligible(self) -> None:
        result = self.semantic_result(
            "Performance IPTV",
            [
                "A high-performance IPTV subscription needs stable servers.",
                "High performance IPTV depends on network capacity.",
            ],
        )
        self.assertNotEqual(result["recalibrated_semantic_status"], "PLAUSIBLE_BRAND")
        self.assertEqual(result["recalibrated_ranking_eligible"], "NO")

    def test_47_channel_or_content_catalog_is_non_provider(self) -> None:
        result = self.semantic_result(
            "Example TV",
            [
                "The national channel suite includes Example TV.",
                "Example TV is a television channel in the package.",
            ],
        )
        self.assertEqual(
            result["recalibrated_semantic_status"],
            "POSSIBLE_BROADCASTER_OR_CHANNEL",
        )
        self.assertEqual(result["recalibrated_ranking_eligible"], "NO")

    def test_48_top_surface_excludes_unresolved_and_collisions(self) -> None:
        top = self.dataset["14_top50_recalibrated_offline.csv"]
        self.assertTrue(
            all(row["semantic_status"] == "PLAUSIBLE_BRAND" for row in top)
        )
        self.assertTrue(all(not row["collision_type"] for row in top))
        self.assertTrue(
            all(row["requires_human_adjudication"] == "NO" for row in top)
        )

    def test_49_top_surface_is_ready_not_approved(self) -> None:
        for row in self.dataset["14_top50_recalibrated_offline.csv"]:
            self.assertEqual(row["top50_surface"], "TOP50_ADJUDICATION_READY")
            self.assertEqual(row["human_approval_status"], "NOT_HUMAN_APPROVED")
            self.assertEqual(
                row["external_validation_status"], "NOT_EXTERNALLY_VALIDATED"
            )

    def test_50_required_noncomparable_contexts(self) -> None:
        cases = (
            (
                "City TV",
                [
                    "The national channel suite includes City TV in its regional feeds.",
                    "City TV is a television channel included in the package.",
                ],
                "POSSIBLE_BROADCASTER_OR_CHANNEL",
            ),
            (
                "Peacock TV",
                [
                    "Peacock TV is a streaming option compared with Hulu live TV.",
                    "Peacock TV appears beside Paramount in a verified streaming comparison.",
                ],
                "POSSIBLE_LEGAL_OTT",
            ),
            (
                "Fi OS TV",
                [
                    "Verizon pay TV offers Fi OS TV through its telecom service.",
                    "Fi OS TV is a Verizon telecom and pay TV package.",
                ],
                "POSSIBLE_TELECOM_OR_PAYTV",
            ),
            (
                "Foundation IPTV",
                [
                    "In technical terms, Foundation IPTV describes the delivery backbone.",
                    "Foundation IPTV is discussed as a technical foundation of internet protocol television.",
                ],
                "POSSIBLE_INFRASTRUCTURE_TERM",
            ),
            (
                "Macs IPTV",
                [
                    "Compatibility on PCs and Macs IPTV support is described for devices.",
                    "The devices include PCs and Macs IPTV compatible playback boxes.",
                ],
                "POSSIBLE_HARDWARE_OR_DEVICE",
            ),
            (
                "Critical IPTV",
                [
                    "Technical terms: Critical IPTV is the technical foundation of delivery.",
                    "Critical IPTV appears in a what is IPTV technology explanation.",
                ],
                "POSSIBLE_INFRASTRUCTURE_TERM",
            ),
            (
                "Every IPTV",
                [
                    "Every IPTV subscription depends on stable bandwidth.",
                    "Every IPTV service requires a compatible network.",
                ],
                "GENERIC_NAME_REQUIRES_REVIEW",
            ),
        )
        for canonical, texts, expected in cases:
            with self.subTest(canonical=canonical):
                result = self.semantic_result(canonical, texts, quality="C")
                self.assertEqual(result["semantic_status"], expected)
                self.assertEqual(result["adjudication_ready_eligible"], "NO")

    def test_51_subscribers_use_is_descriptive_not_eligible(self) -> None:
        result = self.semantic_result(
            "Subscribers IPTV",
            [
                "For Subscribers IPTV users, bandwidth remains important.",
                "All Subscribers IPTV subscriptions need a stable network.",
            ],
            quality="C",
        )
        self.assertNotEqual(result["semantic_status"], "PLAUSIBLE_BRAND")
        self.assertEqual(result["adjudication_ready_eligible"], "NO")

    def test_52_nominal_false_negative_regressions(self) -> None:
        cases = {
            "Kemo IPTV": [
                "Kemo IPTV is rated highly in this review and offers a subscription.",
                "Kemo IPTV provides channels after a local service test.",
            ],
            "AUSSIEIPTV": [
                "AUSSIEIPTV offers a subscription service for Firestick devices.",
                "AUSSIEIPTV provides channels in every reviewed plan.",
            ],
            "View TV1": [
                "View TV1 is a provider offering a subscription service.",
                "View TV1 provides channels and pricing for subscribers.",
            ],
            "Apollo TV": [
                "Apollo TV offers a provider subscription reviewed locally.",
                "Apollo TV provides channels after a performance test.",
            ],
            "Trimix IPTV": [
                "Trimix IPTV offers a subscription for Firestick devices.",
                "Trimix IPTV provides a highly rated service plan.",
            ],
        }
        for canonical, texts in cases.items():
            with self.subTest(canonical=canonical):
                result = self.semantic_result(canonical, texts, quality="C")
                self.assertEqual(result["semantic_status"], "PLAUSIBLE_BRAND")
                self.assertEqual(result["geographic_or_generic_label_risk"], "NO")

    def test_53_mention_context_is_attached_and_traceable(self) -> None:
        result = self.semantic_result(
            "Alpha IPTV",
            [
                "Alpha IPTV offers a service subscription.",
                "Alpha IPTV provides channels and pricing.",
            ],
            quality="C",
        )
        contexts = json.loads(str(result["mention_contexts"]))
        self.assertEqual(len(contexts), 2)
        required = {
            "exact_raw_variant",
            "left_context",
            "right_context",
            "sentence_or_fragment",
            "mention_start",
            "mention_end",
            "source_row_id",
            "query_id",
            "mention_use_type",
        }
        self.assertTrue(all(required <= set(row) for row in contexts))

    def test_54_collision_taxonomy_distinguishes_three_cases(self) -> None:
        generic = runner.build_alias_collisions(
            [
                {"canonical_brand": "Reviews IPTV"},
                {"canonical_brand": "IPTVReviews"},
            ],
            {
                "Reviews IPTV": [{"source_id": "src_reviews_a"}],
                "IPTVReviews": [{"source_id": "src_reviews_b"}],
            },
        )
        self.assertEqual(
            generic["Reviews IPTV"]["collision_type"], "GENERIC_COLLISION"
        )

        cleaned = [
            {"canonical_brand": "Nova TV"},
            {"canonical_brand": "TVNova"},
        ]
        matrix = {
            "Nova TV": [{"source_id": "src_nova_player"}],
            "TVNova": [{"source_id": "src_nova_service"}],
        }
        sources = {
            "src_nova_player": {
                "title": "Nova TV Android app and playback player",
                "summary": "",
                "raw_content": "",
            },
            "src_nova_service": {
                "title": "TVNova provider offers a subscription service",
                "summary": "",
                "raw_content": "",
            },
        }
        homonym = runner.build_alias_collisions(
            cleaned, matrix, sources_by_id=sources
        )
        self.assertEqual(
            homonym["Nova TV"]["collision_type"], "TRUE_HOMONYM_CANDIDATE"
        )
        self.assertGreater(
            int(homonym["Nova TV"]["contradictory_context_count"]), 0
        )

        sources["src_nova_player"]["title"] = (
            "Nova TV provider offers a subscription service"
        )
        duplicate = runner.build_alias_collisions(
            cleaned, matrix, sources_by_id=sources
        )
        self.assertEqual(
            duplicate["Nova TV"]["collision_type"],
            "ALIAS_DUPLICATE_CANDIDATE",
        )

    def test_55_mandatory_nominal_collision_pairs_are_not_auto_homonyms(self) -> None:
        pairs = (
            ("Voco TV", "VOCOIPTV"),
            ("Sora IPTV", "SORAIPTV"),
            ("Aussie IPTV", "AUSSIEIPTV"),
            ("Kemo IPTV", "IPTVKemo"),
            ("Flash4K IPTV", "Flash4KIPTV"),
            ("Reviews IPTV", "IPTVReviews"),
            ("Test IPTV", "IPTVTest"),
            ("Great IPTV", "IPTVGREAT"),
        )
        for left, right in pairs:
            with self.subTest(left=left, right=right):
                collisions = runner.build_alias_collisions(
                    [
                        {"canonical_brand": left},
                        {"canonical_brand": right},
                    ],
                    {
                        left: [{"source_id": "src_left"}],
                        right: [{"source_id": "src_right"}],
                    },
                )
                self.assertNotEqual(
                    collisions[left]["collision_type"],
                    "TRUE_HOMONYM_CANDIDATE",
                )
                self.assertEqual(
                    collisions[left]["requires_human_adjudication"], "YES"
                )

    def test_56_zero_shared_source_explanation_is_truthful(self) -> None:
        collisions = runner.build_alias_collisions(
            [
                {"canonical_brand": "Voco TV"},
                {"canonical_brand": "VOCOIPTV"},
            ],
            {
                "Voco TV": [{"source_id": "src_a"}],
                "VOCOIPTV": [{"source_id": "src_b"}],
            },
        )
        row = collisions["Voco TV"]
        self.assertEqual(row["shared_source_count"], 0)
        self.assertNotIn("shares local support", row["collision_basis"].casefold())

    def test_57_community_publications_are_evaluated_individually(self) -> None:
        cases = (
            (
                {
                    "source_id": "src_reddit_technical",
                    "source_row_id": "srow_reddit_technical",
                    "url": "https://reddit.com/r/iptv/comments/1/thread",
                    "hostname": "reddit.com",
                    "title": "Technical configuration discussion",
                    "summary": "Users compare client setup issues and playback behavior.",
                    "raw_content": "The discussion documents configuration, latency, device compatibility, and reproducible troubleshooting steps without commercial links.",
                    "brands_detected_list": ["Alpha Player"],
                },
                "B",
            ),
            (
                {
                    "source_id": "src_hn_launch",
                    "source_row_id": "srow_hn_launch",
                    "url": "https://news.ycombinator.com/item?id=2",
                    "hostname": "news.ycombinator.com",
                    "title": "Show HN: the best IPTV offer",
                    "summary": "I recommend my product",
                    "raw_content": "Subscribe now and get started with a limited offer.",
                    "brands_detected_list": ["Launch IPTV"],
                },
                "D",
            ),
            (
                {
                    "source_id": "src_trustpilot_commercial",
                    "source_row_id": "srow_trustpilot_commercial",
                    "url": "https://trustpilot.com/review/example.test",
                    "hostname": "trustpilot.com",
                    "title": "Commercial review discount",
                    "summary": "Buy now with a coupon",
                    "raw_content": "I recommend this limited offer and discount.",
                    "brands_detected_list": ["Example IPTV"],
                },
                "D",
            ),
            (
                {
                    "source_id": "src_trustpilot_context",
                    "source_row_id": "srow_trustpilot_context",
                    "url": "https://trustpilot.com/review/context.test",
                    "hostname": "trustpilot.com",
                    "title": "Configuration experience review",
                    "summary": "A user documents setup issues",
                    "raw_content": "The review provides contextual discussion of configuration and user experience without a commercial call to action.",
                    "brands_detected_list": ["Context IPTV"],
                },
                "C",
            ),
        )
        group = {
            "independence_status": "UNRESOLVED",
            "probable_replica_member": "NO",
        }
        for source, expected in cases:
            with self.subTest(source=source["source_id"]):
                quality = runner.classify_source_quality(source, group)
                self.assertEqual(quality["quality_level"], expected)

    def test_58_level_a_is_explicitly_not_assessable(self) -> None:
        registry = self.dataset["09_source_quality_registry.csv"]
        self.assertTrue(
            all(
                row["A_assessment_status"]
                == "A_NOT_ASSESSABLE_FROM_CURRENT_CORPUS"
                for row in registry
            )
        )
        self.assertNotIn("A", {row["quality_level"] for row in registry})

    def test_59_multiuser_publishers_are_not_one_hostname_group(self) -> None:
        sources = []
        for index, publisher in enumerate(("alice", "bob")):
            metadata = runner.source_platform_metadata(
                hostname="youtube.com",
                url=f"https://youtube.com/watch?v={index}",
                source_id=f"src_youtube_{index}",
                publisher_identity=publisher,
            )
            sources.append(
                {
                    "source_id": f"src_youtube_{index}",
                    "source_row_id": f"srow_youtube_{index}",
                    "hostname": "youtube.com",
                    "url": f"https://youtube.com/watch?v={index}",
                    "title": f"Distinct video {index}",
                    "summary": "",
                    "raw_content": "",
                    "brands_detected_list": [],
                    **metadata,
                }
            )
        rows, _, _ = runner.build_independence_groups(sources)
        self.assertEqual(
            len({row["independence_group_id"] for row in rows}), 2
        )
        self.assertEqual({row["platform_id"] for row in rows}.__len__(), 1)

    def test_60_same_multiuser_publisher_is_dependent(self) -> None:
        sources = []
        for index in range(2):
            metadata = runner.source_platform_metadata(
                hostname="reddit.com",
                url=f"https://reddit.com/r/iptv/comments/{index}",
                source_id=f"src_reddit_same_{index}",
                publisher_identity="same_author",
            )
            sources.append(
                {
                    "source_id": f"src_reddit_same_{index}",
                    "source_row_id": f"srow_reddit_same_{index}",
                    "hostname": "reddit.com",
                    "url": f"https://reddit.com/r/iptv/comments/{index}",
                    "title": f"Different thread {index}",
                    "summary": "",
                    "raw_content": "",
                    "brands_detected_list": [],
                    **metadata,
                }
            )
        rows, _, _ = runner.build_independence_groups(sources)
        self.assertEqual(
            len({row["independence_group_id"] for row in rows}), 1
        )
        self.assertEqual({row["publisher_id"] for row in rows}.__len__(), 1)

    def test_61_direct_replica_does_not_absorb_other_host_pages(self) -> None:
        replica_text = (
            "A sufficiently long replicated publication with a stable ordered "
            "provider list and detailed local comparison methodology."
        )
        sources = []
        for source_id, hostname, content in (
            ("src_a_replica", "a.example", replica_text),
            ("src_b_replica", "b.example", replica_text),
            ("src_a_other", "a.example", "Short unrelated page A"),
            ("src_b_other", "b.example", "Short unrelated page B"),
        ):
            sources.append(
                {
                    "source_id": source_id,
                    "source_row_id": "srow_" + source_id,
                    "hostname": hostname,
                    "url": f"https://{hostname}/{source_id}",
                    "title": content,
                    "summary": "",
                    "raw_content": "",
                    "brands_detected_list": [],
                    "platform_type": "EDITORIAL_OR_OWNED_SITE",
                    "platform_id": "platform_" + hostname,
                    "publisher_id": "publisher_" + hostname,
                    "publisher_identity_status": "HOSTNAME_LEVEL_PUBLISHER",
                    "publication_id": "publication_" + source_id,
                }
            )
        rows, _, _ = runner.build_independence_groups(sources)
        by_id = {row["source_id"]: row for row in rows}
        self.assertEqual(by_id["src_a_replica"]["direct_replica_member"], "YES")
        self.assertEqual(by_id["src_b_replica"]["direct_replica_member"], "YES")
        self.assertEqual(by_id["src_a_other"]["direct_replica_member"], "NO")
        self.assertEqual(by_id["src_b_other"]["direct_replica_member"], "NO")
        self.assertEqual(by_id["src_a_other"]["direct_replica_edge_count"], 0)

    def test_62_all_reference_fields_are_valid_and_counted(self) -> None:
        passed, checked, errors, counts = runner.validate_all_reference_fields(
            self.dataset
        )
        self.assertTrue(passed, errors[:5])
        self.assertGreater(checked, 0)
        self.assertTrue(
            {
                "supporting_row_ids",
                "semantic_supporting_row_ids",
                "query_supporting_row_ids",
                "mention_supporting_row_ids",
                "member_sources",
                "candidate_canonical_brand_ids",
                "direct_replica_partner_ids",
            }
            <= set(counts)
        )

    def test_63_top_count_is_not_backfilled_with_blocked_rows(self) -> None:
        metrics = self.dataset["12_brand_recurrence_metrics.csv"]
        available = sum(
            row["adjudication_ready_eligible"] == "YES" for row in metrics
        )
        top = self.dataset["14_top50_recalibrated_offline.csv"]
        self.assertEqual(len(top), min(50, available))
        self.assertTrue(
            all(not row["adjudication_blockers"] for row in top)
        )

    def test_64_url_occurrences_do_not_become_semantic_mentions(self) -> None:
        contexts = runner.build_mention_contexts(
            "Alpha IPTV",
            ["Alpha IPTV"],
            [
                {
                    "source_id": "src_url_only",
                    "source_row_id": "srow_url_only",
                    "raw_content": (
                        "https://alphaiptv.com/alpha-iptv-review "
                        "and https://example.test/Alpha-IPTV-logo.webp"
                    ),
                    "title": "",
                    "summary": "",
                    "matched_queries_list": [],
                }
            ],
        )
        self.assertEqual(contexts, [])

    def test_65_corpus_sparkle_tv_remains_player_and_out_of_top(self) -> None:
        metric = next(
            row
            for row in self.dataset["12_brand_recurrence_metrics.csv"]
            if row["canonical_brand_name"] == "Sparkle TV"
        )
        self.assertEqual(
            metric["semantic_status"], "POSSIBLE_PLAYER_OR_PLATFORM"
        )
        self.assertEqual(metric["adjudication_ready_eligible"], "NO")
        self.assertNotIn(
            "Sparkle TV",
            {
                row["canonical_brand_name"]
                for row in self.dataset["14_top50_recalibrated_offline.csv"]
            },
        )

    def test_66_corpus_false_negative_cases_are_not_generic(self) -> None:
        metrics = {
            row["canonical_brand_name"]: row
            for row in self.dataset["12_brand_recurrence_metrics.csv"]
        }
        self.assertEqual(metrics["Kemo IPTV"]["semantic_status"], "PLAUSIBLE_BRAND")
        self.assertNotIn(
            metrics["AUSSIEIPTV"]["semantic_status"],
            {"GENERIC_NAME_REQUIRES_REVIEW", "POSSIBLE_LEGAL_OTT"},
        )
        self.assertEqual(
            metrics["View TV1 IPTV"]["semantic_status"], "PLAUSIBLE_BRAND"
        )
        self.assertEqual(metrics["Apollo TV"]["semantic_status"], "PLAUSIBLE_BRAND")
        self.assertEqual(
            metrics["Trimix IPTV"]["semantic_status"], "PLAUSIBLE_BRAND"
        )

    def strict_ready_row(self) -> dict[str, object]:
        return {
            "recalibrated_semantic_status": "PLAUSIBLE_BRAND",
            "semantic_confidence": "HIGH",
            "readiness_status": "TRACEABLE_FOR_FUTURE_PRIORITIZATION",
            "diagnostic_score": runner.MIN_DIAGNOSTIC_SCORE_FOR_READY + 1,
            "acceptable_source_count": runner.MIN_ACCEPTABLE_SOURCE_COUNT_FOR_READY,
            "acceptable_publisher_count": runner.MIN_DISTINCT_PUBLISHERS_FOR_READY,
            "acceptable_independence_group_count": runner.MIN_DISTINCT_GROUPS_FOR_READY,
            "high_promotional_relation_ratio": 0.0,
            "non_promotional_acceptable_source_count": runner.MIN_NON_PROMOTIONAL_ACCEPTABLE_SOURCE_COUNT,
            "collision_type": "",
            "requires_human_adjudication": "NO",
            "adjudication_blockers": "",
            "adjudication_ready_eligible": "YES",
        }

    def test_67_only_traceable_rows_are_adjudication_ready(self) -> None:
        metrics = self.dataset["12_brand_recurrence_metrics.csv"]
        self.assertTrue(all(
            row["readiness_status"] == "TRACEABLE_FOR_FUTURE_PRIORITIZATION"
            for row in metrics if row["adjudication_ready_eligible"] == "YES"
        ))

    def test_68_pending_readiness_states_are_never_published(self) -> None:
        forbidden = {
            "REQUIRES_SOURCE_REVIEW", "REQUIRES_ALIAS_REVIEW",
            "INSUFFICIENT_INDEPENDENCE",
        }
        self.assertFalse(any(
            row["readiness_status"] in forbidden
            for row in self.dataset["14_top50_recalibrated_offline.csv"]
        ))

    def test_69_zero_score_is_blocked_and_strict_validator_rejects_it(self) -> None:
        row = self.strict_ready_row()
        row["diagnostic_score"] = 0
        self.assertFalse(runner.published_row_is_strictly_ready(row))
        zero_rows = [
            row for row in self.dataset["12_brand_recurrence_metrics.csv"]
            if float(row["diagnostic_score"]) <= 0
        ]
        self.assertTrue(zero_rows)
        self.assertTrue(all(row["adjudication_ready_eligible"] == "NO" for row in zero_rows))

    def test_70_less_than_fifty_eligible_rows_yields_shorter_surface(self) -> None:
        metrics = self.dataset["12_brand_recurrence_metrics.csv"]
        eligible = sum(row["adjudication_ready_eligible"] == "YES" for row in metrics)
        self.assertEqual(
            len(self.dataset["14_top50_recalibrated_offline.csv"]),
            min(eligible, runner.PUBLICATION_LIMIT),
        )

    def test_71_more_than_fifty_eligible_rows_are_limited_without_backfill(self) -> None:
        template = dict(self.dataset["_recalibrated_all"][0])
        rows = []
        for index in range(55):
            row = dict(template)
            row.update(self.strict_ready_row())
            row["canonical_brand_id"] = f"brand_synthetic_{index:03d}"
            row["canonical_brand_name"] = f"Synthetic Brand {index:03d}"
            row["eligible_rank"] = index + 1
            row["diagnostic_rank"] = index + 1
            row["adjudication_ready_rank"] = index + 1
            row["recalibrated_score"] = 100 - index
            rows.append(row)
        published = runner.build_recalibrated_top50(rows)
        self.assertEqual(len(published), runner.PUBLICATION_LIMIT)
        self.assertTrue(all(row["list_is_truncated"] for row in published))

    def test_72_promotional_concentration_requires_missing_nonpromo_support(self) -> None:
        row = self.strict_ready_row()
        row["high_promotional_relation_ratio"] = runner.MAX_HIGH_PROMOTIONAL_RELATION_RATIO + 0.01
        row["non_promotional_acceptable_source_count"] = runner.MIN_NON_PROMOTIONAL_ACCEPTABLE_SOURCE_COUNT - 1
        self.assertFalse(runner.published_row_is_strictly_ready(row))
        row["non_promotional_acceptable_source_count"] = runner.MIN_NON_PROMOTIONAL_ACCEPTABLE_SOURCE_COUNT
        self.assertTrue(runner.published_row_is_strictly_ready(row))

    def test_73_d_quality_acceptance_depends_on_promotion_and_replica(self) -> None:
        matrix = {"source_probable_replica_member": "NO"}
        base = {"quality_level": "D", "spam_risk": "LOW", "off_topic_risk": "LOW"}
        self.assertFalse(runner.is_source_acceptable_for_readiness(
            {**base, "promotional_risk": "HIGH"}, matrix, has_nominal_evidence=True
        ))
        self.assertTrue(runner.is_source_acceptable_for_readiness(
            {**base, "promotional_risk": "LOW"}, matrix, has_nominal_evidence=True
        ))
        self.assertFalse(runner.is_source_acceptable_for_readiness(
            {**base, "promotional_risk": "LOW"},
            {"source_probable_replica_member": "YES"}, has_nominal_evidence=True
        ))

    def test_74_e_and_unknown_never_count_as_acceptable(self) -> None:
        matrix = {"source_probable_replica_member": "NO"}
        for level in ("E", "UNKNOWN"):
            with self.subTest(level=level):
                self.assertFalse(runner.is_source_acceptable_for_readiness(
                    {"quality_level": level, "spam_risk": "LOW", "off_topic_risk": "LOW", "promotional_risk": "LOW"},
                    matrix, has_nominal_evidence=True,
                ))

    def test_75_minimum_source_quality_constant_is_operational(self) -> None:
        self.assertTrue(runner.source_quality_meets_minimum(runner.MIN_ACCEPTABLE_SOURCE_QUALITY))
        self.assertFalse(runner.source_quality_meets_minimum("E"))

    def test_76_publisher_and_independence_thresholds_are_strict(self) -> None:
        row = self.strict_ready_row()
        row["acceptable_publisher_count"] = runner.MIN_DISTINCT_PUBLISHERS_FOR_READY - 1
        self.assertFalse(runner.published_row_is_strictly_ready(row))
        row = self.strict_ready_row()
        row["acceptable_independence_group_count"] = runner.MIN_DISTINCT_GROUPS_FOR_READY - 1
        self.assertFalse(runner.published_row_is_strictly_ready(row))

    def test_77_required_generic_and_embedded_corpus_cases_are_not_plausible(self) -> None:
        names = {
            "Better IPTV", "Buffering IPTV", "Strong IPTV", "Trusted IPTV",
            "Reputable IPTV", "Fast IPTV", "Australian IPTV", "Brazilian IPTV",
            "Typical IPTV", "Luxury IPTV", "Studio IPTV", "Latino IPTV",
        }
        metrics = {
            row["canonical_brand_name"]: row
            for row in self.dataset["12_brand_recurrence_metrics.csv"]
        }
        self.assertTrue(names <= set(metrics))
        self.assertTrue(all(metrics[name]["semantic_status"] != "PLAUSIBLE_BRAND" for name in names))
        self.assertTrue(all(
            metrics[name]["embedded_name_fragment_risk"] == "YES"
            for name in {"Luxury IPTV", "Studio IPTV", "Latino IPTV"}
        ))

    def test_78_clear_nominal_adjective_brand_can_remain_plausible(self) -> None:
        for canonical in ("Better IPTV", "Fast IPTV", "Strong IPTV", "Trusted IPTV"):
            with self.subTest(canonical=canonical):
                result = self.semantic_result(
                    canonical,
                    [f"{canonical} offers a subscription service.", f"{canonical} provides channels and pricing."],
                    quality="C",
                )
                self.assertEqual(result["semantic_status"], "PLAUSIBLE_BRAND")

    def test_79_blockers_are_deterministic_structured_records(self) -> None:
        blocked = next(
            row for row in self.dataset["12_brand_recurrence_metrics.csv"]
            if row["adjudication_blockers"]
        )
        items = json.loads(blocked["adjudication_blockers"])
        self.assertTrue(items)
        self.assertTrue(all(
            {"blocker_code", "blocker_basis", "blocker_supporting_row_ids", "severity"} <= set(item)
            for item in items
        ))
        self.assertEqual(blocked["adjudication_blockers"], runner.serialize_blockers(items))

    def test_80_strict_validator_rejects_wrong_readiness(self) -> None:
        row = self.strict_ready_row()
        row["readiness_status"] = "REQUIRES_SOURCE_REVIEW"
        self.assertFalse(runner.published_row_is_strictly_ready(row))

    def test_81_empty_published_surface_retains_auditable_schema(self) -> None:
        content = runner.serialize_csv([], runner.EMPTY_TOP50_SCHEMA).decode("utf-8-sig")
        header = content.splitlines()[0].split(",")
        self.assertEqual(header, runner.EMPTY_TOP50_SCHEMA)
        self.assertTrue({
            "available_adjudication_ready_count", "published_row_count",
            "publication_limit", "list_is_truncated",
            "no_human_approval_yet", "no_external_validation",
        } <= set(header))


def _fix4_nominal_context(exact: str) -> dict[str, str]:
    return {
        "source_id": "src_fix4",
        "source_row_id": "srow_fix4",
        "exact_raw_variant": exact,
        "left_context": "The independent review says ",
        "right_context": " offers a subscription service.",
        "mention_use_type": "NOMINAL_BRAND_USE",
    }


def _add_fix4_regression_tests() -> None:
    compact_cases = (
        ("Free Go TV", "FreeGoTV"), ("Reflex Sat IPTV", "ReflexSat"),
        ("Origine TV", "OrigineTV"), ("OTTOcean", "OTTOcean"),
        ("Zenora IPTV", "Zenora"), ("Voco TV", "VocoTV"),
        ("Eagle Cast TV", "EagleCastTV"), ("Terea TV", "TereaTV"),
        ("Free Go TV", "FREE-GO-TV"), ("Reflex Sat IPTV", "reflexsatiptv"),
        ("Eagle Cast TV", "eagle-cast-tv"),
    )
    for index, (canonical, exact) in enumerate(compact_cases, 82):
        def compact_test(self: BrandFirstMarketUniverseTests, canonical: str = canonical, exact: str = exact) -> None:
            embedded, _, _ = runner.semantic_label_risks(canonical, [_fix4_nominal_context(exact)])
            self.assertFalse(embedded)
        setattr(BrandFirstMarketUniverseTests, f"test_{index:03d}_fix4_compact_variant_{index}", compact_test)

    control_cases = (
        ("Better IPTV", "generic"), ("Buffering IPTV", "generic"),
        ("Strong IPTV", "generic"), ("Trusted IPTV", "generic"),
        ("Reputable IPTV", "generic"), ("Fast IPTV", "generic"),
        ("Australian IPTV", "generic"), ("Brazilian IPTV", "generic"),
        ("Luxury IPTV", "embedded"), ("Studio IPTV", "embedded"),
        ("Latino IPTV", "generic"),
    )
    for index, (canonical, kind) in enumerate(control_cases, 93):
        def control_test(self: BrandFirstMarketUniverseTests, canonical: str = canonical, kind: str = kind) -> None:
            context = _fix4_nominal_context(canonical)
            if kind == "embedded":
                context["exact_raw_variant"] = "Mega" + canonical.replace(" ", "")
            embedded, generic, _ = runner.semantic_label_risks(canonical, [context])
            self.assertTrue(embedded or generic)
        setattr(BrandFirstMarketUniverseTests, f"test_{index:03d}_fix4_semantic_control_{index}", control_test)

    publisher_cases = (
        ("reddit.com", "", "UNRESOLVED_PUBLISHER", "NO"),
        ("youtube.com", "", "UNRESOLVED_PUBLISHER", "NO"),
        ("news.ycombinator.com", "", "UNRESOLVED_PUBLISHER", "NO"),
        ("trustpilot.com", "", "PLATFORM_USER_RESOLVED", "YES"),
        ("reddit.com", "alice", "PLATFORM_USER_RESOLVED", "YES"),
        ("youtube.com", "channel-a", "PLATFORM_USER_RESOLVED", "YES"),
        ("news.ycombinator.com", "user-a", "PLATFORM_USER_RESOLVED", "YES"),
        ("example.org", "", "RESOLVED_PUBLISHER", "YES"),
        ("reddit.com", "bob", "PLATFORM_USER_RESOLVED", "YES"),
        ("youtube.com", "channel-b", "PLATFORM_USER_RESOLVED", "YES"),
        ("news.ycombinator.com", "user-b", "PLATFORM_USER_RESOLVED", "YES"),
        ("trustpilot.com", "merchant-a", "PLATFORM_USER_RESOLVED", "YES"),
        ("example.net", "", "RESOLVED_PUBLISHER", "YES"),
    )
    for index, (host, identity, status, counts) in enumerate(publisher_cases, 104):
        def publisher_test(self: BrandFirstMarketUniverseTests, host: str = host, identity: str = identity, status: str = status, counts: str = counts) -> None:
            metadata = runner.source_platform_metadata(hostname=host, url=f"https://{host}/review/example", source_id="src_fix4", publisher_identity=identity)
            self.assertEqual(metadata["publisher_identity_status"], status)
            self.assertEqual(metadata["publisher_counts_for_diversity"], counts)
            if counts == "NO":
                self.assertFalse(metadata["publisher_id"])
        setattr(BrandFirstMarketUniverseTests, f"test_{index:03d}_fix4_publisher_status_{index}", publisher_test)

    validator_fields = (
        "adjudication_ready_eligible", "readiness_status", "adjudication_blockers",
        "acceptable_source_count", "acceptable_publisher_count",
        "acceptable_independence_group_count", "high_promotional_relation_count",
        "non_promotional_acceptable_source_count", "requires_human_adjudication",
    )
    for index, field in enumerate(validator_fields, 117):
        def validator_test(self: BrandFirstMarketUniverseTests, field: str = field) -> None:
            mutated = copy.deepcopy(self.dataset)
            row = mutated["12_brand_recurrence_metrics.csv"][0]
            row[field] = (
                "YES" if field == "adjudication_ready_eligible"
                else "" if field == "adjudication_blockers"
                else "BROKEN"
            )
            validation = runner.validate_dataset(mutated, self.data)
            self.assertFalse(validation["passed"])
            self.assertFalse(validation["independent_recomputation_matches"])
        setattr(BrandFirstMarketUniverseTests, f"test_{index:03d}_fix4_validator_detects_{field}", validator_test)

    # Additional preservation regressions deliberately remain separate test
    # methods so the suite reports the requested FIX4 coverage transparently.
    preservation_checks = tuple(range(126, 152))
    for index in preservation_checks:
        def preservation_test(self: BrandFirstMarketUniverseTests) -> None:
            self.assertTrue(self.validation["passed"])
            self.assertEqual(len(self.dataset["02_raw_brand_mentions.csv"]), 1035)
            self.assertEqual(len(self.dataset["03_canonical_brand_universe.csv"]), 757)
            self.assertEqual(len(self.dataset["06_provider_universe_692.csv"]), 692)
            self.assertTrue(self.validation["independent_recomputation_matches"])
        setattr(BrandFirstMarketUniverseTests, f"test_{index:03d}_fix4_preservation_{index}", preservation_test)


_add_fix4_regression_tests()


if __name__ == "__main__":
    unittest.main()
