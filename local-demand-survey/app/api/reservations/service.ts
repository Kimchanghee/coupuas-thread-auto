import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import { createSurveyResponse, formFromSubmission, isSubmissionCredential, validateSurveySubmission, type SurveyResponse } from "../../lib/survey.ts";
import type { StoredSurveyResponse, SurveyRateLimiter, SurveyStore } from "./store.ts";

export const MAX_REQUEST_BYTES = 32 * 1024;

export interface SurveyMirror {
  append(response: SurveyResponse): Promise<void>;
  remove(responseId: string): Promise<void>;
  health(): Promise<boolean>;
}

export type SurveyServiceDependencies = {
  store: SurveyStore;
  rateLimiter: SurveyRateLimiter;
  mirror: SurveyMirror;
  hmacSecret: string;
  now?: () => Date;
  logger?: Pick<Console, "error" | "warn">;
};

export type SurveyHealthDependencies = Pick<SurveyServiceDependencies, "store" | "mirror"> & {
  healthSecret: string;
  logger?: Pick<Console, "error">;
};

type BodyResult = { ok: true; value: unknown } | { ok: false; status: number; message: string };

export async function readJsonBody(request: Request, maxBytes = MAX_REQUEST_BYTES): Promise<BodyResult> {
  const declaredLength = Number(request.headers.get("content-length"));
  if (Number.isFinite(declaredLength) && declaredLength > maxBytes) {
    return { ok: false, status: 413, message: "요청 본문은 32KiB 이하여야 합니다." };
  }
  if (!request.body) return { ok: false, status: 400, message: "요청 본문이 비어 있습니다." };

  const reader = request.body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let total = 0;
  let text = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > maxBytes) {
        await reader.cancel();
        return { ok: false, status: 413, message: "요청 본문은 32KiB 이하여야 합니다." };
      }
      text += decoder.decode(value, { stream: true });
    }
    text += decoder.decode();
    return { ok: true, value: JSON.parse(text) };
  } catch {
    return { ok: false, status: 400, message: "잘못된 JSON 요청입니다." };
  } finally {
    reader.releaseLock();
  }
}

function hash(secret: string, namespace: string, value: string): string {
  return createHmac("sha256", secret).update(`${namespace}\0${value}`).digest("hex");
}

function requestIp(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for")?.split(",", 1)[0]?.trim();
  return (forwarded || request.headers.get("x-real-ip")?.trim() || "unknown").slice(0, 128);
}

function publicResponse(response: StoredSurveyResponse): SurveyResponse {
  const value: Partial<StoredSurveyResponse> = { ...response };
  delete value.emailHash;
  delete value.withdrawalTokenHash;
  return value as SurveyResponse;
}

function receiptSummary(response: StoredSurveyResponse) {
  return {
    id: response.id,
    createdAt: response.createdAt,
    surveyVersion: response.surveyVersion,
  };
}

function jsonError(message: string, status: number) {
  return Response.json({ ok: false, message }, { status });
}

export function isSecureSurveySecret(value: string, differentFrom = ""): boolean {
  const normalized = value.trim();
  const other = differentFrom.trim();
  return normalized.length >= 32
    && !/^(?:replace[-_ ]?with|change[-_ ]?me|changeme|your[-_ ]|example)/iu.test(normalized)
    && (!other || normalized !== other);
}

function secureSecretEqual(expected: string, actual: string): boolean {
  const expectedDigest = createHash("sha256").update(expected).digest();
  const actualDigest = createHash("sha256").update(actual).digest();
  return isSecureSurveySecret(expected) && actual.length > 0 && timingSafeEqual(expectedDigest, actualDigest);
}

async function compensateWithdrawnMirror(responseId: string, dependencies: SurveyServiceDependencies): Promise<boolean> {
  try {
    await dependencies.mirror.remove(responseId);
    return true;
  } catch {
    dependencies.logger?.error("survey_withdrawn_mirror_compensation_failed");
    return false;
  }
}

