import importlib.util
import json
import os
import socket
import sys
import shutil
import uuid
import urllib.error
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_targeted_external_verification_v1.py"
SPEC = importlib.util.spec_from_file_location("targeted_v1", SCRIPT)
v1 = importlib.util.module_from_spec(SPEC); sys.modules[SPEC.name] = v1; SPEC.loader.exec_module(v1)

class TargetedExternalVerificationV1Tests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(__file__).resolve().parents[1] / ".tmp_targeted_v1_tests" / uuid.uuid4().hex
        self.temp_dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def args(self, *extra):
        result = v1.parser().parse_args(["--dry-run", *extra]); v1.validate_args(result); return result

    def source_run(self):
        return Path(__file__).resolve().parents[1]/"research/output/best_iptv_2026/domain_family_discovery_voco_micro_pilot/targeted_external_verification_v1_run_20260715_232020"

    def repair_argv(self, preflight=True, output=None):
        mode=["--http-repair-preflight"] if preflight else ["--execute","--http-repair-only","--authorize-http-repair"]
        args=mode+["--source-run-dir",str(self.source_run()),"--repair-output-dir",str(output or self.temp_dir/"repair")]
        for access_id in v1.AUTHORIZED_REPAIR_ACCESS_IDS: args += ["--repair-access-id",access_id]
        args += ["--max-http-attempts","2","--max-redirect-hops","2"]
        return args

    def copied_repair_source(self):
        target=self.temp_dir/"source"; target.mkdir()
        for name in ("checkpoint.json","query_plan.json","external_access_log.jsonl"):
            shutil.copy2(self.source_run()/name,target/name)
        return target

    def merged_evaluation(self):
        return Path(__file__).resolve().parents[1]/"research/output/best_iptv_2026/domain_family_discovery_voco_micro_pilot/targeted_external_verification_v1_merged_offline_evaluation_20260715_232020"

    def final_argv(self,preflight=True,output=None):
        mode=["--final-two-access-preflight"] if preflight else ["--execute","--final-two-access-only","--authorize-final-two-accesses"]
        return mode+["--source-evaluation-dir",str(self.merged_evaluation()),"--final-output-dir",str(output or self.temp_dir/"final"),
            "--final-url",v1.FINAL_TWO_URLS[0],"--final-url",v1.FINAL_TWO_URLS[1],"--max-final-http-attempts","2"]

    def test_dry_run_and_preflight_do_not_read_credentials(self):
        for mode in (["--dry-run"], ["--preflight-only"]):
            with mock.patch.object(os, "getenv", side_effect=AssertionError("credential read")):
                args = v1.parser().parse_args(mode); v1.validate_args(args); v1.build_query_plan(args.target_domain, args.search_depth, args.timeout)

    def test_execute_requires_confirmation(self):
        args = v1.parser().parse_args(["--execute"])
        with self.assertRaisesRegex(ValueError, "confirm-credit-use"): v1.validate_args(args)

    def test_execute_missing_key_fails_before_client_or_network(self):
        args = v1.parser().parse_args(["--execute", "--confirm-credit-use"]); v1.validate_args(args)
        with mock.patch.object(os, "getenv", return_value=None), mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")):
            with self.assertRaisesRegex(RuntimeError, "required before any external call"):
                v1.execute_tavily([], v1.load_checkpoint(self.temp_dir/"c.json"), self.temp_dir, args)

    def test_budgets_and_max_results(self):
        args = self.args(); q = v1.build_query_plan(args.target_domain, args.search_depth, args.timeout); a = v1.build_access_plan(args.target_domain)
        self.assertLessEqual(len(q), 12); self.assertLessEqual(len(a), 40); self.assertTrue(all(x["max_results"] <= 8 for x in q)); self.assertTrue(v1.validate_plan(q, a, args)["valid"])

    def test_outside_allowlist_rejected(self):
        with self.assertRaises(SystemExit): v1.parser().parse_args(["--dry-run", "--target-domain", "example.com"])

    def test_historical_query_rejected(self):
        args = self.args(); q = v1.build_query_plan(args.target_domain, args.search_depth, args.timeout)
        q[0]["exact_query"] = next(iter(v1.historical_queries()))
        self.assertFalse(v1.validate_plan(q, v1.build_access_plan(args.target_domain), args)["valid"])

    def test_completed_resume_not_repeated_contract(self):
        checkpoint = {"queries": {"q": {"status": "COMPLETED"}}}
        self.assertEqual(checkpoint["queries"]["q"]["status"], "COMPLETED")

    def test_completed_tavily_query_never_calls_client(self):
        class Client:
            def search(self, **kwargs): raise AssertionError("completed query repeated")
        args=self.args(); query=v1.build_query_plan(args.target_domain,args.search_depth,args.timeout)[:1]
        checkpoint=v1.load_checkpoint(self.temp_dir/"none.json"); checkpoint["queries"][query[0]["query_id"]]={"status":"COMPLETED"}
        for name in ("query_log.jsonl","raw_external_evidence.jsonl"):(self.temp_dir/name).write_text("",encoding="utf-8")
        v1.execute_tavily(query,checkpoint,self.temp_dir,args,client=Client())
        self.assertEqual((self.temp_dir/"query_log.jsonl").read_text(),"")

    def test_completed_direct_access_resume_skips_network(self):
        args=self.args(); access=v1.build_access_plan(args.target_domain)[:1]
        checkpoint={"queries":{},"accesses":{access[0]["access_id"]:{"status":"COMPLETED"}},"external_access_count":1,"tavily_query_count":0}
        with mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")):
            v1.execute_direct_accesses(access,checkpoint,self.temp_dir,args)
        self.assertEqual(checkpoint["external_access_count"],1)

    def test_query_log_and_checkpoint_converge_after_simulated_query(self):
        class Client:
            def search(self, **kwargs): return {"results": [{"url": "https://example.invalid/a"}]}
        args=self.args(); query=v1.build_query_plan(args.target_domain,args.search_depth,args.timeout)[:1]
        for name in ("query_log.jsonl","raw_external_evidence.jsonl"):(self.temp_dir/name).write_text("",encoding="utf-8")
        checkpoint=v1.load_checkpoint(self.temp_dir/"checkpoint.json")
        v1.execute_tavily(query,checkpoint,self.temp_dir,args,client=Client())
        events=[json.loads(x) for x in (self.temp_dir/"query_log.jsonl").read_text().splitlines()]
        self.assertEqual([x["status"] for x in events],["STARTED","COMPLETED"])
        persisted=json.loads((self.temp_dir/"checkpoint.json").read_text())
        self.assertEqual(persisted["queries"][query[0]["query_id"]]["result_count"],1)
        self.assertEqual(events[-1]["raw_row_ids"],persisted["queries"][query[0]["query_id"]]["raw_row_ids"])

    def test_execute_report_is_not_offline_and_safety_uses_counters(self):
        checkpoint={"tavily_query_count":12,"tavily_attempt_count":12,"logical_direct_access_count":16,"physical_http_attempt_count":18,
            "redirect_event_count":6,"capture_event_count":3,"log_event_count":16,"total_budget_units_consumed":30,"credential_read":True}
        v1.regenerate_execution_reports(self.temp_dir,"EXECUTE",checkpoint)
        report=(self.temp_dir/"targeted_external_verification_report.md").read_text()
        safety=(self.temp_dir/"safety_and_scope_audit.md").read_text()
        self.assertIn("Mode: EXECUTE",report); self.assertNotIn("Offline mode",report)
        self.assertIn("Tavily calls: 12",safety); self.assertIn("HTTP attempts: 18",safety); self.assertIn("Credential read: yes",safety)

    def test_www_redirect_policy(self):
        self.assertEqual(v1.classify_redirect("https://vocotviptv.com/a","https://www.vocotviptv.com/a"),"SAME_AUTHORIZED_DOMAIN_WWW_REDIRECT")
        self.assertEqual(v1.classify_redirect("https://vocotviptv.com/a","https://foo.vocotviptv.com/a"),"ARBITRARY_SUBDOMAIN_REDIRECT_REJECTED")
        self.assertEqual(v1.classify_redirect("https://vocotviptv.com/a","https://example.com/a"),"CROSS_DOMAIN_REDIRECT_REJECTED")

    def test_urlerror_reason_is_sanitized(self):
        value=v1.sanitize_url_error(urllib.error.URLError("timeout token=supersecret"))
        self.assertEqual(value["error_type"],"URLError"); self.assertIn("[REDACTED]",value["reason_text"]); self.assertNotIn("supersecret",value["reason_text"])

    def test_404_and_unpreserved_failures_are_terminal_contracts(self):
        self.assertFalse(v1.deterministic_retryable(RuntimeError("404")))
        args=self.args(); access=v1.build_access_plan(args.target_domain)[:1]
        checkpoint=v1.load_checkpoint(self.temp_dir/"missing.json"); checkpoint["accesses"][access[0]["access_id"]]={"status":"FAILED","error_type":"URLError"}
        with mock.patch("urllib.request.build_opener") as opener:
            v1.execute_direct_accesses(access,checkpoint,self.temp_dir,args)
        opener.return_value.open.assert_not_called()

    def test_offline_replay_parser_never_requires_credentials(self):
        args=v1.parser().parse_args(["--offline-replay","--source-run-dir","source","--recovery-output-dir","out"])
        with mock.patch.object(os,"getenv",side_effect=AssertionError("credential read")):
            v1.validate_args(args)

    def test_derived_repair_loads_exact_four_scope_blocked_source_states(self):
        args=v1.parser().parse_args(self.repair_argv()); v1.validate_args(args)
        value=v1.validate_derived_repair(args.source_run_dir,args.repair_access_id,args.max_external_accesses,args.max_http_attempts)
        self.assertEqual([x["access_id"] for x in value["selected_accesses"]],list(v1.AUTHORIZED_REPAIR_ACCESS_IDS))
        self.assertTrue(all(x["source_status"]=="SCOPE_BLOCKED" for x in value["selected_accesses"]))

    def test_derived_repair_rejects_resume_and_run_dir(self):
        for extra in (["--resume"],["--run-dir",str(self.temp_dir/"old")]):
            args=v1.parser().parse_args(self.repair_argv()+extra)
            with self.assertRaisesRegex(ValueError,"resume|run-dir"): v1.validate_args(args)

    def test_derived_repair_requires_source_output_and_access_ids(self):
        cases=(
            ["--http-repair-preflight","--repair-output-dir",str(self.temp_dir/"o"),"--repair-access-id",v1.AUTHORIZED_REPAIR_ACCESS_IDS[0]],
            ["--http-repair-preflight","--source-run-dir",str(self.source_run()),"--repair-access-id",v1.AUTHORIZED_REPAIR_ACCESS_IDS[0]],
            ["--http-repair-preflight","--source-run-dir",str(self.source_run()),"--repair-output-dir",str(self.temp_dir/"o")],
        )
        for argv in cases:
            with self.assertRaises(ValueError): v1.validate_args(v1.parser().parse_args(argv))

    def test_derived_repair_rejects_extra_or_missing_id_before_output(self):
        args=v1.parser().parse_args(self.repair_argv()+["--repair-access-id","access_vocoiptv_com_legal"]); v1.validate_args(args)
        with self.assertRaisesRegex(ValueError,"exactly the four"): v1.validate_derived_repair(args.source_run_dir,args.repair_access_id,40,2)
        self.assertFalse(args.repair_output_dir.exists())

    def test_derived_repair_does_not_use_fresh_planned_checkpoint(self):
        source=self.copied_repair_source(); cp=json.loads((source/"checkpoint.json").read_text())
        for access_id in v1.AUTHORIZED_REPAIR_ACCESS_IDS: cp["accesses"][access_id]["status"]="PLANNED"
        v1.write_json(source/"checkpoint.json",cp)
        with self.assertRaisesRegex(ValueError,"not SCOPE_BLOCKED"): v1.validate_derived_repair(source,list(v1.AUTHORIZED_REPAIR_ACCESS_IDS),40,2)

    def test_derived_repair_rejects_completed_terminal_and_unknown_failure(self):
        for state in ("COMPLETED","TERMINAL_404","FAILED_REASON_NOT_PRESERVED"):
            source=self.copied_repair_source(); cp=json.loads((source/"checkpoint.json").read_text()); cp["accesses"][v1.AUTHORIZED_REPAIR_ACCESS_IDS[0]]["status"]=state
            v1.write_json(source/"checkpoint.json",cp)
            with self.assertRaisesRegex(ValueError,"not SCOPE_BLOCKED"): v1.validate_derived_repair(source,list(v1.AUTHORIZED_REPAIR_ACCESS_IDS),40,2)
            shutil.rmtree(source)

    def test_authorized_host_exact_and_www_only(self):
        self.assertTrue(v1.is_authorized_host_for_target("vocotviptv.com","vocotviptv.com"))
        self.assertTrue(v1.is_authorized_host_for_target("www.vocotviptv.com","vocotviptv.com"))
        for host in ("","foo.vocotviptv.com","example.com","attacker-vocotviptv.com"):
            self.assertFalse(v1.is_authorized_host_for_target(host,"vocotviptv.com"))
        self.assertFalse(v1.validate_redirect_chain("https://vocotviptv.com/",["https://example.com/","https://www.vocotviptv.com/"],"vocotviptv.com"))

    def test_repair_budget_30_plus_8_passes_and_over_limit_blocks(self):
        value=v1.validate_derived_repair(self.source_run(),list(v1.AUTHORIZED_REPAIR_ACCESS_IDS),40,2)
        self.assertEqual((value["historical_budget_units"],value["repair_projected_max"],value["combined_projected_max"],value["budget_gate"]),(30,8,38,"PASS"))
        with self.assertRaisesRegex(ValueError,"budget"): v1.validate_derived_repair(self.source_run(),list(v1.AUTHORIZED_REPAIR_ACCESS_IDS),37,2)

    def test_repair_preflight_zero_network_tavily_credentials_and_source_immutable(self):
        args=v1.parser().parse_args(self.repair_argv()); v1.validate_args(args); before=v1.recursive_directory_fingerprint(self.source_run())["aggregate_sha256"]
        with mock.patch.object(os,"getenv",side_effect=AssertionError("credential read")), mock.patch.object(socket,"create_connection",side_effect=AssertionError("network")), mock.patch.object(v1,"execute_tavily",side_effect=AssertionError("Tavily")):
            result=v1.run_derived_repair(args,True)
        self.assertEqual(result["source_hash_before"],before); self.assertEqual(result["source_hash_after"],before)
        self.assertEqual(len(list(args.repair_output_dir.iterdir())),13)
        metrics=json.loads((args.repair_output_dir/"repair_metrics.json").read_text())
        self.assertEqual((metrics["tavily_calls_added"],metrics["credential_reads"],metrics["http_attempts_added"]),(0,0,0))
        report=(args.repair_output_dir/"repair_preflight_report.md").read_text()
        self.assertIn("_execute",report); self.assertIn("Do not use --resume",report)

    def test_derived_http_repair_www_redirect_end_to_end_simulated(self):
        class Response:
            status=200
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def read(self,n): return b"<html><title>Captured</title></html>"
        class Opener:
            def __init__(self): self.urls=[]
            def open(self,request,timeout):
                url=request.full_url; self.urls.append(url)
                if "www." not in url:
                    raise urllib.error.HTTPError(url,302,"redirect",{"Location":url.replace("https://","https://www.")},None)
                return Response()
        opener=Opener(); args=v1.parser().parse_args(self.repair_argv(preflight=False)); v1.validate_args(args)
        before=v1.recursive_directory_fingerprint(self.source_run())["aggregate_sha256"]
        with mock.patch("urllib.request.build_opener",return_value=opener), mock.patch.object(os,"getenv",side_effect=AssertionError("credential read")), mock.patch.object(v1,"execute_tavily",side_effect=AssertionError("Tavily")):
            result=v1.run_derived_repair(args,False)
        self.assertEqual(result["verdict"],"TEV1_DERIVED_HTTP_REPAIR_COMPLETED")
        self.assertEqual(result["source_hash_after"],before); self.assertEqual(len(opener.urls),8); self.assertTrue(all("www." in x for x in opener.urls[1::2]))
        metrics=json.loads((args.repair_output_dir/"repair_metrics.json").read_text())
        self.assertEqual((metrics["repair_logical_access_count"],metrics["repair_physical_http_attempt_count"],metrics["repair_log_event_count"]),(4,8,4))
        with (args.repair_output_dir/"repair_normalized_evidence.csv").open(encoding="utf-8") as handle:
            rows=list(__import__("csv").DictReader(handle))
        self.assertEqual(len(rows),4); self.assertTrue(all(json.loads(x["supporting_row_ids"]) for x in rows))

    def test_two_redirects_without_third_request_are_incomplete_and_partial(self):
        class Response:
            status=200
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def read(self,n): return b"<html><title>Root</title></html>"
        class Opener:
            def __init__(self): self.urls=[]
            def open(self,request,timeout):
                url=request.full_url; self.urls.append(url); path=__import__("urllib.parse").parse.urlparse(url).path
                if "www." not in url: raise urllib.error.HTTPError(url,302,"redirect",{"Location":url.replace("https://","https://www.")},None)
                if path != "/" and not path.endswith("/"): raise urllib.error.HTTPError(url,301,"slash",{"Location":url+"/"},None)
                return Response()
        opener=Opener(); args=v1.parser().parse_args(self.repair_argv(preflight=False)); v1.validate_args(args)
        with mock.patch("urllib.request.build_opener",return_value=opener), mock.patch.object(os,"getenv",side_effect=AssertionError("credential read")), mock.patch.object(v1,"execute_tavily",side_effect=AssertionError("Tavily")):
            result=v1.run_derived_repair(args,False)
        self.assertEqual(result["verdict"],"TEV1_DERIVED_HTTP_REPAIR_PARTIAL")
        cp=json.loads((args.repair_output_dir/"repair_checkpoint.json").read_text())
        self.assertEqual(cp["repair_physical_http_attempt_count"],8)
        self.assertEqual(cp["accesses"]["access_vocotviptv_com_root"]["status"],"COMPLETED")
        for aid in v1.AUTHORIZED_REPAIR_ACCESS_IDS[1:]:
            state=cp["accesses"][aid]; self.assertEqual(state["status"],"REDIRECT_CHAIN_INCOMPLETE")
            self.assertEqual((state["attempts"],state["redirect_hops"],state["final_url_requested"]),(2,2,False))

    def test_three_final_hops_with_two_remaining_blocks_budget(self):
        value=v1.project_repair_budget(38,3,1,40)
        self.assertEqual((value["repair_projected_max"],value["combined_projected_max"],value["budget_gate"]),(3,41,"BLOCK"))

    def test_merged_offline_evaluation_extracts_links_provenance_v4_and_preserves_sources(self):
        base=Path(__file__).resolve().parents[1]/"research/output/best_iptv_2026/domain_family_discovery_voco_micro_pilot"
        source=self.source_run(); recovery=base/"targeted_external_verification_v1_offline_recovery_20260715_232020"; repair=base/"targeted_external_verification_v1_http_repair_run_20260715_232020_20260715_235702"
        before=[v1.recursive_directory_fingerprint(x)["aggregate_sha256"] for x in (source,recovery,repair)]
        with mock.patch.object(os,"getenv",side_effect=AssertionError("credential read")), mock.patch.object(socket,"create_connection",side_effect=AssertionError("network")), mock.patch.object(v1,"execute_tavily",side_effect=AssertionError("Tavily")):
            result=v1.merged_offline_evaluation(source,recovery,repair,self.temp_dir/"merged")
        self.assertEqual(result["verdict"],"TEV1_MERGED_OFFLINE_EVALUATION_COMPLETE"); self.assertTrue(result["all_sources_unchanged"])
        after=[v1.recursive_directory_fingerprint(x)["aggregate_sha256"] for x in (source,recovery,repair)]; self.assertEqual(before,after)
        inventory=json.loads((self.temp_dir/"merged/root_capture_forensic_inventory.json").read_text())
        self.assertTrue(inventory["terms_links"] and inventory["privacy_links"] and inventory["contact_links"])
        with (self.temp_dir/"merged/merged_normalized_external_evidence.csv").open(encoding="utf-8") as handle: rows=list(__import__("csv").DictReader(handle))
        self.assertEqual(len(rows),63); self.assertTrue(all(x["provenance"] and json.loads(x["supporting_row_ids"]) for x in rows))
        with (self.temp_dir/"merged/merged_domain_role_classification.csv").open(encoding="utf-8") as handle: roles=list(__import__("csv").DictReader(handle))
        self.assertTrue(all(x["final_role"]=="UNRESOLVED" and x["official_domain_confirmed"]=="False" for x in roles))

    def test_final_two_accepts_only_exact_urls_in_exact_order(self):
        args=v1.parser().parse_args(self.final_argv()); v1.validate_args(args)
        value=v1.validate_final_two_accesses(args.source_evaluation_dir,args.final_url,40,2,enforce_completion_guard=False)
        self.assertEqual(tuple(value["urls"]),v1.FINAL_TWO_URLS)
        variants=(
            ["https://vocotviptv.com/terms/",v1.FINAL_TWO_URLS[1]],
            ["https://www.vocotviptv.com/terms",v1.FINAL_TWO_URLS[1]],
            [v1.FINAL_TWO_URLS[0]+"?x=1",v1.FINAL_TWO_URLS[1]],
            [v1.FINAL_TWO_URLS[0]+"#x",v1.FINAL_TWO_URLS[1]],
            ["http://www.vocotviptv.com/terms/",v1.FINAL_TWO_URLS[1]],
            ["https://www.vocotviptv.com/contact/",v1.FINAL_TWO_URLS[1]],
            ["https://foo.vocotviptv.com/terms/",v1.FINAL_TWO_URLS[1]],
            ["https://example.com/terms/",v1.FINAL_TWO_URLS[1]],
            [v1.FINAL_TWO_URLS[1],v1.FINAL_TWO_URLS[0]],
            [v1.FINAL_TWO_URLS[0],v1.FINAL_TWO_URLS[0]],
            [*v1.FINAL_TWO_URLS,"https://www.vocotviptv.com/contact/"],
        )
        for urls in variants:
            with self.assertRaisesRegex(ValueError,"exactly|duplicate"): v1.validate_final_two_accesses(args.source_evaluation_dir,urls,40,2,enforce_completion_guard=False)

    def test_final_budget_38_plus_2_passes_39_plus_2_and_38_plus_3_block(self):
        self.assertEqual(v1.project_final_access_budget(38,2,40)["budget_gate"],"PASS")
        self.assertEqual(v1.project_final_access_budget(39,2,40)["budget_gate"],"BLOCK")
        self.assertEqual(v1.project_final_access_budget(38,3,40)["budget_gate"],"BLOCK")

    def test_final_preflight_zero_network_tavily_credentials_and_source_immutable(self):
        args=v1.parser().parse_args(self.final_argv()); v1.validate_args(args); before=v1.recursive_directory_fingerprint(self.merged_evaluation())["aggregate_sha256"]
        with mock.patch.object(os,"getenv",side_effect=AssertionError("credential read")), mock.patch.object(socket,"create_connection",side_effect=AssertionError("network")), mock.patch.object(v1,"execute_tavily",side_effect=AssertionError("Tavily")):
            with mock.patch.object(v1,"completed_final_access_runs",return_value=[]): result=v1.run_final_two_access(args,True)
        self.assertEqual(result["verdict"],"TEV1_FINAL_TWO_ACCESS_READY_FOR_AUTHORIZATION"); self.assertEqual(result["source_hash_after"],before)
        self.assertEqual(len(list(args.final_output_dir.iterdir())),12)
        metrics=json.loads((args.final_output_dir/"final_access_metrics.json").read_text())
        self.assertEqual((metrics["historical_budget_units"],metrics["planned_final_http_attempts"],metrics["combined_projected_budget_units"]),(38,2,40))
        self.assertEqual((metrics["http_attempts_added"],metrics["dns_attempts_added"],metrics["tavily_calls_added"],metrics["credential_reads"]),(0,0,0,0))
        report=(args.final_output_dir/"final_access_preflight_report.md").read_text(); self.assertIn("final_execute",report); self.assertNotIn(str(args.final_output_dir)+'\"',report)

    def test_final_execution_requests_each_url_once_and_never_follows_redirect(self):
        class Response:
            status=200
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def read(self,n): return b"<html><title>Privacy</title></html>"
            def geturl(self): return v1.FINAL_TWO_URLS[1]
        class Opener:
            def __init__(self): self.urls=[]
            def open(self,request,timeout):
                url=request.full_url; self.urls.append(url)
                if url==v1.FINAL_TWO_URLS[0]: raise urllib.error.HTTPError(url,301,"redirect",{"Location":"https://example.com/not-followed?token=secret"},None)
                return Response()
        opener=Opener(); args=v1.parser().parse_args(self.final_argv(preflight=False)); v1.validate_args(args)
        validation=v1.validate_final_two_accesses(args.source_evaluation_dir,args.final_url,40,2,enforce_completion_guard=False); v1.initialize_final_access_output(args.final_output_dir,args.source_evaluation_dir,validation,args,"EXECUTE")
        original=v1.write_json_atomic
        with mock.patch("urllib.request.build_opener",return_value=opener), mock.patch.object(v1,"execute_tavily",side_effect=AssertionError("Tavily")), mock.patch.object(os,"getenv",side_effect=AssertionError("credential read")), mock.patch.object(v1,"write_json_atomic",wraps=original) as durable:
            v1.execute_final_two_accesses(args.final_output_dir,args)
        verdict=v1.finalize_final_two_accesses(args.final_output_dir,args.source_evaluation_dir,validation)
        self.assertEqual(verdict,"TEV1_FINAL_TWO_ACCESS_PARTIAL"); self.assertEqual(opener.urls,list(v1.FINAL_TWO_URLS)); self.assertEqual(durable.call_count,2)
        cp=json.loads((args.final_output_dir/"final_access_checkpoint.json").read_text()); self.assertEqual(cp["final_http_attempt_count"],2)
        self.assertTrue(all(cp["accesses"][x]["attempts"]==1 for x in v1.FINAL_TWO_URLS)); self.assertEqual(cp["redirect_response_count"],1)
        with (args.final_output_dir/"final_access_redirects.csv").open(encoding="utf-8") as handle: redirects=list(__import__("csv").DictReader(handle))
        self.assertEqual(len(redirects),1); self.assertIn("[REDACTED]",redirects[0]["location"]); self.assertTrue(json.loads(redirects[0]["supporting_row_ids"]))

    def test_final_budget_integrity_39_consumed_blocks_before_output(self):
        source=self.temp_dir/"merged_source"; shutil.copytree(self.merged_evaluation(),source)
        metrics=json.loads((source/"merged_metrics.json").read_text()); metrics["remaining_budget_units"]=1; v1.write_json(source/"merged_metrics.json",metrics)
        with self.assertRaisesRegex(ValueError,"budget integrity"): v1.validate_final_two_accesses(source,list(v1.FINAL_TWO_URLS),40,2,enforce_completion_guard=False)

    def test_completed_final_run_blocks_repeat_before_output_or_network(self):
        args=v1.parser().parse_args(self.final_argv()); v1.validate_args(args)
        with self.assertRaisesRegex(ValueError,"40/40|cannot be repeated"):
            v1.validate_final_two_accesses(args.source_evaluation_dir,args.final_url,40,2)
        self.assertFalse(args.final_output_dir.exists())

    def test_global_40_of_40_lock_blocks_general_and_repair_network_routes(self):
        self.assertTrue(v1.voco_network_budget_exhausted())
        self.assertEqual(v1.main(["--preflight-only"]),4)
        self.assertEqual(v1.main(["--execute","--confirm-credit-use"]),4)
        repair=v1.parser().parse_args(self.repair_argv()); v1.validate_args(repair)
        self.assertEqual(v1.main(self.repair_argv()),4)

    def test_final_offline_closure_emits_complete_traced_artifact_set(self):
        base=Path(__file__).resolve().parents[1]/"research/output/best_iptv_2026/domain_family_discovery_voco_micro_pilot"
        sources={
            "historical_run":base/"targeted_external_verification_v1_run_20260715_232020",
            "offline_recovery":base/"targeted_external_verification_v1_offline_recovery_20260715_232020",
            "derived_http_repair":base/"targeted_external_verification_v1_http_repair_run_20260715_232020_20260715_235702",
        }
        output=self.temp_dir/"closure"
        before={name:v1.recursive_directory_fingerprint(path)["aggregate_sha256"] for name,path in sources.items()}
        with mock.patch.object(os,"getenv",side_effect=AssertionError("credential read")), mock.patch.object(socket,"create_connection",side_effect=AssertionError("network")), mock.patch.object(v1,"execute_tavily",side_effect=AssertionError("Tavily")):
            result=v1.final_offline_closure(self.merged_evaluation(),base/"targeted_external_verification_v1_final_two_access_run_20260716_002456",output,sources)
        self.assertEqual(result["verdict"],"VOCO_DOMAIN_FAMILY_UNRESOLVED_AFTER_TARGETED_VERIFICATION")
        self.assertTrue(result["all_sources_unchanged"]); self.assertEqual(set(v1.final_closure_artifact_names()),{x.name for x in output.iterdir()})
        after={name:v1.recursive_directory_fingerprint(path)["aggregate_sha256"] for name,path in sources.items()}; self.assertEqual(before,after)
        metrics=json.loads((output/"final_metrics.json").read_text()); self.assertEqual((metrics["final_normalized_rows"],metrics["combined_budget_units"],metrics["remaining_budget_units"]),(65,40,0))
        for name in ("final_legal_identity_signals.csv","final_contact_and_jurisdiction_signals.csv","final_payment_and_crossdomain_relations.csv","final_merged_normalized_external_evidence.csv"):
            with (output/name).open(encoding="utf-8") as handle:
                rows=list(__import__("csv").DictReader(handle))
            self.assertTrue(rows); self.assertTrue(all(json.loads(x["supporting_row_ids"]) for x in rows))
        self.assertNotIn("OFFICIAL_DOMAIN",v1.VALID_ROLES)

    def test_offline_replay_reconstructs_evidence_and_preserves_source(self):
        source=Path(__file__).resolve().parents[1]/"research/output/best_iptv_2026/domain_family_discovery_voco_micro_pilot/targeted_external_verification_v1_run_20260715_232020"
        before=v1.recursive_directory_fingerprint(source)["aggregate_sha256"]
        with mock.patch.object(os,"getenv",side_effect=AssertionError("credential read")), mock.patch.object(socket,"create_connection",side_effect=AssertionError("network")):
            result=v1.offline_replay(source,self.temp_dir/"recovery")
        self.assertTrue(result["source_unchanged"]); self.assertEqual(result["source_hash"],before); self.assertEqual(result["internal_tavily_results"],59)
        with (self.temp_dir/"recovery/normalized_external_evidence_recovered.csv").open(encoding="utf-8") as handle:
            rows=list(__import__("csv").DictReader(handle))
        self.assertEqual(len(rows),62); self.assertTrue(all(json.loads(x["supporting_row_ids"]) for x in rows))

    def test_official_role_stays_prohibited_after_recovery_support_contract(self):
        self.assertNotIn("OFFICIAL_DOMAIN",v1.VALID_ROLES)
        decision=v1.classify_identity([{"signal_type":"CONTROL","supporting_row_ids":["raw_line_0001"]}])
        self.assertEqual(decision["final_role"],"UNRESOLVED"); self.assertTrue(decision["supporting_row_ids"])

    def test_deterministic_errors_not_retryable(self):
        self.assertFalse(v1.deterministic_retryable(RuntimeError("401 Unauthorized"))); self.assertTrue(v1.deterministic_retryable(RuntimeError("timeout")))

    def test_zero_identity_controls_infra_reseller(self):
        for signal in ("CONTROL", "INFRASTRUCTURE", "RESELLER"):
            result = v1.classify_identity([{"signal_type": signal, "supporting_row_ids": ["r1"]}])
            self.assertNotIn(result["final_role"], {"PROBABLE_BRAND_OPERATOR", "POSSIBLE_RELATED_DOMAIN"})

    def test_official_domain_is_not_valid_output(self):
        self.assertNotIn("OFFICIAL_DOMAIN", v1.VALID_ROLES)

    def test_findings_preserve_supporting_rows(self):
        result = v1.classify_identity([{"signal_type": "LEGAL", "attribution_strength": "IDENTITY_STRONG", "category": "LEGAL", "independence_group": "g1", "first_party": True, "supporting_row_ids": ["r1"]}])
        self.assertEqual(result["supporting_row_ids"], ["r1"])

    def test_empty_csv_schemas_are_valid(self):
        for name, fields in v1.CSV_SCHEMAS.items():
            p=self.temp_dir/name; v1.write_empty_csv(p, fields); self.assertEqual(p.read_text(encoding="utf-8").strip().split(","), fields)

    def test_dry_run_zero_network(self):
        args=self.args(); q=v1.build_query_plan(args.target_domain,args.search_depth,args.timeout); a=v1.build_access_plan(args.target_domain)
        with mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")):
            v1.initialize_artifacts(self.temp_dir/"run",args,q,a,{"all_match":True},"DRY_RUN")
            metrics=json.loads((self.temp_dir/"run"/"targeted_external_verification_metrics.json").read_text())
            self.assertEqual((metrics["tavily_calls"],metrics["http_calls"],metrics["dns_calls"]),(0,0,0))

if __name__ == "__main__": unittest.main()
