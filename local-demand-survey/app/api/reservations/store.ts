import { randomUUID, timingSafeEqual } from "node:crypto";
import type { SurveyResponse } from "../../lib/survey.ts";

const RESPONSE_TTL_SECONDS = 365 * 24 * 60 * 60;
const KEY_PREFIX = "thread-auto:survey:v2";

export type MirrorStatus = "pending" | "mirrored";

export type StoredSurveyResponse = SurveyResponse & {
  emailHash: string;
  withdrawalTokenHash: string;
};

export type ReserveResult =
  | { kind: "created" | "existing"; response: StoredSurveyResponse; mirrorStatus: MirrorStatus }
  | { kind: "id_conflict" }
  | { kind: "withdrawn" };

export type AuthorizedResult =
  | { kind: "authorized"; response: StoredSurveyResponse }
  | { kind: "missing" }
  | { kind: "forbidden" }
  | { kind: "withdrawn" };

export type MirrorRetryAuthorization =
  | { kind: "authorized"; response: StoredSurveyResponse; mirrorStatus: MirrorStatus }
  | { kind: "missing" }
  | { kind: "forbidden" }
  | { kind: "withdrawn" };

export type MirrorFinishResult = "mirrored" | "pending" | "withdrawn" | "stale";

export interface SurveyStore {
  reserve(response: StoredSurveyResponse): Promise<ReserveResult>;
  authorizeMirrorRetry(responseId: string, withdrawalTokenHash: string): Promise<MirrorRetryAuthorization>;
  claimMirror(responseId: string): Promise<string | null>;
  finishMirror(responseId: string, lease: string, succeeded: boolean): Promise<MirrorFinishResult>;
  beginWithdrawal(responseId: string, withdrawalTokenHash: string): Promise<AuthorizedResult>;
  finalizeWithdrawal(responseId: string, withdrawalTokenHash: string): Promise<"deleted" | "missing" | "forbidden">;
  health(): Promise<boolean>;
}

export interface SurveyRateLimiter {
  allow(ipHash: string, identifierHash: string): Promise<boolean>;
}

export function resolveRedisRestConfig(environment: Record<string, string | undefined> = process.env): { url: string; token: string } {
  const upstashUrl = environment.UPSTASH_REDIS_REST_URL?.trim();
  const upstashToken = environment.UPSTASH_REDIS_REST_TOKEN?.trim();
  if (upstashUrl || upstashToken) {
    if (!upstashUrl || !upstashToken) throw new Error("UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN must be configured together");
    return { url: upstashUrl, token: upstashToken };
  }
  const kvUrl = environment.KV_REST_API_URL?.trim();
  const kvToken = environment.KV_REST_API_TOKEN?.trim();
  if (!kvUrl || !kvToken) throw new Error("Upstash Redis REST configuration is missing");
  return { url: kvUrl, token: kvToken };
}

type RedisResult = { result?: unknown; error?: string };

export class UpstashRedis {
  private readonly url: string;
  private readonly token: string;
  private readonly timeoutMs: number;

  constructor(url: string, token: string, timeoutMs = 5_000) {
    let parsed: URL;
    try {
      parsed = new URL(url);
    } catch {
      throw new Error("Upstash Redis REST configuration is missing or invalid");
    }
    if (parsed.protocol !== "https:" || parsed.username || parsed.password || !parsed.hostname || !token) {
      throw new Error("Upstash Redis REST configuration is missing or invalid");
    }
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 10_000) {
      throw new Error("Upstash Redis timeout is invalid");
    }
    this.url = parsed.toString();
    this.token = token;
    this.timeoutMs = timeoutMs;
  }

  async command(parts: (string | number)[]): Promise<unknown> {
    const response = await fetch(this.url.replace(/\/+$/u, ""), {
      method: "POST",
      headers: {
        authorization: `Bearer ${this.token}`,
        "content-type": "application/json",
      },
      body: JSON.stringify(parts),
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(this.timeoutMs),
    });
    const body = await response.json().catch(() => null) as RedisResult | null;
    if (!response.ok || !body || body.error) throw new Error(`Upstash Redis command failed (${response.status})`);
    return body.result;
  }
}

