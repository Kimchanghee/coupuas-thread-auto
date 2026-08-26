create table private.password_reset_rate_limit_counters (
  rate_key text primary key,
  hit_count integer not null check (hit_count > 0),
  expires_at timestamptz not null,
  created_at timestamptz not null default statement_timestamp(),
  updated_at timestamptz not null default statement_timestamp(),
  constraint password_reset_rate_key_format check (
    rate_key ~ '^password-reset:v1:(ip|identifier):[a-f0-9]{64}:[0-9]+$'
  )
);

alter table private.password_reset_rate_limit_counters enable row level security;
revoke all on table private.password_reset_rate_limit_counters from public, anon, authenticated;

create table private.password_reset_rate_limit_settings (
  setting_key text primary key,
  setting_value text not null,
  updated_at timestamptz not null default statement_timestamp(),
  constraint password_reset_rate_limit_setting_key check (
    setting_key = 'rpc_secret_sha256'
  ),
  constraint password_reset_rate_limit_setting_value check (
    setting_value ~ '^[a-f0-9]{64}$'
  )
);

alter table private.password_reset_rate_limit_settings enable row level security;
revoke all on table private.password_reset_rate_limit_settings from public, anon, authenticated;

insert into private.password_reset_rate_limit_settings(setting_key, setting_value)
values (
  'rpc_secret_sha256',
  'ba71c141ae3f75ffa15bcac73c36f13742a2c3b475ad9abc05fbd82dbdc1092a'
)
on conflict (setting_key) do update
  set setting_value = excluded.setting_value,
      updated_at = statement_timestamp();

create function private.consume_password_reset_rate_limit_impl(
  p_ip_key text,
  p_identifier_key text,
  p_ttl_seconds integer,
  p_rpc_secret text
)
returns table(ip_count integer, identifier_count integer)
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_expected_hash text;
  v_ip_count integer;
  v_identifier_count integer;
  v_now timestamptz := statement_timestamp();
begin
  if p_rpc_secret is null or length(p_rpc_secret) < 32 or length(p_rpc_secret) > 1024 then
    raise exception 'INVALID_RATE_LIMIT_CREDENTIAL' using errcode = '28000';
  end if;

  select setting_value
    into v_expected_hash
    from private.password_reset_rate_limit_settings
   where setting_key = 'rpc_secret_sha256';

  if v_expected_hash is null or
     encode(extensions.digest(convert_to(p_rpc_secret, 'UTF8'), 'sha256'), 'hex') <> v_expected_hash then
    raise exception 'INVALID_RATE_LIMIT_CREDENTIAL' using errcode = '28000';
  end if;

  if p_ip_key is null or
     p_ip_key !~ '^password-reset:v1:ip:[a-f0-9]{64}:[0-9]+$' or
     p_identifier_key is null or
     p_identifier_key !~ '^password-reset:v1:identifier:[a-f0-9]{64}:[0-9]+$' or
     p_ip_key = p_identifier_key then
    raise exception 'INVALID_RATE_LIMIT_KEY' using errcode = '22023';
  end if;

  if p_ttl_seconds is null or p_ttl_seconds < 60 or p_ttl_seconds > 86400 then
    raise exception 'INVALID_RATE_LIMIT_TTL' using errcode = '22023';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(least(p_ip_key, p_identifier_key), 0)
  );
  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(greatest(p_ip_key, p_identifier_key), 0)
  );

  insert into private.password_reset_rate_limit_counters as counters(
    rate_key,
    hit_count,
    expires_at,
    created_at,
    updated_at
  )
  values (
    p_ip_key,
    1,
    v_now + pg_catalog.make_interval(secs => p_ttl_seconds),
    v_now,
    v_now
  )
  on conflict (rate_key) do update
     set hit_count = case when counters.expires_at <= v_now then 1 else counters.hit_count + 1 end,
         expires_at = case
           when counters.expires_at <= v_now
             then v_now + pg_catalog.make_interval(secs => p_ttl_seconds)
           else counters.expires_at
         end,
         updated_at = v_now
  returning hit_count into v_ip_count;

  insert into private.password_reset_rate_limit_counters as counters(
    rate_key,
    hit_count,
    expires_at,
    created_at,
    updated_at
  )
  values (
    p_identifier_key,
    1,
    v_now + pg_catalog.make_interval(secs => p_ttl_seconds),
    v_now,
    v_now
  )
  on conflict (rate_key) do update
     set hit_count = case when counters.expires_at <= v_now then 1 else counters.hit_count + 1 end,
         expires_at = case
           when counters.expires_at <= v_now
             then v_now + pg_catalog.make_interval(secs => p_ttl_seconds)
           else counters.expires_at
         end,
         updated_at = v_now
  returning hit_count into v_identifier_count;

  if pg_catalog.random() < 0.01 then
    delete from private.password_reset_rate_limit_counters
     where expires_at < v_now;
  end if;

  return query select v_ip_count, v_identifier_count;
end;
$function$;

create function public.consume_password_reset_rate_limit(
  p_ip_key text,
  p_identifier_key text,
  p_ttl_seconds integer,
  p_rpc_secret text
)
returns table(ip_count integer, identifier_count integer)
language sql
security invoker
set search_path = ''
as $function$
  select result.ip_count, result.identifier_count
    from private.consume_password_reset_rate_limit_impl(
      p_ip_key,
      p_identifier_key,
      p_ttl_seconds,
      p_rpc_secret
    ) as result;
$function$;

revoke execute on function private.consume_password_reset_rate_limit_impl(text, text, integer, text)
  from public, authenticated;
revoke execute on function public.consume_password_reset_rate_limit(text, text, integer, text)
  from public, authenticated;
grant execute on function private.consume_password_reset_rate_limit_impl(text, text, integer, text)
  to anon, service_role;
grant execute on function public.consume_password_reset_rate_limit(text, text, integer, text)
  to anon, service_role;

comment on table private.password_reset_rate_limit_counters is
  'Fixed-window counters containing HMAC-derived keys only.';
comment on table private.password_reset_rate_limit_settings is
  'Server-only password reset rate-limit configuration; stores a one-way RPC secret digest.';
comment on function public.consume_password_reset_rate_limit(text, text, integer, text) is
  'Atomically increments the IP and identifier password-reset counters after shared-secret verification.';
