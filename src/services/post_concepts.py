# -*- coding: utf-8 -*-
"""Post writing concept definitions for Coupang Threads copy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class PostConcept:
    id: str
    number: int
    name: str
    short_label: str
    description: str
    prompt: str
    uses_current_issues: bool = False

    @property
    def display_label(self) -> str:
        return f"{self.number}. {self.name}"


CONCEPT_CURIOSITY = "curiosity_hook"
CONCEPT_TODAY_ISSUE = "today_issue"
CONCEPT_PROBLEM_SOLUTION = "problem_solution"
CONCEPT_BUYING_GUIDE = "buying_guide"
DEFAULT_POST_CONCEPT_ID = CONCEPT_CURIOSITY


POST_CONCEPTS: tuple[PostConcept, ...] = (
    PostConcept(
        id=CONCEPT_CURIOSITY,
        number=1,
        name="호기심 훅",
        short_label="기존 컨셉",
        description="지금까지 쓰던 짧고 장난기 있는 어그로형 상품 훅입니다.",
        prompt=(
            "컨셉: 호기심 훅.\n"
            "- 지금까지의 기본 방식이다.\n"
            "- 상품의 실제 사용 장면과 불편함을 뒤집어서 짧은 호기심을 만든다.\n"
            "- 광고 설명문처럼 쓰지 말고 Threads에서 사람이 툭 던지는 말처럼 쓴다."
        ),
    ),
    PostConcept(
        id=CONCEPT_TODAY_ISSUE,
        number=2,
        name="오늘 이슈 연결",
        short_label="뉴스/상황 연결",
        description="현재 이슈가 되는 뉴스, 날씨, 생활 상황을 상품 사용 맥락과 엮습니다.",
        prompt=(
            "컨셉: 오늘 이슈 연결.\n"
            "- 제공된 최신 헤드라인/상황 중 상품과 자연스럽게 연결되는 맥락 하나만 고른다.\n"
            "- 특정 인물, 참사, 사고, 정치 갈등을 판매 문구처럼 이용하지 않는다.\n"
            "- 상품이 사회 문제를 해결한다고 과장하지 않는다.\n"
            "- 뉴스가 상품과 직접 맞지 않으면 날씨, 계절, 외출, 집안일 같은 현재 생활 상황으로 바꿔 쓴다.\n"
            "- 첫 줄에는 현재 사람들이 체감할 만한 상황을 넣고, 둘째 줄에는 상품군이 왜 떠오르는지 자연스럽게 잇는다."
        ),
        uses_current_issues=True,
    ),
    PostConcept(
        id=CONCEPT_PROBLEM_SOLUTION,
        number=3,
        name="생활 문제 해결",
        short_label="불편 해결",
        description="일상 불편을 먼저 짚고 상품을 해결 후보처럼 보여주는 컨셉입니다.",
        prompt=(
            "컨셉: 생활 문제 해결.\n"
            "- 첫 줄은 사용자가 겪는 귀찮음, 더움, 습기, 정리 문제 같은 생활 불편을 구체적으로 짚는다.\n"
            "- 둘째 줄은 상품군을 해결 후보처럼 자연스럽게 연결한다.\n"
            "- 치료, 보장, 확정 효과처럼 검증이 필요한 표현은 쓰지 않는다."
        ),
    ),
    PostConcept(
        id=CONCEPT_BUYING_GUIDE,
        number=4,
        name="구매 기준 제안",
        short_label="고르는 기준",
        description="상품을 고를 때 놓치기 쉬운 기준을 제안하는 실용형 컨셉입니다.",
        prompt=(
            "컨셉: 구매 기준 제안.\n"
            "- 첫 줄은 이 상품군을 고를 때 사람들이 놓치기 쉬운 기준 하나를 말한다.\n"
            "- 둘째 줄은 현재 상품이 그 기준으로 다시 보이게 만든다.\n"
            "- 가격, 성능, 효과를 확인 없이 단정하지 않는다."
        ),
    ),
)

_CONCEPT_BY_ID = {concept.id: concept for concept in POST_CONCEPTS}
_CONCEPT_BY_NUMBER = {str(concept.number): concept for concept in POST_CONCEPTS}


def normalize_concept_id(value: str | int | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return DEFAULT_POST_CONCEPT_ID
    if raw in _CONCEPT_BY_ID:
        return raw
    if raw in _CONCEPT_BY_NUMBER:
        return _CONCEPT_BY_NUMBER[raw].id
    lowered = raw.lower()
    for concept in POST_CONCEPTS:
        if lowered in {
            concept.id.lower(),
            concept.name.lower(),
            concept.short_label.lower(),
            concept.display_label.lower(),
        }:
            return concept.id
    return DEFAULT_POST_CONCEPT_ID


def get_post_concept(value: str | int | None = None) -> PostConcept:
    return _CONCEPT_BY_ID[normalize_concept_id(value)]


def concept_labels() -> list[str]:
    return [concept.display_label for concept in POST_CONCEPTS]


def concept_ids() -> list[str]:
    return [concept.id for concept in POST_CONCEPTS]


def format_current_issue_context(headlines: Iterable[str]) -> str:
    cleaned: list[str] = []
    for headline in headlines:
        text = " ".join(str(headline or "").split())
        if text and text not in cleaned:
            cleaned.append(text)
        if len(cleaned) >= 8:
            break
    if not cleaned:
        return "최신 헤드라인을 가져오지 못했다. 현재 계절, 날씨, 외출/집안 생활 상황 중심으로 작성한다."
    lines = "\n".join(f"- {headline}" for headline in cleaned)
    return f"현재 참고 가능한 한국 뉴스/상황 헤드라인:\n{lines}"
