import { createHmac, randomUUID } from "node:crypto";

const DEFAULT_WINDOW_SECONDS = 10 * 60;
const DEFAULT_IP_LIMIT = 10;
const DEFAULT_IDENTIFIER_LIMIT = 3;
const TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify";

// Both counters are updated in one Redis command, so concurrent serverless
// instances cannot independently admit requests past either threshold.
const INCREMENT_WINDOW_SCRIPT = `
local ip_count = redis.call("INCR", KEYS[1])
if ip_count == 1 then redis.call("EXPIRE", KEYS[1], ARGV[1]) end
local identifier_count = redis.call("INCR", KEYS[2])
if identifier_count == 1 then redis.call("EXPIRE", KEYS[2], ARGV[1]) end
return {ip_count, identifier_count}
`.trim();

export class PasswordResetRateLimitConfigurationError extends Error {
  constructor(message) {
    super(message);
    this.name = "PasswordResetRateLimitConfigurationError";
  }
}

function requiredSecret(value, name) {
  const normalized = String(value || "").trim();
  if (normalized.length < 32) {
    throw new PasswordResetRateLimitConfigurationError(`${name} must contain at least 32 characters`);
  }
  return normalized;
}

function positiveInteger(value, fallback, name) {
  if (value === undefined || value === null || value === "") return fallback;
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 1 || parsed > 86_400) {
    throw new PasswordResetRateLimitConfigurationError(`${name} must be a positive integer`);
  }
  return parsed;
}

export function passwordResetRateLimitConfiguration(env = process.env) {
  const upstashUrl = String(env.UPSTASH_REDIS_REST_URL || "").trim();
  const upstashToken = String(env.UPSTASH_REDIS_REST_TOKEN || "").trim();
  const kvUrl = String(env.KV_REST_API_URL || "").trim();
  const kvToken = String(env.KV_REST_API_TOKEN || "").trim();
  const supabaseUrl = String(env.PASSWORD_RESET_SUPABASE_URL || "").trim();
  const supabasePublishableKey = String(
    env.PASSWORD_RESET_SUPABASE_PUBLISHABLE_KEY || "",
  ).trim();
  const supabaseRpcSecret = String(env.PASSWORD_RESET_SUPABASE_RPC_SECRET || "").trim();
  const hasAnyUpstashCredential = Boolean(upstashUrl || upstashToken);
  const hasCompleteUpstashCredentials = Boolean(upstashUrl && upstashToken);
  const hasAnyKvCredential = Boolean(kvUrl || kvToken);
  const hasCompleteKvCredentials = Boolean(kvUrl && kvToken);
  const hasCompleteRedisCredentials =
    hasCompleteUpstashCredentials || hasCompleteKvCredentials;
  const hasAnySupabaseCredential = Boolean(
    supabaseUrl || supabasePublishableKey || supabaseRpcSecret,
  );
  const hasCompleteSupabaseCredentials = Boolean(
    supabaseUrl && supabasePublishableKey && supabaseRpcSecret,
  );

  if (hasAnyUpstashCredential && !hasCompleteUpstashCredentials) {
    throw new PasswordResetRateLimitConfigurationError(
      "UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN must be configured together",
    );
  }
  if (!hasCompleteUpstashCredentials && hasAnyKvCredential && !hasCompleteKvCredentials) {
    throw new PasswordResetRateLimitConfigurationError(
      "KV_REST_API_URL and KV_REST_API_TOKEN must be configured together",
    );
  }
  if (
    !hasCompleteRedisCredentials &&
    hasAnySupabaseCredential &&
    !hasCompleteSupabaseCredentials
  ) {
    throw new PasswordResetRateLimitConfigurationError(
      "PASSWORD_RESET_SUPABASE_URL, PASSWORD_RESET_SUPABASE_PUBLISHABLE_KEY, and PASSWORD_RESET_SUPABASE_RPC_SECRET must be configured together",
    );
  }
  if (!hasCompleteRedisCredentials && !hasCompleteSupabaseCredentials) {
    throw new PasswordResetRateLimitConfigurationError(
      "a complete durable rate-limit backend credential set is required",
    );
  }

  const hmacSecret = requiredSecret(
    env.PASSWORD_RESET_RATE_LIMIT_HMAC_SECRET,
    "PASSWORD_RESET_RATE_LIMIT_HMAC_SECRET",
  );
  if (hmacSecret === String(env.PASSWORD_RESET_PROXY_SECRET || "").trim()) {
    throw new PasswordResetRateLimitConfigurationError(
      "PASSWORD_RESET_RATE_LIMIT_HMAC_SECRET must be distinct from PASSWORD_RESET_PROXY_SECRET",
    );
  }
  const shared = {
    hmacSecret,
    windowSeconds: positiveInteger(
      env.PASSWORD_RESET_RATE_LIMIT_WINDOW_SECONDS,
      DEFAULT_WINDOW_SECONDS,
      "PASSWORD_RESET_RATE_LIMIT_WINDOW_SECONDS",
    ),
    ipLimit: positiveInteger(
      env.PASSWORD_RESET_RATE_LIMIT_IP_MAX,
      DEFAULT_IP_LIMIT,
      "PASSWORD_RESET_RATE_LIMIT_IP_MAX",
    ),
    identifierLimit: positiveInteger(
      env.PASSWORD_RESET_RATE_LIMIT_IDENTIFIER_MAX,
      DEFAULT_IDENTIFIER_LIMIT,
      "PASSWORD_RESET_RATE_LIMIT_IDENTIFIER_MAX",
    ),
  };

  if (!hasCompleteRedisCredentials) {
    if (!/^[A-Za-z0-9._-]{20,2048}$/.test(supabasePublishableKey)) {
      throw new PasswordResetRateLimitConfigurationError(
        "PASSWORD_RESET_SUPABASE_PUBLISHABLE_KEY is invalid",
      );
    }
    const rpcSecret = requiredSecret(
      supabaseRpcSecret,
      "PASSWORD_RESET_SUPABASE_RPC_SECRET",
    );
    if (
      rpcSecret === hmacSecret ||
      rpcSecret === String(env.PASSWORD_RESET_PROXY_SECRET || "").trim()
    ) {
      throw new PasswordResetRateLimitConfigurationError(
        "PASSWORD_RESET_SUPABASE_RPC_SECRET must be distinct from other password reset secrets",
      );
    }
    let url;
    try {
      url = new URL(supabaseUrl);
    } catch {
      throw new PasswordResetRateLimitConfigurationError(
        "PASSWORD_RESET_SUPABASE_URL is invalid",
      );
    }
    if (
      url.protocol !== "https:" ||
      url.username ||
      url.password ||
      url.pathname !== "/" ||
      url.search ||
      url.hash
    ) {
      throw new PasswordResetRateLimitConfigurationError(
        "PASSWORD_RESET_SUPABASE_URL must be an HTTPS origin",
      );
    }
    return {
      backend: "supabase",
      url: url.toString(),
      publishableKey: supabasePublishableKey,
      rpcSecret,
      ...shared,
    };
  }

  const rawUrl = hasCompleteUpstashCredentials ? upstashUrl : kvUrl;
  const token = hasCompleteUpstashCredentials ? upstashToken : kvToken;
  let url;
  try {
    url = new URL(rawUrl);
  } catch {
    throw new PasswordResetRateLimitConfigurationError(
      "UPSTASH_REDIS_REST_URL or KV_REST_API_URL is invalid",
    );
  }
  if (url.protocol !== "https:" || url.username || url.password) {
    throw new PasswordResetRateLimitConfigurationError("password reset Redis REST URL must be HTTPS");
  }
  return {
    backend: "redis",
    url: url.toString(),
    token,
    ...shared,
  };
}

