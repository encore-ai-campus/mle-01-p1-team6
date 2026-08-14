"""Crawler and parser for Aladin community reviews."""

from __future__ import annotations

import re
import time
from typing import Any

import requests

from aladin_html import HTMLTreeParser, clean_text, first, has_class, parse_int


COMMUNITY_REVIEW_URL = (
    "https://www.aladin.co.kr/ucl/shop/product/ajax/GetCommunityListAjax.aspx"
)


def request_review_html(
    session: requests.Session,
    params: dict[str, Any],
    *,
    retries: int = 3,
    timeout: int = 30,
) -> str:
    """Request one community-review page."""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = session.get(
                COMMUNITY_REVIEW_URL,
                params=params,
                timeout=timeout,
                headers={
                    "Referer": (
                        "https://www.aladin.co.kr/shop/wproduct.aspx?"
                        f"ItemId={params['itemId']}"
                    ),
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(2**attempt)
    raise RuntimeError(f"커뮤니티 리뷰 AJAX 호출 실패: {last_error}") from last_error


def parse_community_reviews(html: str, item_id: int) -> tuple[list[dict[str, Any]], int]:
    """Parse review rows and the total count from one AJAX response."""
    parser = HTMLTreeParser()
    parser.feed(html)
    review_nodes = parser.root.find_all(
        lambda node: node.tag == "div" and has_class(node, "hundred_list")
    )
    reviews: list[dict[str, Any]] = []

    for review_node in review_nodes:
        paper_node = first(
            review_node,
            lambda node: re.fullmatch(r"div_commentReviewPaper\d+", node.get("id"))
            is not None,
        )
        paper_id_match = (
            re.fullmatch(r"div_commentReviewPaper(\d+)", paper_node.get("id"))
            if paper_node else None
        )
        if not paper_id_match:
            continue
        paper_id = int(paper_id_match.group(1))

        content_node = first(review_node, lambda node: node.get("id") == f"spnPaper{paper_id}")
        left_node = first(
            review_node,
            lambda node: node.tag == "div" and has_class(node, "left"),
        )
        left_links = left_node.find_all(lambda node: node.tag == "a") if left_node else []
        left_spans = left_node.find_all(lambda node: node.tag == "span") if left_node else []

        author_link = left_links[0] if left_links else None
        author = clean_text(author_link.text()) if author_link else ""
        author_url = author_link.get("href") if author_link else ""
        left_text = [clean_text(node.text()) for node in left_spans]
        date = next((value for value in left_text if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)), "")
        recommendation_count = next(
            (parse_int(r"공감\s*\((\d+)\)", value) for value in left_text if "공감" in value),
            0,
        )
        comment_count = next(
            (parse_int(r"댓글\s*\((\d+)\)", clean_text(link.text()))
             for link in left_links if "댓글" in link.text()),
            0,
        )

        image_nodes = review_node.find_all(lambda node: node.tag == "img")
        rating = 0.0
        for image in image_nodes:
            source = image.get("src")
            if "icon_star_on" in source:
                rating += 1
            elif "icon_star_half" in source:
                rating += 0.5

        blog_links = [
            node.get("href")
            for node in review_node.find_all(lambda node: node.tag == "a")
            if node.get("href", "").startswith("https://blog.aladin.co.kr/")
        ]
        review_url = next(
            (url for url in blog_links if f"/{paper_id}" in url and "#Comment_" not in url),
            "",
        )
        has_buyer_label = any(image.get("alt") == "구매자" for image in image_nodes)

        reviews.append(
            {
                "itemId": item_id,
                "paperId": paper_id,
                "rating": rating or None,
                "content": clean_text(content_node.text()) if content_node else "",
                "author": author,
                "authorUrl": author_url,
                "reviewUrl": review_url,
                "date": date,
                "recommendationCount": recommendation_count,
                "commentCount": comment_count,
                "isOrderer": has_buyer_label,
            }
        )

    total_count = parse_int(r"Pager\.totalRowCount\s*=\s*(\d+)", html, len(reviews))
    return reviews, total_count


def fetch_community_reviews(
    session: requests.Session,
    item_id: int,
    *,
    page_size: int = 100,
    delay: float = 0.3,
) -> list[dict[str, Any]]:
    """Fetch all community reviews for one item, page by page."""
    if item_id <= 0:
        return []

    all_reviews: list[dict[str, Any]] = []
    seen_paper_ids: set[int] = set()
    page = 1
    total_count = None
    while total_count is None or len(all_reviews) < total_count:
        start_number = (page - 1) * page_size + 1
        params: dict[str, Any] = {
            "ProductItemId": item_id,
            "itemId": item_id,
            "pageCount": page_size,
            "communitytype": "CommentReview",
            "nemoType": -1,
            "page": page,
            "startNumber": start_number,
            "endNumber": page * page_size,
            "sort": 2,
            "IsOrderer": 2,
            "BranchType": 1,
            "IsAjax": "true",
            "pageType": 0,
        }
        response_html = request_review_html(session, params)
        reviews, total_count = parse_community_reviews(response_html, item_id)
        if not reviews:
            break
        new_reviews = [review for review in reviews if review["paperId"] not in seen_paper_ids]
        if not new_reviews:
            break
        seen_paper_ids.update(review["paperId"] for review in new_reviews)
        all_reviews.extend(new_reviews)
        if len(reviews) < page_size:
            break
        page += 1
        time.sleep(delay)

    return all_reviews[:total_count] if total_count is not None else all_reviews
