"""Source-grounded Wikipedia lookup and short Nemotron paraphrases."""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from typing import Any
import time

from .schemas import CatalogItem

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "StoryScout/1.0 (educational catalog enrichment; https://github.com/shivam2931120/StoryScout)"


def _json_request(request, opener, timeout: int = 15) -> dict:
    for attempt in range(4):
        try:
            with opener(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code not in {429, 503} or attempt == 3:
                raise
            retry_after = error.headers.get("Retry-After") if error.headers else None
            try:
                delay = min(20.0, max(1.0, float(retry_after))) if retry_after else 2.0 ** attempt
            except ValueError:
                delay = 2.0 ** attempt
            time.sleep(delay)
    raise RuntimeError("Wikipedia API retry limit reached")


def _title_key(value: str) -> str:
    value = re.sub(r"\s*\(\d{4}(?:\s+(?:film|movie|novel))?\)\s*$", "", value, flags=re.I)
    value = re.sub(r"\s*\((?:film|novel|book|movie|short story)\)\s*$", "", value, flags=re.I)
    inverted = re.match(r"^(.*),\s*(The|A|An)$", value, flags=re.I)
    if inverted:
        value = f"{inverted.group(2)} {inverted.group(1)}"
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def find_wikipedia_source(item: CatalogItem, opener=urllib.request.urlopen) -> dict[str, str] | None:
    """Find an exact-title Wikipedia article and return its lead as source text.

    The title must match exactly after removing a year or common disambiguator;
    fuzzy title matches are rejected to avoid attaching another work's plot.
    """
    title = re.sub(r"\s*\(\d{4}(?:\s+(?:film|movie|novel))?\)\s*$", "", item.title, flags=re.I).strip()
    inverted = re.match(r"^(.*),\s*(The|A|An)$", title, flags=re.I)
    if inverted:
        title = f"{inverted.group(2)} {inverted.group(1)}"
    search_params = urllib.parse.urlencode({
        "action": "query", "list": "search", "srsearch": title,
        "srlimit": 8, "format": "json", "utf8": 1,
    })
    request = urllib.request.Request(f"{WIKIPEDIA_API}?{search_params}", headers={"User-Agent": USER_AGENT})
    search = _json_request(request, opener)
    matches = []
    wanted = _title_key(title)
    for result in search.get("query", {}).get("search", []):
        candidate = result.get("title", "")
        key = _title_key(candidate)
        ratio = SequenceMatcher(None, wanted, key).ratio()
        if key == wanted or ratio >= 0.96:
            domain_hint = "film" if item.media_type == "movie" else "novel"
            opposite_hint = "novel" if item.media_type == "movie" else "film"
            score = 3 if key == wanted else 0
            if domain_hint in candidate.casefold():
                score += 2
            if opposite_hint in candidate.casefold():
                score -= 2
            if item.year and str(item.year) in candidate:
                score += 1
            matches.append((score, candidate))
    if not matches:
        return None
    matches.sort(key=lambda value: (-value[0], value[1].casefold()))
    page_params = urllib.parse.urlencode({
        "action": "query", "prop": "extracts|pageprops", "exintro": 1,
        "explaintext": 1, "exchars": 6000, "ppprop": "disambiguation",
        "titles": "|".join(dict.fromkeys(title for _, title in matches)), "format": "json", "utf8": 1,
    })
    request = urllib.request.Request(f"{WIKIPEDIA_API}?{page_params}", headers={"User-Agent": USER_AGENT})
    time.sleep(0.35)
    pages = _json_request(request, opener).get("query", {}).get("pages", {})
    page_by_title = {str(page.get("title", "")): page for page in pages.values()}
    for _, candidate in matches:
        page = page_by_title.get(candidate)
        if not page:
            continue
        extract = re.sub(r"\s+", " ", str(page.get("extract", ""))).strip()
        if page.get("pageprops", {}).get("disambiguation") is not None or len(extract) < 100:
            continue
        page_title = str(page.get("title", ""))
        url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(page_title.replace(" ", "_"), safe="()_:,'")
        return {"title": page_title, "excerpt": extract[:6000], "url": url}
    return None


class NemotronDescriptionSummarizer:
    """Paraphrase supplied source text; never write a synopsis from title alone."""

    def __init__(self, api_key: str, model: str | None = None, client: Any | None = None):
        import os
        self.model = model or os.getenv("STORYSCOUT_NVIDIA_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
        if client is None:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url="https://integrate.api.nvidia.com/v1", timeout=40.0, max_retries=1)
        self.client = client

    def summarize_batch(self, records: list[dict[str, str]]) -> dict[str, str]:
        if not records:
            return {}
        compact = [{k: record[k] for k in ("id", "title", "media_type", "year", "source_excerpt")} for record in records]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": (
                    "Write a short, spoiler-free catalog description for each work using only its supplied source excerpt. "
                    "Do not add facts from memory, infer plot details from the title or genre, or invent mood/content warnings. "
                    "If the excerpt does not clearly describe that exact work, return an empty description. "
                    "Each nonempty description must be at most 40 words and a faithful paraphrase. "
                    "Return JSON only as {\"summaries\":[{\"id\":string,\"description\":string}]} and include every input id."
                )},
                {"role": "user", "content": json.dumps(compact, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=max(200, 70 * len(records)),
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        payload = json.loads(response.choices[0].message.content or "{}")
        expected = {record["id"] for record in records}
        output: dict[str, str] = {}
        for result in payload.get("summaries", []):
            item_id = result.get("id")
            summary = re.sub(r"\s+", " ", str(result.get("description", ""))).strip()
            if item_id in expected and summary and len(summary.split()) <= 40:
                output[item_id] = summary
        return output


def get_server_api_key() -> str | None:
    """Read a server-side NVIDIA key without printing or exposing its value."""
    import os
    value = os.getenv("NVIDIA_API_KEY", "").strip()
    if value:
        return value
    try:
        import tomllib
        from pathlib import Path
        secrets_path = Path(__file__).resolve().parents[1] / ".streamlit" / "secrets.toml"
        with secrets_path.open("rb") as file:
            return str(tomllib.load(file).get("NVIDIA_API_KEY", "")).strip() or None
    except (OSError, ValueError, TypeError):
        return None
