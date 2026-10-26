"""Reproducible offline checks of TripStar's existing demo.

Run: PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python evals/run_offline_demo_eval.py
All external model, search, and map responses are SYNTHETIC. This evaluates
application plumbing and selected product requirements, NOT live recommendation
quality, price accuracy, real generation latency, cost, or user satisfaction.
Production code and backend/data are not changed. Task files use a temporary dir.
"""
from __future__ import annotations

import asyncio
import contextlib
import copy
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
from types import SimpleNamespace
from unittest import mock
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ["ENABLE_USER_MEMORY"] = "false"

import httpx
from fastapi import FastAPI
from hello_agents import SimpleAgent
from pydantic import ValidationError
from app.agents import trip_planner_agent as agents
from app.api.routes import trip as trip_routes
from app.models.schemas import TripRequest, TripPlan
from app.services import community_search, google_map_service


def request_fixture(stays=(2,), language="zh", legacy=False):
    cities = [{"city": f"模拟城市{chr(65+i)}", "days": n} for i, n in enumerate(stays)]
    start = date(2026, 11, 1)
    payload = {
        "city": cities[0]["city"], "cities": cities,
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=sum(stays)-1)).isoformat(),
        "travel_days": sum(stays), "transportation": "公共交通",
        "accommodation": "经济型酒店", "preferences": ["历史文化", "亲子"],
        "free_text_input": "模拟需求：少走路，至少安排一次室内活动", "language": language,
        "user_id": "synthetic-evaluation-user",
    }
    if legacy:
        payload.pop("cities")
    return payload


def plan_fixture(request):
    """Synthetic output oracle. Never used as a real travel recommendation."""
    days = []
    weather = []
    index = 0
    for city_index, stay in enumerate(request.cities):
        for local_index in range(stay.days):
            current_date = (date.fromisoformat(request.start_date) + timedelta(days=index)).isoformat()
            days.append({
                "date": current_date, "day_index": index, "city": stay.city,
                "is_transfer_day": city_index > 0 and local_index == 0,
                "transfer_info": "模拟城际交通建议" if city_index > 0 and local_index == 0 else "",
                "description": "SYNTHETIC TEST FIXTURE", "transportation": request.transportation,
                "accommodation": request.accommodation,
                "hotel": {"name": f"SIM-{stay.city}-酒店", "address": "模拟地址", "estimated_cost": 300},
                "attractions": [{
                    "name": f"SIM-{stay.city}-景点{j}", "address": "模拟地址",
                    "location": {"longitude": 110.0 + city_index, "latitude": 30.0 + j/10},
                    "visit_duration": 60, "description": "模拟景点，不能作为实际出行依据",
                    "ticket_price": 20, "reservation_required": j == 1,
                    "reservation_tips": "模拟预约提示" if j == 1 else "",
                } for j in (1, 2)],
                "meals": [{"type": kind, "name": f"SIM-{kind}", "estimated_cost": 30}
                          for kind in ("breakfast", "lunch", "dinner")],
            })
            weather.append({"date": current_date, "city": stay.city, "day_weather": "模拟晴",
                            "night_weather": "模拟晴", "day_temp": 20, "night_temp": 10})
            index += 1
    return {
        "city": request.city, "cities": [s.city for s in request.cities],
        "start_date": request.start_date, "end_date": request.end_date,
        "days": days, "weather_info": weather, "overall_suggestions": "仅用于离线软件测试",
        "budget": {"total_attractions": index*40, "total_hotels": index*300,
                   "total_meals": index*90, "total_transportation": index*20,
                   "total_inter_city_transport": 0, "total": index*450},
    }


class SyntheticTool:
    expandable = False

    def __init__(self, name, calls):
        self.name = name
        self.description = "SYNTHETIC external map response"
        self.calls = calls

    def get_parameters(self):
        return []

    def run(self, params):
        self.calls.append({"tool": self.name, "arguments": copy.deepcopy(params)})
        city = params.get("city", "")
        if self.name.endswith("weather"):
            return f"SYNTHETIC-WEATHER:{city}:20C"
        return f"SYNTHETIC-HOTEL:{city}:SIM-{city}-酒店"


class SyntheticToolBundle:
    name = "amap"
    description = "Offline tool fixture"
    expandable = True

    def __init__(self, calls):
        self.calls = calls

    def get_expanded_tools(self):
        return [SyntheticTool(name, self.calls) for name in
                ("amap_maps_weather", "amap_maps_text_search")]


