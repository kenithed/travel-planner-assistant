"""Disabled community-search interface for the public preview.

This module has no network calls, credential handling, signing or browser data.
External-provider implementations are intentionally not distributed.
"""
import json


class CommunitySearchUnavailableError(RuntimeError):
    pass


class CommunityFetchError(RuntimeError):
    pass


class CommunityImageProxyError(RuntimeError):
    pass


def _unavailable(*args, **kwargs):
    raise CommunitySearchUnavailableError("公开展示版未包含社区搜索模块，实时检索不可用。")


class CommunityClient:
    """Interface hook for offline fixtures only; never creates a live session."""
    def __init__(self, *args, **kwargs):
        pass

    search_notes = _unavailable
    get_note_detail = _unavailable


get_community_client = _unavailable
get_note_detail_ssr = _unavailable


def search_community_attractions(city, keywords, language="zh"):
    return json.dumps({"available": False, "attractions": [],
        "message": "公开展示版未包含社区搜索模块；没有检索证据，不得声称已核实景点、票价或开放状态。"}, ensure_ascii=False)


def geocode_amap(address, city, *, name_zh="", name_en=""):
    from .map_dispatcher import geocode_unified
    return geocode_unified(address, city, address_zh=name_zh, address_en=name_en)


def fetch_community_image_bytes(url):
    raise CommunityImageProxyError("公开展示版未包含社区图片下载模块。")


async def get_photo_bytes_from_community(keyword):
    return None


async def get_photo_from_community(keyword):
    return ""
