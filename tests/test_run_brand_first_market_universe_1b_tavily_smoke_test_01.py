import argparse
import csv
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts/run_brand_first_market_universe_1b_tavily_smoke_test_01.py"
SPEC = importlib.util.spec_from_file_location("brand_first_1b_smoke", SCRIPT)
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


class BrandFirstMarketUniverse1BTavilySmokeTest01Tests(unittest.TestCase):
    def setUp(self):
        self.test_output_root = runner.OUTPUT_ROOT / f"_offline_tests_{uuid.uuid4().hex}"
        self.test_output_root.mkdir(parents=True, exist_ok=False)
        self.run_dir = self.test_output_root / "run_20990101_000000"
        self.git = {
            "head": "6a8e129afc1a16c11e36d991f5bd708d9f9f7030",
            "origin_main_local": "6a8e129afc1a16c11e36d991f5bd708d9f9f7030",
            "divergence": "0\t0",
            "branch": "main",
        }
        self.historical_before = runner.protected_fingerprints()

    def tearDown(self):
        shutil.rmtree(self.test_output_root, ignore_errors=True)

    def initialize(self):
        return runner.initialize_run(
            self.run_dir,
            git=self.git,
            tvly_version=runner.EXPECTED_TVLY_VERSION,
            historical_before=self.historical_before,
            originated_from_powershell=True,
        )

    @staticmethod
    def completed(payload, stderr=b""):
        return subprocess.CompletedProcess(
            args=["tvly", "search"], returncode=0,
            stdout=json.dumps(payload, ensure_ascii=False).encode("utf-8"), stderr=stderr,
        )

    @staticmethod
    def result_payload(query_id="q", count=1):
        return {
            "query": query_id,
            "results": [
                {
                    "title": f"Title {index}",
                    "url": f"https://Example.COM/path/{index}?b=2&a=1#fragment",
                    "content": f"Mechanical result {index}",
                    "score": 0.9 - index / 100,
                }
                for index in range(1, count + 1)
            ],
        }

    def test_frozen_queries_are_exact_ordered_and_plan_hash_is_stable(self):
        expected = [
            (1, "digitalizard_q1_official_company", "BRAND_CANDIDATE", '"DigitaLizard IPTV" official website company'),
            (2, "digitalizard_q2_reviews_reseller_operator", "BRAND_CANDIDATE", '"DigitaLizard IPTV" reviews app reseller operator'),
            (3, "smarters_q3_official_player_application", "NEGATIVE_CONTROL", '"IPTV Smarters Pro" official website player application'),
            (4, "smarters_q4_subscription_provider", "NEGATIVE_CONTROL", '"IPTV Smarters Pro" IPTV subscription provider'),
        ]
        actual = [(q["sequence"], q["query_id"], q["role"], q["query"]) for q in runner.FROZEN_QUERIES]
        self.assertEqual(actual, expected)
        self.assertEqual(runner.frozen_plan_hash(), "705f46e9873801e581039a6f116a7905524764ec91eb0465798fed2c989fd7fe")
        runner.validate_frozen_plan(runner.frozen_plan())

    def test_frozen_search_contract_and_cli_flags(self):
        config = runner.FROZEN_CONFIG
        self.assertEqual(config["product"], "Tavily Search")
        self.assertEqual(config["search_depth"], "basic")
        self.assertEqual(config["max_results_per_query"], 5)
        self.assertEqual(config["max_physical_calls"], 4)
        self.assertEqual(config["max_physical_calls_per_query"], 1)
        self.assertEqual(config["automatic_retries"], 0)
        self.assertEqual(config["max_theoretical_results"], 20)
        command = runner.tvly_command(runner.FROZEN_QUERIES[0])
        self.assertEqual(command[:2], ["tvly", "search"])
        self.assertEqual(command[-5:], ["--depth", "basic", "--max-results", "5", "--json"])
        joined = " ".join(command)
        for forbidden in ("--include-answer", "--include-images", "--include-raw-content", "extract", "crawl", "research"):
            self.assertNotIn(forbidden, joined)

    def test_plan_tampering_query_order_and_configuration_all_block(self):
        cases = []
        changed_query = runner.frozen_plan()
        changed_query["queries"][0]["query"] += " changed"
        cases.append(changed_query)
        changed_order = runner.frozen_plan()
        changed_order["queries"][0], changed_order["queries"][1] = changed_order["queries"][1], changed_order["queries"][0]
        cases.append(changed_order)
        changed_results = runner.frozen_plan()
        changed_results["configuration"]["max_results_per_query"] = 6
        cases.append(changed_results)
        changed_depth = runner.frozen_plan()
        changed_depth["configuration"]["search_depth"] = "advanced"
        cases.append(changed_depth)
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(runner.RunnerBlocked) as caught:
                    runner.validate_frozen_plan(value)
                self.assertEqual(caught.exception.run_state, "BLOCKED_CONFIGURATION")

    def test_budget_blocks_fifth_attempt_and_second_attempt_per_query(self):
        checkpoint = runner.initial_checkpoint("test", "hash")
        checkpoint["calls_reserved"] = 4
        with self.assertRaises(runner.RunnerBlocked) as caught:
            runner.validate_budget(checkpoint, runner.FROZEN_QUERIES[0]["query_id"])
        self.assertEqual(caught.exception.run_state, "BLOCKED_BUDGET")

        checkpoint["calls_reserved"] = 1
        query_id = runner.FROZEN_QUERIES[0]["query_id"]
        checkpoint["queries"][query_id]["attempts_reserved"] = 1
        with self.assertRaises(runner.RunnerBlocked):
            runner.validate_budget(checkpoint, query_id)

    def test_dry_run_has_no_backend_auth_environment_or_real_run(self):
        before_children = sorted(path.name for path in runner.OUTPUT_ROOT.iterdir())
        with mock.patch.object(runner, "invoke_tvly_search", side_effect=AssertionError("backend called")), \
             mock.patch.object(runner, "local_tvly_version", side_effect=AssertionError("auth-adjacent command called")), \
             mock.patch.object(os, "getenv", side_effect=AssertionError("environment read")):
            summary = runner.dry_run_summary()
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = runner.main(["--dry-run"])
        after_children = sorted(path.name for path in runner.OUTPUT_ROOT.iterdir())
        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["verdict"], "DRY_RUN_OFFLINE_PASS")
        self.assertEqual(summary["network_calls"], 0)
        self.assertEqual(summary["authentication_checks"], 0)
        self.assertFalse(summary["real_run_created"])
        self.assertEqual(before_children, after_children)
        self.assertIn("DRY_RUN_OFFLINE_PASS", stdout.getvalue())

    def test_execute_and_resume_require_exact_token_and_powershell_origin(self):
        for argv in (
            ["--execute"],
            ["--execute", "--approval-token", "wrong", "--execution-origin", "powershell"],
            ["--execute", "--approval-token", runner.APPROVAL_TOKEN],
            ["--execute", "--resume-run", str(self.run_dir), "--approval-token", runner.APPROVAL_TOKEN],
        ):
            args = runner.parser().parse_args(argv)
            with self.subTest(argv=argv), self.assertRaises(runner.RunnerBlocked):
                runner.validate_args(args)
        valid = runner.parser().parse_args([
            "--execute", "--approval-token", runner.APPROVAL_TOKEN,
            "--execution-origin", "powershell",
        ])
        runner.validate_args(valid)

    def test_zero_results_complete_without_retry_and_outputs_validate(self):
        manifest, checkpoint = self.initialize()
        calls = []

        def fake_backend(query_item):
            calls.append(query_item["query_id"])
            return self.completed({"query": query_item["query"], "results": []})

        exit_code = runner.process_run(
            self.run_dir, manifest, checkpoint, self.historical_before,
            backend=fake_backend,
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(calls, [item["query_id"] for item in runner.FROZEN_QUERIES])
        final_checkpoint = runner.read_json(self.run_dir / "checkpoint.json")
        self.assertEqual(final_checkpoint["calls_reserved"], 4)
        self.assertEqual(final_checkpoint["calls_performed"], 4)
        self.assertEqual(final_checkpoint["run_state"], "EXECUTION_COMPLETED")
        self.assertTrue(all(state["status"] == "COMPLETED" for state in final_checkpoint["queries"].values()))
        self.assertTrue(all(state["result_count"] == 0 for state in final_checkpoint["queries"].values()))
        schemas = runner.validate_artifacts(self.run_dir, require_completed=True)
        self.assertEqual(schemas["ledger_rows"], 4)
        self.assertEqual(schemas["raw_response_rows"], 4)
        self.assertEqual(schemas["normalized_rows"], 0)

    def test_authentication_stops_immediately_and_redacts_stderr(self):
        manifest, checkpoint = self.initialize()
        calls = []

        def fake_backend(query_item):
            calls.append(query_item["query_id"])
            synthetic_secret = "tvly-" + "supersecret123456"
            return subprocess.CompletedProcess(
                args=["tvly"], returncode=3, stdout=b"",
                stderr=("Unauthorized API " + "key: " + synthetic_secret).encode("utf-8"),
            )

        exit_code = runner.process_run(
            self.run_dir, manifest, checkpoint, self.historical_before,
            backend=fake_backend,
        )
        self.assertEqual(exit_code, 3)
        self.assertEqual(len(calls), 1)
        final = runner.read_json(self.run_dir / "checkpoint.json")
        self.assertEqual(final["run_state"], "BLOCKED_AUTHENTICATION")
        self.assertEqual(final["calls_reserved"], 1)
        self.assertEqual(final["calls_performed"], 1)
        all_text = "\n".join((self.run_dir / name).read_text(encoding="utf-8") for name in runner.REQUIRED_ARTIFACTS)
        self.assertNotIn("supersecret", all_text)
        self.assertIn("[REDACTED]", all_text)

    def test_checkpoint_and_every_artifact_write_use_atomic_replace(self):
        replace_targets = []
        real_replace = os.replace

        def observed_replace(source, target):
            replace_targets.append(Path(target).name)
            return real_replace(source, target)

        with mock.patch.object(runner.os, "replace", side_effect=observed_replace):
            self.initialize()
        for artifact in runner.REQUIRED_ARTIFACTS:
            self.assertIn(artifact, replace_targets)
        self.assertIn("checkpoint.json", replace_targets)
        self.assertFalse(list(self.run_dir.glob(".*.tmp")))

    def test_resume_skips_completed_query_without_calling_it(self):
        manifest, checkpoint = self.initialize()
        first_id = runner.FROZEN_QUERIES[0]["query_id"]
        first = checkpoint["queries"][first_id]
        first.update({
            "status": "COMPLETED", "attempts_reserved": 1,
            "physical_call_number": 1, "started_at": "2026-01-01T00:00:00+00:00",
            "finished_at": "2026-01-01T00:00:01+00:00", "result_count": 0,
            "exit_code": 0, "error_class": None, "raw_row_ids": ["raw_existing"],
        })
        checkpoint["calls_reserved"] = 1
        checkpoint["calls_performed"] = 1
        runner.atomic_write_json(self.run_dir / "checkpoint.json", checkpoint)
        runner.refresh_outputs(self.run_dir, manifest, checkpoint, self.historical_before)
        resumed_manifest, resumed_checkpoint = runner.validate_run_compatibility(
            self.run_dir, self.test_output_root,
        )
        calls = []

        def fake_backend(query_item):
            calls.append(query_item["query_id"])
            return self.completed({"results": []})

        exit_code = runner.process_run(
            self.run_dir, resumed_manifest, resumed_checkpoint,
            self.historical_before, backend=fake_backend,
        )
        self.assertEqual(exit_code, 0)
        self.assertNotIn(first_id, calls)
        self.assertEqual(len(calls), 3)
        final = runner.read_json(self.run_dir / "checkpoint.json")
        self.assertEqual(final["queries"][first_id]["status"], "COMPLETED")
        self.assertEqual(final["resume_events"][0]["disposition"], "SKIPPED_ALREADY_COMPLETED")

    def test_resume_rejects_historical_foreign_and_incompatible_runs(self):
        for historical_name in runner.HISTORICAL_BLOCKED_NAMES:
            with self.subTest(name=historical_name), self.assertRaises(runner.RunnerBlocked):
                runner.validate_run_compatibility(self.test_output_root / historical_name, self.test_output_root)

        manifest, checkpoint = self.initialize()
        del manifest, checkpoint
        foreign_root = self.test_output_root / "foreign"
        foreign_root.mkdir()
        foreign_run = foreign_root / self.run_dir.name
        shutil.copytree(self.run_dir, foreign_run)
        with self.assertRaises(runner.RunnerBlocked):
            runner.validate_run_compatibility(foreign_run, self.test_output_root)

        tampered = runner.read_json(self.run_dir / "query_plan.json")
        tampered["canonical_plan_hash"] = "0" * 64
        runner.atomic_write_json(self.run_dir / "query_plan.json", tampered)
        with self.assertRaises(runner.RunnerBlocked):
            runner.validate_run_compatibility(self.run_dir, self.test_output_root)

    def test_new_execution_rejects_completed_or_partial_compatible_sibling(self):
        for index, state in enumerate(("EXECUTION_COMPLETED", "EXECUTION_PARTIAL"), 1):
            sibling = self.test_output_root / f"run_20990101_00000{index}"
            sibling.mkdir()
            runner.atomic_write_json(sibling / "manifest.json", {
                "state": state,
                "plan_hash": runner.frozen_plan_hash(),
            })
            with self.subTest(state=state), self.assertRaises(runner.RunnerBlocked):
                runner.ensure_no_completed_sibling(self.test_output_root)
            shutil.rmtree(sibling)

    def test_ambiguous_reserved_attempt_is_never_repeated(self):
        manifest, checkpoint = self.initialize()
        query_id = runner.FROZEN_QUERIES[0]["query_id"]
        checkpoint["queries"][query_id].update({
            "status": "ATTEMPT_RESERVED", "attempts_reserved": 1,
            "physical_call_number": 1, "started_at": runner.utc_now(),
        })
        checkpoint["calls_reserved"] = 1
        runner.atomic_write_json(self.run_dir / "checkpoint.json", checkpoint)
        runner.refresh_outputs(self.run_dir, manifest, checkpoint, self.historical_before)
        with self.assertRaises(runner.RunnerBlocked) as caught:
            runner.validate_run_compatibility(self.run_dir, self.test_output_root)
        self.assertEqual(caught.exception.run_state, "BLOCKED_INTEGRITY")

    def test_raw_response_preserved_normalization_reproducible_and_redacted(self):
        query_item = runner.FROZEN_QUERIES[0]
        payload = self.result_payload(query_item["query_id"], 2)
        payload["results"][0]["content"] = "Bear" + "er " + "abcdefghijklmnopqrstuvwxyz"
        when = "2026-07-18T12:00:00+00:00"
        raw_a, normalized_a = runner.normalize_results(query_item, payload, when)
        raw_b, normalized_b = runner.normalize_results(query_item, payload, when)
        self.assertEqual(raw_a, raw_b)
        self.assertEqual(normalized_a, normalized_b)
        self.assertEqual(raw_a["raw_payload"]["query"], query_item["query_id"])
        self.assertEqual(len(normalized_a), 2)
        self.assertEqual(normalized_a[0]["canonical_url"], "https://example.com/path/1?a=1&b=2")
        self.assertEqual(normalized_a[0]["registrable_domain"], "example.com")
        self.assertIn("[REDACTED]", normalized_a[0]["snippet_content"])
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", json.dumps(raw_a))

    def test_successful_payloads_generate_raw_normalized_domain_and_integrity_schemas(self):
        manifest, checkpoint = self.initialize()

        def fake_backend(query_item):
            return self.completed(self.result_payload(query_item["query_id"], 2))

        exit_code = runner.process_run(
            self.run_dir, manifest, checkpoint, self.historical_before,
            backend=fake_backend,
        )
        self.assertEqual(exit_code, 0)
        schemas = runner.validate_artifacts(self.run_dir, require_completed=True)
        self.assertEqual(schemas["raw_response_rows"], 4)
        self.assertEqual(schemas["normalized_rows"], 8)
        self.assertEqual(schemas["domain_rows"], 1)
        integrity = runner.read_json(self.run_dir / "integrity_manifest.json")
        self.assertTrue(integrity["historical_runs_unchanged"])
        self.assertEqual(set(integrity["artifacts"]), set(runner.REQUIRED_ARTIFACTS) - {"integrity_manifest.json"})
        with (self.run_dir / "domain_summary.csv").open(encoding="utf-8", newline="") as handle:
            domain_rows = list(csv.DictReader(handle))
        self.assertEqual(domain_rows[0]["domain"], "example.com")
        self.assertEqual(domain_rows[0]["result_count"], "8")

    def test_invoke_tvly_search_overlays_utf8_without_replacing_inherited_environment(self):
        fake_environment = {
            "EXISTING_AUTH_CONTEXT": "opaque-inherited-value",
            "PYTHONUTF8": "legacy",
        }
        observed = {}

        def fake_run(*args, **kwargs):
            observed["args"] = args
            observed["kwargs"] = kwargs
            observed["environment_during_call"] = dict(fake_environment)
            return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=b'{"results": []}', stderr=b"")

        with mock.patch.object(runner.os, "environ", fake_environment), \
             mock.patch.object(runner.subprocess, "run", side_effect=fake_run):
            process = runner.invoke_tvly_search(runner.FROZEN_QUERIES[0])

        self.assertEqual(process.returncode, 0)
        self.assertIs(observed["kwargs"]["env"], None)
        self.assertFalse(observed["kwargs"]["text"])
        self.assertEqual(observed["environment_during_call"]["PYTHONUTF8"], "1")
        self.assertEqual(observed["environment_during_call"]["PYTHONIOENCODING"], "utf-8")
        self.assertEqual(observed["environment_during_call"]["EXISTING_AUTH_CONTEXT"], "opaque-inherited-value")
        self.assertEqual(fake_environment["PYTHONUTF8"], "legacy")
        self.assertNotIn("PYTHONIOENCODING", fake_environment)

    def test_historical_cp1252_character_now_round_trips_as_utf8(self):
        text = "📺 Español: café, niño — acción; Greek Ω; CJK 漢字"
        with self.assertRaises(UnicodeEncodeError):
            text.encode("cp1252")
        encoded = text.encode("utf-8")
        split_inside_emoji = [encoded[:1], encoded[1:3], encoded[3:8], encoded[8:]]
        self.assertEqual(runner.decode_child_stream(b"".join(split_inside_emoji), "stdout"), text)

    def test_complete_fake_four_query_execution_preserves_fragmented_unicode(self):
        manifest, checkpoint = self.initialize()
        calls = []
        unicode_text = "📺 Español: café, niño — acción; Greek Ω; CJK 漢字"

        def fake_backend(query_item):
            calls.append(query_item["query_id"])
            payload = {
                "query": query_item["query"],
                "results": [{
                    "title": unicode_text,
                    "url": f"https://example.com/{query_item['sequence']}",
                    "content": unicode_text,
                    "score": 0.75,
                }],
            }
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            emoji_offset = encoded.index("📺".encode("utf-8"))
            fragments = [encoded[:emoji_offset + 1], encoded[emoji_offset + 1:emoji_offset + 3], encoded[emoji_offset + 3:]]
            return subprocess.CompletedProcess(
                args=["tvly", "search"], returncode=0,
                stdout=b"".join(fragments), stderr="aviso español — 📺".encode("utf-8"),
            )

        exit_code = runner.process_run(
            self.run_dir, manifest, checkpoint, self.historical_before,
            backend=fake_backend,
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(calls, [item["query_id"] for item in runner.FROZEN_QUERIES])
        final = runner.read_json(self.run_dir / "checkpoint.json")
        self.assertEqual(final["run_state"], "EXECUTION_COMPLETED")
        self.assertEqual(final["calls_performed"], 4)
        self.assertTrue(all(state["attempts_reserved"] == 1 for state in final["queries"].values()))
        raw_text = (self.run_dir / "raw_results.jsonl").read_text(encoding="utf-8")
        csv_text = (self.run_dir / "normalized_results.csv").read_text(encoding="utf-8")
        self.assertIn(unicode_text, raw_text)
        self.assertIn(unicode_text, csv_text)
        manifest_value = runner.read_json(self.run_dir / "manifest.json")
        self.assertEqual(manifest_value["child_process_text_contract"], runner.CHILD_TEXT_CONTRACT)
        self.assertNotIn("opaque-inherited-value", "\n".join(
            (self.run_dir / name).read_text(encoding="utf-8") for name in runner.REQUIRED_ARTIFACTS
        ))
        runner.validate_artifacts(self.run_dir, require_completed=True)

    def test_empty_and_invalid_json_each_stop_once_without_retry(self):
        for index, stdout in enumerate((b"", b"not-json"), 1):
            run_dir = self.test_output_root / f"run_20990101_00001{index}"
            manifest, checkpoint = runner.initialize_run(
                run_dir, git=self.git, tvly_version=runner.EXPECTED_TVLY_VERSION,
                historical_before=self.historical_before, originated_from_powershell=True,
            )
            calls = []

            def fake_backend(query_item, payload=stdout):
                calls.append(query_item["query_id"])
                return subprocess.CompletedProcess(args=["tvly"], returncode=0, stdout=payload, stderr=b"")

            exit_code = runner.process_run(run_dir, manifest, checkpoint, self.historical_before, backend=fake_backend)
            self.assertEqual(exit_code, 4)
            self.assertEqual(len(calls), 1)
            final = runner.read_json(run_dir / "checkpoint.json")
            self.assertEqual(final["calls_reserved"], 1)
            self.assertEqual(final["calls_performed"], 1)
            self.assertEqual(final["queries"][runner.FROZEN_QUERIES[0]["query_id"]]["status"], "FAILED")

    def test_nonzero_unicode_stderr_and_invalid_utf8_stop_safely_without_retry(self):
        cases = (
            (1, b"", "falló ñ — 📺".encode("utf-8"), "TVLY_PROCESS_ERROR"),
            (0, b"\xff", b"", "TVLY_OUTPUT_DECODE_ERROR"),
        )
        for index, (returncode, stdout, stderr, error_class) in enumerate(cases, 1):
            run_dir = self.test_output_root / f"run_20990101_00002{index}"
            manifest, checkpoint = runner.initialize_run(
                run_dir, git=self.git, tvly_version=runner.EXPECTED_TVLY_VERSION,
                historical_before=self.historical_before, originated_from_powershell=True,
            )
            calls = []

            def fake_backend(query_item, rc=returncode, out=stdout, err=stderr):
                calls.append(query_item["query_id"])
                return subprocess.CompletedProcess(args=["tvly"], returncode=rc, stdout=out, stderr=err)

            exit_code = runner.process_run(run_dir, manifest, checkpoint, self.historical_before, backend=fake_backend)
            self.assertEqual(exit_code, 4)
            self.assertEqual(len(calls), 1)
            final = runner.read_json(run_dir / "checkpoint.json")
            first = final["queries"][runner.FROZEN_QUERIES[0]["query_id"]]
            self.assertEqual(first["error_class"], error_class)
            errors = runner.read_jsonl(run_dir / "errors.jsonl")
            self.assertEqual(errors[0]["error_class"], error_class)
            if returncode == 1:
                self.assertIn("falló ñ — 📺", errors[0]["message"])

    def test_report_contains_no_semantic_verdict(self):
        manifest, checkpoint = self.initialize()
        report = (self.run_dir / "smoke_test_report.md").read_text(encoding="utf-8").upper()
        for term in runner.FORBIDDEN_REPORT_TERMS:
            self.assertNotIn(term, report)
        self.assertIn("TECHNICAL SMOKE-TEST REPORT", report)

    def test_power_shell_block_has_structured_json_auth_gate_and_exit_propagation(self):
        block = runner.powershell_block()
        self.assertTrue(block.startswith("& {\n"))
        self.assertTrue(block.endswith("\n}"))
        self.assertIn("Set-Location -LiteralPath $projectRoot", block)
        self.assertIn("$env:PYTHONUTF8 = '1'", block)
        self.assertIn("$env:PYTHONIOENCODING = 'utf-8'", block)
        self.assertIn("Get-Command tvly -ErrorAction SilentlyContinue", block)
        self.assertEqual(block.count("tvly --status --json"), 1)
        self.assertIn("2> $statusErrorFile", block)
        self.assertIn("($authenticationJson | Out-String).Trim()", block)
        self.assertIn("$authenticationExitCode -ne 0", block)
        self.assertIn("[string]::IsNullOrWhiteSpace($authenticationText)", block)
        self.assertIn("ConvertFrom-Json -ErrorAction Stop", block)
        self.assertIn("Remove-Item -LiteralPath $statusErrorFile -Force -ErrorAction SilentlyContinue", block)
        self.assertEqual(block.count("exit 3"), 4)
        self.assertNotIn("authenticationConfirmed", block)
        self.assertNotIn("available|found|via", block.casefold())
        self.assertEqual(block.count("--execute"), 1)
        self.assertEqual(block.count(runner.APPROVAL_TOKEN), 1)
        self.assertIn("--execution-origin powershell", block)
        self.assertIn("exit $runnerExitCode", block)
        self.assertIn("RUN_DIR=*", block)
        self.assertGreater(block.index("$runnerOutput = & python"), block.index("finally {"))
        credential_variable = "TAVILY_" + "API_KEY"
        self.assertNotIn(credential_variable + " =", block)
        self.assertNotIn(credential_variable + "=", block)

    def test_protected_historical_runs_are_byte_identical_after_offline_checks(self):
        before = runner.protected_fingerprints()
        runner.dry_run_summary()
        after = runner.protected_fingerprints()
        self.assertTrue(runner.protected_hashes_match(before, after))
        self.assertEqual(
            {name: value["aggregate_sha256"] for name, value in before.items()},
            {name: value["aggregate_sha256"] for name, value in after.items()},
        )


if __name__ == "__main__":
    unittest.main()