const RESERVE_SCRIPT = `
if redis.call('EXISTS', KEYS[3]) == 1 then return {'withdrawn'} end
local existing = redis.call('GET', KEYS[1])
if existing then
  local decoded = cjson.decode(existing)
  if decoded.withdrawalTokenHash ~= ARGV[1] then
    return {'id_conflict'}
  end
  local mirror = redis.call('GET', KEYS[2]) or 'pending'
  if mirror == 'withdrawing' then return {'withdrawn'} end
  if mirror ~= 'mirrored' then mirror = 'pending' end
  return {'existing', existing, mirror}
end
redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
redis.call('SET', KEYS[2], 'pending', 'EX', ARGV[3])
return {'created', ARGV[2], 'pending'}
`;

const CLAIM_MIRROR_SCRIPT = `
local state = redis.call('GET', KEYS[1])
local now = tonumber(redis.call('TIME')[1])
if state == 'pending' then
  redis.call('SET', KEYS[1], 'claim:' .. ARGV[1] .. ':' .. now, 'KEEPTTL')
  return 1
end
if state and string.sub(state, 1, 6) == 'claim:' then
  local claimedAt = tonumber(string.match(state, '^claim:[^:]+:(%d+)$'))
  if claimedAt and now - claimedAt >= tonumber(ARGV[2]) then
    redis.call('SET', KEYS[1], 'claim:' .. ARGV[1] .. ':' .. now, 'KEEPTTL')
    return 1
  end
end
return 0
`;

const FINISH_MIRROR_SCRIPT = `
local state = redis.call('GET', KEYS[1])
if state == 'withdrawing' or redis.call('EXISTS', KEYS[2]) == 1 then return 'withdrawn' end
if not state then return 'stale' end
local prefix = 'claim:' .. ARGV[1] .. ':'
if string.sub(state, 1, string.len(prefix)) ~= prefix then return 'stale' end
if ARGV[2] == '1' then
  redis.call('SET', KEYS[1], 'mirrored', 'KEEPTTL')
  return 'mirrored'
end
redis.call('SET', KEYS[1], 'pending', 'KEEPTTL')
return 'pending'
`;

const AUTHORIZE_MIRROR_RETRY_SCRIPT = `
if redis.call('EXISTS', KEYS[3]) == 1 then return {'withdrawn'} end
local existing = redis.call('GET', KEYS[1])
if not existing then return {'missing'} end
local decoded = cjson.decode(existing)
if decoded.withdrawalTokenHash ~= ARGV[1] then return {'forbidden'} end
local mirror = redis.call('GET', KEYS[2]) or 'pending'
if mirror == 'withdrawing' then return {'withdrawn'} end
if mirror ~= 'mirrored' then mirror = 'pending' end
return {'authorized', existing, mirror}
`;

const BEGIN_WITHDRAWAL_SCRIPT = `
local existing = redis.call('GET', KEYS[1])
if not existing then
  if redis.call('EXISTS', KEYS[3]) == 1 then return {'withdrawn'} end
  return {'missing'}
end
local decoded = cjson.decode(existing)
if decoded.withdrawalTokenHash ~= ARGV[1] then return {'forbidden'} end
local ttl = redis.call('TTL', KEYS[1])
if ttl < 1 then ttl = tonumber(ARGV[2]) end
redis.call('SET', KEYS[2], 'withdrawing', 'EX', ttl)
redis.call('SET', KEYS[3], '1', 'EX', ARGV[2])
redis.call('DEL', KEYS[4])
return {'authorized', existing}
`;

