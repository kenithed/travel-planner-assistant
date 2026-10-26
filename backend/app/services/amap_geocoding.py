"""AMap-only geocoding adapter, independent of optional community search."""
from collections import deque
from typing import Optional
import threading
import time
import httpx
from ..config import get_settings

_amap_geocode_warning_lock = threading.Lock()
_amap_geocode_warning_keys: set[tuple[str, str]] = set()
_amap_geocode_rate_lock = threading.Lock()
_amap_geocode_request_times = deque()
_AMAP_GEOCODE_RATE_LIMIT = 3
_AMAP_GEOCODE_RATE_WINDOW = 1.0


def _wait_for_amap_geocode_slot() -> None:
    """限制高德地理编码请求启动速率，避免超过官方 3 次/秒上限。"""
    while True:
        wait_seconds = 0.0
        now = time.monotonic()
        with _amap_geocode_rate_lock:
            while (
                _amap_geocode_request_times
                and now - _amap_geocode_request_times[0] >= _AMAP_GEOCODE_RATE_WINDOW
            ):
                _amap_geocode_request_times.popleft()

            if len(_amap_geocode_request_times) < _AMAP_GEOCODE_RATE_LIMIT:
                _amap_geocode_request_times.append(now)
                return

            wait_seconds = _AMAP_GEOCODE_RATE_WINDOW - (
                now - _amap_geocode_request_times[0]
            )

        if wait_seconds > 0:
            time.sleep(wait_seconds)


def _geocode_amap_raw(address: str, city: str) -> Optional[dict]:
    """纯高德 Web 服务地理编码（供 map_dispatcher 降级调用）。

    返回: {"longitude": float, "latitude": float}；失败返回 None。
    不再用固定坐标兜底，避免把景点静默标到错误城市。
    """
    settings = get_settings()
    if not settings.vite_amap_web_key:
        return None

    params = {
        "key": settings.vite_amap_web_key,
        "address": address,
        "output": "JSON",
    }
    if city:
        params["city"] = city

    try:
        _wait_for_amap_geocode_slot()
        resp = httpx.get("https://restapi.amap.com/v3/geocode/geo", params=params, timeout=5, trust_env=False)
        data = resp.json()
        if data.get("status") == "1" and data.get("geocodes"):
            location = data["geocodes"][0].get("location", "")
            if not location:
                return None
            lon, lat = location.split(",")
            return {"longitude": float(lon), "latitude": float(lat)}
        info = str(data.get("info") or "")
        warning_key = (address, info)
        with _amap_geocode_warning_lock:
            if warning_key not in _amap_geocode_warning_keys:
                _amap_geocode_warning_keys.add(warning_key)
                print(f"高德地理编码无结果 ({address}): status={data.get('status')} info={info}")
    except Exception as e:
        print(f"高德地理编码查阅失败 ({address}): {e}")

    return None


