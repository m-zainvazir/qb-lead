-- Module 3: inbound webhook and email (docs/decisions/0003-inbound-path.md).
--
-- Public inbound routes have no signed-in user. Instead of widening system_db(), the API
-- switches to the NOLOGIN role `ingest`, which can only EXECUTE the functions below.
-- Each function looks up a token (by hash) or an email address, and inserts one private
-- raw item for that company. Nothing else is reachable from this role.

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'ingest') then
    create role ingest nologin noinherit nobypassrls;
  end if;
end
$$;
grant ingest to app_api with inherit false, set true;
grant usage on schema private to ingest;

-- ---------------------------------------------------------------------------
-- Inserting a private item (shared by webhook, email and the "Send test" button)
-- ---------------------------------------------------------------------------
create function private.insert_private_item(
  p_tenant_id uuid, p_source_key text, p_external_id text, p_title text, p_body text,
  p_url text, p_author text, p_posted_at timestamptz, p_payload jsonb
) returns uuid
language plpgsql volatile security definer set search_path = '' as $$
declare
  v_id uuid;
begin
  insert into public.raw_items (source_key, external_id, visibility, tenant_id, url,
                                author_handle, title, body, posted_at, payload)
  values (p_source_key,
          left(p_tenant_id::text || ':' || coalesce(nullif(p_external_id, ''),
                                                     gen_random_uuid()::text), 300),
          'private', p_tenant_id, left(p_url, 2000), left(p_author, 200), left(p_title, 500),
          left(p_body, 50000), p_posted_at, coalesce(p_payload, '{}'::jsonb))
  on conflict (source_key, external_id) do nothing
  returning id into v_id;
  return v_id;  -- null when this external id was already received
end
$$;
revoke all on function private.insert_private_item(uuid, text, text, text, text, text, text, timestamptz, jsonb) from public;

create function private.ingest_webhook(
  p_token_hash text, p_external_id text, p_title text, p_body text, p_url text,
  p_author text, p_posted_at timestamptz, p_payload jsonb
) returns table (tenant_id uuid, raw_item_id uuid)
language plpgsql volatile security definer set search_path = '' as $$
declare
  v_tenant uuid;
begin
  select e.tenant_id into v_tenant
  from public.inbound_endpoints e
  join public.tenants t on t.id = e.tenant_id and t.status = 'active'
  where e.token_hash = p_token_hash and e.kind = 'webhook' and e.revoked_at is null;
  if v_tenant is null then
    raise exception 'unknown endpoint' using errcode = 'LG404';
  end if;
  return query select v_tenant, private.insert_private_item(
    v_tenant, 'webhook', p_external_id, p_title, p_body, p_url, p_author, p_posted_at, p_payload);
end
$$;

create function private.ingest_email(
  p_email_local text, p_external_id text, p_title text, p_body text, p_url text,
  p_posted_at timestamptz, p_payload jsonb
) returns table (tenant_id uuid, raw_item_id uuid)
language plpgsql volatile security definer set search_path = '' as $$
declare
  v_tenant uuid;
begin
  select e.tenant_id into v_tenant
  from public.inbound_endpoints e
  join public.tenants t on t.id = e.tenant_id and t.status = 'active'
  where e.email_local = lower(p_email_local) and e.kind = 'email' and e.revoked_at is null;
  if v_tenant is null then
    raise exception 'unknown endpoint' using errcode = 'LG404';
  end if;
  return query select v_tenant, private.insert_private_item(
    v_tenant, 'email', p_external_id, p_title, p_body, p_url, null, p_posted_at, p_payload);
end
$$;

revoke all on function private.ingest_webhook(text, text, text, text, text, text, timestamptz, jsonb) from public;
revoke all on function private.ingest_email(text, text, text, text, text, timestamptz, jsonb) from public;
grant execute on function private.ingest_webhook(text, text, text, text, text, text, timestamptz, jsonb) to ingest;
grant execute on function private.ingest_email(text, text, text, text, text, timestamptz, jsonb) to ingest;

-- ---------------------------------------------------------------------------
-- Managing endpoints (owners and admins, from user_db)
-- ---------------------------------------------------------------------------
create function private.create_inbound_endpoint(
  p_tenant_id uuid, p_kind text, p_token_hash text, p_hint text, p_email_local text
) returns uuid
language plpgsql volatile security definer set search_path = '' as $$
declare
  v_id uuid;
begin
  if not private.has_role(p_tenant_id, array['owner', 'admin']) then
    raise exception 'not allowed' using errcode = '42501';
  end if;
  if (select count(*) from public.inbound_endpoints e
      where e.tenant_id = p_tenant_id and e.revoked_at is null) >= 10 then
    raise exception 'too many active endpoints; revoke one first' using errcode = 'LG409';
  end if;
  insert into public.inbound_endpoints (tenant_id, kind, token_hash, token_hint, email_local)
  values (p_tenant_id, p_kind, p_token_hash, p_hint, p_email_local)
  returning id into v_id;
  perform private.write_audit('inbound_endpoint.created', p_tenant_id, 'inbound_endpoint',
                              v_id::text, jsonb_build_object('kind', p_kind));
  return v_id;
end
$$;

create function private.revoke_inbound_endpoint(p_endpoint_id uuid) returns uuid
language plpgsql volatile security definer set search_path = '' as $$
declare
  v_tenant uuid;
begin
  update public.inbound_endpoints e set revoked_at = now()
  where e.id = p_endpoint_id and e.revoked_at is null
    and private.has_role(e.tenant_id, array['owner', 'admin'])
  returning e.tenant_id into v_tenant;
  if v_tenant is null then
    raise exception 'endpoint not found' using errcode = 'LG404';
  end if;
  perform private.write_audit('inbound_endpoint.revoked', v_tenant, 'inbound_endpoint',
                              p_endpoint_id::text, '{}'::jsonb);
  return v_tenant;
end
$$;

create function private.send_test_item(p_tenant_id uuid) returns uuid
language plpgsql volatile security definer set search_path = '' as $$
begin
  if not private.has_role(p_tenant_id, array['owner', 'admin']) then
    raise exception 'not allowed' using errcode = '42501';
  end if;
  return private.insert_private_item(
    p_tenant_id, 'webhook', null, 'Test lead from your webhook',
    'This is a test item. Real items arrive when your website form or n8n flow posts to your webhook address.',
    null, 'test', now(), jsonb_build_object('test', true));
end
$$;

revoke all on function private.create_inbound_endpoint(uuid, text, text, text, text) from public;
revoke all on function private.revoke_inbound_endpoint(uuid) from public;
revoke all on function private.send_test_item(uuid) from public;
grant execute on function private.create_inbound_endpoint(uuid, text, text, text, text) to authenticated;
grant execute on function private.revoke_inbound_endpoint(uuid) to authenticated;
grant execute on function private.send_test_item(uuid) to authenticated;
