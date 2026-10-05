-- Cleanup for duplicate companies AND duplicate contacts. Safe to run
-- repeatedly (a no-op once nothing is duplicated).
--
-- Companies: for each set sharing the same name, keeps the OLDEST row,
-- fills in anything it's missing from the newer duplicates, moves their
-- contacts and tags onto it, recomputes contact_count, then deletes the
-- duplicates. "Same name" uses the same rule as the Importeren button:
-- case, extra spaces, dots/commas and a trailing legal form (BV, B.V., NV,
-- BVBA, GmbH, Ltd, ...) are ignored, so "Acme BV" / "Acme B.V." / "Acme"
-- are one company.
--
-- Contacts (after the companies are merged): within one company, a contact
-- is a duplicate of an older one when they share an e-mail address, or
-- share a first+last name and neither has a DIFFERENT e-mail (two people
-- with the same name but different e-mail addresses are kept). The oldest
-- row is kept and takes over any field it has blank.
--
-- CAVEAT: this assumes same name == same company, which is true for the
-- accidental-duplicate case this is meant to fix, but would incorrectly
-- merge two genuinely different companies that happen to share a name
-- (e.g. "Acme NV" and "Acme BV" that really are separate legal entities).
-- Preview which companies would be merged (run this on its own first and
-- check the "names" column — each row is a group that becomes ONE company):
--
--   select key, count(*) as rows, array_agg(name) as names
--   from (
--     select name, coalesce(nullif(btrim(regexp_replace(
--       regexp_replace(regexp_replace(lower(btrim(name)), '[.,]', '', 'g'), '\s+', ' ', 'g'),
--       '\s(bv|nv|bvba|cvba|sprl|srl|vof|cv|gmbh|ag|ltd|llc|inc|sa|sas)$', '')), ''),
--       lower(btrim(name))) as key
--     from public.companies
--   ) t
--   group by key having count(*) > 1 order by rows desc;
--
-- Wrapped in a transaction so it's all-or-nothing.

begin;

create function pg_temp.name_key(n text) returns text language sql immutable as $$
  select coalesce(
    nullif(btrim(regexp_replace(
      regexp_replace(regexp_replace(lower(btrim(n)), '[.,]', '', 'g'), '\s+', ' ', 'g'),
      '\s(bv|nv|bvba|cvba|sprl|srl|vof|cv|gmbh|ag|ltd|llc|inc|sa|sas)$', '')), ''),
    lower(btrim(n)))
$$;

create temporary table _dupe_keepers as
select distinct on (pg_temp.name_key(name))
  id as keeper_id, pg_temp.name_key(name) as name_key
from public.companies
order by pg_temp.name_key(name), created_at asc, id asc;

create temporary table _dupe_map as
select c.id as dupe_id, k.keeper_id
from public.companies c
join _dupe_keepers k on pg_temp.name_key(c.name) = k.name_key
where c.id <> k.keeper_id;

select count(*) as duplicate_rows_to_remove from _dupe_map;

