-- Leadbeheer — schema for the shared companies/contacts store.
-- Run this once in your Supabase project's SQL editor (Project > SQL Editor > New query).
-- Uses the SAME project as Marktmonitor, so it reuses your existing `profiles` /
-- `auth.users` accounts — anyone who can already log in to Marktmonitor can log
-- in here too, no new registration needed.
--
-- Safe to re-run: every statement below is guarded (if not exists / drop if
-- exists / on conflict), so running this again after a partial failure won't
-- duplicate or break anything.

-- Make sure gen_random_uuid() resolves without schema-qualifying it — some
-- projects don't have pgcrypto on the search_path used by the SQL editor,
-- which would otherwise fail the CREATE TABLE below and roll back everything
-- in this script (explaining a "table not found" error afterwards).
create extension if not exists pgcrypto;

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
  job_title        text not null default '',
  gender           text not null default '',
  email            text not null default '',
  email2           text not null default '',
  mobile_phone     text not null default '',
  work_phone       text not null default '',
  beller           text not null default '',
  vervolg          text not null default '',
  follow_up_date   date,
  notities         text not null default '',
  belaantekeningen text not null default '',
  hook             text not null default '',
  created_at       timestamptz not null default now()
);

-- Added after the initial release — ALTER so this script still works against
-- a `contacts` table created before these columns existed.
alter table public.contacts add column if not exists job_title text not null default '';
alter table public.contacts add column if not exists follow_up_date date;

create index if not exists idx_contacts_company on public.contacts(company_id);

-- User-created labels (like mailbox tags), many-to-many with companies.
create table if not exists public.tags (
  id         uuid primary key default gen_random_uuid(),
  name       text not null,
  created_at timestamptz not null default now()
);
-- Case-insensitive uniqueness so "Hot lead" and "hot lead" can't both be
-- created — the app checks this client-side too, but the constraint is what
-- actually prevents it under concurrent edits.
create unique index if not exists idx_tags_name_lower on public.tags (lower(name));

create table if not exists public.company_tags (
  company_id uuid not null references public.companies(id) on delete cascade,
  tag_id     uuid not null references public.tags(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (company_id, tag_id)
);
create index if not exists idx_company_tags_tag on public.company_tags(tag_id);

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
alter table public.companies    enable row level security;
alter table public.contacts     enable row level security;
alter table public.tags         enable row level security;
alter table public.company_tags enable row level security;

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

drop policy if exists "authenticated read tags" on public.tags;
create policy "authenticated read tags" on public.tags
  for select to authenticated using (true);

drop policy if exists "authenticated write tags" on public.tags;
create policy "authenticated write tags" on public.tags
  for all to authenticated using (true) with check (true);

drop policy if exists "authenticated read company_tags" on public.company_tags;
create policy "authenticated read company_tags" on public.company_tags
  for select to authenticated using (true);

drop policy if exists "authenticated write company_tags" on public.company_tags;
create policy "authenticated write company_tags" on public.company_tags
  for all to authenticated using (true) with check (true);

-- Live updates in the browser (company/contact/tag changes push to every
-- open tab). Wrapped so re-running this script (or a table already being a
-- member) can't error out and roll back everything else above.
do $$
begin
  begin
    execute 'alter publication supabase_realtime add table public.companies';
  exception when duplicate_object then null;
  end;
  begin
    execute 'alter publication supabase_realtime add table public.contacts';
  exception when duplicate_object then null;
  end;
  begin
    execute 'alter publication supabase_realtime add table public.tags';
  exception when duplicate_object then null;
  end;
  begin
    execute 'alter publication supabase_realtime add table public.company_tags';
  exception when duplicate_object then null;
  end;
end $$;

-- Optional: a few example rows so the page isn't empty on first load.
-- Safe to delete straight from the Leadbeheer UI once you have real data.
-- (Guarded with NOT EXISTS rather than ON CONFLICT: `companies.name` has no
-- unique constraint, so ON CONFLICT DO NOTHING wouldn't actually catch a
-- re-run and would duplicate these rows every time the script is run.)
insert into public.companies (name, linkedin, stage, notes, contact_count)
select v.name, v.linkedin, v.stage, v.notes, 0
from (values
  ('Van Herck Verpakkingen', 'https://www.linkedin.com/company/van-herck-verpakkingen', 'gecontacteerd', 'Bezig met vervanging van hun huidige leverancier voor kartonnen verpakkingen. Vervolgafspraak gepland.'),
  ('BrightFlow Software', 'https://www.linkedin.com/company/brightflow-software', 'nieuw', 'Binnengekomen via de website. Nog niet gecontacteerd.')
) as v(name, linkedin, stage, notes)
where not exists (select 1 from public.companies c where c.name = v.name);

-- A couple of example contacts for those two companies, so expanding a
-- company shows what a filled-in row looks like. Matched to the company by
-- name (not id, since the id is a random uuid we don't know ahead of time),
-- and guarded so re-running this script won't create duplicates.
insert into public.contacts (
  company_id, first_name, last_name, job_title, gender, email, mobile_phone, work_phone,
  beller, vervolg, follow_up_date, notities, belaantekeningen, hook
)
select c.id, v.first_name, v.last_name, v.job_title, v.gender, v.email, v.mobile_phone, v.work_phone,
  v.beller, v.vervolg, v.follow_up_date, v.notities, v.belaantekeningen, v.hook
from public.companies c
join (values
  ('Van Herck Verpakkingen', 'Els', 'Verhoeven', 'Inkoopmanager', 'Vrouw', 'els.verhoeven@vanherck-voorbeeld.be',
   '+32 478 12 34 56', '+32 3 210 00 10', 'Mathieu', 'Bellen op 12/09 voor prijsofferte', current_date + 3,
   'Beslisser voor inkoop verpakkingsmateriaal.', 'Positief gesprek op 5/09, vraagt vergelijkende offerte.',
   'Zoekt duurzamere verpakking i.k.v. hun ESG-rapportage.'),
  ('Van Herck Verpakkingen', 'Tom', 'Peeters', 'Technisch Coördinator', 'Man', 'tom.peeters@vanherck-voorbeeld.be',
   '+32 475 22 11 09', '', '', '', null,
   'Technisch aanspreekpunt, geen beslissingsbevoegdheid.', '', ''),
  ('BrightFlow Software', 'Sara', 'De Wilde', 'Head of Operations', 'Vrouw', 'sara.dewilde@brightflow-voorbeeld.io',
   '+32 496 33 44 55', '', 'Mathieu', 'Eerste kennismakingscall inplannen', current_date - 2,
   'Head of Operations, contact gelegd via LinkedIn.', '',
   'Team groeit snel, mogelijk nood aan extra licenties binnen 2 maanden.')
) as v(company_name, first_name, last_name, job_title, gender, email, mobile_phone, work_phone,
       beller, vervolg, follow_up_date, notities, belaantekeningen, hook)
  on v.company_name = c.name
where not exists (
  select 1 from public.contacts ct
  where ct.company_id = c.id and ct.first_name = v.first_name and ct.last_name = v.last_name
);

-- Tell PostgREST to pick up the new tables immediately, instead of waiting
-- for its own periodic schema refresh.
notify pgrst, 'reload schema';
