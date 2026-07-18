import argparse
import copy
import csv
import importlib.util
import io
import json
import shutil
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts/run_brand_first_1b_tavily_api_completion.py"
SPEC = importlib.util.spec_from_file_location("brand_first_1b_api_completion", SCRIPT)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return copy.deepcopy(response)


class BrandFirst1BTavilyApiCompletionTests(unittest.TestCase):
    def setUp(self):
        self.test_root = PROJECT_ROOT / f".tmp_api_completion_tests_{uuid.uuid4().hex}"
        self.test_root.mkdir(parents=False, exist_ok=False)
        self.output_root = self.test_root / "api_completion"
        self.partial_before = runner.directory_fingerprint(runner.PARTIAL_RUN)

    def tearDown(self):
        shutil.rmtree(self.test_root, ignore_errors=True)

    @staticmethod
    def payload(query, count, text="Mechanical result"):
        return {
            "query": query,
            "results": [
                {
                    "title": f"{text} {index}",
                    "url": f"https://Example.COM/path/{index}?b=2&a=1#fragment",
                    "content": f"{text} content {index}",
                    "score": 0.95 - index / 100,
                }
                for index in range(1, count + 1)
            ],
        }

    def execute_with(self, client, stamp="20990101_000000"):
        factory_keys = []

        def factory(api_key):
            factory_keys.append(api_key)
            return client

        result = runner.execute_completion(
            output_root=self.output_root,
            client_factory=factory,
            api_key_reader=lambda name: "opaque-unit-test-context",
            stamp=stamp,
        )
        return result, factory_keys

    def assert_partial_unchanged(self):
        self.assertEqual(
            runner.directory_fingerprint(runner.PARTIAL_RUN)["aggregate_sha256"],
            self.partial_before["aggregate_sha256"],
        )

    def test_frozen_contract_contains_only_authorized_q3_and_q4(self):
        plan = runner.query_plan()
        runner.validate_frozen_plan(plan)
        self.assertEqual(
            [item["query_id"] for item in plan["queries"]],
            [
                "smarters_q3_official_player_application_api_recovery",
                "smarters_q4_subscription_provider_api_completion",
            ],
        )
        self.assertTrue(plan["authorized_q3_technical_repeat"])
        self.assertTrue(plan["q1_q2_not_repeated"])
        self.assertEqual(plan["max_calls"], 2)
        self.assertEqual(plan["retry_limit"], 0)
        self.assertFalse({item["query_id"] for item in plan["queries"]} & runner.Q1_Q2_IDS)

    def test_complete_fake_execution_uses_exactly_two_calls_and_exact_sdk_parameters(self):
        client = FakeClient([
            self.payload(runner.AUTHORIZED_QUERIES[0]["query"], 5),
            self.payload(runner.AUTHORIZED_QUERIES[1]["query"], 0),
        ])
        (exit_code, run_dir), factory_keys = self.execute_with(client)
        self.assertEqual(exit_code, 0)
        self.assertIsNotNone(run_dir)
        self.assertEqual(factory_keys, ["opaque-unit-test-context"])
        self.assertEqual(len(client.calls), 2)
        for call, query_item in zip(client.calls, runner.AUTHORIZED_QUERIES):
            self.assertEqual(call["query"], query_item["query"])
            self.assertEqual({key: call[key] for key in runner.SEARCH_CONFIG}, runner.SEARCH_CONFIG)
        schemas = runner.validate_artifacts(run_dir, require_completed=True)
        self.assertEqual(schemas["checkpoint"]["calls_used"], 2)
        self.assertEqual(schemas["raw_rows"], 2)
        self.assertEqual(schemas["normalized_rows"], 5)
        self.assertEqual(schemas["error_rows"], 0)
        self.assertTrue(schemas["integrity"]["partial_run_unchanged"])
        self.assert_partial_unchanged()

    def test_unicode_is_preserved_in_json_jsonl_csv_and_markdown_is_utf8(self):
        unicode_text = "📺 Español: café, niño — acción; Greek Ω; CJK 漢字"
        client = FakeClient([
            self.payload(runner.AUTHORIZED_QUERIES[0]["query"], 5, unicode_text),
            self.payload(runner.AUTHORIZED_QUERIES[1]["query"], 0),
        ])
        (exit_code, run_dir), _ = self.execute_with(client)
        self.assertEqual(exit_code, 0)
        raw_text = (run_dir / "raw_results.jsonl").read_text(encoding="utf-8")
        csv_text = (run_dir / "normalized_results.csv").read_text(encoding="utf-8")
        report = (run_dir / "completion_report.md").read_text(encoding="utf-8")
        self.assertIn(unicode_text, raw_text)
        self.assertIn(unicode_text, csv_text)
        self.assertTrue(report.startswith("# Tavily API completion report"))
        self.assertEqual(raw_text.encode("utf-8").decode("utf-8"), raw_text)
        self.assertEqual(csv_text.encode("utf-8").decode("utf-8"), csv_text)
        with (run_dir / "normalized_results.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 5)
        self.assertIn("📺", rows[0]["title"])

    def test_zero_result_responses_complete_without_retry(self):
        client = FakeClient([{"results": []}, {"results": []}])
        (exit_code, run_dir), _ = self.execute_with(client)
        self.assertEqual(exit_code, 0)
        self.assertEqual(len(client.calls), 2)
        checkpoint = runner.read_json(run_dir / "checkpoint.json")
        self.assertEqual(checkpoint["run_state"], "EXECUTION_COMPLETED")
        self.assertTrue(all(item["attempts"] == 1 for item in checkpoint["queries"].values()))
        self.assertTrue(all(item["result_count"] == 0 for item in checkpoint["queries"].values()))

    def test_missing_authentication_stops_before_client_run_or_call(self):
        factory_called = False

        def factory(_api_key):
            nonlocal factory_called
            factory_called = True
            return FakeClient([])

        with self.assertRaises(runner.RunnerBlocked) as caught:
            runner.execute_completion(
                output_root=self.output_root,
                client_factory=factory,
                api_key_reader=lambda name: None,
                stamp="20990101_000000",
            )
        self.assertIn("unavailable", str(caught.exception))
        self.assertFalse(factory_called)
        self.assertFalse(self.output_root.exists())
        self.assert_partial_unchanged()

    def test_completed_compatible_run_blocks_before_credentials_client_or_new_run(self):
        first_client = FakeClient([{"results": []}, {"results": []}])
        (exit_code, authoritative), _ = self.execute_with(first_client)
        self.assertEqual(exit_code, 0)
        self.assertEqual(runner.completed_compatible_run(self.output_root), authoritative)

        credential_reads = []
        factory_calls = []
        with self.assertRaises(runner.RunnerBlocked) as caught:
            runner.execute_completion(
                output_root=self.output_root,
                client_factory=lambda key: factory_calls.append(key),
                api_key_reader=lambda name: credential_reads.append(name),
                stamp="20990101_000001",
            )
        self.assertEqual(caught.exception.run_state, "BLOCKED_ALREADY_COMPLETED")
        self.assertIn(authoritative.name, str(caught.exception))
        self.assertEqual(authoritative, caught.exception.run_dir)
        self.assertEqual(credential_reads, [])
        self.assertEqual(factory_calls, [])
        self.assertEqual(len(list(self.output_root.iterdir())), 1)

        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(runner, "execute_completion", side_effect=caught.exception):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                main_code = runner.main([
                    "--execute", "--approval-token", runner.APPROVAL_TOKEN,
                    "--execution-origin", "powershell",
                ])
        self.assertEqual(3, main_code)
        self.assertEqual(f"RUN_DIR={authoritative}\n", stdout.getvalue())
        self.assertIn("BLOCKED_ALREADY_COMPLETED", stderr.getvalue())

    def test_401_and_429_are_sanitized_and_never_retried(self):
        for code in (401, 429):
            with self.subTest(code=code):
                secret = "tvly-" + "syntheticsecret987654321"
                client = FakeClient([RuntimeError(f"HTTP {code} api key: {secret}")])
                (exit_code, run_dir), _ = self.execute_with(client, stamp=f"20990101_000{code}")
                self.assertEqual(exit_code, 1)
                self.assertEqual(len(client.calls), 1)
                errors = (run_dir / "errors.jsonl").read_text(encoding="utf-8")
                all_artifacts = "\n".join(
                    path.read_text(encoding="utf-8")
                    for path in run_dir.iterdir()
                    if path.is_file()
                )
                self.assertIn("[REDACTED]", errors)
                self.assertNotIn("syntheticsecret", all_artifacts)
                checkpoint = runner.read_json(run_dir / "checkpoint.json")
                self.assertEqual(checkpoint["calls_used"], 1)
                self.assertEqual(checkpoint["queries"][runner.AUTHORIZED_QUERIES[1]["query_id"]]["state"], "PENDING")
                self.assertEqual(runner.read_jsonl(run_dir / "errors.jsonl")[0]["retry_performed"], False)
        self.assert_partial_unchanged()

    def test_checkpoint_is_atomically_written_before_and_after_each_query(self):
        client = FakeClient([{"results": []}, {"results": []}])
        snapshots = []
        original = runner.atomic_write_json

        def recording_write(path, value):
            if path.name == "checkpoint.json":
                snapshots.append(copy.deepcopy(value))
            return original(path, value)

        with mock.patch.object(runner, "atomic_write_json", side_effect=recording_write):
            (exit_code, _run_dir), _ = self.execute_with(client)
        self.assertEqual(exit_code, 0)
        for query_item in runner.AUTHORIZED_QUERIES:
            query_id = query_item["query_id"]
            states = [snapshot["queries"][query_id]["state"] for snapshot in snapshots]
            self.assertIn("ATTEMPT_RESERVED", states)
            self.assertIn("COMPLETED", states)
        self.assertEqual(len(client.calls), 2)

    def test_raw_hash_and_normalized_ids_are_reproducible(self):
        query = runner.AUTHORIZED_QUERIES[0]
        payload = self.payload(query["query"], 5, "📺 café — niño")
        raw_a, rows_a = runner.normalize_response(query, payload, "2026-07-18T12:00:00+00:00")
        raw_b, rows_b = runner.normalize_response(query, payload, "2026-07-18T12:00:00+00:00")
        self.assertEqual(raw_a, raw_b)
        self.assertEqual(rows_a, rows_b)
        self.assertEqual(raw_a["raw_payload_sha256"], runner.sha256_json(raw_a["raw_payload"]))
        self.assertEqual(len({row["result_id"] for row in rows_a}), 5)

    def test_dry_run_has_no_credentials_client_network_or_output(self):
        summary = runner.dry_run_summary()
        self.assertTrue(summary["sdk_available_locally"])
        self.assertEqual(summary["credential_reads"], 0)
        self.assertEqual(summary["client_instances"], 0)
        self.assertEqual(summary["network_calls"], 0)
        self.assertFalse(summary["run_created"])
        self.assertEqual(summary["max_calls"], 2)
        self.assertFalse(self.output_root.exists())

        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = runner.main(["--dry-run"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(json.loads(stdout.getvalue())["network_calls"], 0)

    def test_execute_requires_exact_token_and_powershell_origin(self):
        invalid = (
            argparse.Namespace(dry_run=False, execute=True, approval_token=None, execution_origin="powershell"),
            argparse.Namespace(dry_run=False, execute=True, approval_token=runner.APPROVAL_TOKEN, execution_origin=None),
        )
        for args in invalid:
            with self.assertRaises(runner.RunnerBlocked):
                runner.validate_args(args)
        runner.validate_args(argparse.Namespace(
            dry_run=False,
            execute=True,
            approval_token=runner.APPROVAL_TOKEN,
            execution_origin="powershell",
        ))

    def test_powershell_block_is_single_api_only_unit_without_secret_value(self):
        block = runner.powershell_block()
        self.assertTrue(block.startswith("& {\n"))
        self.assertTrue(block.endswith("\n}"))
        self.assertEqual(block.count("run_brand_first_1b_tavily_api_completion.py"), 1)
        self.assertEqual(block.count(r"Env:\TAVILY_API_KEY"), 1)
        self.assertEqual(block.count("$env:TAVILY_API_KEY"), 1)
        self.assertEqual(block.count(runner.APPROVAL_TOKEN), 1)
        self.assertIn("--execution-origin powershell", block)
        self.assertNotIn("tvly --status", block)
        self.assertNotIn("run_brand_first_market_universe_1b_tavily_smoke_test_01.py", block)
        self.assertNotIn("--resume-run", block)
        self.assertNotIn("digitalizard_q1", block)
        self.assertNotIn("digitalizard_q2", block)
        self.assertIn("RUN_DIR=*", block)
        self.assertNotIn("exit ", block)
        self.assertIn('Write-Output "RUNNER_EXIT_CODE=$runnerExitCode"', block)
        self.assertIn("DO_NOT_RUN_AGAIN_IF_RUN_DIR_WAS_PRINTED", block)

    def test_protected_partial_run_is_byte_identical_after_all_fakes(self):
        self.assertEqual(self.partial_before["aggregate_sha256"], runner.EXPECTED_PARTIAL_RUN_SHA256)
        self.assert_partial_unchanged()


if __name__ == "__main__":
    unittest.main()