class SyntheticLLM:
    def __init__(self, plan, mode="valid"):
        self.plan = plan
        self.mode = mode
        self.calls = []
        self.planner_attempts = 0

    def invoke(self, messages, **kwargs):
        self.calls.append({"messages": copy.deepcopy(messages), "kwargs": copy.deepcopy(kwargs)})
        system = messages[0]["content"] if messages[0]["role"] == "system" else ""
        last = messages[-1]["content"]
        if "你是天气查询专家" in system or "你是酒店推荐专家" in system:
            if last.startswith("工具执行结果"):
                return last
            if "你是天气查询专家" in system:
                city = re.search(r"请查询(.+?)的天气信息", last).group(1)
                return f"[TOOL_CALL:amap_maps_weather:city={city}]"
            city = re.search(r"请搜索(.+?)的", last).group(1)
            return f"[TOOL_CALL:amap_maps_text_search:keywords=酒店,city={city}]"
        if "你是行程规划专家" in system:
            self.planner_attempts += 1
            if self.mode == "always_timeout" or (self.mode == "timeout_once" and self.planner_attempts == 1):
                raise TimeoutError("SYNTHETIC model timeout")
            if self.mode == "malformed":
                return '{"broken":'
            text = json.dumps(self.plan, ensure_ascii=False)
            if self.mode == "fenced":
                text = "```json\n" + text + "\n```"
            if self.mode == "trailing_comma":
                text = text[:-1] + ",}"
            return text
        # The JSON repair fallback also remains offline.
        return "SYNTHETIC unrecoverable JSON"


class FakeWebSocket:
    """Exercises the actual handler/queue, not a browser network handshake."""
    def __init__(self):
        self.events = []
        self.closed = False

    async def accept(self):
        pass

    async def send_json(self, event):
        self.events.append(copy.deepcopy(event))

    async def close(self, code=1000):
        self.closed = True


def build_planner(llm, calls):
    def init_tools(owner, settings):
        owner._active_tool = SyntheticToolBundle(calls)
    with mock.patch.object(agents, "get_llm", return_value=llm), \
         mock.patch.object(agents, "get_settings", return_value=SimpleNamespace()), \
         mock.patch("app.services.map_dispatcher.get_map_provider", return_value="amap"), \
         mock.patch.object(agents.MultiAgentTripPlanner, "_init_amap_tools", init_tools):
        return agents.MultiAgentTripPlanner()


async def run_pipeline(payload, mode="valid"):
    request = TripRequest(**payload)
    plan = plan_fixture(request)
    if mode == "temperature_units":
        plan["weather_info"][0]["day_temp"] = "20°C"
    if mode == "missing_single_city_fields":
        plan.pop("cities")
        for day in plan["days"]:
            day.pop("city")
    calls = []
    xhs_calls = []
    events = []
    llm = SyntheticLLM(plan, mode)
    planner = build_planner(llm, calls)
    app = FastAPI()
    app.include_router(trip_routes.router, prefix="/api")
    original_update = trip_routes._update_task_state

    async def record_update(task_id, **kwargs):
        events.append({k: v for k, v in kwargs.items() if k != "result"})
        await original_update(task_id, **kwargs)

    def fake_xhs(city, keywords, language):
        xhs_calls.append({"city": city, "keywords": keywords, "language": language})
        if mode == "cookie_error":
            raise community_search.CommunitySearchUnavailableError("SYNTHETIC cookie expired")
        if mode == "search_error":
            raise community_search.CommunityFetchError("SYNTHETIC search unavailable")
        return f"SYNTHETIC-ATTRACTIONS:{city}:SIM-{city}-景点1,SIM-{city}-景点2"

    with tempfile.TemporaryDirectory(prefix="tripstar-offline-eval-") as temp_dir, \
         mock.patch.object(trip_routes, "_TASKS_DATA_DIR", Path(temp_dir)), \
         mock.patch.object(trip_routes, "_tasks", {}), \
         mock.patch.object(trip_routes, "get_trip_planner_agent", return_value=planner), \
         mock.patch.object(trip_routes, "_update_task_state", record_update), \
         mock.patch.object(community_search, "search_community_attractions", fake_xhs), \
         mock.patch.object(agents, "get_llm", return_value=llm):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://offline.test") as client:
            submission = await client.post("/api/trip/plan", json=payload)
            assert submission.status_code == 200, submission.text
            task_id = submission.json()["task_id"]
            ws = FakeWebSocket()
            await asyncio.wait_for(trip_routes.trip_task_ws(ws, task_id), timeout=10)
            status_response = await client.get(f"/api/trip/status/{task_id}")
            assert status_response.status_code == 200
            status = status_response.json()
            disk = json.loads((Path(temp_dir) / f"{task_id}.json").read_text())
            assert disk["status"] == status["status"]
            assert ws.events[-1]["status"] == status["status"] and ws.closed
            should_fail = mode in ("always_timeout", "malformed", "cookie_error", "search_error")
            assert status["status"] == ("failed" if should_fail else "completed"), status
            if should_fail:
                assert status.get("error") and not status.get("result")
            else:
                result = status["result"]
                data = result["data"]
                assert result["plan_id"] == task_id
                assert len(data["days"]) == request.travel_days
                assert data["cities"] == [c.city for c in request.cities]
                assert all(d["city"] for d in data["days"])
                assert data["days"][0]["attractions"][0]["reservation_required"] is True
                assert data["weather_info"][0]["day_temp"] == 20
                graph = result["graph_data"]
                ids = {n["id"] for n in graph["nodes"]}
                assert graph["edges"] and all(e["source"] in ids and e["target"] in ids for e in graph["edges"])
                assert len(calls) == 2 * len(request.cities)
                assert [c["arguments"]["city"] for c in calls[::2]] == [c.city for c in request.cities]
                query = next(c["messages"][-1]["content"] for c in llm.calls
                             if "你是行程规划专家" in c["messages"][0]["content"])
                assert request.free_text_input in query
                assert all(p in query for p in request.preferences)
                for city in request.cities:
                    for prefix in ("SYNTHETIC-ATTRACTIONS:", "SYNTHETIC-WEATHER:", "SYNTHETIC-HOTEL:"):
                        assert prefix + city.city in query
                if request.language != "zh":
                    assert {"en": "English", "ja": "Japanese"}[request.language] in query
                assert any(e.get("stage") == "graph_building" for e in events)
                assert events[-1]["progress"] == 100
            if mode in ("timeout_once", "always_timeout"):
                assert llm.planner_attempts == 2
            return {"terminal_status": status["status"], "planner_attempts": llm.planner_attempts,
                    "map_tool_calls": calls, "attraction_calls": xhs_calls,
                    "stages": [e.get("stage") for e in events], "websocket_event_count": len(ws.events),
                    "synthetic_fixture_only": True}


