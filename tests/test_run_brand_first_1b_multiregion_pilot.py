from __future__ import annotations

import importlib.util
import io
import shutil
import unittest
import uuid
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "scripts" / "run_brand_first_1b_multiregion_pilot.py"
SPEC = importlib.util.spec_from_file_location("multiregion_pilot", MODULE_PATH)
assert SPEC and SPEC.loader
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


class FakeClient:
    def __init__(self) -> None:
        self.search_calls: list[dict] = []
        self.map_calls: list[dict] = []
        self.extract_calls: list[dict] = []

    def search(self, **kwargs):
        self.search_calls.append(kwargs)
        number = len(self.search_calls)
        return {
            "results": [{
                "title": f"Comparativa IPTV número {number}",
                "url": f"https://source{number}.example.com/list?utm_source=test",
                "content": "Reseña de mercado independiente",
                "score": 0.9,
            }]
        }

    def map(self, **kwargs):
        self.map_calls.append(kwargs)
        return {"results": [kwargs["url"] + "/concrete-review"]}

    def extract(self, **kwargs):
        self.extract_calls.append(kwargs)
        return {"results": [{"url": kwargs["urls"][0], "raw_content": "Marca Ñandú"}]}


class MultiregionPilotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_root = PROJECT_ROOT / f".tmp_multiregion_pilot_{uuid.uuid4().hex}"
        self.temp_root.mkdir()

    def tearDown(self) -> None:
        if self.temp_root.exists():
            shutil.rmtree(self.temp_root)

    def make_extract_ready_run(self, page_count: int = 8) -> Path:
        run_dir = self.temp_root / "run_extract_ready"
        run_dir.mkdir()
        manifest, checkpoint = pilot.initialize_run(run_dir)
        for operation in checkpoint["operations"].values():
            operation.update({"state": "COMPLETED", "attempts": 1})
        for index in range(1, 6):
            checkpoint["operations"][f"map_fixture_{index:02d}"] = {
                "stage": "map", "state": "COMPLETED", "attempts": 1,
                "result_count": 0, "raw_record_ids": [],
            }
        checkpoint["operations_used"] = {"search": 10, "map": 5, "extract": 0, "global": 15}
        checkpoint["run_state"] = "AWAITING_OFFLINE_EXTRACT_SELECTION"
        checkpoint["active_stage"] = "offline_extract_selection"
        mapped_rows = []
        selected_pages = []
        for index in range(1, page_count + 1):
            url = f"https://fixture{((index - 1) % 3) + 1}.example/reseña-{index}"
            map_row_id = f"maprow_fixture_{index:02d}"
            mapped_rows.append({
                "map_row_id": map_row_id,
                "map_operation_id": f"map_fixture_{((index - 1) % 5) + 1:02d}",
                "selection_id": f"map_selection_{((index - 1) % 5) + 1:02d}",
                "source_url": "https://fixture.example/seed",
                "mapped_rank": index,
                "mapped_url": url,
                "canonical_url": url,
                "domain": f"fixture{((index - 1) % 3) + 1}.example",
                "raw_record_id": f"map_raw_fixture_{index:02d}",
            })
            selected_pages.append({
                "selection_id": f"extract_selection_{index:02d}",
                "url": url,
                "map_source_id": map_row_id,
                "mapped_url": url,
                "selection_reason": f"Página útil número {index}",
                "supporting_row_ids": [map_row_id],
            })
        pilot.write_csv(run_dir / "mapped_pages.csv", pilot.MAPPED_FIELDS, mapped_rows)
        pilot.checkpoint_write(run_dir, checkpoint)
        pilot.refresh_outputs(run_dir, manifest, checkpoint)
        selection_plan = {
            "schema_version": "brand_first_market_universe_1b_extract_selection_plan.v1",
            "run_id": run_dir.name,
            "checkpoint_state": checkpoint["run_state"],
            "extract_budget_max": pilot.BUDGET["extract"],
            "selected_map_row_ids": [item["map_source_id"] for item in selected_pages],
        }
        pilot.atomic_write_json(run_dir / "extract_selection.json", {
            "schema_version": pilot.SCHEMA_VERSION,
            "selection_status": "APPROVED",
            "selection_plan": selection_plan,
            "selection_plan_sha256": pilot.sha256_json(selection_plan),
            "selected_pages": selected_pages,
        })
        return run_dir

    def test_frozen_contract_and_dry_run_are_offline(self) -> None:
        summary = pilot.dry_run_summary()
        self.assertEqual(10, summary["search_operations"])
        self.assertEqual(
            {"search": 10, "map": 5, "extract": 10, "global": 25,
             "absolute_global_ceiling": 30, "automatic_retries": 0},
            summary["budgets"],
        )
        self.assertEqual(0, summary["credential_reads"])
        self.assertEqual(0, summary["client_instances"])
        self.assertEqual(0, summary["network_operations"])
        self.assertFalse(summary["run_created"])
        self.assertFalse(summary["blocked_capabilities"]["crawl"]["authorized"])
        self.assertFalse(summary["blocked_capabilities"]["research"]["authorized"])
        self.assertEqual([], list(self.temp_root.iterdir()))

    def test_minus_one_client_termination_is_normalized_before_reservation(self) -> None:
        run_dir = self.make_extract_ready_run()
        protected = {
            name: pilot.sha256_file(run_dir / name)
            for name in ("integrity_manifest.json", "checkpoint.json", "operation_ledger.jsonl")
        }
        key_reads: list[str] = []

        def terminated_factory(key: str):
            raise SystemExit(-1)

        with self.assertRaises(pilot.RunnerBlocked) as caught:
            pilot.resume_run(
                run_dir, "extract", output_root=self.temp_root,
                client_factory=terminated_factory,
                api_key_reader=lambda name: key_reads.append(name) or "fake-test-key",
            )
        self.assertEqual("BLOCKED_CLIENT_INITIALIZATION", caught.exception.run_state)
        self.assertEqual(pilot.EXIT_TECHNICAL, caught.exception.exit_code)
        self.assertIn("terminated unexpectedly with code -1", str(caught.exception))
        self.assertIn("no operation was reserved", str(caught.exception))
        self.assertEqual(["TAVILY_API_KEY"], key_reads)
        self.assertEqual(
            protected,
            {name: pilot.sha256_file(run_dir / name) for name in protected},
        )
        self.assertFalse(any(
            row.get("event") == "ATTEMPT_RESERVED" and row.get("stage") == "extract"
            for row in pilot.read_jsonl(run_dir / "operation_ledger.jsonl")
        ))

        stderr = io.StringIO()
        with mock.patch.object(pilot, "resume_run", side_effect=caught.exception):
            with redirect_stderr(stderr):
                exit_code = pilot.main([
                    "--resume-run", str(run_dir), "--stage", "extract",
                    "--approval-token", pilot.APPROVAL_TOKEN,
                    "--execution-origin", "powershell",
                ])
        self.assertEqual(pilot.EXIT_TECHNICAL, exit_code)
        self.assertIn("BLOCKED_CLIENT_INITIALIZATION", stderr.getvalue())
        self.assertIn("no operation was reserved", stderr.getvalue())

    def test_approved_eight_page_extract_reaches_reservation_and_completes_once(self) -> None:
        run_dir = self.make_extract_ready_run()

        class ReservationObservingClient(FakeClient):
            def extract(inner_self, **kwargs):
                ledger = pilot.read_jsonl(run_dir / "operation_ledger.jsonl")
                self.assertEqual("ATTEMPT_RESERVED", ledger[-1]["event"])
                self.assertEqual("extract", ledger[-1]["stage"])
                checkpoint = pilot.read_json(run_dir / "checkpoint.json")
                self.assertEqual(
                    "ATTEMPT_RESERVED",
                    checkpoint["operations"][ledger[-1]["operation_id"]]["state"],
                )
                inner_self.extract_calls.append(kwargs)
                return {"results": [{
                    "url": kwargs["urls"][0],
                    "raw_content": "Marca Ñandú — comparación útil",
                }]}

        client = ReservationObservingClient()
        code, _ = pilot.resume_run(
            run_dir, "extract", output_root=self.temp_root,
            client_factory=lambda key: client,
            api_key_reader=lambda name: "fake-test-key",
        )
        self.assertEqual(pilot.EXIT_SUCCESS, code)
        self.assertEqual(8, len(client.extract_calls))
        checkpoint = pilot.read_json(run_dir / "checkpoint.json")
        self.assertEqual({"search": 10, "map": 5, "extract": 8, "global": 23}, checkpoint["operations_used"])
        extract_operations = [
            operation for operation in checkpoint["operations"].values()
            if operation["stage"] == "extract"
        ]
        self.assertEqual(8, len(extract_operations))
        self.assertTrue(all(operation["state"] == "COMPLETED" for operation in extract_operations))
        self.assertTrue(all(operation["attempts"] == 1 for operation in extract_operations))
        self.assertEqual(8, len(pilot.read_jsonl(run_dir / "extracted_pages.jsonl")))
        self.assertEqual([], pilot.read_jsonl(run_dir / "errors.jsonl"))
        self.assertIn("Marca Ñandú — comparación útil", (run_dir / "extracted_pages.jsonl").read_text(encoding="utf-8"))
        pilot.validate_artifacts(run_dir, allow_incomplete=False)

        late_key_reads: list[str] = []
        for completed_stage in ("search", "map", "extract"):
            with self.subTest(completed_stage=completed_stage):
                with self.assertRaises(pilot.RunnerBlocked) as blocked:
                    pilot.resume_run(
                        run_dir, completed_stage, output_root=self.temp_root,
                        client_factory=lambda key: self.fail("client must not be created"),
                        api_key_reader=lambda name: late_key_reads.append(name) or "unused",
                    )
                self.assertEqual("BLOCKED_STAGE", blocked.exception.run_state)
        self.assertEqual([], late_key_reads)

    def test_corrupt_extract_selection_hash_blocks_clearly_before_client(self) -> None:
        run_dir = self.make_extract_ready_run()
        selection = pilot.read_json(run_dir / "extract_selection.json")
        selection["selection_plan_sha256"] = "0" * 64
        pilot.atomic_write_json(run_dir / "extract_selection.json", selection)
        key_reads: list[str] = []
        with self.assertRaises(pilot.RunnerBlocked) as caught:
            pilot.resume_run(
                run_dir, "extract", output_root=self.temp_root,
                client_factory=lambda key: self.fail("client must not be created"),
                api_key_reader=lambda name: key_reads.append(name) or "unused",
            )
        self.assertEqual("BLOCKED_SELECTION", caught.exception.run_state)
        self.assertEqual(pilot.EXIT_CONFIGURATION, caught.exception.exit_code)
        self.assertIn("plan hash mismatch", str(caught.exception))
        self.assertEqual([], key_reads)
        checkpoint = pilot.read_json(run_dir / "checkpoint.json")
        self.assertEqual(0, checkpoint["operations_used"]["extract"])

    def test_complete_staged_fake_flow_uses_exact_parameters_and_no_retries(self) -> None:
        client = FakeClient()
        key_reads: list[str] = []

        def key_reader(name: str) -> str:
            key_reads.append(name)
            return "fake-test-key"

        code, run_dir = pilot.execute_new(
            output_root=self.temp_root,
            client_factory=lambda key: client,
            api_key_reader=key_reader,
            stamp="20260718_120000",
        )
        self.assertEqual(0, code)
        assert run_dir is not None
        checkpoint = pilot.read_json(run_dir / "checkpoint.json")
        self.assertEqual("AWAITING_OFFLINE_SOURCE_SELECTION", checkpoint["run_state"])
        self.assertEqual(10, len(client.search_calls))
        for query, call in zip(pilot.SEARCH_QUERIES, client.search_calls):
            self.assertEqual(query["query"], call["query"])
            self.assertEqual(pilot.SEARCH_CONFIG, {k: v for k, v in call.items() if k != "query"})

        sources = pilot.read_csv(run_dir / "source_registry.csv")
        pilot.atomic_write_json(run_dir / "source_selection.json", {
            "schema_version": pilot.SCHEMA_VERSION,
            "selection_status": "APPROVED",
            "selected_sources": [
                {"selection_id": f"source_{index}", "source_url": row["canonical_url"]}
                for index, row in enumerate(sources[:2], start=1)
            ],
        })
        code, _ = pilot.resume_run(
            run_dir, "map", output_root=self.temp_root,
            client_factory=lambda key: client, api_key_reader=key_reader,
        )
        self.assertEqual(0, code)
        self.assertEqual(2, len(client.map_calls))
        for call in client.map_calls:
            self.assertEqual(pilot.MAP_CONFIG, {k: v for k, v in call.items() if k != "url"})

        mapped = pilot.read_csv(run_dir / "mapped_pages.csv")
        pilot.atomic_write_json(run_dir / "extract_selection.json", {
            "schema_version": pilot.SCHEMA_VERSION,
            "selection_status": "APPROVED",
            "selected_pages": [
                {"selection_id": f"page_{index}", "url": row["canonical_url"]}
                for index, row in enumerate(mapped[:2], start=1)
            ],
        })
        code, _ = pilot.resume_run(
            run_dir, "extract", output_root=self.temp_root,
            client_factory=lambda key: client, api_key_reader=key_reader,
        )
        self.assertEqual(0, code)
        self.assertEqual(2, len(client.extract_calls))
        for call in client.extract_calls:
            self.assertEqual(pilot.EXTRACT_CONFIG, {k: v for k, v in call.items() if k != "urls"})
            self.assertEqual(1, len(call["urls"]))

        validated = pilot.validate_artifacts(run_dir, allow_incomplete=False)
        checkpoint = validated["checkpoint"]
        self.assertEqual(
            "ACQUISITION_COMPLETED_PENDING_OFFLINE_CONSOLIDATION",
            checkpoint["run_state"],
        )
        self.assertEqual({"search": 10, "map": 2, "extract": 2, "global": 14}, checkpoint["operations_used"])
        self.assertTrue(all(item["attempts"] <= 1 for item in checkpoint["operations"].values()))
        self.assertEqual(0, len(pilot.read_jsonl(run_dir / "errors.jsonl")))
        self.assertEqual(set(pilot.REQUIRED_ARTIFACTS), {path.name for path in run_dir.iterdir()})
        self.assertIn("Marca Ñandú", (run_dir / "extracted_pages.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(0, pilot.artifact_secret_findings(run_dir))
        metrics = pilot.read_json(run_dir / "pilot_metrics.json")
        self.assertEqual(set("ABCDE"), set(metrics["sources_by_provisional_level"]))
        self.assertEqual(10, metrics["marginal_value_by_stage"]["search_unique_source_urls"])
        self.assertEqual(2, metrics["marginal_value_by_stage"]["map_new_unique_urls"])
        self.assertEqual(2, metrics["marginal_value_by_stage"]["extract_page_envelopes"])
        self.assertEqual("PENDING_OFFLINE_CONSOLIDATION", metrics["seo_duplication_review_status"])
        self.assertEqual(["TAVILY_API_KEY"] * 3, key_reads)

        calls_before_blocked_resumes = (
            len(client.search_calls), len(client.map_calls), len(client.extract_calls), len(key_reads)
        )
        for completed_stage in ("search", "map", "extract"):
            with self.subTest(completed_stage=completed_stage):
                with self.assertRaises(pilot.RunnerBlocked) as caught:
                    pilot.resume_run(
                        run_dir, completed_stage, output_root=self.temp_root,
                        client_factory=lambda key: client, api_key_reader=key_reader,
                    )
                self.assertEqual("BLOCKED_STAGE", caught.exception.run_state)
        self.assertEqual(calls_before_blocked_resumes, (
            len(client.search_calls), len(client.map_calls), len(client.extract_calls), len(key_reads)
        ))

    def test_existing_compatible_run_blocks_before_key_client_or_new_directory(self) -> None:
        run_dir = self.temp_root / "run_existing"
        run_dir.mkdir()
        pilot.initialize_run(run_dir)
        key_reads = 0
        client_creations = 0

        def key_reader(name: str) -> str:
            nonlocal key_reads
            key_reads += 1
            return "unused"

        def factory(key: str):
            nonlocal client_creations
            client_creations += 1
            return FakeClient()

        with self.assertRaises(pilot.RunnerBlocked) as caught:
            pilot.execute_new(
                output_root=self.temp_root, client_factory=factory,
                api_key_reader=key_reader, stamp="20260718_120001",
            )
        self.assertEqual("BLOCKED_EXISTING_RUN", caught.exception.run_state)
        self.assertEqual(0, key_reads)
        self.assertEqual(0, client_creations)
        self.assertEqual([run_dir], list(self.temp_root.iterdir()))

    def test_invalid_offline_selection_blocks_before_key_or_client(self) -> None:
        run_dir = self.temp_root / "run_invalid_selection"
        run_dir.mkdir()
        manifest, checkpoint = pilot.initialize_run(run_dir)
        checkpoint["run_state"] = "AWAITING_OFFLINE_SOURCE_SELECTION"
        checkpoint["active_stage"] = "offline_source_selection"
        pilot.checkpoint_write(run_dir, checkpoint)
        pilot.refresh_outputs(run_dir, manifest, checkpoint)
        pilot.atomic_write_json(run_dir / "source_selection.json", {
            "schema_version": pilot.SCHEMA_VERSION,
            "selection_status": "APPROVED",
            "selected_sources": [{"source_url": "https://unseen.example/path"}],
        })
        key_reads: list[str] = []
        with self.assertRaises(pilot.RunnerBlocked) as caught:
            pilot.resume_run(
                run_dir, "map", output_root=self.temp_root,
                client_factory=lambda key: self.fail("client must not be created"),
                api_key_reader=lambda name: key_reads.append(name) or "unused",
            )
        self.assertEqual("BLOCKED_SELECTION", caught.exception.run_state)
        self.assertEqual([], key_reads)

    def test_authentication_error_stops_on_first_attempt_without_retry(self) -> None:
        class AuthFailureClient(FakeClient):
            def search(self, **kwargs):
                self.search_calls.append(kwargs)
                raise RuntimeError("401 unauthorized tvly-secret-must-be-redacted")

        client = AuthFailureClient()
        code, run_dir = pilot.execute_new(
            output_root=self.temp_root,
            client_factory=lambda key: client,
            api_key_reader=lambda name: "fake-test-key",
            stamp="20260718_120002",
        )
        self.assertEqual(pilot.EXIT_AUTHENTICATION, code)
        assert run_dir is not None
        self.assertEqual(1, len(client.search_calls))
        checkpoint = pilot.read_json(run_dir / "checkpoint.json")
        self.assertEqual("STOPPED_ON_ERROR", checkpoint["run_state"])
        self.assertEqual(1, checkpoint["operations_used"]["global"])
        errors = pilot.read_jsonl(run_dir / "errors.jsonl")
        self.assertEqual("AUTHENTICATION_ERROR", errors[0]["error_signature"])
        self.assertFalse(errors[0]["retry_performed"])
        self.assertNotIn("tvly-secret-must-be-redacted", (run_dir / "errors.jsonl").read_text(encoding="utf-8"))

    def test_structural_error_stops_on_first_attempt_without_retry(self) -> None:
        class StructuralFailureClient(FakeClient):
            def search(self, **kwargs):
                self.search_calls.append(kwargs)
                return {"unexpected": []}

        client = StructuralFailureClient()
        code, run_dir = pilot.execute_new(
            output_root=self.temp_root,
            client_factory=lambda key: client,
            api_key_reader=lambda name: "fake-test-key",
            stamp="20260718_120003",
        )
        self.assertEqual(pilot.EXIT_TECHNICAL, code)
        assert run_dir is not None
        self.assertEqual(1, len(client.search_calls))
        checkpoint = pilot.read_json(run_dir / "checkpoint.json")
        self.assertEqual("STOPPED_ON_ERROR", checkpoint["run_state"])
        self.assertEqual(1, checkpoint["operations_used"]["global"])
        self.assertEqual(
            "STRUCTURAL_RESPONSE_ERROR",
            pilot.read_jsonl(run_dir / "errors.jsonl")[0]["error_signature"],
        )

    def test_powershell_block_keeps_window_open_and_prints_guard_message(self) -> None:
        block = pilot.powershell_block()
        self.assertNotIn("exit $runnerExitCode", block)
        self.assertIn('Write-Output "RUNNER_EXIT_CODE=$runnerExitCode"', block)
        self.assertIn("NEXT_STAGE=OFFLINE_SOURCE_SELECTION_BEFORE_MAP", block)
        self.assertIn("DO_NOT_RUN_AGAIN_IF_RUN_DIR_WAS_PRINTED", block)
        self.assertNotIn("tvly-", block.lower())


if __name__ == "__main__":
    unittest.main()
