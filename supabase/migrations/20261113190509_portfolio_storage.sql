-- Module 2: private storage bucket for portfolio files.
--
-- Files live under "<tenant_id>/<random>.<ext>". Storage policies read the first folder
-- of the path and check membership, so a user can only touch their own company's
-- folder, also when calling the Storage API directly. The bucket is private: there is
-- no public URL, and downloads use short-lived signed links.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('portfolio', 'portfolio', false, 10485760, array[
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain'
])
on conflict (id) do update
  set public = false,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

-- The company id an object path belongs to (null when the first folder is not a uuid).
create function private.object_tenant(p_name text) returns uuid
language plpgsql immutable set search_path = '' as $$
declare
  v_first text := split_part(p_name, '/', 1);
begin
  if v_first ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' then
    return v_first::uuid;
  end if;
  return null;
end
$$;
revoke all on function private.object_tenant(text) from public;
grant execute on function private.object_tenant(text) to authenticated, service_role;

create policy portfolio_objects_select on storage.objects for select to authenticated
  using (bucket_id = 'portfolio' and private.is_member(private.object_tenant(name)));

create policy portfolio_objects_insert on storage.objects for insert to authenticated
  with check (
    bucket_id = 'portfolio'
    and private.has_role(private.object_tenant(name), array['owner', 'admin'])
    and name !~ '\.\.'
  );

create policy portfolio_objects_delete on storage.objects for delete to authenticated
  using (bucket_id = 'portfolio'
         and private.has_role(private.object_tenant(name), array['owner', 'admin']));
-- No UPDATE policy: files are replaced by uploading a new object, never overwritten.