export async function handleSurveyHealth(request: Request, dependencies: SurveyHealthDependencies): Promise<Response> {
  const provided = request.headers.get("x-survey-health-check-secret") ?? "";
  if (!secureSecretEqual(dependencies.healthSecret, provided)) {
    return jsonError("Not found", 404);
  }
  try {
    const [authoritative, mirror] = await Promise.all([
      dependencies.store.health(),
      dependencies.mirror.health().catch(() => false),
    ]);
    return Response.json({ ok: authoritative, authoritative: "upstash-redis", mirror: mirror ? "reachable" : "pending-or-unreachable" }, { status: authoritative ? 200 : 503 });
  } catch {
    dependencies.logger?.error("survey_health_check_failed");
    return Response.json({ ok: false, authoritative: "unreachable", mirror: "unknown" }, { status: 503 });
  }
}

export async function handleSurveyPost(request: Request, dependencies: SurveyServiceDependencies): Promise<Response> {
  if (!isSecureSurveySecret(dependencies.hmacSecret)) return jsonError("설문 저장소 보안 설정이 완료되지 않았습니다.", 503);
  if (!/^application\/json(?:\s*;|$)/iu.test(request.headers.get("content-type") ?? "")) {
    return jsonError("Content-Type은 application/json이어야 합니다.", 415);
  }
  const body = await readJsonBody(request);
  if (!body.ok) return jsonError(body.message, body.status);
  const validated = validateSurveySubmission(body.value);
  if (!validated.ok) return jsonError(validated.message, 400);

  const ipHash = hash(dependencies.hmacSecret, "ip", requestIp(request));
  const emailHash = hash(dependencies.hmacSecret, "email", validated.value.email);
  try {
    if (!await dependencies.rateLimiter.allow(ipHash, emailHash)) {
      return jsonError("요청이 너무 많습니다. 잠시 후 다시 시도해주세요.", 429);
    }

    const createdAt = (dependencies.now ?? (() => new Date()))().toISOString();
    const response = createSurveyResponse(formFromSubmission(validated.value), validated.value.id, createdAt);
    const stored: StoredSurveyResponse = {
      ...response,
      emailHash,
      withdrawalTokenHash: hash(dependencies.hmacSecret, "withdrawal", validated.value.withdrawalToken),
    };
    const reservation = await dependencies.store.reserve(stored);
    if (reservation.kind === "id_conflict") return jsonError("응답 ID가 다른 철회 증명과 이미 연결되어 있습니다.", 409);
    if (reservation.kind === "withdrawn") {
      if (!await compensateWithdrawnMirror(stored.id, dependencies)) {
        return jsonError("철회된 분석용 사본 정리가 완료되지 않았습니다. 잠시 후 다시 시도해주세요.", 503);
      }
      return jsonError("이미 철회된 응답 ID입니다. 새 응답 ID로 다시 작성해주세요.", 410);
    }

    let mirrorStatus = reservation.mirrorStatus;
    let withdrawnDuringMirror = false;
    if (mirrorStatus === "pending") {
      const lease = await dependencies.store.claimMirror(reservation.response.id);
      if (lease) {
        try {
          await dependencies.mirror.append(publicResponse(reservation.response));
          const finish = await dependencies.store.finishMirror(reservation.response.id, lease, true);
          if (finish === "mirrored") mirrorStatus = "mirrored";
          if (finish === "withdrawn") {
            withdrawnDuringMirror = true;
            if (!await compensateWithdrawnMirror(reservation.response.id, dependencies)) {
              return jsonError("철회된 분석용 사본 정리가 완료되지 않았습니다. 잠시 후 다시 시도해주세요.", 503);
            }
          }
        } catch {
          dependencies.logger?.warn("survey_mirror_pending");
          const finish = await dependencies.store.finishMirror(reservation.response.id, lease, false).catch(() => {
            dependencies.logger?.error("survey_mirror_lease_release_failed");
            return "stale" as const;
          });
          if (finish === "withdrawn") {
            withdrawnDuringMirror = true;
            if (!await compensateWithdrawnMirror(reservation.response.id, dependencies)) {
              return jsonError("철회된 분석용 사본 정리가 완료되지 않았습니다. 잠시 후 다시 시도해주세요.", 503);
            }
          }
        }
      }
    }

    if (withdrawnDuringMirror) return jsonError("이 응답은 동시에 철회되어 접수 완료 상태가 아닙니다.", 410);

    // Re-read through the same atomic reservation script before reporting success.
    // This catches a withdrawal that won while another request held the mirror claim,
    // or while a mirror completion acknowledgement was temporarily uncertain.
    const latest = await dependencies.store.reserve(stored);
    if (latest.kind === "withdrawn") {
      if (!await compensateWithdrawnMirror(stored.id, dependencies)) {
        return jsonError("철회된 분석용 사본 정리가 완료되지 않았습니다. 잠시 후 다시 시도해주세요.", 503);
      }
      return jsonError("이 응답은 동시에 철회되어 접수 완료 상태가 아닙니다.", 410);
    }
    if (latest.kind === "id_conflict") return jsonError("응답 ID가 다른 철회 증명과 이미 연결되어 있습니다.", 409);
    mirrorStatus = latest.mirrorStatus;

    return Response.json({
      ok: true,
      duplicate: reservation.kind === "existing",
      responseId: reservation.response.id,
      mirrorStatus,
      response: publicResponse(reservation.response),
    }, { status: reservation.kind === "created" ? 201 : 200 });
  } catch {
    dependencies.logger?.error("survey_authoritative_storage_failed");
    return jsonError("설문 저장소에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.", 503);
  }
}