const FINALIZE_WITHDRAWAL_SCRIPT = `
local existing = redis.call('GET', KEYS[1])
if not existing then return 'missing' end
local decoded = cjson.decode(existing)
if decoded.withdrawalTokenHash ~= ARGV[1] then return 'forbidden' end
if redis.call('GET', KEYS[2]) ~= 'withdrawing' or redis.call('EXISTS', KEYS[4]) ~= 1 then return 'forbidden' end
redis.call('DEL', KEYS[1], KEYS[2], KEYS[3])
return 'deleted'
`;

function responseKey(responseId: string) { return `${KEY_PREFIX}:response:${responseId}`; }
function mirrorKey(responseId: string) { return `${KEY_PREFIX}:mirror:${responseId}`; }
function mirrorLockKey(responseId: string) { return `${KEY_PREFIX}:mirror-lock:${responseId}`; }
function withdrawalTombstoneKey(responseId: string) { return `${KEY_PREFIX}:withdrawn:${responseId}`; }

function secureEqual(left: string, right: string): boolean {
  const a = Buffer.from(left);
  const b = Buffer.from(right);
  return a.length === b.length && timingSafeEqual(a, b);
}

export class UpstashSurveyStore implements SurveyStore {
  private readonly redis: UpstashRedis;

  constructor(redis: UpstashRedis) { this.redis = redis; }

  async reserve(response: StoredSurveyResponse): Promise<ReserveResult> {
    const result = await this.redis.command([
      "EVAL", RESERVE_SCRIPT, 3,
      responseKey(response.id), mirrorKey(response.id), withdrawalTombstoneKey(response.id),
      response.withdrawalTokenHash, JSON.stringify(response), RESPONSE_TTL_SECONDS,
    ]);
    if (!Array.isArray(result) || typeof result[0] !== "string") throw new Error("Unexpected Redis reservation result");
    if (result[0] === "id_conflict" || result[0] === "withdrawn") return { kind: result[0] };
    if ((result[0] === "created" || result[0] === "existing") && typeof result[1] === "string") {
      const parsed = JSON.parse(result[1]) as StoredSurveyResponse;
      return { kind: result[0], response: parsed, mirrorStatus: result[2] === "mirrored" ? "mirrored" : "pending" };
    }
    throw new Error("Invalid Redis reservation result");
  }

  async authorizeMirrorRetry(responseId: string, withdrawalTokenHash: string): Promise<MirrorRetryAuthorization> {
    const result = await this.redis.command([
      "EVAL", AUTHORIZE_MIRROR_RETRY_SCRIPT, 3,
      responseKey(responseId), mirrorKey(responseId), withdrawalTombstoneKey(responseId),
      withdrawalTokenHash,
    ]);
    if (!Array.isArray(result) || typeof result[0] !== "string") throw new Error("Unexpected Redis mirror authorization result");
    if (result[0] === "missing" || result[0] === "forbidden" || result[0] === "withdrawn") return { kind: result[0] };
    if (result[0] === "authorized" && typeof result[1] === "string") {
      return {
        kind: "authorized",
        response: JSON.parse(result[1]) as StoredSurveyResponse,
        mirrorStatus: result[2] === "mirrored" ? "mirrored" : "pending",
      };
    }
    throw new Error("Invalid Redis mirror authorization result");
  }

  async claimMirror(responseId: string): Promise<string | null> {
    const lease = randomUUID();
    const result = await this.redis.command(["EVAL", CLAIM_MIRROR_SCRIPT, 1, mirrorKey(responseId), lease, 300]);
    return Number(result) === 1 ? lease : null;
  }

  async finishMirror(responseId: string, lease: string, succeeded: boolean): Promise<MirrorFinishResult> {
    const result = await this.redis.command([
      "EVAL", FINISH_MIRROR_SCRIPT, 2,
      mirrorKey(responseId), withdrawalTombstoneKey(responseId), lease, succeeded ? 1 : 0,
    ]);
    if (result === "mirrored" || result === "pending" || result === "withdrawn" || result === "stale") return result;
    throw new Error("Unexpected Redis mirror completion result");
  }

