# Password reset production checklist

Password recovery fails closed until every item below is complete. Never paste
production secrets into issues, logs, chat, or source control.

## 1. Auth service

1. Apply the idempotent PostgreSQL migration that creates
   `password_reset_tokens`, `password_reset_rate_buckets`, and
   `password_reset_request_receipts`.
2. Configure the `newshopping-shorts-auth` production environment:
   - `PASSWORD_RESET_ENABLED=true`
   - `RESEND_API_KEY`
   - `PASSWORD_RESET_FROM_EMAIL` using a verified sender domain
   - `PASSWORD_RESET_HASH_SECRET` with a random value of at least 32 characters
   - `PASSWORD_RESET_PROXY_SECRET` with a random value of at least 32 characters
   - `PASSWORD_RESET_PUBLIC_URL=https://coupuas-thread-auto-ten.vercel.app/reset-password`
3. Deploy the auth service and verify that unsigned `/user/password-reset/process`
   requests return 404.

## 2. Public recovery site

1. Set `PASSWORD_RESET_PROXY_SECRET` to the exact same value as the auth service.
2. Configure one durable atomic rate-limit backend. Requests fail closed before
   queueing if any required value is missing or the backend command fails.
   The existing Supabase auth project is the production path:
   - Apply every pending migration under `supabase/migrations/` in timestamp order.
   - `PASSWORD_RESET_SUPABASE_URL` using the project HTTPS API origin
   - `PASSWORD_RESET_SUPABASE_PUBLISHABLE_KEY` using a low-privilege publishable key
   - `PASSWORD_RESET_SUPABASE_RPC_SECRET` using the random value whose SHA-256
     digest is stored by the migration; never reuse another password-reset secret
   - The RPC accepts only HMAC-derived fixed-window keys, increments both counters
     in one PostgreSQL transaction, and keeps its tables in the private schema.
   Upstash Redis remains a supported alternative:
   - `UPSTASH_REDIS_REST_URL` using the database HTTPS REST endpoint
   - `UPSTASH_REDIS_REST_TOKEN` using the standard write token, never the
     read-only or browser-exposed token
   - Vercel Marketplace installations that inject `KV_REST_API_URL` and
     `KV_REST_API_TOKEN` are also supported. The `UPSTASH_REDIS_REST_*` pair
     takes precedence when both naming schemes are present.
   - `PASSWORD_RESET_RATE_LIMIT_HMAC_SECRET` using a separate random value of
     at least 32 characters
   - Optional tuning: `PASSWORD_RESET_RATE_LIMIT_WINDOW_SECONDS` (default 600),
     `PASSWORD_RESET_RATE_LIMIT_IP_MAX` (default 10), and
     `PASSWORD_RESET_RATE_LIMIT_IDENTIFIER_MAX` (default 3)
3. The limiter stores only context-separated HMAC digests of the canonical IP
   and normalized identifier. It increments both fixed-window counters in one
   atomic backend operation. Never log or store the raw values in rate-limit keys.
4. Optional: set `TURNSTILE_SECRET_KEY` after adding a Turnstile widget that
   submits its short-lived token as `captcha_token`. When configured, server-side
   Siteverify failure suppresses queue delivery while retaining the same generic
   public response.
5. Confirm the Vercel build contains the private `queue/v2beta` trigger for
   `thread-pilot-password-reset`. Transient delivery failures retry at most five
   total deliveries; the fifth failure is acknowledged with the structured
   `password_reset_queue_retry_exhausted` log event and no raw identifier or IP.
6. Review the staged Vercel Firewall rule `Password reset request observation`.
   It matches only `POST /api/password-reset/request`, measures 10 requests per
   10 minutes per IP, and initially logs excess traffic without blocking it.
7. Publish the observation rule, review legitimate traffic, then change its
   exceed action to rate-limit/429 before enabling password reset publicly.
   This is defense in depth and does not replace the application-level durable
   limiter. Never skip the observation period or broaden the path condition.
8. Deploy the site only after the auth and rate-limit migrations and environment validation pass.
   `/api/readiness` reports `passwordResetProtectionConfigured: true` only when
   the proxy signing secret and all durable limiter settings are valid.

## 3. Live acceptance test

Use a dedicated test account and verify this exact sequence:

1. Submit its username and receive one real email.
2. Confirm the URL contains the token only in the fragment (`#token=`), then the
   browser immediately removes the fragment from the visible address.
3. Set a new password and confirm the link cannot be reused.
4. Confirm every previous session is rejected.
5. Confirm the desktop app logs in with the new password.
6. Confirm an unknown account returns the same public message and sends no mail.
7. Confirm excess requests do not enqueue additional reset work and retain the
   same generic 202 response. Separately confirm the defense-in-depth firewall
   returns 429 at its configured threshold.
8. Force the durable backend/network failure in a preview deployment and confirm the endpoint
   fails closed with the generic service-unavailable response.

If delivery or verification fails, set `PASSWORD_RESET_ENABLED=false` on the auth
service and roll back the public-site deployment. Existing login remains available.