def assess_probe(name):
    """Check desired product behavior; unsupported behavior is a FAILED check."""
    payload = request_fixture()
    if name == "extra_party_budget_fields":
        extras = {"adults": 2, "children_ages": [7], "rooms": 1, "hotel_budget_total": 1500}
        data = TripRequest(**(payload | extras)).model_dump()
        missing = [k for k in extras if k not in data]
        return not missing, {"silently_dropped_fields": missing}
    invalid = {
        "inconsistent_dates_days": {"travel_days": 5},
        "empty_destination": {"city": "", "cities": []},
        "invalid_date": {"start_date": "not-a-date"},
    }
    if name in invalid:
        try:
            TripRequest(**(payload | invalid[name]))
            return False, {"invalid_request_accepted": True}
        except ValidationError:
            return True, {"invalid_request_accepted": False}
    request = TripRequest(**payload)
    fixture = plan_fixture(request)
    parser = object.__new__(agents.MultiAgentTripPlanner)
    if name in ("budget_sum_validation", "hotel_candidate_membership", "attraction_candidate_membership"):
        if name == "budget_sum_validation":
            fixture["budget"]["total"] = 1
        elif name == "hotel_candidate_membership":
            fixture["days"][0]["hotel"]["name"] = "OUTSIDE-CANDIDATE-POOL"
        else:
            fixture["days"][0]["attractions"][0]["name"] = "OUTSIDE-CANDIDATE-POOL"
        parser._llm_repair_json = lambda broken: broken
        try:
            parsed = parser._parse_response(json.dumps(fixture), request)
            return False, {"adversarial_output_accepted": True,
                           "check_scope": "production output parser; no candidate validation stage was found"}
        except ValueError:
            return True, {"adversarial_output_accepted": False}
    if name == "source_link_preservation":
        fixture["days"][0]["hotel"]["booking_url"] = "https://example.invalid/synthetic-hotel"
        fixture["days"][0]["attractions"][0]["source_url"] = "https://example.invalid/synthetic-source"
        output = TripPlan(**fixture).model_dump()
        preserved = ("booking_url" in output["days"][0]["hotel"] and
                     "source_url" in output["days"][0]["attractions"][0])
        return preserved, {"links_preserved": preserved}
    if name == "agent_task_history_isolation":
        llm = SyntheticLLM(fixture)
        planner = build_planner(llm, [])
        with mock.patch.object(agents, "_multi_agent_planner", planner):
            a = agents.get_trip_planner_agent()
            a.planner_agent.run("SYNTHETIC TASK A")
            b = agents.get_trip_planner_agent()
            b.planner_agent.run("SYNTHETIC TASK B")
        leaked = any(m["content"] == "SYNTHETIC TASK A" for m in llm.calls[-1]["messages"])
        return not leaked, {"same_instance": a is b, "prior_task_in_second_prompt": leaked}
    if name == "google_subtool_argument_mapping":
        service_calls = []
        class FakeGoogleService:
            def __init__(self, **kwargs):
                pass
            def get_weather(self, city):
                service_calls.append(city)
                return []
        with mock.patch.object(google_map_service, "GoogleMapService", FakeGoogleService):
            parser._init_google_tools(SimpleNamespace(google_maps_api_key="synthetic", google_maps_proxy=""))
        agent = SimpleAgent(name="mapping-probe", llm=SyntheticLLM(fixture))
        agent.add_tool(parser._active_tool)
        result = agent._execute_tool_call("google_maps_weather", "city=模拟城市A")
        return service_calls == ["模拟城市A"], {"service_calls": service_calls, "result": result}
    raise ValueError(name)


