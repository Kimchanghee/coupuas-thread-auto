import type { SurveyResponse } from "../../lib/survey.ts";

const JOINER = " | ";

function text(value: unknown) {
  if (Array.isArray(value)) return value.map((item) => String(item ?? "").trim()).filter(Boolean).join(JOINER);
  if (typeof value === "string") return value.trim();
  if (typeof value === "number") return Number.isFinite(value) ? value : "";
  if (typeof value === "boolean") return value ? "동의" : "미동의";
  return "";
}

export function toSheetRow(payload: SurveyResponse) {
  return [
    text(payload.id),
    text(payload.createdAt),
    text(payload.surveyVersion),
    "", // 이름은 authoritative store에만 보관
    "", // 이메일은 authoritative store에만 보관
    text(payload.privacyConsent),
    text(payload.marketingConsent),
    text(payload.interview),
    "", // 자유 입력은 Sheets 미러에서 제외
    text(payload.stage),
    text(payload.platforms),
    text(payload.monthlyPosts),
    "",
    text(payload.bottlenecks),
    text(payload.manualMinutes),
    text(payload.desiredPosts),
    text(payload.tools),
    text(payload.controlPreference),
    text(payload.intent),
    text(payload.priceReaction),
    text(payload.comfortablePrice),
    text(payload.paymentPreference),
    text(payload.valuedBundle),
    text(payload.purchaseBlockers),
    text(payload.purchaseTiming),
    text(payload.courseTopics),
    text(payload.support),
    text(payload.liveTime),
    "",
    "",
    "",
    "",
    "",
    text(payload.demandScore),
    text(payload.segment),
    "사전조사 접수",
  ];
}
