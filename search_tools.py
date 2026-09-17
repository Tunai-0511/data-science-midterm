"""Pure HTML parsers and safety checks shared by the Selenium questions.

The functions in this module deliberately do not drive a browser.  Keeping the
DOM interpretation separate makes it possible to test category boundaries and
completion claims without faking Selenium itself.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from bs4 import BeautifulSoup, Tag


NEWS_BASE = "https://news.google.com/"
NEWS_OUTPUT_CATEGORIES = (
    "焦點新聞",
    "地方新聞",
    "您的主題",
    "更多新聞",
)
_GOOGLE_BLOCK_MARKERS = (
    "our systems have detected unusual traffic",
    "unusual traffic from your computer network",
    "detected unusual traffic",
    "不是機器人",
    "異常流量",
    "驗證您是人類",
    "verify you are human",
    "captcha",
)
_MOMO_BLOCK_MARKERS = (
    "access denied",
    "request rejected",
    "challenge validation",
    "驗證您是人類",
    "captcha",
)


def search_box_score(attributes: dict[str, str]) -> int:
    """Score an input only when its own attributes identify search semantics."""

    folded = {
        key: _clean(str(value or "")).casefold()
        for key, value in attributes.items()
    }
    if folded.get("type") in {"email", "password", "tel"}:
        return 0
    score = 0
    if folded.get("name") == "q":
        score += 4
    if folded.get("type") == "search":
        score += 3
    semantic_text = " ".join(
        folded.get(key, "")
        for key in ("name", "id", "placeholder", "aria-label", "title")
    )
    if any(token in semantic_text for token in ("search", "搜尋", "關鍵字", "keyword")):
        score += 3
    return score


def pagination_action(text: str, aria_label: str) -> str | None:
    """Classify pagination only from an exact visible or accessible label."""

    labels = {_clean(text).casefold(), _clean(aria_label).casefold()}
    if labels & {"更多結果", "more results"}:
        return "more"
    if labels & {"下一頁", "下一页", "next", "next page"}:
        return "next"
    return None


def _clean(value: str) -> str:
    return " ".join(value.split())


def is_verification_page(title: str, html: str, url: str) -> bool:
    """Return True only for recognizable verification/protection pages."""

    soup = BeautifulSoup(html[:500_000], "html.parser")
    for hidden in soup(["script", "style", "template", "noscript"]):
        hidden.decompose()
    visible_text = soup.get_text(" ", strip=True)
    haystack = f"{title}\n{url}\n{visible_text}".casefold()
    return "/sorry/" in url.casefold() or any(
        marker.casefold() in haystack for marker in _GOOGLE_BLOCK_MARKERS
    )


def _unwrap_google_url(href: str) -> str:
    absolute = urljoin("https://www.google.com/", href)
    parsed = urlparse(absolute)
    if parsed.netloc.endswith("google.com") and parsed.path == "/url":
        target = parse_qs(parsed.query).get("q", [""])[0]
        if target:
            return unquote(target)
    return absolute


def _inside_ad(element: Tag) -> bool:
    for ancestor in (element, *element.parents):
        if not isinstance(ancestor, Tag):
            continue
        if ancestor.get("data-text-ad") is not None:
            return True
        if ancestor.get("id") in {"tads", "bottomads", "taw"}:
            return True
        classes = set(ancestor.get("class") or ())
        if {"commercial-unit-desktop-top", "pla-unit"} & classes:
            return True
    return False


def extract_google_results(html: str) -> list[dict[str, str]]:
    """Extract title/link pairs from Google's natural-results main area.

    An ``h3`` inside an anchor is Google's most stable accessible contract for
    a titled result.  We still require the result-area boundary and reject known
    ad containers; the function never falls back to every page link.
    """

    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one("#search")
    if scope is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for heading in scope.find_all("h3"):
        anchor = heading.find_parent("a", href=True)
        if anchor is None or _inside_ad(anchor):
            continue
        title = _clean(heading.get_text(" ", strip=True))
        url = _unwrap_google_url(str(anchor["href"]))
        parsed = urlparse(url)
        if not title or parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc.endswith("google.com"):
            continue
        if url in seen:
            continue
        seen.add(url)
        rows.append({"title": title, "url": url})
    return rows


def _exact_heading_tags(scope: Tag | BeautifulSoup, label: str) -> list[Tag]:
    found: list[Tag] = []
    for tag in scope.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        if _clean(tag.get_text(" ", strip=True)) == label:
            found.append(tag)
    for tag in scope.select('[role="heading"]'):
        if tag not in found and _clean(tag.get_text(" ", strip=True)) == label:
            found.append(tag)
    return found


def _looks_like_news_link(anchor: Tag) -> bool:
    href = str(anchor.get("href") or "")
    path = urlparse(urljoin(NEWS_BASE, href)).path
    if path.startswith(("/read/", "/articles/", "/rss/articles/")):
        return True
    return anchor.find_parent("article") is not None and anchor.find(
        ["h3", "h4", "h5"]
    ) is not None


def _news_links(scope: Tag) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in scope.find_all("a", href=True):
        if not _looks_like_news_link(anchor):
            continue
        title_node = anchor.find(["h3", "h4", "h5"])
        title = _clean(
            (title_node or anchor).get_text(" ", strip=True)
        )
        url = urljoin(NEWS_BASE, str(anchor["href"]))
        if not title or url in seen:
            continue
        seen.add(url)
        rows.append({"title": title, "url": url})
    return rows


def _smallest_link_container(
    heading: Tag,
    *,
    forbidden_headings: Iterable[str] = (),
) -> Tag | None:
    forbidden = set(forbidden_headings)
    for parent in heading.parents:
        if not isinstance(parent, Tag):
            continue
        if parent.name not in {"div", "section", "article", "main", "c-wiz"}:
            continue
        if forbidden:
            labels = {
                _clean(tag.get_text(" ", strip=True))
                for tag in parent.find_all(
                    ["h1", "h2", "h3", "h4", "h5", "h6"]
                )
            }
            if labels & forbidden:
                continue
        if _news_links(parent):
            return parent
    return None


def extract_google_news_sections(
    html: str,
) -> tuple[dict[str, list[dict[str, str]]], list[str]]:
    """Extract only requested Google News sections using visible headings.

    Missing or renamed sections are returned separately.  This is intentional:
    layout changes and personalization must become a partial result rather than
    an invented "all sections" success.
    """

    soup = BeautifulSoup(html, "html.parser")
    output: dict[str, list[dict[str, str]]] = {}

    summary_container: Tag | None = None
    summary_headings = _exact_heading_tags(soup, "焦點提要")
    if summary_headings:
        summary_container = _smallest_link_container(summary_headings[0])
        if summary_container is not None:
            for child_label in ("焦點新聞", "地方新聞"):
                child_candidates = _exact_heading_tags(summary_container, child_label)
                if not child_candidates:
                    continue
                child_scope = _smallest_link_container(
                    child_candidates[0],
                    forbidden_headings={"焦點新聞", "地方新聞"} - {child_label},
                )
                if child_scope is not None:
                    rows = _news_links(child_scope)
                    if rows:
                        output[child_label] = rows

    standalone_labels = ("焦點新聞", "地方新聞", "您的主題", "更多新聞")
    for label in standalone_labels:
        combined: list[dict[str, str]] = list(output.get(label, []))
        seen: set[str] = {row["url"] for row in combined}
        for heading in _exact_heading_tags(soup, label):
            if summary_container is not None and heading in summary_container.descendants:
                continue
            scope = _smallest_link_container(
                heading,
                forbidden_headings=set(standalone_labels) - {label},
            )
            if scope is None:
                continue
            for row in _news_links(scope):
                if row["url"] not in seen:
                    seen.add(row["url"])
                    combined.append(row)
        if combined:
            output[label] = combined

    missing = [name for name in NEWS_OUTPUT_CATEGORIES if name not in output]
    return output, missing


def inspect_momo_search_result(
    html: str, current_url: str, query: str
) -> tuple[bool, str]:
    """Confirm that momo has loaded a real result DOM for ``query``."""

    soup = BeautifulSoup(html, "html.parser")
    visible_soup = BeautifulSoup(html[:500_000], "html.parser")
    for hidden in visible_soup(["script", "style", "template", "noscript"]):
        hidden.decompose()
    visible_text = visible_soup.get_text(" ", strip=True).casefold()
    if any(marker.casefold() in visible_text for marker in _MOMO_BLOCK_MARKERS):
        return False, "頁面是存取驗證或拒絕頁，並非商品搜尋結果"

    parsed_url = urlparse(current_url)
    decoded_location = unquote(f"{parsed_url.path}?{parsed_url.query}").casefold()
    is_search_url = (
        parsed_url.netloc.casefold().endswith("momoshop.com.tw")
        and "search" in parsed_url.path.casefold()
        and query.casefold() in decoded_location
    )
    if not is_search_url:
        return False, "目前不是可驗證的 momo 搜尋結果網址"
    query_folded = query.casefold()
    query_evidence = query_folded in unquote(current_url).casefold()
    if not query_evidence:
        for field in soup.select("input, textarea"):
            if query_folded == _clean(str(field.get("value") or "")).casefold():
                query_evidence = True
                break
    if not query_evidence:
        headings = " ".join(
            tag.get_text(" ", strip=True)
            for tag in soup.find_all(["h1", "h2"])
        ).casefold()
        query_evidence = query_folded in headings

    result_regions = soup.select(
        ".listAreaUl, .goods-list, .goodsList, #productList, "
        "[class*='searchResult'], [data-testid*='product-list']"
    )
    product_links = []
    for region in result_regions:
        product_links.extend(
            anchor
            for anchor in region.find_all("a", href=True)
            if "goodsdetail" in str(anchor["href"]).casefold()
            or "goods/" in str(anchor["href"]).casefold()
        )
    if not product_links:
        return False, "找不到載入完成的商品結果，不能把首頁或空白頁存為成果"
    if not query_evidence:
        return False, "商品卡已出現，但頁面沒有 nba 搜尋條件的可驗證證據"
    return True, f"已驗證搜尋條件與 {len(product_links)} 個商品連結"


def completion_status(stop_reason: str) -> str:
    """Map a pagination stop reason to an honest assignment status."""

    return "passed" if stop_reason == "no_next_after_navigation" else "partial"
