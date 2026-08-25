import assert from "node:assert/strict";
import test from "node:test";
import {
  calculateDemand,
  createSurveyResponse,
  initialForm,
  validateDraftFormState,
  validateSurveySubmission,
} from "../app/lib/survey.ts";
import { toSheetRow } from "../app/api/reservations/sheet-row.ts";
import { validForm, validSubmission } from "./fixtures.ts";

test("visible comparison option receives its intended six-point price score", () => {
  const form = validForm();
  assert.equal(calculateDemand(form), 91);
  assert.equal(calculateDemand({ ...form, priceReaction: "현재는 구매 어려움" }), 86);
});

test("strict submission schema normalizes email and rejects client-owned or unknown fields", () => {
  const accepted = validateSurveySubmission(validSubmission());
  assert.equal(accepted.ok, true);
  if (accepted.ok) assert.equal(accepted.value.email, "person@example.com");

  for (const extra of [
    { createdAt: "2020-01-01T00:00:00.000Z" },
    { demandScore: 100 },
    { segment: "조작" },
    { adminNote: "관리자" },
  ]) {
    const rejected = validateSurveySubmission({ ...validSubmission(), ...extra });
    assert.equal(rejected.ok, false);
  }
});

test("schema rejects invalid enums, duplicate arrays, oversized text and incomplete contact", () => {
  assert.equal(validateSurveySubmission(validSubmission({ stage: "임의 단계" })).ok, false);
  assert.equal(validateSurveySubmission(validSubmission({ platforms: ["쿠팡파트너스", "쿠팡파트너스"] })).ok, false);
  assert.equal(validateSurveySubmission(validSubmission({ painWords: "가".repeat(1001) })).ok, false);
  assert.equal(validateSurveySubmission(validSubmission({ contactMethod: "문자", contact: "" })).ok, false);
  assert.equal(validateSurveySubmission({ ...validSubmission(), privacyConsent: false }).ok, false);
});

test("draft schema accepts incomplete valid forms and rejects corrupted shapes", () => {
  assert.equal(validateDraftFormState(structuredClone(initialForm)).ok, true);
  assert.equal(validateDraftFormState({}).ok, false);
  assert.equal(validateDraftFormState({ ...initialForm, platforms: {} }).ok, false);
});

test("Sheets reporting row omits direct identifiers and free text", () => {
  const normalized = validateSurveySubmission(validSubmission());
  assert.equal(normalized.ok, true);
  if (!normalized.ok) return;
  const response = createSurveyResponse(normalized.value, normalized.value.id, "2026-08-26T00:00:00.000Z");
  const row = toSheetRow(response);
  assert.equal(row.length, 36);
  assert.equal(row[0], response.id);
  for (const index of [3, 4, 8, 12, 28, 29, 30, 31, 32]) assert.equal(row[index], "");
  assert.equal(row.includes(response.email), false);
  assert.equal(row.includes(response.painWords), false);
});