export function isPasswordResetRateLimitConfigured(env = process.env) {
  try {
    passwordResetRateLimitConfiguration(env);
    return true;
  } catch {
    return false;
  }
}

export function isPasswordResetProtectionConfigured(env = process.env) {
  return (
    String(env.PASSWORD_RESET_PROXY_SECRET || "").trim().length >= 32 &&
    isPasswordResetRateLimitConfigured(env)
  );
}

export function createUpstashFixedWindowStore({ url, token, fetchImpl = globalThis.fetch }) {
  const endpoint = new URL(url).toString();
  if (typeof fetchImpl !== "function") {
    throw new PasswordResetRateLimitConfigurationError("fetch is unavailable");
  }
  return {
    async increment(keys, ttlSeconds) {
      if (!Array.isArray(keys) || keys.length !== 2) {
        throw new Error("password reset rate limiter requires two keys");
      }
      const response = await fetchImpl(endpoint, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify([
          "EVAL",
          INCREMENT_WINDOW_SCRIPT,
          2,
          keys[0],
          keys[1],
          ttlSeconds,
        ]),
        redirect: "error",
        signal: AbortSignal.timeout(4_000),
      });
      let payload;
      try {
        payload = await response.json();
      } catch {
        throw new Error("password reset rate-limit backend returned invalid JSON");
      }
      if (
        !response.ok ||
        payload?.error ||
        !Array.isArray(payload?.result) ||
        payload.result.length !== 2
      ) {
        throw new Error("password reset rate-limit backend rejected the command");
      }
      const counts = payload.result.map((value) => Number(value));
      if (counts.some((value) => !Number.isSafeInteger(value) || value < 1)) {
        throw new Error("password reset rate-limit backend returned invalid counters");
      }
      return counts;
    },
  };
}

