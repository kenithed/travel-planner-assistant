"""Offline regression tests. All places/prices here are explicit test fixtures."""
import json
import time
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI

from app.api.routes.chat import router
from app.models.schemas import Attraction, DayPlan, TripPlan, Budget, TripChatRequest
from app.models.trip_edit import EditIntent, TripEditApplyRequest
from app.services import nearby_search as nearby
from app.services import trip_edit_service as edits


def fixture_plan():
    def attraction(name, lng, lat, price=20):
        return Attraction(name=name, address="测试地址", location={"longitude": lng, "latitude": lat},
                          visit_duration=90, description="离线测试景点", ticket_price=price)
    return TripPlan(city="北京", cities=["北京"], start_date="2026-10-30", end_date="2026-10-31",
        overall_suggestions="离线测试行程，不代表实际推荐",
        days=[DayPlan(date="2026-10-30", day_index=0, city="北京", description="第一天测试",
            transportation="公共交通", accommodation="测试酒店", hotel={"name":"测试酒店","estimated_cost":300},
            meals=[{"type":"lunch","name":"测试午餐","estimated_cost":50}],
            attractions=[attraction("测试原景点",116.397,39.917),attraction("测试相邻景点",116.405,39.925)]),
            DayPlan(date="2026-10-31", day_index=1, city="北京", description="第二天测试", transportation="地铁",
            accommodation="测试酒店", attractions=[attraction("测试其他天景点",116.38,39.90)])],
        budget=Budget(total_attractions=60,total_hotels=300,total_meals=50,total_transportation=30,total_inter_city_transport=200,total=640))


def candidate(n=1, lng=None, lat=39.918, **changes):
    item = dict(id=f"fixture-{n}",name=f"离线测试博物馆{n}",address="北京市东城区测试地址",district="东城区",city="北京市",
        category="科教文化服务;博物馆",location={"longitude":lng or 116.398+n*.001,"latitude":lat},ticket_price=None,
        source="离线测试数据",source_url="https://uri.amap.com/marker?position=116.4,39.918")
    item.update(changes)
    return item


class FixtureSearch:
    def __init__(self, results=None, factory=None):
        self.calls=[]
        self.results=results if results is not None else [candidate(i) for i in (1,2,3)]
        self.factory=factory
    async def search(self, **kwargs):
        self.calls.append(kwargs)
        return deepcopy(self.factory(kwargs) if self.factory else self.results)


class ChatEditTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        edits._proposals.clear()
        self.plan=fixture_plan()
        self.request=TripChatRequest(message="把第一天第一个景点换成附近博物馆",trip_plan=self.plan.model_dump(),mode="auto")
        self.intent=EditIntent(intent="replace",day_number=1,attraction_number=1,search_query="博物馆")

    async def preview(self, **kwargs):
        return await edits.prepare_edit(self.request,intent=kwargs.pop("intent",self.intent),searcher=kwargs.pop("searcher",FixtureSearch()),**kwargs)

    def apply_request(self, preview, **changes):
        return TripEditApplyRequest(proposal_id=preview["proposal"]["id"],candidate_id=changes.pop("candidate_id","fixture-1"),trip_plan=changes.pop("trip_plan",self.plan),**changes)

    async def test_preview_does_not_change_plan_and_searches_both_references(self):
        searcher=FixtureSearch()
        original=self.plan.model_dump()
        preview=await self.preview(searcher=searcher)
        self.assertEqual(self.request.trip_plan,original)
        self.assertEqual(preview["kind"],"replacement_preview")
        self.assertEqual(preview["proposal"]["radius_km"],5)
        self.assertEqual({c["center"]["longitude"] for c in searcher.calls},{116.397,116.405})
        self.assertEqual({c["city"] for c in searcher.calls},{"北京"})

    async def test_second_page_is_used_before_expansion(self):
        searcher=FixtureSearch(factory=lambda q: [candidate(1)] if q["page"]==1 else [candidate(2),candidate(3)])
        preview=await self.preview(searcher=searcher)
        self.assertEqual({c["page"] for c in searcher.calls},{1,2})
        self.assertEqual(preview["proposal"]["radius_km"],5)

    async def test_expands_to_ten_km_and_warns(self):
        searcher=FixtureSearch(factory=lambda q: [] if q["radius_m"]==5000 else [candidate(i,lng=116.48+i*.001) for i in (1,2,3)])
        preview=await self.preview(searcher=searcher)
        self.assertEqual(preview["proposal"]["radius_km"],10)
        self.assertIn("10 公里",preview["proposal"]["warnings"][0])

    async def test_no_results_preserves_original(self):
        result=await self.preview(searcher=FixtureSearch([]))
        self.assertEqual(result["kind"],"no_results")
        self.assertFalse(edits._proposals)

    async def test_scope_duplicate_distance_indoor_and_district_filters(self):
        raw=[candidate(),candidate(2,name="测试其他天景点"),candidate(3,city="上海市"),candidate(4,lng=116.0,lat=40.5),
             candidate(5,location={"longitude":0,"latitude":0}),candidate(6,name="露天遗址公园"),candidate(7,district="西城区",address="西城区"),candidate()]
        intent=self.intent.model_copy(update={"indoor_only":True,"district":"东城区"})
        self.assertEqual([x["id"] for x in edits.rank_candidates(raw,self.plan,0,0,intent,5)],["fixture-1"])

    async def test_route_ranking_prefers_shared_nearby_area(self):
        candidates=edits.rank_candidates([candidate(2,lng=116.46),candidate(1)],self.plan,0,0,self.intent,10)
        self.assertEqual(candidates[0]["id"],"fixture-1")
        self.assertLess(candidates[0]["route_delta_km"],candidates[1]["route_delta_km"])

    async def test_unknown_ticket_cannot_pass_hard_cap(self):
        preview=await self.preview(intent=self.intent.model_copy(update={"max_ticket_price":50}))
        self.assertTrue(all(not c["can_apply"] for c in preview["proposal"]["candidates"]))
        with self.assertRaisesRegex(ValueError,"不可应用"):
            edits.apply_edit(self.apply_request(preview))

    async def test_apply_is_local_and_updates_unknown_budget_and_graph(self):
        preview=await self.preview()
        before=self.plan.model_dump()
        result=edits.apply_edit(self.apply_request(preview))
        after=result["data"]
        self.assertEqual(self.plan.model_dump(),before)
        self.assertEqual(after["days"][1],before["days"][1])
        for key in ("hotel","meals","transportation","accommodation"):
            self.assertEqual(after["days"][0][key],before["days"][0][key])
        self.assertEqual(after["days"][0]["attractions"][1],before["days"][0]["attractions"][1])
        self.assertIsNone(after["days"][0]["attractions"][0]["ticket_price"])
        self.assertEqual(after["budget"]["total"],620)
        self.assertEqual(after["budget"]["total_inter_city_transport"],200)
        self.assertEqual(after["budget"]["unknown_ticket_count"],1)
        graph=json.dumps(result["graph_data"],ensure_ascii=False)
        self.assertIn("门票待核实",graph)
        self.assertIn("已知费用小计",graph)
        self.assertIn("离线测试博物馆1",graph)
        self.assertNotIn("测试原景点",graph)

    async def test_forged_candidate_expiry_and_stale_plan_rejected(self):
        preview=await self.preview()
        with self.assertRaisesRegex(ValueError,"不可应用"):
            edits.apply_edit(self.apply_request(preview,candidate_id="invented-place"))
        changed=self.plan.model_copy(deep=True)
        changed.days[1].description="手动修改"
        with self.assertRaisesRegex(ValueError,"发生变化"):
            edits.apply_edit(self.apply_request(preview,trip_plan=changed))
        edits._proposals[preview["proposal"]["id"]]["expires_at"]=time.monotonic()-1
        with self.assertRaisesRegex(ValueError,"过期"):
            edits.apply_edit(self.apply_request(preview))

    async def test_missing_coordinates_fail_without_search(self):
        for a in self.request.trip_plan["days"][0]["attractions"]:
            a["location"]={"longitude":0,"latitude":0}
        searcher=FixtureSearch()
        with self.assertRaisesRegex(nearby.NearbySearchError,"坐标"):
            await self.preview(searcher=searcher)
        self.assertFalse(searcher.calls)

    async def test_explicit_target_overrides_ui_and_ambiguity_is_clarified(self):
        request=self.request.model_copy(update={"target_day_index":0,"target_attraction_index":0})
        self.assertEqual(edits.resolve_target(self.plan,EditIntent(intent="replace",attraction_name="测试其他天景点"),request),(1,0))
        with self.assertRaises(nearby.NearbySearchError):
            edits.resolve_target(self.plan,EditIntent(intent="replace",attraction_name="测试原景点",attraction_number=2),request)
        with self.assertRaises(nearby.NearbySearchError):
            edits.resolve_target(self.plan,EditIntent(intent="replace"),self.request)
        with self.assertRaises(nearby.NearbySearchError):
            edits.resolve_target(self.plan,EditIntent(intent="replace",day_number=5),request)

    async def test_question_or_unsupported_constraint_does_not_search(self):
        searcher=FixtureSearch()
        result=await self.preview(intent=EditIntent(intent="ask",reply="这是问答"),searcher=searcher)
        self.assertEqual(result["kind"],"answer")
        result=await self.preview(intent=self.intent.model_copy(update={"unsupported_constraints":["全天总预算500元"]}),searcher=searcher)
        self.assertEqual(result["kind"],"clarify")
        self.assertFalse(searcher.calls)

    async def test_routes_handle_error_and_stale_confirmation(self):
        app=FastAPI();app.include_router(router,prefix="/api")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
            with patch("app.api.routes.chat.prepare_edit",side_effect=nearby.NearbySearchError("认证失败，原行程没有变化")):
                response=await client.post("/api/chat/ask",json=self.request.model_dump())
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json()["kind"],"clarify")
            preview=await self.preview()
            changed=self.plan.model_copy(deep=True);changed.days[0].description="新修改"
            response=await client.post("/api/chat/edit/apply",json=self.apply_request(preview,trip_plan=changed).model_dump())
            self.assertEqual(response.status_code,409)


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def request_with_payload(self, payload):
        self.requests=[]
        def handle(request):
            self.requests.append(request)
            return httpx.Response(200,json=payload)
        client=httpx.AsyncClient(transport=httpx.MockTransport(handle))
        with patch.object(nearby,"get_settings",return_value=SimpleNamespace(vite_amap_web_key="fixture-secret")),patch.object(nearby.httpx,"AsyncClient",return_value=client):
            return await nearby.AmapNearbySearch().search(center={"longitude":116.397,"latitude":39.917},city="北京",query="博物馆",radius_m=5000,page=2)

    async def test_amap_contract_and_consumer_average_is_not_ticket(self):
        pois=[{"id":"one","name":"测试博物馆","location":"116.4,39.918","cityname":"北京市","type":"博物馆","biz_ext":{"cost":"180"}}]
        pois += [{**pois[0],"id":"gate","name":"测试景点北门"},{**pois[0],"id":"far","location":"117,40"}]
        result=await self.request_with_payload({"status":"1","pois":pois})
        self.assertEqual(len(result),1)
        self.assertIsNone(result[0]["ticket_price"])
        params=self.requests[0].url.params
        self.assertEqual(params["page"],"2");self.assertEqual(params["radius"],"5000");self.assertEqual(params["city"],"北京")

    async def test_invalid_key_is_not_treated_as_empty_success_or_exposed(self):
        with self.assertRaises(nearby.NearbySearchError) as ctx:
            await self.request_with_payload({"status":"0","infocode":"10001"})
        self.assertIn("认证失败",str(ctx.exception));self.assertNotIn("fixture-secret",str(ctx.exception))

    async def test_malformed_provider_shape(self):
        with self.assertRaises(nearby.NearbySearchError):
            await self.request_with_payload([])

    async def test_malformed_llm_output_is_safe_clarification(self):
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={"choices":[{"message":{"content":"{bad-json}"}}]})))
        with patch.object(edits,"_get_llm_runtime_config",return_value={"api_key":"fixture-secret","base_url":"https://test.invalid","model_id":"test"}),patch.object(edits.httpx,"AsyncClient",return_value=client):
            with self.assertRaisesRegex(nearby.NearbySearchError,"原行程没有变化"):
                await edits.parse_intent(TripChatRequest(message="换景点",trip_plan=fixture_plan().model_dump(),mode="auto"))
