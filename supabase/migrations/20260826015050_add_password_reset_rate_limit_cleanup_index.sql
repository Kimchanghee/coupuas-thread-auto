create index if not exists password_reset_rate_limit_counters_expires_idx
  on private.password_reset_rate_limit_counters(expires_at);
