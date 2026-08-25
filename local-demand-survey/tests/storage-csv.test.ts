import assert from "node:assert/strict";
import test from "node:test";
import {
  clearDraftStorage,
  clearLegacySurveyStorage,
  clearSurveyStorage,
  DRAFT_STORAGE_KEY,
  DRAFT_TTL_MS,
  loadDraft,
  loadReceipt,
  RECEIPT_STORAGE_KEY,
  RECEIPT_TTL_MS,
  receiptSummary,
  saveDraft,
  saveReceipt,
} from "../app/lib/client-storage.ts";
import { createSurveyResponse, formFromSubmission, validateSurveySubmission } from "../app/lib/survey.ts";
import { csvEscape, neutralizeSpreadsheetFormula } from "../app/lib/csv.ts";
import { validSubmission } from "./fixtures.ts";

class FakeStorage {
  readonly values = new Map<string, string>();
  failWrites = false;
  getItem(key: string) { return this.values.get(key) ?? null; }
  setItem(key: string, value: string) {
    if (this.failWrites) throw new Error("quota exceeded");
    this.values.set(key, value);
  }
  removeItem(key: string) { this.values.delete(key); }
}

function records(createdAt = "2026-08-26T00:00:00.000Z") {
  const submission = validateSurveySubmission(validSubmission());
  if (!submission.ok) throw new Error(submission.message);
  assert.equal(submission.ok, true);
  const credential = { id: submission.value.id, withdrawalToken: submission.value.withdrawalToken };
  const form = formFromSubmission(submission.value);
  const response = createSurveyResponse(form, credential.id, createdAt);
  const summary = receiptSummary(response);
  if (!summary) throw new Error("receipt summary failed");
  return { credential, form, response, summary };
}

test("draft and receipt storage validate schema and expire stale values", () => {
  const storage = new FakeStorage();
  const { credential, form, response, summary } = records();
  assert.equal(saveDraft(storage, { form, credential }, 1000), true);
  assert.deepEqual(loadDraft(storage, 1001), { form, credential });
  assert.equal(loadDraft(storage, 1000 + DRAFT_TTL_MS + 1), null);
  assert.equal(storage.getItem(DRAFT_STORAGE_KEY), null);

  // Even a legacy/full response passed by a caller is canonicalized before persistence.
  assert.equal(saveReceipt(storage, { response, credential, mirrorStatus: "mirrored" }, 2000), true);
  assert.doesNotMatch(storage.getItem(RECEIPT_STORAGE_KEY) ?? "", /fullName|email|painWords|demandScore|segment/);
  assert.deepEqual(loadReceipt(storage, 2001), { response: summary, credential, mirrorStatus: "mirrored" });
});

test("corrupt localStorage never reaches the UI and write failures remain best effort", () => {
  const storage = new FakeStorage();
  storage.values.set(DRAFT_STORAGE_KEY, JSON.stringify({ version: 2, expiresAt: Date.now() + 1000, value: {} }));
  storage.values.set(RECEIPT_STORAGE_KEY, "{broken");
  assert.equal(loadDraft(storage), null);
  assert.equal(loadReceipt(storage), null);

  storage.failWrites = true;
  const { credential, form, summary } = records();
  assert.equal(saveDraft(storage, { form, credential }), false);
  assert.equal(saveReceipt(storage, { response: summary, credential, mirrorStatus: "pending" }), false);
});

test("a pending mirror receipt stores only a summary and retry credential", () => {
  const localStorage = new FakeStorage();
  const sessionStorage = new FakeStorage();
  const { credential, form, summary } = records();
  assert.equal(saveDraft(sessionStorage, { form, credential }, 1000), true);
  assert.equal(saveReceipt(localStorage, { response: summary, credential, mirrorStatus: "pending" }, 1000), true);

  const reloadedReceipt = loadReceipt(localStorage, 1001);
  const reloadedDraft = loadDraft(sessionStorage, 1001);
  assert.ok(reloadedReceipt);
  assert.deepEqual(reloadedDraft, { form, credential });
  assert.equal(reloadedReceipt.mirrorStatus, "pending");
  const persisted = localStorage.getItem(RECEIPT_STORAGE_KEY) ?? "";
  assert.doesNotMatch(persisted, /Person Name|person@example\.com|painWords|fullName|email|demandScore|segment/);

  assert.equal(saveReceipt(localStorage, { ...reloadedReceipt, mirrorStatus: "mirrored" }, 1002), true);
  clearDraftStorage(sessionStorage);
  assert.equal(loadDraft(sessionStorage, 1003), null);
  assert.equal(loadReceipt(localStorage, 1003)?.mirrorStatus, "mirrored");
});

