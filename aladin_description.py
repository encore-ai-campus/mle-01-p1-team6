"""Crawler for the publisher-provided book introduction."""

from __future__ import annotations

import re

import requests

from aladin_html import HTMLTreeParser, clean_text, first


PUBLISHER_DESC_URL = "https://www.aladin.co.kr/shop/product/getContents.aspx"


def fetch_publisher_description(
    session: requests.Session,
    item_id: int,
    isbn: str,
    *,
    timeout: int = 30,
) -> str:
    """Crawl the publisher description section from an Aladin product page."""
    if item_id <= 0 or not isbn:
        return ""

    response = session.get(
        PUBLISHER_DESC_URL,
        params={"ISBN": isbn, "name": "PublisherDesc", "type": 0, "date": 13},
        timeout=timeout,
        headers={
            "Referer": f"https://www.aladin.co.kr/shop/wproduct.aspx?ItemId={item_id}",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    response.raise_for_status()

    parser = HTMLTreeParser()
    parser.feed(response.text)
    content_node = first(
        parser.root,
        lambda node: node.get("id") == "div_PublisherDesc_All",
    ) or first(
        parser.root,
        lambda node: node.get("id") == "div_PublisherDesc_Short",
    )
    if content_node is None:
        return ""

    return re.sub(
        r"\s*(더보기\s*\n?\s*닫기)\s*$",
        "",
        clean_text(content_node.text()),
    ).strip()