def main():
    out = ROOT / "evals" / "offline-results"
    out.mkdir(parents=True, exist_ok=True)
    records = []
    log = io.StringIO()

    def record(case_id, group, action):
        try:
            detail = action()
            passed = detail.pop("passed", True)
            records.append({"id": case_id, "group": group, "passed": passed, "observed": detail})
        except Exception as exc:
            records.append({"id": case_id, "group": group, "passed": False,
                            "error": f"{type(exc).__name__}: {exc}"})

    # Enforce offline execution even if a future application change misses a mock.
    with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log), \
         mock.patch.object(socket.socket, "connect", side_effect=RuntimeError("Network forbidden in offline evaluation")):
        for language in ("zh", "en", "ja"):
            for label, stays, legacy in (("single_1d", (1,), True), ("single_3d", (3,), False),
                                         ("two_cities", (2, 1), False), ("five_cities", (2, 2, 2, 2, 2), False)):
                payload = request_fixture(stays, language, legacy)
                record(f"flow_{language}_{label}", "synthetic_pipeline",
                       lambda p=payload: asyncio.run(run_pipeline(p)))
        for mode in ("timeout_once", "always_timeout", "malformed", "cookie_error", "search_error",
                     "fenced", "trailing_comma", "temperature_units"):
            record(f"fault_{mode}", "fault_and_format_handling",
                   lambda m=mode: asyncio.run(run_pipeline(request_fixture(), m)))
        for name in ("extra_party_budget_fields", "inconsistent_dates_days", "empty_destination", "invalid_date",
                     "budget_sum_validation", "hotel_candidate_membership", "attraction_candidate_membership",
                     "source_link_preservation", "agent_task_history_isolation", "google_subtool_argument_mapping"):
            def probe(n=name):
                passed, detail = assess_probe(n)
                return {"passed": passed, **detail}
            record(name, "targeted_product_requirements", probe)

    groups = {}
    for group in sorted({r["group"] for r in records}):
        selected = [r for r in records if r["group"] == group]
        groups[group] = {"total": len(selected), "passed": sum(r["passed"] for r in selected),
                         "failed": sum(not r["passed"] for r in selected)}
    sources = ["backend/app/agents/trip_planner_agent.py", "backend/app/api/routes/trip.py",
               "backend/app/models/schemas.py", "backend/app/services/knowledge_graph_service.py",
               "evals/run_offline_demo_eval.py"]
    result = {
        "generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "evaluation_type": "offline synthetic integration and targeted capability checks",
        "synthetic_data": True, "live_llm_calls": 0, "live_map_calls": 0, "live_xhs_calls": 0,
        "external_boundaries_replaced": ["LLM outputs", "map tool discovery and responses", "XHS search"],
        "executed_production_logic": ["FastAPI HTTP route", "background task", "SimpleAgent tool loop",
                                      "planner prompt construction", "JSON parser", "Pydantic schemas",
                                      "knowledge graph", "WebSocket handler/queues", "temporary task persistence"],
        "limitations": ["No browser UI or real WebSocket network handshake test",
                        "No hotel price, availability, recall, attraction relevance, latency, cost or user outcome measurement",
                        "Language cases check instruction propagation, not real model translation quality",
                        "Nominal scenarios use a fresh planner; reuse is assessed separately by the isolation probe",
                        "Targeted requirements are selected known-risk checks, not a random sample or overall product score"],
        "python_version": sys.version.split()[0],
        "hello_agents_version": importlib.metadata.version("hello-agents"),
        "source_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources},
        "summary": groups, "cases": records,
    }
    (out / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "execution.log").write_text(log.getvalue(), encoding="utf-8")
    summary = ["TripStar 离线模拟测试", "所有外部模型、搜索、地图返回均为合成数据。", ""]
    for group, counts in groups.items():
        summary.append(f"{group}: {counts['passed']}/{counts['total']} passed; {counts['failed']} failed")
    summary.extend(["", "未通过的检查："] + [r["id"] for r in records if not r["passed"]])
    summary.extend(["", "以上不能写成真实行程生成成功率、酒店推荐准确率或景点推荐满意度。",
                    "复现：PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python evals/run_offline_demo_eval.py"])
    (out / "summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(json.dumps(groups, ensure_ascii=False, indent=2))
    print(f"Detailed results: {out / 'results.json'}")


if __name__ == "__main__":
    main()
