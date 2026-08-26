create policy "deny direct password reset counter access"
  on private.password_reset_rate_limit_counters
  for all
  to anon, authenticated
  using (false)
  with check (false);

create policy "deny direct password reset setting access"
  on private.password_reset_rate_limit_settings
  for all
  to anon, authenticated
  using (false)
  with check (false);
