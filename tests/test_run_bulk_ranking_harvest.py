from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import unittest
import uuid
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts/run_bulk_ranking_harvest.py"
SPEC = importlib.util.spec_from_file_location("bulk_ranking_harvest", SCRIPT)
runner = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(runner)


RAW_SENTINEL = "RAW-CONTENT-MUST-NEVER-REACH-CONSOLE-Ω"


class HttpError(RuntimeError):
    def __init__(self, status_code: int, message: str = "fake failure") -> None:
        super().__init__(f"HTTP {status_code} {message}")
        self.status_code = status_code


def ranking_content(seed: int) -> str:
    lines = [
        "# Best IPTV Providers 2026",
        "Written by Offline Test Author",
        "## Our Methodology",
        "We tested and compared multiple subscription services.",
        RAW_SENTINEL,
        "| Provider | Region | Review |",
        "| --- | --- | --- |",
    ]
    for position in range(1, 7):
        brand = ((seed * 7 + position) % 70) + 1
        lines.append(f"## {position}. Brand{brand:03d} IPTV")
        lines.append(f"**Brand{brand:03d} IPTV** provider review and subscription comparison.")
    lines.extend([
        "## 90. Android TV Box",
        "## 91. IPTV Smarters Pro",
        "## 92. Mystery Stream",
    ])
    return "\n".join(lines)


class FakeTavilyClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.search_number = 0

    def search(self, **kwargs):
        self.calls.append(("search", kwargs))
        self.search_number += 1
        results = []
        for rank in range(1, 11):
            domain_number = ((rank - 1) % 10) + 1
            url = f"https://ranking{domain_number}.example/best-iptv-{self.search_number:02d}-{rank:02d}-2026"
            results.append({
                "url": url,
                "title": f"10 Best IPTV Providers 2026 List {self.search_number}-{rank}",
                "content": "Tested provider comparison with reviews, subscriptions and methodology.",
                "raw_content": ranking_content(self.search_number * 10 + rank),
                "score": 0.91,
            })
        return {"request_id": f"search-{self.search_number}", "usage": {"credits": 1}, "results": results}

    def map(self, **kwargs):
        self.calls.append(("map", kwargs))
        domain = runner.domain_from_url(kwargs["url"])
        results = [f"https://{domain}/best-iptv-map-{index:02d}-2026" for index in range(1, 11)]
        return {"request_id": f"map-{len(self.calls)}", "usage": {"credits": 1}, "results": results}

    def crawl(self, **kwargs):
        self.calls.append(("crawl", kwargs))
        domain = runner.domain_from_url(kwargs["url"])
        results = [
            {
                "url": f"https://{domain}/best-iptv-crawl-{index:02d}-2026",
                "title": f"Best IPTV Crawl Ranking {index} 2026",
                "raw_content": ranking_content(index + len(self.calls) * 10),
            }
            for index in range(1, 26)
        ]
        return {"request_id": f"crawl-{len(self.calls)}", "usage": {"credits": 1}, "results": results}

    def extract(self, **kwargs):
        self.calls.append(("extract", kwargs))
        results = [
            {"url": url, "title": runner.slug_title(url), "raw_content": ranking_content(index + len(self.calls) * 20)}
            for index, url in enumerate(kwargs["urls"], 1)
        ]
        return {
            "request_id": f"extract-{len(self.calls)}",
            "usage": {"credits": 1},
            "results": results,
            "failed_results": [],
        }


class BulkRankingHarvestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = PROJECT_ROOT / f".tmp_bulk_ranking_harvest_{uuid.uuid4().hex}"
        self.root.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def output_root(self, label: str) -> Path:
        return self.root / label

    def test_frozen_query_inventory_and_sdk_configs(self) -> None:
        self.assertEqual(len(runner.SEARCH_QUERIES), 24)
        self.assertEqual([row["sequence"] for row in runner.SEARCH_QUERIES], list(range(1, 25)))
        self.assertEqual(len({row["operation_id"] for row in runner.SEARCH_QUERIES}), 24)
        self.assertEqual(runner.SEARCH_CONFIG["search_depth"], "advanced")
        self.assertEqual(runner.SEARCH_CONFIG["max_results"], 10)
        self.assertEqual(runner.SEARCH_CONFIG["include_raw_content"], "markdown")
        self.assertEqual(runner.MAP_CONFIG["limit"], 60)
        self.assertEqual(runner.CRAWL_CONFIG["limit"], 25)
        self.assertEqual(runner.EXTRACT_CONFIG["extract_depth"], "advanced")
        self.assertEqual(runner.REQUEST_BUDGET["global"], 41)
        self.assertEqual(runner.PLAN_HASH, runner.sha256_json(runner.harvest_plan()))

    def test_ranking_filter_scores_structure_and_excludes_noise(self) -> None:
        useful = runner.score_ranking_page(
            title="10 Best IPTV Providers 2026", url="https://ranking.example/best-iptv-2026",
            raw_content=ranking_content(1), tavily_score=0.9, region="GLOBAL", language="en",
        )
        self.assertEqual(useful["eligibility"], "ELIGIBLE")
        self.assertIn(useful["source_level"], {"A", "B", "C"})
        self.assertGreaterEqual(useful["candidate_count"], 4)
        noise = runner.score_ranking_page(
            title="Android TV Box Setup", url="https://example.com/android-tv-box",
            raw_content="# Android TV Box\nInstall setup hardware player app", tavily_score=0.9,
        )
        self.assertEqual(noise["eligibility"], "EXCLUDED")
        self.assertEqual(noise["source_level"], "E")

    def test_brand_filter_excludes_hardware_and_player_and_keeps_review_nonblocking(self) -> None:
        self.assertEqual(runner.classify_candidate("Android TV Box"), "EXCLUDED_HARDWARE")
        self.assertEqual(runner.classify_candidate("IPTV Smarters Pro"), "EXCLUDED_PLAYER_APP")
        self.assertEqual(runner.classify_candidate("Brand007 IPTV"), "IPTV_SERVICE_CANDIDATE")
        self.assertEqual(runner.classify_candidate("Mystery Stream"), "REVIEW")

    def test_dry_run_and_preflight_do_not_read_key_create_client_or_run(self) -> None:
        before = list(self.root.iterdir())
        with mock.patch.object(runner, "inherited_api_key_reader", side_effect=AssertionError("key read")), mock.patch.object(runner, "sdk_client_factory", side_effect=AssertionError("client")):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                self.assertEqual(runner.main(["--dry-run"]), 0)
                self.assertEqual(runner.main(["--preflight"]), 0)
        self.assertEqual(before, list(self.root.iterdir()))
        self.assertNotIn(RAW_SENTINEL, stdout.getvalue())

    def test_full_fake_execution_obeys_all_request_and_content_ceilings(self) -> None:
        client = FakeTavilyClient()
        run_dir = runner.execute_new(client, self.output_root("full"), "20260718_120000")
        counts = runner.read_json(run_dir / "checkpoint.json")["request_counts"]
        self.assertEqual(counts, {"search": 24, "map": 10, "crawl": 4, "extract": 3, "global": 41})
        calls = Counter(name for name, _ in client.calls)
        self.assertEqual(calls, Counter({"search": 24, "map": 10, "crawl": 4, "extract": 3}))
        self.assertTrue(all(len(kwargs["urls"]) <= 20 for name, kwargs in client.calls if name == "extract"))
        self.assertEqual(len(runner.read_csv(run_dir / "ranking_sources.csv")), 240)
        self.assertLessEqual(len(runner.read_csv(run_dir / "mapped_pages.csv")), 600)
        self.assertEqual(sum(len(row["raw_payload"]["results"]) for row in runner.read_jsonl(run_dir / "crawled_pages.jsonl")), 100)
        self.assertLessEqual(sum(len(row["raw_payload"]["results"]) for row in runner.read_jsonl(run_dir / "extracted_pages.jsonl")), 60)
        self.assertEqual(runner.read_json(run_dir / "manifest.json")["state"], "COMPLETE")

    def test_full_fake_execution_persists_raw_but_console_summary_is_compact(self) -> None:
        run_dir = runner.execute_new(FakeTavilyClient(), self.output_root("context"), "20260718_120001")
        self.assertIn(RAW_SENTINEL, (run_dir / "search_results.jsonl").read_text(encoding="utf-8"))
        self.assertIn(RAW_SENTINEL, (run_dir / "crawled_pages.jsonl").read_text(encoding="utf-8"))
        summary = "\n".join(runner.compact_summary(run_dir))
        self.assertNotIn(RAW_SENTINEL, summary)
        self.assertNotIn("raw_content", summary)
        self.assertIn("TOP20=", summary)
        self.assertLess(len(summary), 3000)

    def test_full_fake_execution_builds_rankings_exclusions_review_and_traceability(self) -> None:
        run_dir = runner.execute_new(FakeTavilyClient(), self.output_root("ranking"), "20260718_120002")
        mentions = runner.read_csv(run_dir / "raw_brand_mentions.csv")
        candidates = runner.read_csv(run_dir / "canonical_iptv_names.csv")
        excluded = runner.read_csv(run_dir / "excluded_non_services.csv")
        review = runner.read_csv(run_dir / "ambiguous_review_queue.csv")
        self.assertGreaterEqual(len(mentions), 300)
        self.assertGreaterEqual(len(candidates), 60)
        self.assertEqual(len(runner.read_csv(run_dir / "top_50_ranked_names.csv")), 50)
        self.assertEqual(len(runner.read_csv(run_dir / "top_20_testing_queue.csv")), 20)
        self.assertTrue(any(row["classification"] == "EXCLUDED_HARDWARE" for row in excluded))
        self.assertTrue(any(row["classification"] == "EXCLUDED_PLAYER_APP" for row in excluded))
        self.assertTrue(review)
        self.assertTrue(all(row["mention_row_id"] in row["supporting_row_ids"] for row in mentions))
        self.assertTrue(all(row["canonical_id"] in row["supporting_row_ids"] or row["supporting_row_ids"] for row in candidates))

    def test_exact_sdk_parameters_and_automatic_domain_selection(self) -> None:
        client = FakeTavilyClient()
        run_dir = runner.execute_new(client, self.output_root("params"), "20260718_120003")
        search_calls = [kwargs for name, kwargs in client.calls if name == "search"]
        self.assertEqual(len(search_calls), 24)
        self.assertTrue(all(call["search_depth"] == "advanced" and call["max_results"] == 10 for call in search_calls))
        self.assertTrue(all(call["exclude_domains"] == list(runner.EXCLUDE_DOMAINS) for call in search_calls))
        map_calls = [kwargs for name, kwargs in client.calls if name == "map"]
        crawl_calls = [kwargs for name, kwargs in client.calls if name == "crawl"]
        extract_calls = [kwargs for name, kwargs in client.calls if name == "extract"]
        self.assertEqual((len(map_calls), len(crawl_calls), len(extract_calls)), (10, 4, 3))
        self.assertTrue(all(call["allow_external"] is False and call["include_usage"] is True for call in map_calls + crawl_calls))
        productivity = runner.read_csv(run_dir / "domain_productivity.csv")
        self.assertEqual(sum(row["selected_for_map"] == "YES" for row in productivity), 10)
        self.assertEqual(sum(row["selected_for_crawl"] == "YES" for row in productivity), 4)

    def test_fake_resume_skips_completed_search_and_finishes_pending_stages(self) -> None:
        output_root = self.output_root("resume")
        run_dir = runner.initialize_run(output_root, "20260718_120004")
        first = FakeTavilyClient()
        checkpoint = runner.read_json(run_dir / "checkpoint.json")
        runner.run_search(first, run_dir, checkpoint)
        self.assertEqual(Counter(name for name, _ in first.calls), Counter({"search": 24}))
        second = FakeTavilyClient()
        completed = runner.resume_existing(second, run_dir, output_root)
        self.assertEqual(completed, run_dir)
        self.assertEqual(sum(name == "search" for name, _ in second.calls), 0)
        self.assertEqual(Counter(name for name, _ in second.calls), Counter({"map": 10, "crawl": 4, "extract": 3}))
        self.assertEqual(runner.read_json(run_dir / "manifest.json")["state"], "COMPLETE")

    def test_ambiguous_reserved_attempt_and_complete_run_block_resume(self) -> None:
        output_root = self.output_root("guards")
        run_dir = runner.initialize_run(output_root, "20260718_120005")
        checkpoint = runner.read_json(run_dir / "checkpoint.json")
        runner.reserve_operation(run_dir, checkpoint, "crawl_guard", "crawl", {"url": "https://example.com"})
        with self.assertRaisesRegex(runner.RunnerBlocked, "ambiguous reserved"):
            runner.validate_resume(run_dir, output_root)
        complete_root = self.output_root("complete_guard")
        complete = runner.execute_new(FakeTavilyClient(), complete_root, "20260718_120006")
        with self.assertRaisesRegex(runner.RunnerBlocked, "already COMPLETE"):
            runner.validate_resume(complete, complete_root)
        with self.assertRaisesRegex(runner.RunnerBlocked, "compatible run already exists"):
            runner.execute_new(FakeTavilyClient(), complete_root, "20260718_120007")

    def _operation_run(self, label: str):
        output_root = self.output_root(label)
        run_dir = runner.initialize_run(output_root, "20260718_130000")
        return run_dir, runner.read_json(run_dir / "checkpoint.json")

    def test_one_retry_only_for_429_5xx_and_timeout(self) -> None:
        failures = [HttpError(429), HttpError(503), TimeoutError("technical timeout")]
        for index, failure in enumerate(failures):
            with self.subTest(failure=type(failure).__name__, index=index):
                run_dir, checkpoint = self._operation_run(f"retry_{index}")
                calls = 0
                def invoke():
                    nonlocal calls
                    calls += 1
                    if calls == 1:
                        raise failure
                    return {"results": []}
                runner.execute_api_operation(
                    run_dir=run_dir, checkpoint=checkpoint, operation_id=f"crawl_retry_{index}",
                    stage="crawl", params={"url": f"https://example{index}.com"}, invoke=invoke,
                    raw_file="crawled_pages.jsonl", result_counter=lambda response: len(runner.response_results(response)),
                )
                operation = checkpoint["operations"][f"crawl_retry_{index}"]
                self.assertEqual((calls, operation["attempts"], operation["retries"], operation["state"]), (2, 2, 1, "COMPLETED"))

    def test_no_retry_for_authentication_400_or_valid_empty(self) -> None:
        run_dir, checkpoint = self._operation_run("auth")
        with self.assertRaises(runner.RunnerBlocked) as caught:
            runner.execute_api_operation(
                run_dir=run_dir, checkpoint=checkpoint, operation_id="crawl_auth", stage="crawl",
                params={"url": "https://example.com"}, invoke=lambda: (_ for _ in ()).throw(HttpError(401)),
                raw_file="crawled_pages.jsonl", result_counter=lambda response: len(runner.response_results(response)),
            )
        self.assertEqual(caught.exception.code, runner.EXIT_AUTHENTICATION)
        self.assertEqual(checkpoint["operations"]["crawl_auth"]["attempts"], 1)

        run_dir, checkpoint = self._operation_run("bad_request")
        result = runner.execute_api_operation(
            run_dir=run_dir, checkpoint=checkpoint, operation_id="crawl_400", stage="crawl",
            params={"url": "https://example.com"}, invoke=lambda: (_ for _ in ()).throw(HttpError(400)),
            raw_file="crawled_pages.jsonl", result_counter=lambda response: len(runner.response_results(response)),
        )
        self.assertIsNone(result)
        self.assertEqual(checkpoint["operations"]["crawl_400"]["attempts"], 1)

        run_dir, checkpoint = self._operation_run("empty")
        runner.execute_api_operation(
            run_dir=run_dir, checkpoint=checkpoint, operation_id="crawl_empty", stage="crawl",
            params={"url": "https://example.com"}, invoke=lambda: {"results": []},
            raw_file="crawled_pages.jsonl", result_counter=lambda response: len(runner.response_results(response)),
        )
        self.assertEqual(checkpoint["operations"]["crawl_empty"]["state"], "COMPLETED")
        self.assertEqual(checkpoint["operations"]["crawl_empty"]["attempts"], 1)

    def test_repeated_structural_error_stops_batch(self) -> None:
        run_dir, checkpoint = self._operation_run("structural")
        for index in range(2):
            if index == 0:
                result = runner.execute_api_operation(
                    run_dir=run_dir, checkpoint=checkpoint, operation_id="map_bad_1", stage="map",
                    params={"url": "https://example.com/1"}, invoke=lambda: {"results": "bad"},
                    raw_file="mapped_results.jsonl", result_counter=lambda response: len(runner.response_results(response)),
                )
                self.assertIsNone(result)
            else:
                with self.assertRaisesRegex(runner.RunnerBlocked, "repeated structural"):
                    runner.execute_api_operation(
                        run_dir=run_dir, checkpoint=checkpoint, operation_id="map_bad_2", stage="map",
                        params={"url": "https://example.com/2"}, invoke=lambda: {"results": "bad"},
                        raw_file="mapped_results.jsonl", result_counter=lambda response: len(runner.response_results(response)),
                    )

    def test_budget_blocks_before_call(self) -> None:
        run_dir, checkpoint = self._operation_run("budget")
        checkpoint["request_counts"]["map"] = runner.REQUEST_BUDGET["map"]
        runner.checkpoint_write(run_dir, checkpoint)
        calls = 0
        def invoke():
            nonlocal calls
            calls += 1
            return {"results": []}
        with self.assertRaises(runner.RunnerBlocked) as caught:
            runner.execute_api_operation(
                run_dir=run_dir, checkpoint=checkpoint, operation_id="map_over_budget", stage="map",
                params={"url": "https://example.com"}, invoke=invoke,
                raw_file="mapped_results.jsonl", result_counter=lambda response: len(runner.response_results(response)),
            )
        self.assertEqual((caught.exception.code, calls), (runner.EXIT_BUDGET, 0))

    def test_atomic_writes_schemas_hashes_utf8_and_no_real_secrets(self) -> None:
        calls = 0
        original = os.replace
        def tracked_replace(source, destination):
            nonlocal calls
            calls += 1
            return original(source, destination)
        with mock.patch.object(runner.os, "replace", side_effect=tracked_replace):
            run_dir = runner.execute_new(FakeTavilyClient(), self.output_root("integrity"), "20260718_120008")
        self.assertGreater(calls, 100)
        for path in run_dir.iterdir():
            if path.is_file():
                path.read_text(encoding="utf-8")
        runner.validate_integrity(run_dir)
        integrity = runner.read_json(run_dir / "integrity_manifest.json")
        self.assertTrue(all(runner.sha256_file(run_dir / name) == metadata["sha256"] for name, metadata in integrity["artifacts"].items()))
        all_text = "\n".join(path.read_text(encoding="utf-8") for path in run_dir.iterdir() if path.is_file())
        self.assertNotRegex(all_text, r"(?i)tvly-[a-z0-9_-]{20,}")

    def test_powershell_block_is_single_run_compact_and_keeps_window_open(self) -> None:
        block = runner.powershell_block()
        self.assertEqual(block.count("run_bulk_ranking_harvest.py"), 1)
        self.assertNotRegex(block, r"(?im)^\s*exit\b")
        self.assertIn("RUN_DIR=", block)
        self.assertIn("RUNNER_EXIT_CODE=", block)
        self.assertIn("DO_NOT_RUN_AGAIN_IF_RUN_DIR_WAS_PRINTED", block)
        self.assertIn("FINAL_STATE=", block)
        self.assertNotRegex(block, r"(?im)Write-(?:Output|Host).*\$env:TAVILY_API_KEY")


if __name__ == "__main__":
    unittest.main()
