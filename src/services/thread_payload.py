"""Canonical two-part Threads payload for product uploads."""

from __future__ import annotations

from typing import Any, Mapping


ROOT_POST = "root_post"
PRODUCT_COMMENT = "product_comment"


def build_product_thread_payload(post_data: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return the fixed root-post + product-comment payload.

    The legacy ``first_post``/``second_post`` keys are accepted only so that
    already queued jobs can still be uploaded. New generation always provides
    the explicit keys.
    """
    root = post_data.get(ROOT_POST) or post_data.get("first_post")
    comment = post_data.get(PRODUCT_COMMENT) or post_data.get("second_post")
    if not isinstance(root, Mapping) or not isinstance(comment, Mapping):
        raise ValueError("본문과 상품 댓글이 모두 필요합니다.")

    root_text = str(root.get("text", "") or "").strip()
    comment_text = str(comment.get("text", "") or "").strip()
    if not root_text or not comment_text:
        raise ValueError("본문과 상품 댓글은 비워둘 수 없습니다.")

    return [
        {
            "role": ROOT_POST,
            "text": root_text,
            "image_path": root.get("media_path") or root.get("image_path"),
        },
        {
            "role": PRODUCT_COMMENT,
            "text": comment_text,
            "image_path": comment.get("media_path") or comment.get("image_path"),
        },
    ]
