import requests
from urllib.parse import urlparse
from typing import Optional, List, Any
from datetime import datetime
from .base import SearchProvider
from ..core.models import SearchResponse, SearchResult, SearchOptions, SourceType, SourceLevel, Classification

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

class SearXNGProvider(SearchProvider):
    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        api_key: Optional[str] = None,
        default_engines: Optional[List[str]] = None
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_engines = default_engines

    @property
    def name(self) -> str:
        return "searxng"

    @property
    def supported_engines(self) -> List[str]:
        return ["google", "bing", "duckduckgo", "baidu", "yandex", "brave"]

    def search(
        self,
        query: str,
        options: Optional[SearchOptions] = None
    ) -> SearchResponse:
        options = options or SearchOptions()
        engines = options.engines or self.default_engines

        params = {
            "q": query,
            "format": "json",
            "limit": options.max_results,
        }

        if engines:
            params["engines"] = ",".join(engines)

        if options.time_range:
            params["time_range"] = options.time_range

        headers = {}
        if self.api_key:
            headers["X-API-KEY"] = self.api_key

        try:
            response = requests.get(
                f"{self.base_url}/search",
                params=params,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(f"Failed to connect to SearXNG at {self.base_url}: {e}")
        except requests.exceptions.Timeout as e:
            raise RuntimeError(f"SearXNG request timed out after 30s: {e}")
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"SearXNG returned HTTP error: {e}")

        content_type = response.headers.get("content-type", "")

        if "application/json" in content_type:
            data = response.json()
            results = self._parse_json_results(data)
            search_time = data.get("time", 0.0)
        else:
            results = self._parse_html_results(response.text)
            search_time = 0.0

        return SearchResponse(
            query=query,
            results=results,
            total_count=len(results),
            search_time=search_time
        )

    def _parse_json_results(self, data: dict) -> List[SearchResult]:
        results = []
        for item in data.get("results", []):
            source_name = ""
            if "engine" in item:
                source_name = item.get("engine", "")
            elif "source" in item and isinstance(item["source"], dict):
                source_name = item["source"].get("name", "")

            result = SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
                source_name=source_name,
                source_domain=self._extract_domain(item.get("url", "")),
                source_type=self._infer_source_type(item),
                source_level=self._infer_source_level(item),
                published_date=self._parse_published_date(item),
            )
            results.append(result)
        return results

    def _parse_html_results(self, html: str) -> List[SearchResult]:
        if not BS4_AVAILABLE:
            raise RuntimeError("beautifulsoup4 is required for HTML parsing. Install with: pip install beautifulsoup4")

        soup = BeautifulSoup(html, "html.parser")
        results = []

        for article in soup.select("article.result"):
            title_elem = article.select_one("h3 a")
            url = title_elem.get("href", "") if title_elem else ""
            title = title_elem.get_text(strip=True) if title_elem else ""

            content_elem = article.select_one("p.content")
            snippet = content_elem.get_text(strip=True) if content_elem else ""

            source_name = ""
            engines_elem = article.select(".engines span")
            if engines_elem:
                source_name = engines_elem[0].get_text(strip=True)

            result = SearchResult(
                title=title,
                url=url,
                snippet=snippet,
                source_name=source_name,
                source_domain=self._extract_domain(url),
                source_type=self._infer_source_type_from_url(url),
                source_level=self._infer_source_level_from_url(url),
                published_date=self._parse_date_from_html(article),
            )
            results.append(result)

        return results

    def _parse_published_date(self, item: dict) -> Optional[str]:
        for key in ["publishedDate", "published_date", "date"]:
            date_val = item.get(key)
            if date_val:
                return self._normalize_date(date_val)
        return None

    def _normalize_date(self, date_val: Any) -> Optional[str]:
        if not date_val:
            return None
        try:
            if isinstance(date_val, (int, float)):
                dt = datetime.fromtimestamp(date_val)
                return dt.isoformat()
            date_str = str(date_val)
            date_str = date_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(date_str)
            return dt.isoformat()
        except:
            return None

    def _parse_date_from_html(self, article) -> Optional[str]:
        time_elem = article.select_one("time")
        if time_elem and time_elem.get("datetime"):
            return self._normalize_date(time_elem.get("datetime"))
        for elem in article.select("span, p, div"):
            text = elem.get_text(strip=True)
            if self._looks_like_date(text):
                return self._normalize_date(text)
        return None

    def _looks_like_date(self, text: str) -> bool:
        import re
        date_patterns = [
            r"\d{4}-\d{2}-\d{2}",
            r"\d{4}/\d{2}/\d{2}",
            r"\d{2}/\d{2}/\d{4}",
        ]
        for pattern in date_patterns:
            if re.search(pattern, text):
                return True
        return False

    def _extract_domain(self, url: str) -> str:
        try:
            return urlparse(url).netloc
        except:
            return ""

    def _infer_source_type(self, item: dict) -> SourceType:
        url = item.get("url", "").lower()
        if "gov.cn" in url or "gov." in url:
            return SourceType.OFFICIAL
        return SourceType.MEDIA

    def _infer_source_level(self, item: dict) -> SourceLevel:
        return SourceLevel.MUNICIPAL

    def validate_config(self) -> bool:
        try:
            resp = requests.get(
                f"{self.base_url}/health",
                timeout=5
            )
            return resp.status_code == 200
        except:
            return False