  async beginWithdrawal(responseId: string, withdrawalTokenHash: string): Promise<AuthorizedResult> {
    const result = await this.redis.command([
      "EVAL", BEGIN_WITHDRAWAL_SCRIPT, 4,
      responseKey(responseId), mirrorKey(responseId), withdrawalTombstoneKey(responseId), mirrorLockKey(responseId),
      withdrawalTokenHash, RESPONSE_TTL_SECONDS,
    ]);
    if (!Array.isArray(result) || typeof result[0] !== "string") throw new Error("Unexpected Redis withdrawal-begin result");
    if (result[0] === "missing" || result[0] === "forbidden" || result[0] === "withdrawn") return { kind: result[0] };
    if (result[0] === "authorized" && typeof result[1] === "string") {
      return { kind: "authorized", response: JSON.parse(result[1]) as StoredSurveyResponse };
    }
    throw new Error("Invalid Redis withdrawal-begin result");
  }

  async finalizeWithdrawal(responseId: string, withdrawalTokenHash: string): Promise<"deleted" | "missing" | "forbidden"> {
    const result = await this.redis.command([
      "EVAL", FINALIZE_WITHDRAWAL_SCRIPT, 4,
      responseKey(responseId), mirrorKey(responseId), mirrorLockKey(responseId), withdrawalTombstoneKey(responseId),
      withdrawalTokenHash,
    ]);
    if (result === "deleted" || result === "missing" || result === "forbidden") return result;
    throw new Error("Unexpected Redis withdrawal result");
  }

  async health(): Promise<boolean> {
    return await this.redis.command(["PING"]) === "PONG";
  }
}

const RATE_LIMIT_SCRIPT = `
local ipCount = redis.call('INCR', KEYS[1])
if ipCount == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
local identifierCount = redis.call('INCR', KEYS[2])
if identifierCount == 1 then redis.call('EXPIRE', KEYS[2], ARGV[2]) end
if ipCount > tonumber(ARGV[3]) or identifierCount > tonumber(ARGV[4]) then return 0 end
return 1
`;

export class UpstashSurveyRateLimiter implements SurveyRateLimiter {
  private readonly redis: UpstashRedis;
  private readonly ipLimit: number;
  private readonly identifierLimit: number;

  constructor(
    redis: UpstashRedis,
    ipLimit = 10,
    identifierLimit = 3,
  ) {
    this.redis = redis;
    this.ipLimit = ipLimit;
    this.identifierLimit = identifierLimit;
  }

  async allow(ipHash: string, identifierHash: string): Promise<boolean> {
    const result = await this.redis.command([
      "EVAL", RATE_LIMIT_SCRIPT, 2,
      `${KEY_PREFIX}:rate:ip:${ipHash}`, `${KEY_PREFIX}:rate:identifier:${identifierHash}`,
      60 * 60, 24 * 60 * 60, this.ipLimit, this.identifierLimit,
    ]);
    return Number(result) === 1;
  }
}

export class MemorySurveyStore implements SurveyStore {
  private readonly responses = new Map<string, StoredSurveyResponse>();
  private readonly mirrors = new Map<string, MirrorStatus | "withdrawing">();
  private readonly mirrorLeases = new Map<string, string>();
  private readonly tombstones = new Set<string>();

  async reserve(response: StoredSurveyResponse): Promise<ReserveResult> {
    if (this.tombstones.has(response.id)) return { kind: "withdrawn" };
    const existing = this.responses.get(response.id);
    if (existing) {
      if (!secureEqual(existing.withdrawalTokenHash, response.withdrawalTokenHash)) return { kind: "id_conflict" };
      const mirrorStatus = this.mirrors.get(response.id) ?? "pending";
      if (mirrorStatus === "withdrawing") return { kind: "withdrawn" };
      return { kind: "existing", response: existing, mirrorStatus };
    }
    this.responses.set(response.id, structuredClone(response));
    this.mirrors.set(response.id, "pending");
    return { kind: "created", response: structuredClone(response), mirrorStatus: "pending" };
  }

