export const SURVEY_VERSION = "2.0-course-research";

export const platforms = [
  "쿠팡파트너스",
  "네이버 쇼핑커넥트",
  "토스쇼핑 파트너스",
  "오늘의집 큐레이터",
  "무신사 파트너스",
  "컬리 큐레이터",
  "올리브영 큐레이터",
] as const;

export const stages = [
  "관심만 있고 아직 시작 전",
  "제휴 플랫폼 가입만 완료",
  "링크를 만들고 가끔 게시",
  "주 3회 이상 직접 운영",
  "매일 운영하며 확장 중",
] as const;

export const monthlyPostOptions = ["0개", "1~5개", "6~15개", "16~30개", "31~90개", "90개 초과"] as const;

export const bottlenecks = [
  "팔릴 상품 고르기",
  "제휴 링크 발급·정리",
  "첫 문장과 후킹 쓰기",
  "이미지·영상 만들기",
  "채널마다 문장 다시 쓰기",
  "대가성 고지·정책 확인",
  "각 채널에 실제 게시하기",
  "매일 꾸준히 반복하기",
  "오류가 났을 때 해결하기",
] as const;

export const desiredPostOptions = ["1개", "2개", "3개", "5개", "10개 이상"] as const;

export const toolOptions = [
  "아직 써본 도구 없음",
  "ChatGPT·Claude 같은 AI",
  "Canva·CapCut",
  "Make·Zapier 같은 자동화",
  "예약 게시 도구",
  "직접 만든 엑셀·템플릿",
  "다른 유료 강의·전자책",
] as const;

export const controlPreferenceOptions = [
  "검수 없이 바로 게시",
  "결과를 보고 한 번 승인",
  "초기에는 승인, 익숙해지면 자동",
  "게시보다 초안 생성까지만",
] as const;

export const priceReactionOptions = [
  "바로 신청 가능",
  "상담 후 결정",
  "다른 상품과 비교 후 결정",
  "가격이 낮아져야 검토",
  "현재는 구매 어려움",
] as const;

export const comfortablePriceOptions = [
  "30만원 이하",
  "31~50만원",
  "51~70만원",
  "71~100만원",
  "성과·지원 조건에 따라 다름",
] as const;

export const paymentPreferenceOptions = ["", "일시불", "카드 할부", "분납", "상관없음"] as const;

export const bundleItems = [
  "프로그램 1년 사용권",
  "1:1 개인 강의",
  "막힐 때 원격 화면 과외",
  "사용법 전자책 PDF",
  "쇼핑 제휴 7개 플랫폼 지원",
  "게시 전 사람 승인·검수",
] as const;

export const purchaseBlockers = [
  "70만원 가격 부담",
  "정말 시간을 줄이는지 불확실",
  "설치·초기 설정이 어려울 것 같음",
  "내 계정과 플랫폼에서 되는지 걱정",
  "자동 게시의 계정·정책 위험 걱정",
  "생성되는 글·이미지 품질 걱정",
  "막혔을 때 지원이 충분한지 걱정",
  "실제 수익으로 이어질지 불확실",
] as const;

export const purchaseTimingOptions = ["지금 바로", "1개월 안", "3개월 안", "나중에 정보만 받고 싶음"] as const;

export const courseTopics = [
  "설치와 첫 실행",
  "7개 제휴 플랫폼 가입·링크 발급",
  "링크 입력부터 게시 전 승인까지",
  "한 상품에서 후킹 4종 고르기",
  "이미지·영상 결과 검수하기",
  "대가성 고지와 플랫폼 정책",
  "계정 연결·권한·안전 중단 기준",
  "오류 로그 읽고 복구하기",
  "채널별 게시 방식과 계정 톤",
  "클릭·구매·7일 지속률 측정",
  "14일 실전 운영 루틴",
] as const;

export const supportOptions = [
  "설치 당일 1:1 화면 공유",
  "첫 게시물까지 함께 세팅",
  "오류 발생 시 원격 접속",
  "카카오톡·채팅 질문",
  "단계별 PDF 체크리스트",
  "라이브 Q&A 다시보기",
  "계정별 문안 피드백",
] as const;

export const liveTimeOptions = [
  "평일 12~14시",
  "평일 18~20시",
  "평일 20~22시",
  "토요일 오전",
  "토요일 저녁",
  "녹화본 선호",
] as const;

export const contactMethodOptions = ["", "카카오톡", "인스타그램 DM", "문자"] as const;