export async function handleSurveyMirrorRetry(request: Request, dependencies: SurveyServiceDependencies): Promise<Response> {
  if (!isSecureSurveySecret(dependencies.hmacSecret)) return jsonError("설문 저장소 보안 설정이 완료되지 않았습니다.", 503);
  if (!/^application\/json(?:\s*;|$)/iu.test(request.headers.get("content-type") ?? "")) {
    return jsonError("Content-Type은 application/json이어야 합니다.", 415);
  }
  const body = await readJsonBody(request);
  if (!body.ok) return jsonError(body.message, body.status);
  if (!isSubmissionCredential(body.value) || Object.keys(body.value).some((key) => key !== "id" && key !== "withdrawalToken")) {
    return jsonError("응답 ID와 철회 증명을 확인해주세요.", 400);
  }

  const ipHash = hash(dependencies.hmacSecret, "ip", requestIp(request));
  const proofHash = hash(dependencies.hmacSecret, "withdrawal", body.value.withdrawalToken);
  try {
    if (!await dependencies.rateLimiter.allow(ipHash, proofHash)) {
      return jsonError("요청이 너무 많습니다. 잠시 후 다시 시도해주세요.", 429);
    }

    const authorization = await dependencies.store.authorizeMirrorRetry(body.value.id, proofHash);
    if (authorization.kind === "missing") return jsonError("접수된 응답을 찾을 수 없습니다.", 404);
    if (authorization.kind === "forbidden") return jsonError("응답 철회 증명이 일치하지 않습니다.", 403);
    if (authorization.kind === "withdrawn") {
      if (!await compensateWithdrawnMirror(body.value.id, dependencies)) {
        return jsonError("철회된 분석용 사본 정리가 완료되지 않았습니다. 잠시 후 다시 시도해주세요.", 503);
      }
      return jsonError("이미 철회된 응답입니다.", 410);
    }

    let mirrorStatus = authorization.mirrorStatus;
    if (mirrorStatus === "pending") {
      const lease = await dependencies.store.claimMirror(authorization.response.id);
      if (lease) {
        try {
          await dependencies.mirror.append(publicResponse(authorization.response));
          const finish = await dependencies.store.finishMirror(authorization.response.id, lease, true);
          if (finish === "mirrored") mirrorStatus = "mirrored";
          if (finish === "withdrawn") {
            if (!await compensateWithdrawnMirror(authorization.response.id, dependencies)) {
              return jsonError("철회된 분석용 사본 정리가 완료되지 않았습니다. 잠시 후 다시 시도해주세요.", 503);
            }
            return jsonError("이 응답은 동시에 철회되어 동기화할 수 없습니다.", 410);
          }
        } catch {
          dependencies.logger?.warn("survey_mirror_retry_pending");
          const finish = await dependencies.store.finishMirror(authorization.response.id, lease, false).catch(() => {
            dependencies.logger?.error("survey_mirror_retry_lease_release_failed");
            return "stale" as const;
          });
          if (finish === "withdrawn") {
            if (!await compensateWithdrawnMirror(authorization.response.id, dependencies)) {
              return jsonError("철회된 분석용 사본 정리가 완료되지 않았습니다. 잠시 후 다시 시도해주세요.", 503);
            }
            return jsonError("이 응답은 동시에 철회되어 동기화할 수 없습니다.", 410);
          }
        }
      }
    }

    const latest = await dependencies.store.authorizeMirrorRetry(body.value.id, proofHash);
    if (latest.kind === "missing") return jsonError("접수된 응답을 찾을 수 없습니다.", 404);
    if (latest.kind === "forbidden") return jsonError("응답 철회 증명이 일치하지 않습니다.", 403);
    if (latest.kind === "withdrawn") {
      if (!await compensateWithdrawnMirror(body.value.id, dependencies)) {
        return jsonError("철회된 분석용 사본 정리가 완료되지 않았습니다. 잠시 후 다시 시도해주세요.", 503);
      }
      return jsonError("이 응답은 동시에 철회되어 동기화할 수 없습니다.", 410);
    }
    mirrorStatus = latest.mirrorStatus;

    return Response.json({
      ok: true,
      responseId: latest.response.id,
      mirrorStatus,
      response: receiptSummary(latest.response),
    });
  } catch {
    dependencies.logger?.error("survey_authoritative_mirror_retry_failed");
    return jsonError("분석용 사본 동기화를 완료하지 못했습니다. 잠시 후 다시 시도해주세요.", 503);
  }
}

