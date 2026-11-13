-- Run once in Supabase: SQL Editor -> New query -> paste -> Run
create table if not exists public.comments (
  id bigint generated always as identity primary key,
  place text not null check (char_length(place) between 1 and 80),
  name  text not null check (char_length(btrim(name)) between 1 and 60),
  body  text not null check (char_length(btrim(body)) > 0
                         and array_length(regexp_split_to_array(btrim(body), '\s+'), 1) <= 1000),
  created_at timestamptz not null default now()
);
create index if not exists comments_place_idx on public.comments(place);

-- At most 50 comments per place
create or replace function public.comments_limit() returns trigger language plpgsql as $$
begin
  if (select count(*) from public.comments where place = new.place) >= 50 then
    raise exception 'comment limit reached for this place';
  end if;
  return new;
end $$;
drop trigger if exists comments_limit_trg on public.comments;
create trigger comments_limit_trg before insert on public.comments
  for each row execute function public.comments_limit();

-- Anyone can read and add comments; nobody can edit or delete from the website
alter table public.comments enable row level security;
drop policy if exists "read comments" on public.comments;
create policy "read comments" on public.comments for select to anon using (true);
drop policy if exists "add comments" on public.comments;
create policy "add comments" on public.comments for insert to anon with check (true);