export type FormState = {
  fullName: string;
  email: string;
  occupation: string;
  stage: string;
  platforms: string[];
  monthlyPosts: string;
  revenueExperience: string;
  bottlenecks: string[];
  manualMinutes: number;
  desiredPosts: string;
  tools: string[];
  controlPreference: string;
  intent: number;
  priceReaction: string;
  comfortablePrice: string;
  paymentPreference: string;
  valuedBundle: string[];
  purchaseBlockers: string[];
  purchaseTiming: string;
  courseTopics: string[];
  support: string[];
  liveTime: string;
  desiredOutcome: string;
  buyCondition: string;
  painWords: string;
  contactMethod: string;
  contact: string;
  interview: boolean;
  marketingConsent: boolean;
  privacyConsent: boolean;
};

export type SurveySubmission = FormState & {
  id: string;
  withdrawalToken: string;
};

export type SurveyResponse = FormState & {
  id: string;
  createdAt: string;
  surveyVersion: string;
  demandScore: number;
  segment: string;
};

export const initialForm: FormState = {
  fullName: "",
  email: "",
  occupation: "",
  stage: "",
  platforms: [],
  monthlyPosts: "",
  revenueExperience: "",
  bottlenecks: [],
  manualMinutes: 30,
  desiredPosts: "",
  tools: [],
  controlPreference: "",
  intent: 5,
  priceReaction: "",
  comfortablePrice: "",
  paymentPreference: "",
  valuedBundle: [],
  purchaseBlockers: [],
  purchaseTiming: "",
  courseTopics: [],
  support: [],
  liveTime: "",
  desiredOutcome: "",
  buyCondition: "",
  painWords: "",
  contactMethod: "",
  contact: "",
  interview: false,
  marketingConsent: false,
  privacyConsent: false,
};

const FORM_KEYS = Object.keys(initialForm) as (keyof FormState)[];
const SUBMISSION_KEYS = new Set([...FORM_KEYS, "id", "withdrawalToken"]);
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const UUID_V4_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const TOKEN_PATTERN = /^[A-Za-z0-9_-]{43,128}$/;

type ValidationResult<T> = { ok: true; value: T } | { ok: false; message: string };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizedString(value: unknown, label: string, maxLength: number, required = true): ValidationResult<string> {
  if (typeof value !== "string") return { ok: false, message: `${label} 형식이 올바르지 않습니다.` };
  const normalized = value.trim();
  if (required && normalized.length === 0) return { ok: false, message: `${label}을(를) 입력해주세요.` };
  if (normalized.length > maxLength) return { ok: false, message: `${label}은(는) ${maxLength}자 이하여야 합니다.` };
  return { ok: true, value: normalized };
}

function enumValue(value: unknown, choices: readonly string[], label: string, allowEmpty = false): ValidationResult<string> {
  if (allowEmpty && value === "") return { ok: true, value: "" };
  if (typeof value !== "string" || !choices.includes(value)) return { ok: false, message: `${label} 선택값이 올바르지 않습니다.` };
  return { ok: true, value };
}

function enumArray(value: unknown, choices: readonly string[], label: string, max = choices.length): ValidationResult<string[]> {
  if (!Array.isArray(value) || value.length < 1 || value.length > max) {
    return { ok: false, message: `${label} 선택 개수를 확인해주세요.` };
  }
  if (value.some((item) => typeof item !== "string" || !choices.includes(item))) {
    return { ok: false, message: `${label} 선택값이 올바르지 않습니다.` };
  }
  if (new Set(value).size !== value.length) return { ok: false, message: `${label}에 중복된 선택이 있습니다.` };
  return { ok: true, value: [...value] };
}

function booleanValue(value: unknown, label: string): ValidationResult<boolean> {
  return typeof value === "boolean" ? { ok: true, value } : { ok: false, message: `${label} 형식이 올바르지 않습니다.` };
}