update public.companies keep set
  -- linkedin/notes/engagement_level are NOT NULL columns (default ''), so
  -- each chain needs a trailing '' fallback for when NEITHER the keeper NOR
  -- any duplicate has a non-empty value — otherwise coalesce lands on NULL
  -- and the update violates the not-null constraint.
  linkedin = coalesce(nullif(keep.linkedin, ''), (select nullif(d.linkedin, '') from public.companies d join _dupe_map m on m.dupe_id = d.id where m.keeper_id = keep.id and nullif(d.linkedin, '') is not null limit 1), ''),
  notes = coalesce(nullif(keep.notes, ''), (select nullif(d.notes, '') from public.companies d join _dupe_map m on m.dupe_id = d.id where m.keeper_id = keep.id and nullif(d.notes, '') is not null limit 1), ''),
  engagement_level = coalesce(nullif(keep.engagement_level, ''), (select nullif(d.engagement_level, '') from public.companies d join _dupe_map m on m.dupe_id = d.id where m.keeper_id = keep.id and nullif(d.engagement_level, '') is not null limit 1), ''),
  organic_impressions = coalesce(keep.organic_impressions, (select d.organic_impressions from public.companies d join _dupe_map m on m.dupe_id = d.id where m.keeper_id = keep.id and d.organic_impressions is not null limit 1)),
  organic_engagements = coalesce(keep.organic_engagements, (select d.organic_engagements from public.companies d join _dupe_map m on m.dupe_id = d.id where m.keeper_id = keep.id and d.organic_engagements is not null limit 1)),
  paid_impressions = coalesce(keep.paid_impressions, (select d.paid_impressions from public.companies d join _dupe_map m on m.dupe_id = d.id where m.keeper_id = keep.id and d.paid_impressions is not null limit 1)),
  paid_clicks = coalesce(keep.paid_clicks, (select d.paid_clicks from public.companies d join _dupe_map m on m.dupe_id = d.id where m.keeper_id = keep.id and d.paid_clicks is not null limit 1)),
  paid_engagements = coalesce(keep.paid_engagements, (select d.paid_engagements from public.companies d join _dupe_map m on m.dupe_id = d.id where m.keeper_id = keep.id and d.paid_engagements is not null limit 1)),
  paid_video_views = coalesce(keep.paid_video_views, (select d.paid_video_views from public.companies d join _dupe_map m on m.dupe_id = d.id where m.keeper_id = keep.id and d.paid_video_views is not null limit 1)),
  paid_conversions = coalesce(keep.paid_conversions, (select d.paid_conversions from public.companies d join _dupe_map m on m.dupe_id = d.id where m.keeper_id = keep.id and d.paid_conversions is not null limit 1)),
  paid_leads = coalesce(keep.paid_leads, (select d.paid_leads from public.companies d join _dupe_map m on m.dupe_id = d.id where m.keeper_id = keep.id and d.paid_leads is not null limit 1)),
  paid_qualified_leads = coalesce(keep.paid_qualified_leads, (select d.paid_qualified_leads from public.companies d join _dupe_map m on m.dupe_id = d.id where m.keeper_id = keep.id and d.paid_qualified_leads is not null limit 1)),
  cost_per_qualified_lead = coalesce(keep.cost_per_qualified_lead, (select d.cost_per_qualified_lead from public.companies d join _dupe_map m on m.dupe_id = d.id where m.keeper_id = keep.id and d.cost_per_qualified_lead is not null limit 1))
from _dupe_keepers dk
where keep.id = dk.keeper_id;

-- Move contacts off the duplicates onto the keeper.
update public.contacts c
set company_id = m.keeper_id
from _dupe_map m
where c.company_id = m.dupe_id;

-- Move tags too, but skip a row that would collide with one the keeper
-- already has for the same tag (company_tags' primary key is
-- (company_id, tag_id), so a straight move could violate it).
update public.company_tags ct
set company_id = m.keeper_id
from _dupe_map m
where ct.company_id = m.dupe_id
  and not exists (
    select 1 from public.company_tags existing
    where existing.company_id = m.keeper_id and existing.tag_id = ct.tag_id
  );
delete from public.company_tags ct
using _dupe_map m
where ct.company_id = m.dupe_id;

-- contact_count's insert/delete trigger doesn't fire for this kind of
-- company_id reassignment, so recompute it directly.
update public.companies keep
set contact_count = (select count(*) from public.contacts c where c.company_id = keep.id)
from _dupe_keepers dk
where keep.id = dk.keeper_id;

delete from public.companies c
using _dupe_map m
where c.id = m.dupe_id;

drop table _dupe_keepers;
drop table _dupe_map;

-- ---- duplicate contacts (now that each company exists only once) ----

create temporary table _contact_dupes as
with ranked as (
  select id, company_id, created_at,
         lower(btrim(email)) as e,
         lower(btrim(regexp_replace(first_name || ' ' || last_name, '\s+', ' ', 'g'))) as n
  from public.contacts
)
select distinct on (d.id) d.id as dupe_id, k.id as keeper_id
from ranked d
join ranked k on k.company_id = d.company_id
  and (k.created_at, k.id) < (d.created_at, d.id)
  and ( (d.e <> '' and d.e = k.e)
     or (d.n <> '' and d.n = k.n and (d.e = '' or k.e = '' or d.e = k.e)) )