test("legacy v2 receipts without mirror status migrate conservatively to pending", () => {
  const storage = new FakeStorage();
  const { credential, response } = records();
  storage.values.set(RECEIPT_STORAGE_KEY, JSON.stringify({
    version: 2,
    expiresAt: 5000,
    value: { response, credential },
  }));
  const migrated = loadReceipt(storage, 1000);
  assert.equal(migrated?.mirrorStatus, "pending");
  assert.deepEqual(migrated?.response, receiptSummary(response));
  assert.doesNotMatch(storage.getItem(RECEIPT_STORAGE_KEY) ?? "", /person@example\.com|fullName|email|demandScore|segment/);
});

test("repeated receipt reloads and mirror retries cannot extend PII retention", () => {
  const storage = new FakeStorage();
  const createdAt = Date.parse("2026-01-01T00:00:00.000Z");
  const deadline = createdAt + RECEIPT_TTL_MS;
  const { credential, form, summary } = records(new Date(createdAt).toISOString());

  assert.equal(saveReceipt(storage, { response: summary, credential, mirrorStatus: "pending" }, createdAt + 1), true);
  const storedExpiry = () => JSON.parse(storage.getItem(RECEIPT_STORAGE_KEY) ?? "null")?.expiresAt;
  assert.equal(storedExpiry(), deadline);

  const afterReload = loadReceipt(storage, createdAt + 100 * 24 * 60 * 60 * 1000);
  assert.ok(afterReload);
  assert.equal(storedExpiry(), deadline);
  assert.equal(saveReceipt(storage, { ...afterReload, mirrorStatus: "mirrored" }, deadline - 1), true);
  assert.equal(storedExpiry(), deadline);

  // A pending retry can leave a 30-day draft near the receipt deadline. Once
  // the absolute receipt deadline arrives, loading it removes both records.
  assert.equal(saveDraft(storage, { form, credential }, deadline - 1000), true);
  assert.equal(loadReceipt(storage, deadline), null);
  assert.equal(storage.getItem(RECEIPT_STORAGE_KEY), null);
  assert.equal(storage.getItem(DRAFT_STORAGE_KEY), null);
});

test("an old rolling-expiry envelope cannot bypass the response creation deadline", () => {
  const storage = new FakeStorage();
  const createdAt = Date.parse("2026-01-01T00:00:00.000Z");
  const deadline = createdAt + RECEIPT_TTL_MS;
  const { credential, form, summary } = records(new Date(createdAt).toISOString());
  assert.equal(saveReceipt(storage, { response: summary, credential, mirrorStatus: "pending" }, createdAt + 1), true);
  assert.equal(saveDraft(storage, { form, credential }, deadline - 1000), true);

  const envelope = JSON.parse(storage.getItem(RECEIPT_STORAGE_KEY) ?? "null");
  envelope.expiresAt = deadline + RECEIPT_TTL_MS;
  storage.values.set(RECEIPT_STORAGE_KEY, JSON.stringify(envelope));

  assert.equal(loadReceipt(storage, deadline), null);
  assert.equal(storage.getItem(RECEIPT_STORAGE_KEY), null);
  assert.equal(storage.getItem(DRAFT_STORAGE_KEY), null);
});

test("full local cleanup removes current and legacy PII keys", () => {
  const storage = new FakeStorage();
  for (const key of [DRAFT_STORAGE_KEY, RECEIPT_STORAGE_KEY, "thread-auto-demand-draft-v1", "thread-auto-demand-responses-v1"]) storage.values.set(key, "value");
  clearSurveyStorage(storage);
  assert.equal(storage.values.size, 0);
});

test("successful receipt migration removes only draft data and legacy PII", () => {
  const storage = new FakeStorage();
  storage.values.set(DRAFT_STORAGE_KEY, "draft");
  storage.values.set(RECEIPT_STORAGE_KEY, "receipt");
  storage.values.set("thread-auto-demand-draft-v1", "legacy-draft");
  storage.values.set("thread-auto-demand-responses-v1", "legacy-responses");
  clearDraftStorage(storage);
  clearLegacySurveyStorage(storage);
  assert.equal(storage.getItem(DRAFT_STORAGE_KEY), null);
  assert.equal(storage.getItem(RECEIPT_STORAGE_KEY), "receipt");
  assert.equal(storage.getItem("thread-auto-demand-responses-v1"), null);
});

test("CSV cells neutralize spreadsheet formulas before quoting", () => {
  for (const prefix of ["=", "+", "-", "@", "\t", "\r", "\n"]) {
    assert.equal(neutralizeSpreadsheetFormula(`${prefix}SUM(A1:A2)`).startsWith("'"), true);
  }
  assert.equal(csvEscape('=CMD("x")'), '"\'=CMD(""x"")"');
  assert.equal(csvEscape("ordinary"), '"ordinary"');
});