export function validateFormState(input: unknown): ValidationResult<FormState> {
  if (!isRecord(input)) return { ok: false, message: "설문 응답 형식이 올바르지 않습니다." };

  const fullName = normalizedString(input.fullName, "이름", 80);
  const email = normalizedString(input.email, "이메일", 254);
  const occupation = normalizedString(input.occupation, "현재 일·업종", 120, false);
  const stage = enumValue(input.stage, stages, "현재 단계");
  const selectedPlatforms = enumArray(input.platforms, platforms, "관심 플랫폼");
  const monthlyPosts = enumValue(input.monthlyPosts, monthlyPostOptions, "월 게시량");
  const revenueExperience = normalizedString(input.revenueExperience, "제휴 수익 경험", 200, false);
  const selectedBottlenecks = enumArray(input.bottlenecks, bottlenecks, "병목");
  const desiredPosts = enumValue(input.desiredPosts, desiredPostOptions, "목표 게시량");
  const tools = enumArray(input.tools, toolOptions, "사용 도구");
  const controlPreference = enumValue(input.controlPreference, controlPreferenceOptions, "게시 승인 방식");
  const priceReaction = enumValue(input.priceReaction, priceReactionOptions, "가격 반응");
  const comfortablePrice = enumValue(input.comfortablePrice, comfortablePriceOptions, "편한 결제 범위");
  const paymentPreference = enumValue(input.paymentPreference, paymentPreferenceOptions, "결제 방식", true);
  const valuedBundle = enumArray(input.valuedBundle, bundleItems, "중요 포함 항목");
  const selectedPurchaseBlockers = enumArray(input.purchaseBlockers, purchaseBlockers, "구매 방해 요소");
  const purchaseTiming = enumValue(input.purchaseTiming, purchaseTimingOptions, "구매 시기");
  const selectedCourseTopics = enumArray(input.courseTopics, courseTopics, "강의 주제", 3);
  const selectedSupport = enumArray(input.support, supportOptions, "지원 방식");
  const liveTime = enumValue(input.liveTime, liveTimeOptions, "라이브 시간");
  const desiredOutcome = normalizedString(input.desiredOutcome, "원하는 결과", 1000);
  const buyCondition = normalizedString(input.buyCondition, "구매 조건", 1000);
  const painWords = normalizedString(input.painWords, "불편 문장", 1000);
  const contactMethod = enumValue(input.contactMethod, contactMethodOptions, "연락 방법", true);
  const contact = normalizedString(input.contact, "연락처", 100, false);
  const interview = booleanValue(input.interview, "인터뷰 동의");
  const marketingConsent = booleanValue(input.marketingConsent, "마케팅 수신 동의");
  const privacyConsent = booleanValue(input.privacyConsent, "개인정보 동의");

  const results = [
    fullName, email, occupation, stage, selectedPlatforms, monthlyPosts, revenueExperience,
    selectedBottlenecks, desiredPosts, tools, controlPreference, priceReaction, comfortablePrice,
    paymentPreference, valuedBundle, selectedPurchaseBlockers, purchaseTiming, selectedCourseTopics,
    selectedSupport, liveTime, desiredOutcome, buyCondition, painWords, contactMethod, contact,
    interview, marketingConsent, privacyConsent,
  ];
  const failed = results.find((result) => !result.ok);
  if (failed && !failed.ok) return failed;

  const normalizedEmail = email.ok ? email.value.toLowerCase() : "";
  if (!EMAIL_PATTERN.test(normalizedEmail)) return { ok: false, message: "이메일 형식이 올바르지 않습니다." };
  if (!Number.isInteger(input.manualMinutes) || Number(input.manualMinutes) < 5 || Number(input.manualMinutes) > 180 || Number(input.manualMinutes) % 5 !== 0) {
    return { ok: false, message: "수작업 시간은 5~180분 범위에서 5분 단위로 입력해주세요." };
  }
  if (!Number.isInteger(input.intent) || Number(input.intent) < 0 || Number(input.intent) > 10) {
    return { ok: false, message: "구매 의향은 0~10 사이의 정수여야 합니다." };
  }
  if (contactMethod.ok && contact.ok && Boolean(contactMethod.value) !== Boolean(contact.value)) {
    return { ok: false, message: "추가 연락처와 연락 방법을 함께 입력해주세요." };
  }
  if (!privacyConsent.ok || privacyConsent.value !== true) {
    return { ok: false, message: "개인정보 수집·이용 필수 동의를 확인해주세요." };
  }

  return {
    ok: true,
    value: {
      fullName: fullName.ok ? fullName.value : "",
      email: normalizedEmail,
      occupation: occupation.ok ? occupation.value : "",
      stage: stage.ok ? stage.value : "",
      platforms: selectedPlatforms.ok ? selectedPlatforms.value : [],
      monthlyPosts: monthlyPosts.ok ? monthlyPosts.value : "",
      revenueExperience: revenueExperience.ok ? revenueExperience.value : "",
      bottlenecks: selectedBottlenecks.ok ? selectedBottlenecks.value : [],
      manualMinutes: Number(input.manualMinutes),
      desiredPosts: desiredPosts.ok ? desiredPosts.value : "",
      tools: tools.ok ? tools.value : [],
      controlPreference: controlPreference.ok ? controlPreference.value : "",
      intent: Number(input.intent),
      priceReaction: priceReaction.ok ? priceReaction.value : "",
      comfortablePrice: comfortablePrice.ok ? comfortablePrice.value : "",
      paymentPreference: paymentPreference.ok ? paymentPreference.value : "",
      valuedBundle: valuedBundle.ok ? valuedBundle.value : [],
      purchaseBlockers: selectedPurchaseBlockers.ok ? selectedPurchaseBlockers.value : [],
      purchaseTiming: purchaseTiming.ok ? purchaseTiming.value : "",
      courseTopics: selectedCourseTopics.ok ? selectedCourseTopics.value : [],
      support: selectedSupport.ok ? selectedSupport.value : [],
      liveTime: liveTime.ok ? liveTime.value : "",
      desiredOutcome: desiredOutcome.ok ? desiredOutcome.value : "",
      buyCondition: buyCondition.ok ? buyCondition.value : "",
      painWords: painWords.ok ? painWords.value : "",
      contactMethod: contactMethod.ok ? contactMethod.value : "",
      contact: contact.ok ? contact.value : "",
      interview: interview.ok ? interview.value : false,
      marketingConsent: marketingConsent.ok ? marketingConsent.value : false,
      privacyConsent: true,
    },
  };
}