order by d.id, k.created_at, k.id;

-- A keeper that is itself a duplicate of something older (A~B, B~C, A!~C)
-- would be deleted out from under its own duplicates; leave those alone,
-- a second run of this script picks up what remains.
delete from _contact_dupes where keeper_id in (select dupe_id from _contact_dupes);

select count(*) as duplicate_contacts_to_remove from _contact_dupes;

update public.contacts k set
  job_title        = coalesce(nullif(k.job_title, ''),        (select nullif(d.job_title, '')        from public.contacts d join _contact_dupes m on m.dupe_id = d.id where m.keeper_id = k.id and nullif(d.job_title, '')        is not null order by d.created_at limit 1), ''),
  gender           = coalesce(nullif(k.gender, ''),           (select nullif(d.gender, '')           from public.contacts d join _contact_dupes m on m.dupe_id = d.id where m.keeper_id = k.id and nullif(d.gender, '')           is not null order by d.created_at limit 1), ''),
  email            = coalesce(nullif(k.email, ''),            (select nullif(d.email, '')            from public.contacts d join _contact_dupes m on m.dupe_id = d.id where m.keeper_id = k.id and nullif(d.email, '')            is not null order by d.created_at limit 1), ''),
  email2           = coalesce(nullif(k.email2, ''),           (select nullif(d.email2, '')           from public.contacts d join _contact_dupes m on m.dupe_id = d.id where m.keeper_id = k.id and nullif(d.email2, '')           is not null order by d.created_at limit 1), ''),
  mobile_phone     = coalesce(nullif(k.mobile_phone, ''),     (select nullif(d.mobile_phone, '')     from public.contacts d join _contact_dupes m on m.dupe_id = d.id where m.keeper_id = k.id and nullif(d.mobile_phone, '')     is not null order by d.created_at limit 1), ''),
  work_phone       = coalesce(nullif(k.work_phone, ''),       (select nullif(d.work_phone, '')       from public.contacts d join _contact_dupes m on m.dupe_id = d.id where m.keeper_id = k.id and nullif(d.work_phone, '')       is not null order by d.created_at limit 1), ''),
  beller           = coalesce(nullif(k.beller, ''),           (select nullif(d.beller, '')           from public.contacts d join _contact_dupes m on m.dupe_id = d.id where m.keeper_id = k.id and nullif(d.beller, '')           is not null order by d.created_at limit 1), ''),
  vervolg          = coalesce(nullif(k.vervolg, ''),          (select nullif(d.vervolg, '')          from public.contacts d join _contact_dupes m on m.dupe_id = d.id where m.keeper_id = k.id and nullif(d.vervolg, '')          is not null order by d.created_at limit 1), ''),
  notities         = coalesce(nullif(k.notities, ''),         (select nullif(d.notities, '')         from public.contacts d join _contact_dupes m on m.dupe_id = d.id where m.keeper_id = k.id and nullif(d.notities, '')         is not null order by d.created_at limit 1), ''),
  belaantekeningen = coalesce(nullif(k.belaantekeningen, ''), (select nullif(d.belaantekeningen, '') from public.contacts d join _contact_dupes m on m.dupe_id = d.id where m.keeper_id = k.id and nullif(d.belaantekeningen, '') is not null order by d.created_at limit 1), ''),
  hook             = coalesce(nullif(k.hook, ''),             (select nullif(d.hook, '')             from public.contacts d join _contact_dupes m on m.dupe_id = d.id where m.keeper_id = k.id and nullif(d.hook, '')             is not null order by d.created_at limit 1), ''),
  follow_up_date   = coalesce(k.follow_up_date,               (select d.follow_up_date               from public.contacts d join _contact_dupes m on m.dupe_id = d.id where m.keeper_id = k.id and d.follow_up_date is not null order by d.created_at limit 1))
where k.id in (select keeper_id from _contact_dupes);

-- contact_count's delete trigger keeps the per-company count in step.
delete from public.contacts c
using _contact_dupes m
where c.id = m.dupe_id;

drop table _contact_dupes;

commit;
