import { initialForm, type FormState, type SurveySubmission } from "../app/lib/survey.ts";

export function validForm(overrides: Partial<FormState> = {}): FormState {
  return {
    ...structuredClone(initialForm),
    fullName: "홍길동",
    email: "Person@Example.COM ",
    stage: "매일 운영하며 확장 중",
    platforms: ["쿠팡파트너스"],
    monthlyPosts: "31~90개",
    bottlenecks: ["매일 꾸준히 반복하기"],
    manualMinutes: 60,
    desiredPosts: "5개",
    tools: ["ChatGPT·Claude 같은 AI"],
    controlPreference: "결과를 보고 한 번 승인",
    intent: 10,
    priceReaction: "다른 상품과 비교 후 결정",
    comfortablePrice: "51~70만원",
    valuedBundle: ["프로그램 1년 사용권"],
    purchaseBlockers: ["70만원 가격 부담"],
    purchaseTiming: "지금 바로",
    courseTopics: ["설치와 첫 실행"],
    support: ["설치 당일 1:1 화면 공유"],
    liveTime: "평일 20~22시",
    desiredOutcome: "매일 운영 루틴 만들기",
    buyCondition: "실제 계정에서 첫 게시 확인",
    painWords: "매번 글을 다시 쓰는 일이 힘들어요",
    privacyConsent: true,
    ...overrides,
  };
}

export function validSubmission(overrides: Partial<SurveySubmission> = {}): SurveySubmission {
  return {
    ...validForm(),
    id: "123e4567-e89b-42d3-a456-426614174000",
    withdrawalToken: "a".repeat(43),
    ...overrides,
  };
}