export function validateDraftFormState(input: unknown): ValidationResult<FormState> {
  if (!isRecord(input) || FORM_KEYS.some((key) => !(key in input)) || Object.keys(input).some((key) => !FORM_KEYS.includes(key as keyof FormState))) {
    return { ok: false, message: "임시 저장된 설문 형식이 올바르지 않습니다." };
  }
  const stringLimits: Partial<Record<keyof FormState, number>> = {
    fullName: 80, email: 254, occupation: 120, revenueExperience: 200,
    desiredOutcome: 1000, buyCondition: 1000, painWords: 1000, contact: 100,
  };
  for (const [key, limit] of Object.entries(stringLimits)) {
    if (typeof input[key] !== "string" || (input[key] as string).length > Number(limit)) {
      return { ok: false, message: "임시 저장된 텍스트 형식이 올바르지 않습니다." };
    }
  }
  const enumFields: [keyof FormState, readonly string[]][] = [
    ["stage", ["", ...stages]], ["monthlyPosts", ["", ...monthlyPostOptions]],
    ["desiredPosts", ["", ...desiredPostOptions]], ["controlPreference", ["", ...controlPreferenceOptions]],
    ["priceReaction", ["", ...priceReactionOptions]], ["comfortablePrice", ["", ...comfortablePriceOptions]],
    ["paymentPreference", paymentPreferenceOptions], ["purchaseTiming", ["", ...purchaseTimingOptions]],
    ["liveTime", ["", ...liveTimeOptions]], ["contactMethod", contactMethodOptions],
  ];
  if (enumFields.some(([key, choices]) => typeof input[key] !== "string" || !choices.includes(input[key] as string))) {
    return { ok: false, message: "임시 저장된 선택값이 올바르지 않습니다." };
  }
  const arrayFields: [keyof FormState, readonly string[], number][] = [
    ["platforms", platforms, platforms.length], ["bottlenecks", bottlenecks, bottlenecks.length],
    ["tools", toolOptions, toolOptions.length], ["valuedBundle", bundleItems, bundleItems.length],
    ["purchaseBlockers", purchaseBlockers, purchaseBlockers.length], ["courseTopics", courseTopics, 3],
    ["support", supportOptions, supportOptions.length],
  ];
  for (const [key, choices, max] of arrayFields) {
    const value = input[key];
    if (!Array.isArray(value) || value.length > max || new Set(value).size !== value.length || value.some((item) => typeof item !== "string" || !choices.includes(item))) {
      return { ok: false, message: "임시 저장된 복수 선택값이 올바르지 않습니다." };
    }
  }
  if (!Number.isInteger(input.manualMinutes) || Number(input.manualMinutes) < 5 || Number(input.manualMinutes) > 180 || Number(input.manualMinutes) % 5 !== 0) {
    return { ok: false, message: "임시 저장된 시간 값이 올바르지 않습니다." };
  }
  if (!Number.isInteger(input.intent) || Number(input.intent) < 0 || Number(input.intent) > 10) {
    return { ok: false, message: "임시 저장된 구매 의향 값이 올바르지 않습니다." };
  }
  for (const key of ["interview", "marketingConsent", "privacyConsent"] as const) {
    if (typeof input[key] !== "boolean") return { ok: false, message: "임시 저장된 동의 값이 올바르지 않습니다." };
  }
  return { ok: true, value: structuredClone(input) as FormState };
}

