from __future__ import annotations

import asyncio
import json
from http.server import ThreadingHTTPServer
from threading import Thread
import unittest
from urllib import request

from assistant_stream_harness.harness_server import HarnessApp, create_handler

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - documented optional browser dependency.
    sync_playwright = None


class AssistantStreamHarnessTest(unittest.TestCase):
    def test_happy_path_emits_valid_ordered_session_events_and_sse_frames(self) -> None:
        app = HarnessApp()

        result = asyncio.run(app.run_command(mode="happy"))

        self.assertEqual(result["status"], "completed")
        self.assertEqual(
            [event["type"] for event in result["events"]],
            ["progress", "progress", "assistant.delta", "assistant.delta", "assistant.final"],
        )
        self.assertEqual([event["sequence"] for event in result["events"]], [1, 2, 3, 4, 5])
        self.assertEqual(result["events"][0]["payload"]["status"], "started")
        self.assertEqual(result["events"][1]["payload"]["status"], "in_progress")
        self.assertEqual(result["events"][2]["payload"]["delta"], "Here is ")
        self.assertEqual(result["events"][4]["payload"]["usage"]["totalTokens"], 10)

        frames = app.bridge.sse_frames()
        self.assertIn("id: event_001\n", frames[0])
        self.assertIn("event: progress\n", frames[0])
        self.assertIn('"type":"progress"', frames[0])
        self.assertIn("event: assistant.final\n", frames[-1])
        self.assertTrue(result["safety"]["metadataOnlyLogs"])

    def test_provider_dependency_failure_emits_safe_typed_error(self) -> None:
        app = HarnessApp()

        result = asyncio.run(app.run_command(mode="provider_failure"))

        self.assertEqual(result["status"], "failed")
        self.assertEqual([event["type"] for event in result["events"]], ["progress", "progress", "error"])
        error_event = result["events"][-1]
        self.assertEqual(error_event["payload"]["errorCode"], "PROVIDER_UNAVAILABLE")
        self.assertEqual(error_event["payload"]["category"], "DEPENDENCY")
        self.assertEqual(error_event["payload"]["metadata"]["dependencyStatus"], "unavailable")
        self.assertTrue(result["safety"]["metadataOnlyLogs"])
        self.assertNotIn("raw", json.dumps(result["events"]))

    def test_proposed_action_flow_emits_valid_sse_and_review_cards(self) -> None:
        app = HarnessApp()

        result = asyncio.run(app.run_command(mode="proposed_actions"))

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["result"]["proposedActionIds"], ["action_001", "action_002"])
        self.assertEqual(
            [event["type"] for event in result["events"]],
            [
                "progress",
                "progress",
                "assistant.delta",
                "assistant.delta",
                "assistant.final",
                "progress",
                "action.proposed",
                "action.proposed",
            ],
        )
        proposed_events = [event for event in result["events"] if event["type"] == "action.proposed"]
        self.assertEqual(proposed_events[0]["payload"]["actionType"], "REPLACE_TEXT")
        self.assertEqual(
            proposed_events[0]["payload"]["resourceRef"],
            {"connector": "google_docs", "resourceId": "google_doc_demo", "resourceType": "document"},
        )
        self.assertEqual(len(result["reviewCards"]), 2)
        self.assertEqual(result["reviewCards"][0]["status"], "PROPOSED")
        self.assertIn("Synthetic sentence", result["reviewCards"][0]["currentText"])
        self.assertTrue(result["safety"]["metadataOnlyLogs"])
        self.assertNotIn("Synthetic sentence with passive wording.", json.dumps(result["events"]))

        frames = app.bridge.sse_frames()
        self.assertIn("event: action.proposed\n", "".join(frames))

    def test_decision_flow_approves_rejects_expires_and_denies_cross_session(self) -> None:
        app = HarnessApp()
        asyncio.run(app.run_command(mode="proposed_actions"))

        approved = asyncio.run(app.decide_action("action_001", decision="approve"))
        rejected = asyncio.run(app.decide_action("action_002", decision="reject"))
        denied = asyncio.run(app.decide_action("action_001", decision="deny_cross_session"))
        expired_setup = asyncio.run(app.run_command(mode="proposed_actions"))
        expired_action_id = expired_setup["result"]["proposedActionIds"][0]
        expired = asyncio.run(app.decide_action(expired_action_id, decision="expire"))

        self.assertEqual(approved["action"]["status"], "APPROVED")
        self.assertEqual(rejected["action"]["status"], "REJECTED")
        self.assertEqual(denied["status"], "failed")
        self.assertEqual(denied["error"]["category"], "AUTHORIZATION")
        self.assertEqual(expired["action"]["status"], "EXPIRED")
        status_events = [event for event in app.bridge.events if event["type"] == "action.status_changed"]
        self.assertTrue(any(event["payload"]["status"] == "EXPIRED" for event in status_events))
        self.assertTrue(expired["safety"]["metadataOnlyLogs"])

    def test_http_demo_serves_proposed_action_decision_flow(self) -> None:
        app = HarnessApp()
        server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(app))
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            command_request = request.Request(
                f"{base_url}/api/assistant-command",
                data=json.dumps({"mode": "proposed_actions"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(command_request, timeout=5) as response:
                command_body = json.loads(response.read().decode("utf-8"))

            self.assertEqual(command_body["status"], "completed")
            self.assertEqual(len(command_body["reviewCards"]), 2)
            action_id = command_body["reviewCards"][0]["actionId"]
            decision_request = request.Request(
                f"{base_url}/api/action-decision",
                data=json.dumps({"actionId": action_id, "decision": "approve"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(decision_request, timeout=5) as response:
                decision_body = json.loads(response.read().decode("utf-8"))

            self.assertEqual(decision_body["action"]["status"], "APPROVED")
            with request.urlopen(f"{base_url}{command_body['eventStreamUrl']}", timeout=5) as response:
                stream_body = response.read().decode("utf-8")
            self.assertIn("event: action.proposed\n", stream_body)
            self.assertIn("event: action.status_changed\n", stream_body)
            self.assertTrue(decision_body["safety"]["metadataOnlyLogs"])
        finally:
            server.shutdown()
            server.server_close()

    def test_http_demo_serves_ui_command_and_sse_frames(self) -> None:
        app = HarnessApp()
        server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(app))
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            with request.urlopen(f"{base_url}/", timeout=5) as response:
                html = response.read().decode("utf-8")
            self.assertIn("Assistant Stream Harness", html)
            self.assertIn("EventSource", html)

            command_request = request.Request(
                f"{base_url}/api/assistant-command",
                data=json.dumps({"mode": "happy"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(command_request, timeout=5) as response:
                command_body = json.loads(response.read().decode("utf-8"))

            self.assertEqual(command_body["status"], "completed")
            self.assertEqual(command_body["eventCount"], 5)
            with request.urlopen(f"{base_url}{command_body['eventStreamUrl']}", timeout=5) as response:
                stream_body = response.read().decode("utf-8")

            self.assertIn("event: progress\n", stream_body)
            self.assertIn("event: assistant.delta\n", stream_body)
            self.assertIn("event: assistant.final\n", stream_body)
            self.assertTrue(app.safety_report()["metadataOnlyLogs"])
            self.assertEqual(len(app.bridge.stream_logs), 2)
        finally:
            server.shutdown()
            server.server_close()

    def test_browser_ui_renders_stream_and_deduplicates_replayed_event_ids(self) -> None:
        if sync_playwright is None:
            self.skipTest("playwright Python package is not installed")

        app = HarnessApp()
        server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(app))
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            with sync_playwright() as playwright:
                browser = playwright.firefox.launch(headless=True)
                page = browser.new_page()
                page.goto(base_url)
                page.get_by_role("button", name="Send command").click()
                page.wait_for_function("document.querySelectorAll('.event').length === 5")
                self.assertEqual(page.locator(".event").count(), 5)
                self.assertEqual(page.locator(".event").nth(0).text_content(), "progressevent_001 CONTEXT.LOADING.STARTED")
                self.assertEqual(page.locator(".event").nth(4).text_content(), "assistant.finalevent_005 stop")
                page.evaluate(
                    """() => {
                      window.appendEvent("progress", {
                        eventId: "event_001",
                        payload: {messageCode: "DUPLICATE_SHOULD_NOT_RENDER"}
                      });
                    }"""
                )
                self.assertEqual(page.locator(".event").count(), 5)
                page.get_by_role("button", name="Run provider failure").click()
                page.wait_for_function(
                    "document.getElementById('command-state').textContent.includes('failed with 3 event')"
                )
                self.assertEqual(page.locator(".event").count(), 3)
                self.assertIn("PROVIDER_UNAVAILABLE", page.locator(".event").nth(2).text_content())
                self.assertEqual(page.locator("#safety").text_content(), "metadata only")
                page.get_by_role("button", name="Create proposed actions").click()
                page.wait_for_function("document.querySelectorAll('.review-card').length === 2")
                self.assertEqual(page.locator(".review-card").count(), 2)
                self.assertIn("Replace text proposal (PROPOSED)", page.locator(".review-card").nth(0).text_content())
                page.locator(".review-card").nth(0).get_by_role("button", name="Approve").click()
                page.wait_for_function("document.getElementById('command-state').textContent.includes('approve -> APPROVED')")
                self.assertIn("APPROVED", page.locator(".review-card").nth(0).text_content())
                page.wait_for_function(
                    "Array.from(document.querySelectorAll('.event')).some((node) => node.textContent.includes('action.status_changed'))"
                )
                browser.close()
        finally:
            server.shutdown()
            server.server_close()

    def test_runtime_module_names_stay_product_generic(self) -> None:
        self.assertEqual(HarnessApp.__module__.split(".")[0], "assistant_stream_harness")
        self.assertNotIn("m5", HarnessApp.__module__)


if __name__ == "__main__":
    unittest.main()
