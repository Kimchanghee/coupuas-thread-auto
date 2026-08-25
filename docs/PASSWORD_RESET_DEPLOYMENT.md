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
2. Confirm the Vercel build contains the private `queue/v2beta` trigger for
   `thread-pilot-password-reset`.
3. Review the staged Vercel Firewall rule `Password reset request observation`.
   It matches only `POST /api/password-reset/request`, measures 10 requests per
   10 minutes per IP, and initially logs excess traffic without blocking it.
4. Publish the observation rule, review legitimate traffic, then change its
   exceed action to rate-limit/429 before enabling password reset publicly.
   Never skip the observation period or broaden the path condition.
5. Deploy the site only after the auth migration and environment validation pass.

## 3. Live acceptance test

Use a dedicated test account and verify this exact sequence:

1. Submit its username and receive one real email.
2. Confirm the URL contains the token only in the fragment (`#token=`), then the
   browser immediately removes the fragment from the visible address.
3. Set a new password and confirm the link cannot be reused.
4. Confirm every previous session is rejected.
5. Confirm the desktop app logs in with the new password.
6. Confirm an unknown account returns the same public message and sends no mail.
7. Confirm the firewall returns 429 after the configured IP threshold.

If delivery or verification fails, set `PASSWORD_RESET_ENABLED=false` on the auth
service and roll back the public-site deployment. Existing login remains available.