export function validateSurveySubmission(input: unknown): ValidationResult<SurveySubmission> {
  if (!isRecord(input)) return { ok: false, message: "설문 응답 형식이 올바르지 않습니다." };
  if (Object.keys(input).some((key) => !SUBMISSION_KEYS.has(key))) {
    return { ok: false, message: "허용되지 않은 설문 필드가 포함되어 있습니다." };
  }
  if (FORM_KEYS.some((key) => !(key in input))) return { ok: false, message: "필수 설문 필드가 누락되었습니다." };

  const form = validateFormState(input);
  if (!form.ok) return form;
  if (typeof input.id !== "string" || !UUID_V4_PATTERN.test(input.id)) {
    return { ok: false, message: "응답 ID 형식이 올바르지 않습니다." };
  }
  if (typeof input.withdrawalToken !== "string" || !TOKEN_PATTERN.test(input.withdrawalToken)) {
    return { ok: false, message: "응답 철회 증명 형식이 올바르지 않습니다." };
  }
  return { ok: true, value: { ...form.value, id: input.id.toLowerCase(), withdrawalToken: input.withdrawalToken } };
}

export function calculateDemand(form: FormState): number {
  const intentScore = form.intent * 5;
  const urgency = form.purchaseTiming === "지금 바로" ? 15 : form.purchaseTiming === "1개월 안" ? 12 : form.purchaseTiming === "3개월 안" ? 7 : 2;
  const workload = form.manualMinutes >= 60 ? 10 : form.manualMinutes >= 30 ? 7 : 4;
  const stageScore = form.stage.includes("매일") ? 10 : form.stage.includes("주 3회") ? 8 : form.stage.includes("가끔") ? 6 : 3;
  const priceScore = form.priceReaction === "바로 신청 가능" ? 15 : form.priceReaction === "상담 후 결정" ? 11 : form.priceReaction === "다른 상품과 비교 후 결정" ? 6 : 1;
  return Math.min(100, intentScore + urgency + workload + stageScore + priceScore);
}

export function demandSegment(score: number): string {
  if (score >= 75) return "우선 상담 고객";
  if (score >= 55) return "조건 확인 고객";
  if (score >= 35) return "교육 필요 고객";
  return "초기 관심 고객";
}

export function createSurveyResponse(form: FormState, id: string, createdAt: string): SurveyResponse {
  const safeForm = Object.fromEntries(FORM_KEYS.map((key) => [key, form[key]])) as FormState;
  const demandScore = calculateDemand(safeForm);
  return {
    ...safeForm,
    id,
    createdAt,
    surveyVersion: SURVEY_VERSION,
    demandScore,
    segment: demandSegment(demandScore),
  };
}

export function formFromSubmission(submission: SurveySubmission): FormState {
  return Object.fromEntries(FORM_KEYS.map((key) => [key, submission[key]])) as FormState;
}

export function formFromSurveyResponse(response: SurveyResponse): FormState {
  return structuredClone(Object.fromEntries(FORM_KEYS.map((key) => [key, response[key]])) as FormState);
}

export function isSurveyResponse(value: unknown): value is SurveyResponse {
  if (!isRecord(value) || typeof value.id !== "string" || !UUID_V4_PATTERN.test(value.id)) return false;
  if (typeof value.createdAt !== "string" || !Number.isFinite(Date.parse(value.createdAt))) return false;
  if (value.surveyVersion !== SURVEY_VERSION || typeof value.demandScore !== "number" || typeof value.segment !== "string") return false;
  const formInput = Object.fromEntries(FORM_KEYS.map((key) => [key, value[key]]));
  const form = validateFormState(formInput);
  return form.ok && calculateDemand(form.value) === value.demandScore && demandSegment(value.demandScore) === value.segment;
}

export function isSubmissionCredential(value: unknown): value is { id: string; withdrawalToken: string } {
  return isRecord(value)
    && typeof value.id === "string"
    && UUID_V4_PATTERN.test(value.id)
    && typeof value.withdrawalToken === "string"
    && TOKEN_PATTERN.test(value.withdrawalToken);
}
