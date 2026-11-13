-- Fix private.audit_tenants() from 20261113181345_hardening.sql: `text[] || 'literal'`
-- is ambiguous in PL/pgSQL and fails at runtime. Use array_append with typed values.

create or replace function private.audit_tenants() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  v_changed text[] := array[]::text[];
begin
  if tg_op = 'INSERT' then
    perform private.audit_insert('tenant.created', new.id, 'tenant', new.id::text,
                                 jsonb_build_object('type', new.type));
    return null;
  end if;
  if new.name is distinct from old.name then
    v_changed := array_append(v_changed, 'name'::text);
  end if;
  if new.branding is distinct from old.branding then
    v_changed := array_append(v_changed, 'branding'::text);
  end if;
  if new.status is distinct from old.status then
    v_changed := array_append(v_changed, 'status'::text);
  end if;
  if new.is_internal is distinct from old.is_internal then
    v_changed := array_append(v_changed, 'is_internal'::text);
  end if;
  if new.custom_domain is distinct from old.custom_domain then
    v_changed := array_append(v_changed, 'custom_domain'::text);
  end if;
  if cardinality(v_changed) > 0 then
    perform private.audit_insert('tenant.updated', new.id, 'tenant', new.id::text,
                                 jsonb_build_object('changed', to_jsonb(v_changed), 'status', new.status));
  end if;
  return null;
end
$$;