  async authorizeMirrorRetry(responseId: string, withdrawalTokenHash: string): Promise<MirrorRetryAuthorization> {
    const response = this.responses.get(responseId);
    if (!response) return this.tombstones.has(responseId) ? { kind: "withdrawn" } : { kind: "missing" };
    if (!secureEqual(response.withdrawalTokenHash, withdrawalTokenHash)) return { kind: "forbidden" };
    const mirrorStatus = this.mirrors.get(responseId) ?? "pending";
    if (mirrorStatus === "withdrawing" || this.tombstones.has(responseId)) return { kind: "withdrawn" };
    return { kind: "authorized", response: structuredClone(response), mirrorStatus };
  }

  async claimMirror(responseId: string): Promise<string | null> {
    if (this.mirrors.get(responseId) !== "pending" || this.mirrorLeases.has(responseId) || this.tombstones.has(responseId)) return null;
    const lease = randomUUID();
    this.mirrorLeases.set(responseId, lease);
    return lease;
  }

  async finishMirror(responseId: string, lease: string, succeeded: boolean): Promise<MirrorFinishResult> {
    if (this.tombstones.has(responseId) || this.mirrors.get(responseId) === "withdrawing") return "withdrawn";
    if (this.mirrorLeases.get(responseId) !== lease) return "stale";
    this.mirrorLeases.delete(responseId);
    this.mirrors.set(responseId, succeeded ? "mirrored" : "pending");
    return succeeded ? "mirrored" : "pending";
  }

  async beginWithdrawal(responseId: string, withdrawalTokenHash: string): Promise<AuthorizedResult> {
    const response = this.responses.get(responseId);
    if (!response) return this.tombstones.has(responseId) ? { kind: "withdrawn" } : { kind: "missing" };
    if (!secureEqual(response.withdrawalTokenHash, withdrawalTokenHash)) return { kind: "forbidden" };
    this.tombstones.add(responseId);
    this.mirrors.set(responseId, "withdrawing");
    this.mirrorLeases.delete(responseId);
    return { kind: "authorized", response: structuredClone(response) };
  }

  async finalizeWithdrawal(responseId: string, withdrawalTokenHash: string): Promise<"deleted" | "missing" | "forbidden"> {
    const response = this.responses.get(responseId);
    if (!response) return "missing";
    if (!secureEqual(response.withdrawalTokenHash, withdrawalTokenHash) || !this.tombstones.has(responseId) || this.mirrors.get(responseId) !== "withdrawing") return "forbidden";
    this.responses.delete(responseId);
    this.mirrors.delete(responseId);
    this.mirrorLeases.delete(responseId);
    return "deleted";
  }

  async health(): Promise<boolean> { return true; }
}

export class MemoryRateLimiter implements SurveyRateLimiter {
  private readonly ipCounts = new Map<string, number>();
  private readonly identifierCounts = new Map<string, number>();
  private readonly ipLimit: number;
  private readonly identifierLimit: number;

  constructor(ipLimit = 10, identifierLimit = 3) {
    this.ipLimit = ipLimit;
    this.identifierLimit = identifierLimit;
  }

  async allow(ipHash: string, identifierHash: string): Promise<boolean> {
    const ipCount = (this.ipCounts.get(ipHash) ?? 0) + 1;
    const identifierCount = (this.identifierCounts.get(identifierHash) ?? 0) + 1;
    this.ipCounts.set(ipHash, ipCount);
    this.identifierCounts.set(identifierHash, identifierCount);
    return ipCount <= this.ipLimit && identifierCount <= this.identifierLimit;
  }
}