export function createSupabaseFixedWindowStore({
  url,
  publishableKey,
  rpcSecret,
  fetchImpl = globalThis.fetch,
}) {
  let endpoint;
  try {
    endpoint = new URL("/rest/v1/rpc/consume_password_reset_rate_limit", url);
  } catch {
    throw new PasswordResetRateLimitConfigurationError("Supabase rate-limit URL is invalid");
  }
  if (endpoint.protocol !== "https:" || endpoint.username || endpoint.password) {
    throw new PasswordResetRateLimitConfigurationError(
      "Supabase rate-limit URL must use HTTPS",
    );
  }
  if (typeof fetchImpl !== "function") {
    throw new PasswordResetRateLimitConfigurationError("fetch is unavailable");
  }
  return {
    async increment(keys, ttlSeconds) {
      if (!Array.isArray(keys) || keys.length !== 2) {
        throw new Error("password reset rate limiter requires two keys");
      }
      const response = await fetchImpl(endpoint.toString(), {
        method: "POST",
        headers: {
          apikey: publishableKey,
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          p_ip_key: keys[0],
          p_identifier_key: keys[1],
          p_ttl_seconds: ttlSeconds,
          p_rpc_secret: rpcSecret,
        }),
        redirect: "error",
        signal: AbortSignal.timeout(4_000),
      });
      let payload;
      try {
        payload = await response.json();
      } catch {
        throw new Error("password reset rate-limit backend returned invalid JSON");
      }
      if (!response.ok || !Array.isArray(payload) || payload.length !== 1) {
        throw new Error("password reset rate-limit backend rejected the command");
      }
      const counts = [Number(payload[0]?.ip_count), Number(payload[0]?.identifier_count)];
      if (counts.some((value) => !Number.isSafeInteger(value) || value < 1)) {
        throw new Error("password reset rate-limit backend returned invalid counters");
      }
      return counts;
    },
  };
}

function rateLimitDigest(secret, kind, value) {
  return createHmac("sha256", secret)
    .update(`${kind}\0${String(value).trim().toLowerCase()}`)
    .digest("hex");
}

export function createPasswordResetRateLimiter({
  store,
  hmacSecret,
  nowImpl = Date.now,
  windowSeconds = DEFAULT_WINDOW_SECONDS,
  ipLimit = DEFAULT_IP_LIMIT,
  identifierLimit = DEFAULT_IDENTIFIER_LIMIT,
}) {
  if (!store || typeof store.increment !== "function") {
    throw new PasswordResetRateLimitConfigurationError("a shared rate-limit store is required");
  }
  const secret = requiredSecret(hmacSecret, "PASSWORD_RESET_RATE_LIMIT_HMAC_SECRET");
  const safeWindow = positiveInteger(windowSeconds, DEFAULT_WINDOW_SECONDS, "windowSeconds");
  const safeIpLimit = positiveInteger(ipLimit, DEFAULT_IP_LIMIT, "ipLimit");
  const safeIdentifierLimit = positiveInteger(
    identifierLimit,
    DEFAULT_IDENTIFIER_LIMIT,
    "identifierLimit",
  );

  return async ({ ipAddress, identifier }) => {
    const timestampSeconds = Math.floor(Number(nowImpl()) / 1000);
    if (!Number.isSafeInteger(timestampSeconds) || timestampSeconds < 0) {
      throw new Error("password reset rate-limit clock is invalid");
    }
    const bucket = Math.floor(timestampSeconds / safeWindow);
    const keys = [
      `password-reset:v1:ip:${rateLimitDigest(secret, "ip", ipAddress)}:${bucket}`,
      `password-reset:v1:identifier:${rateLimitDigest(secret, "identifier", identifier)}:${bucket}`,
    ];
    const [ipCount, identifierCount] = await store.increment(keys, safeWindow + 5);
    return {
      allowed: ipCount <= safeIpLimit && identifierCount <= safeIdentifierLimit,
      retryAfterSeconds: safeWindow - (timestampSeconds % safeWindow),
    };
  };
}

export async function consumePasswordResetRateLimit(
  input,
  { env = process.env, fetchImpl = globalThis.fetch, nowImpl = Date.now } = {},
) {
  const config = passwordResetRateLimitConfiguration(env);
  const store =
    config.backend === "supabase"
      ? createSupabaseFixedWindowStore({
          url: config.url,
          publishableKey: config.publishableKey,
          rpcSecret: config.rpcSecret,
          fetchImpl,
        })
      : createUpstashFixedWindowStore({
          url: config.url,
          token: config.token,
          fetchImpl,
        });
  const limiter = createPasswordResetRateLimiter({
    store,
    hmacSecret: config.hmacSecret,
    nowImpl,
    windowSeconds: config.windowSeconds,
    ipLimit: config.ipLimit,
    identifierLimit: config.identifierLimit,
  });
  return limiter(input);
}

export async function verifyPasswordResetCaptcha(
  { token, ipAddress },
  { env = process.env, fetchImpl = globalThis.fetch, requestId = randomUUID() } = {},
) {
  const secret = String(env.TURNSTILE_SECRET_KEY || "").trim();
  if (!secret) return true;
  const responseToken = String(token || "").trim();
  if (!responseToken || responseToken.length > 2_048) return false;
  const response = await fetchImpl(TURNSTILE_VERIFY_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({
      secret,
      response: responseToken,
      remoteip: ipAddress,
      idempotency_key: requestId,
    }),
    redirect: "error",
    signal: AbortSignal.timeout(5_000),
  });
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error("password reset CAPTCHA returned invalid JSON");
  }
  if (!response.ok) throw new Error("password reset CAPTCHA verification failed");
  return payload?.success === true;
}
