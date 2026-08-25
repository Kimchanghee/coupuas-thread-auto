import { isSubmissionCredential, isSurveyResponse, validateDraftFormState, type FormState, type SurveyResponse } from "./survey.ts";

export const DRAFT_STORAGE_KEY = "thread-auto-demand-draft-v2";
export const RECEIPT_STORAGE_KEY = "thread-auto-demand-receipt-v2";
export const DRAFT_TTL_MS = 30 * 24 * 60 * 60 * 1000;
export const RECEIPT_TTL_MS = 365 * 24 * 60 * 60 * 1000;

export type SubmissionCredential = { id: string; withdrawalToken: string };
export type DraftRecord = { form: FormState; credential: SubmissionCredential };
export type ReceiptMirrorStatus = "pending" | "mirrored";
export type ReceiptSummary = Pick<SurveyResponse, "id" | "createdAt" | "surveyVersion">;
export type ReceiptRecord = { response: ReceiptSummary; credential: SubmissionCredential; mirrorStatus: ReceiptMirrorStatus };

type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;
type Envelope = { version: 2; expiresAt: number; value: unknown };

function readEnvelope(storage: StorageLike, key: string, now: number, onExpired?: () => void): unknown | null {
  try {
    const raw = storage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<Envelope>;
    if (parsed.version !== 2 || typeof parsed.expiresAt !== "number" || parsed.expiresAt <= now) {
      storage.removeItem(key);
      if (typeof parsed.expiresAt === "number" && parsed.expiresAt <= now) onExpired?.();
      return null;
    }
    return parsed.value;
  } catch {
    try { storage.removeItem(key); } catch { /* best-effort cleanup */ }
    return null;
  }
}

function writeEnvelope(storage: StorageLike, key: string, value: unknown, expiresAt: number): boolean {
  try {
    storage.setItem(key, JSON.stringify({ version: 2, expiresAt, value } satisfies Envelope));
    return true;
  } catch {
    return false;
  }
}

export function loadDraft(storage: StorageLike, now = Date.now()): DraftRecord | null {
  const value = readEnvelope(storage, DRAFT_STORAGE_KEY, now);
  if (!value || typeof value !== "object") return null;
  const candidate = value as Partial<DraftRecord>;
  const form = validateDraftFormState(candidate.form);
  if (!form.ok || !isSubmissionCredential(candidate.credential)) {
    try { storage.removeItem(DRAFT_STORAGE_KEY); } catch { /* best-effort cleanup */ }
    return null;
  }
  return { form: form.value, credential: candidate.credential };
}

export function saveDraft(storage: StorageLike, draft: DraftRecord, now = Date.now()): boolean {
  return writeEnvelope(storage, DRAFT_STORAGE_KEY, draft, now + DRAFT_TTL_MS);
}

export function loadReceipt(storage: StorageLike, now = Date.now()): ReceiptRecord | null {
  const value = readEnvelope(storage, RECEIPT_STORAGE_KEY, now, () => clearSurveyStorage(storage));
  if (!value || typeof value !== "object") return null;
  const candidate = value as Partial<ReceiptRecord>;
  const keys = Object.keys(value);
  const hasOnlyKnownKeys = keys.every((key) => key === "response" || key === "credential" || key === "mirrorStatus");
  const mirrorStatus = candidate.mirrorStatus ?? "pending";
  const response = receiptSummary(candidate.response);
  if (!hasOnlyKnownKeys || (mirrorStatus !== "pending" && mirrorStatus !== "mirrored") || !response || !isSubmissionCredential(candidate.credential) || response.id !== candidate.credential.id) {
    try { storage.removeItem(RECEIPT_STORAGE_KEY); } catch { /* best-effort cleanup */ }
    return null;
  }
  const receipt = { response, credential: candidate.credential, mirrorStatus };
  const expiresAt = receiptExpiresAt(receipt.response);
  if (!Number.isFinite(expiresAt) || expiresAt <= now) {
    clearSurveyStorage(storage);
    return null;
  }
  // Migrate old rolling-expiry envelopes and ensure every reload retains the
  // original submission-based deadline instead of extending it.
  writeEnvelope(storage, RECEIPT_STORAGE_KEY, receipt, expiresAt);
  return receipt;
}

export function saveReceipt(storage: StorageLike, receipt: ReceiptRecord, now = Date.now()): boolean {
  const summary = receiptSummary(receipt.response);
  if (!summary || !isSubmissionCredential(receipt.credential) || summary.id !== receipt.credential.id || (receipt.mirrorStatus !== "pending" && receipt.mirrorStatus !== "mirrored")) return false;
  const expiresAt = receiptExpiresAt(summary);
  if (!Number.isFinite(expiresAt) || expiresAt <= now) {
    clearSurveyStorage(storage);
    return false;
  }
  return writeEnvelope(storage, RECEIPT_STORAGE_KEY, { ...receipt, response: summary }, expiresAt);
}

export function receiptExpiresAt(response: Pick<ReceiptSummary, "createdAt">): number {
  return Date.parse(response.createdAt) + RECEIPT_TTL_MS;
}

export function isReceiptExpired(response: Pick<ReceiptSummary, "createdAt">, now = Date.now()): boolean {
  return receiptExpiresAt(response) <= now;
}

export function receiptSummary(value: unknown): ReceiptSummary | null {
  if (isSurveyResponse(value)) {
    return {
      id: value.id,
      createdAt: value.createdAt,
      surveyVersion: value.surveyVersion,
    };
  }
  if (!value || typeof value !== "object") return null;
  const candidate = value as Partial<ReceiptSummary>;
  const keys = Object.keys(value);
  if (!keys.every((key) => ["id", "createdAt", "surveyVersion"].includes(key))) return null;
  if (typeof candidate.id !== "string" || typeof candidate.createdAt !== "string" || !Number.isFinite(Date.parse(candidate.createdAt))) return null;
  if (typeof candidate.surveyVersion !== "string" || candidate.surveyVersion.length > 40) return null;
  return candidate as ReceiptSummary;
}

export function clearSurveyStorage(storage: StorageLike): void {
  for (const key of [DRAFT_STORAGE_KEY, RECEIPT_STORAGE_KEY, "thread-auto-demand-draft-v1", "thread-auto-demand-responses-v1"]) {
    try { storage.removeItem(key); } catch { /* best-effort cleanup */ }
  }
}

export function clearDraftStorage(storage: StorageLike): void {
  for (const key of [DRAFT_STORAGE_KEY, "thread-auto-demand-draft-v1"]) {
    try { storage.removeItem(key); } catch { /* best-effort cleanup */ }
  }
}

export function clearLegacySurveyStorage(storage: StorageLike): void {
  for (const key of ["thread-auto-demand-draft-v1", "thread-auto-demand-responses-v1"]) {
    try { storage.removeItem(key); } catch { /* best-effort cleanup */ }
  }
}

export function createSubmissionCredential(): SubmissionCredential {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  const withdrawalToken = btoa(String.fromCharCode(...bytes))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replace(/=+$/u, "");
  return { id: crypto.randomUUID(), withdrawalToken };
}
