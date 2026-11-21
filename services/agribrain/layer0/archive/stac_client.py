"""Fail-closed STAC search with exhaustive bounded continuation traversal.

The STAC collection search contract reports an *entire* interval, not one page.
An unavailable catalog, truncated pagination, or untrusted continuation cannot
be interpreted as an empty / completed historical window by ArchiveBootstrap.
"""
import json
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlsplit

import requests

from .cdse_client import CDSEClient


class STACClient:
    def __init__(self, cdse_client: Optional[CDSEClient] = None):
        self.stac_url = os.environ.get(
            "AGRIWISE_STAC_URL",
            "https://api.dataspace.copernicus.eu/stac/search",
        )
        # The bootstrap and STAC clients must agree on their offline default.
        self.offline = os.environ.get("AGRIWISE_ARCHIVE_OFFLINE", "false").lower() == "true"
        self.cdse_client = cdse_client or CDSEClient()

    def search(
        self,
        geometry_geojson: Dict[str, Any],
        start_time: str,
        end_time: str,
        collections: List[str],
        limit: int = 100,
        max_pages: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Exhaust a bounded STAC search before reporting a complete result.

        Supports ordinary STAC rel=next links using GET or POST, with optional
        POST body and merge fields. No cross-origin redirects / next endpoints
        are trusted with the CDSE Authorization header.
        """
        if self.offline:
            raise RuntimeError("stac_catalog_offline_not_complete")
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("invalid_stac_limit")
        if type(max_pages) is not int or not 1 <= max_pages <= 10000:
            raise ValueError("invalid_stac_max_pages")
        if not isinstance(collections, list) or not collections:
            raise ValueError("stac_collections_required")

        original_url = self.stac_url
        original_origin = urlsplit(original_url)
        if original_origin.scheme != "https" or not original_origin.hostname:
            raise RuntimeError("stac_endpoint_must_use_https")
        origin = (original_origin.scheme, original_origin.netloc)
        base_payload = {
            "intersects": geometry_geojson,
            "datetime": f"{start_time}/{end_time}",
            "collections": collections,
            "limit": limit,
        }
        current_payload = dict(base_payload)
        current_url = original_url
        current_method = "POST"
        headers = dict(self.cdse_client.get_auth_header() or {})
        headers["Content-Type"] = "application/json"
        results: List[Dict[str, Any]] = []
        seen = set()

        for page_number in range(max_pages):
            parsed = urlsplit(current_url)
            if (parsed.scheme, parsed.netloc) != origin or parsed.username or parsed.password:
                raise RuntimeError("untrusted_stac_pagination_origin")
            page_identity = (
                current_method, current_url,
                json.dumps(current_payload, sort_keys=True) if current_payload is not None else "",
            )
            if page_identity in seen:
                raise RuntimeError("stac_pagination_cycle_detected")
            seen.add(page_identity)
            try:
                if current_method == "POST":
                    response = requests.post(
                        current_url, json=current_payload, headers=headers, timeout=45,
                        allow_redirects=False,
                    )
                elif current_method == "GET":
                    response = requests.get(
                        current_url, headers=headers, timeout=45,
                        allow_redirects=False,
                    )
                else:
                    raise RuntimeError("unsupported_stac_pagination_method")
                if 300 <= response.status_code < 400:
                    raise RuntimeError("stac_unsafe_redirect")
                response.raise_for_status()
                page = response.json()
            except requests.RequestException as exc:
                raise RuntimeError(
                    f"stac_query_incomplete:page={page_number + 1}:{type(exc).__name__}"
                ) from exc
            except ValueError as exc:
                raise RuntimeError("stac_invalid_json_response") from exc

            if not isinstance(page, dict) or not isinstance(page.get("features"), list):
                raise RuntimeError("stac_invalid_feature_collection")
            if any(not isinstance(feature, dict) for feature in page["features"]):
                raise RuntimeError("stac_invalid_feature")
            results.extend(page["features"])

            links = page.get("links") or []
            if not isinstance(links, list) or any(not isinstance(link, dict) for link in links):
                raise RuntimeError("stac_invalid_links")
            next_links = [link for link in links if link.get("rel") == "next"]
            if len(next_links) > 1:
                raise RuntimeError("stac_ambiguous_next_page")
            if not next_links:
                context = page.get("context") or {}
                if not isinstance(context, dict):
                    raise RuntimeError("stac_invalid_search_context")
                matched = page.get("numberMatched", context.get("matched"))
                if matched is not None:
                    if type(matched) is not int or matched < 0:
                        raise RuntimeError("stac_invalid_matched_count")
                    if len(results) < matched:
                        raise RuntimeError("stac_missing_continuation_link")
                elif len(page["features"]) >= limit:
                    # Without a next link or matched count, a full page could
                    # be truncated by the provider. Never certify completion.
                    raise RuntimeError("stac_full_page_without_completion_proof")
                return results
            next_link = next_links[0]
            href = next_link.get("href")
            if not isinstance(href, str) or not href:
                raise RuntimeError("stac_next_page_has_no_href")
            next_url = urljoin(current_url, href)
            next_origin = urlsplit(next_url)
            if (next_origin.scheme, next_origin.netloc) != origin or (
                next_origin.username or next_origin.password
            ):
                raise RuntimeError("untrusted_stac_pagination_origin")
            method = str(next_link.get("method") or "GET").upper()
            if method not in ("GET", "POST"):
                raise RuntimeError("unsupported_stac_pagination_method")
            if method == "POST":
                link_body = next_link.get("body")
                if link_body is None:
                    next_payload = dict(base_payload)
                elif not isinstance(link_body, dict):
                    raise RuntimeError("invalid_stac_pagination_body")
                elif next_link.get("merge") is True:
                    next_payload = dict(current_payload or base_payload)
                    next_payload.update(link_body)
                else:
                    next_payload = dict(link_body)
            else:
                next_payload = None
            current_url, current_method, current_payload = (
                next_url, method, next_payload
            )

        raise RuntimeError("stac_pagination_limit_exhausted")
