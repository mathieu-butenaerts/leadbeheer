-- Leadbeheer — schema for the shared companies/contacts store.
-- Run this once in your Supabase project's SQL editor (Project > SQL Editor > New query).
-- Uses the SAME project as Marktmonitor, so it reuses your existing `profiles` /
-- `auth.users` accounts — anyone who can already log in to Marktmonitor can log
-- in here too, no new registration needed.

create table if not exists public.companies (
  id           uuid primary key default gen_random_uuid(),
  name         text not null,
  linkedin     text not null default '',
  stage        text not null default 'nieuw',
  notes        text not null default '',
  contact_count integer not null default 0,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create table if not exists public.contacts (
  id               uuid primary key default gen_random_uuid(),
  company_id       uuid not null references public.companies(id) on delete cascade,
  first_name       text not null default '',
  last_name        text not null default '',
  gender           text not null default '',
  email            text not null default '',
  email2           text not null default '',
  mobile_phone     text not null default '',
  work_phone       text not null default '',
  beller           text not null default '',
  vervolg          text not null default '',
  notities         text not null default '',
  belaantekeningen text not null default '',
  hook             text not null default '',
  created_at       timestamptz not null default now()
);

create index if not exists idx_contacts_company on public.contacts(company_id);

-- Keep companies.contact_count in sync automatically, so the browser never
-- has to read-modify-write it (that would race when two people edit at once).
create or replace function public.leads_sync_contact_count() returns trigger
language plpgsql security definer as $$
begin
  if (tg_op = 'INSERT') then
    update public.companies set contact_count = contact_count + 1, updated_at = now()
      where id = new.company_id;
    return new;
  elsif (tg_op = 'DELETE') then
    update public.companies set contact_count = greatest(0, contact_count - 1), updated_at = now()
      where id = old.company_id;
    return old;
  end if;
  return null;
end;
$$;

drop trigger if exists trg_contacts_count_ins on public.contacts;
create trigger trg_contacts_count_ins after insert on public.contacts
  for each row execute function public.leads_sync_contact_count();

drop trigger if exists trg_contacts_count_del on public.contacts;
create trigger trg_contacts_count_del after delete on public.contacts
  for each row execute function public.leads_sync_contact_count();

-- Row-level security: any signed-in (authenticated) user can read and write.
-- Mirrors the same trust model Marktmonitor already uses for status updates
-- on the `tenders` table — access control lives in Supabase Auth, not in the
-- page being "private".
alter table public.companies enable row level security;
alter table public.contacts  enable row level security;

drop policy if exists "authenticated read companies" on public.companies;
create policy "authenticated read companies" on public.companies
  for select to authenticated using (true);

drop policy if exists "authenticated write companies" on public.companies;
create policy "authenticated write companies" on public.companies
  for all to authenticated using (true) with check (true);

drop policy if exists "authenticated read contacts" on public.contacts;
create policy "authenticated read contacts" on public.contacts
  for select to authenticated using (true);

drop policy if exists "authenticated write contacts" on public.contacts;
create policy "authenticated write contacts" on public.contacts
  for all to authenticated using (true) with check (true);

-- Live updates in the browser (company/contact changes push to every open tab).
-- If this errors with "already a member", the publication already includes
-- the table — safe to ignore.
alter publication supabase_realtime add table public.companies;
alter publication supabase_realtime add table public.contacts;

-- Optional: a few example rows so the page isn't empty on first load.
-- Safe to delete straight from the Leadbeheer UI once you have real data.
insert into public.companies (name, linkedin, stage, notes, contact_count)
values
  ('Van Herck Verpakkingen', 'https://www.linkedin.com/company/van-herck-verpakkingen', 'gecontacteerd', 'Bezig met vervanging van hun huidige leverancier voor kartonnen verpakkingen. Vervolgafspraak gepland.', 0),
  ('BrightFlow Software', 'https://www.linkedin.com/company/brightflow-software', 'nieuw', 'Binnengekomen via de website. Nog niet gecontacteerd.', 0)
on conflict do nothing;