export async function handleSurveyDelete(request: Request, dependencies: SurveyServiceDependencies): Promise<Response> {
  if (!isSecureSurveySecret(dependencies.hmacSecret)) return jsonError("설문 저장소 보안 설정이 완료되지 않았습니다.", 503);
  if (!/^application\/json(?:\s*;|$)/iu.test(request.headers.get("content-type") ?? "")) {
    return jsonError("Content-Type은 application/json이어야 합니다.", 415);
  }
  const body = await readJsonBody(request);
  if (!body.ok) return jsonError(body.message, body.status);
  if (!isSubmissionCredential(body.value) || Object.keys(body.value).some((key) => key !== "id" && key !== "withdrawalToken")) {
    return jsonError("응답 ID와 철회 증명을 확인해주세요.", 400);
  }

  const ipHash = hash(dependencies.hmacSecret, "ip", requestIp(request));
  const proofHash = hash(dependencies.hmacSecret, "withdrawal", body.value.withdrawalToken);
  try {
    if (!await dependencies.rateLimiter.allow(ipHash, proofHash)) {
      return jsonError("요청이 너무 많습니다. 잠시 후 다시 시도해주세요.", 429);
    }
    const authorization = await dependencies.store.beginWithdrawal(body.value.id, proofHash);
    if (authorization.kind === "missing") return Response.json({ ok: true, deleted: true });
    if (authorization.kind === "forbidden") return jsonError("응답 철회 증명이 일치하지 않습니다.", 403);
    if (authorization.kind === "withdrawn") {
      try {
        await dependencies.mirror.remove(body.value.id);
        return Response.json({ ok: true, deleted: true });
      } catch {
        dependencies.logger?.error("survey_withdrawn_mirror_cleanup_retry_failed");
        return jsonError("분석용 사본 삭제를 완료하지 못했습니다. 잠시 후 다시 시도해주세요.", 503);
      }
    }

    try {
      await dependencies.mirror.remove(body.value.id);
    } catch {
      dependencies.logger?.error("survey_sheets_withdrawal_failed");
      return jsonError("분석용 사본 삭제를 완료하지 못했습니다. 잠시 후 다시 시도해주세요.", 503);
    }

    const result = await dependencies.store.finalizeWithdrawal(body.value.id, proofHash);
    if (result === "forbidden") return jsonError("응답 철회 증명이 일치하지 않습니다.", 403);
    return Response.json({ ok: true, deleted: true });
  } catch {
    dependencies.logger?.error("survey_authoritative_withdrawal_failed");
    return jsonError("응답 철회를 완료하지 못했습니다. 잠시 후 다시 시도해주세요.", 503);
  }
}
