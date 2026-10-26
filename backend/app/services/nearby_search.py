"""有界的高德周边搜索。密钥错误与零结果严格区分，不使用模型补造地点。

接口字段依据 https://lbs.amap.com/api/webservice/guide/api/search/#around
biz_ext.cost 是人均消费，不能当作门票；本服务不把它转换成 ticket_price。
"""
import math
import re
from typing import Any
from urllib.parse import urlencode

import httpx

from ..config import get_settings


class NearbySearchError(Exception):
    pass


def valid_location(raw: Any) -> bool:
    try:
        lng, lat = float(raw["longitude"]), float(raw["latitude"])
        return math.isfinite(lng) and math.isfinite(lat) and -180 <= lng <= 180 and -90 <= lat <= 90 and (lng, lat) != (0, 0)
    except (TypeError, KeyError, ValueError):
        return False


def distance_km(a: dict, b: dict) -> float:
    lat1, lat2 = math.radians(a["latitude"]), math.radians(b["latitude"])
    dlat = lat2 - lat1
    dlng = math.radians(b["longitude"] - a["longitude"])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 6371.0088 * 2 * math.asin(min(1, math.sqrt(max(0, h))))


def text_value(value: Any, limit: int = 200) -> str:
    # 高德的空值有时为 []。不把数组转换为展示文本。
    return re.sub(r"[<>\x00-\x1f]", "", value).strip()[:limit] if isinstance(value, str) else ""


def normalize_city(city: str) -> str:
    return re.sub(r"[\s市]", "", re.split(r"[-·/]", city)[-1])


class AmapNearbySearch:
    async def search(self, *, center: dict, city: str, query: str, radius_m: int, page: int) -> list[dict]:
        key = get_settings().vite_amap_web_key
        if not key:
            raise NearbySearchError("附近搜索需要高德 Web 服务 Key，请在服务配置中填写。")
        params = {
            "key": key,
            "location": f"{center['longitude']:.6f},{center['latitude']:.6f}",
            "city": city,
            "keywords": query,
            "types": "110000|140100|140200|140300|140400",
            "radius": radius_m,
            "sortrule": "distance",
            "offset": 25,
            "page": page,
            "extensions": "all",
        }
        try:
            async with httpx.AsyncClient(timeout=8, trust_env=False) as client:
                response = await client.get("https://restapi.amap.com/v3/place/around", params=params)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError):
            # 不回传含 key 的请求 URL / 原始异常。
            raise NearbySearchError("附近搜索暂时不可用，请稍后重试。原行程没有变化。") from None
        if not isinstance(data, dict):
            raise NearbySearchError("附近搜索返回格式异常，请稍后重试。")
        if data.get("status") != "1":
            code = str(data.get("infocode", ""))
            if code in {"10001", "10002", "10005", "10006", "10007", "10008", "10009", "10012", "10013"}:
                raise NearbySearchError(f"高德附近搜索认证失败（{code}），请检查 Web 服务 Key 与权限。原行程没有变化。")
            if code in {"10003", "10004", "10010", "10014", "10019", "10020", "10021", "10044"}:
                raise NearbySearchError("高德附近搜索额度或频率受限，请稍后重试。原行程没有变化。")
            raise NearbySearchError("高德附近搜索返回异常，暂时无法核实附近候选。原行程没有变化。")
        pois = data.get("pois", [])
        if not isinstance(pois, list):
            raise NearbySearchError("附近搜索返回格式异常，请稍后重试。")
        results = []
        for poi in pois:
            if not isinstance(poi, dict):
                continue
            try:
                lng, lat = map(float, str(poi.get("location", "")).split(","))
            except (ValueError, TypeError):
                continue
            location = {"longitude": lng, "latitude": lat}
            if not valid_location(location) or distance_km(center, location) > radius_m / 1000:
                continue
            poi_city = text_value(poi.get("cityname"))
            if normalize_city(poi_city) != normalize_city(city):
                continue
            name, poi_id = text_value(poi.get("name")), text_value(poi.get("id"), 100)
            if not name or not poi_id:
                continue
            # 景区的停车场、厕所、出入口不能作为一次完整游览的替代。
            if re.search(r"停车场|洗手间|卫生间|公共厕所|售票处|游客服务中心|出入口|[东西南北正侧]门(?:\(|（|$)", name):
                continue
            results.append({
                "id": poi_id,
                "name": name,
                "address": "".join(text_value(poi.get(k)) for k in ("pname", "cityname", "adname", "address")),
                "district": text_value(poi.get("adname")),
                "city": poi_city,
                "category": text_value(poi.get("type")),
                "location": location,
                "ticket_price": None,
                "source": "高德地图周边搜索",
                "source_url": "https://uri.amap.com/marker?" + urlencode({"position": f"{lng},{lat}", "name": name, "src": "travel-planner", "coordinate": "gaode", "callnative": 0}),
            })
        return results
