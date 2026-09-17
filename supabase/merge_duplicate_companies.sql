-- One-time cleanup for duplicate companies created by importing before the
-- page had finished loading (fixed in the app now — see index.html, the
-- Importeren/Nieuw bedrijf/Exporteren buttons stay disabled until data has
-- actually loaded). Run the preview query in the README/chat first to see
-- which names are affected before running this.
--
-- For each set of companies sharing the same name (case/whitespace
-- insensitive): keeps the OLDEST row, fills in anything it's missing from
-- the newer duplicates, moves their contacts and tags onto it, recomputes
-- contact_count, then deletes the duplicates.
--
-- CAVEAT: this assumes same name == same company, which is true for the
-- accidental-duplicate case this is meant to fix, but would incorrectly
-- merge two genuinely different companies that happen to share a name.
-- Check the preview list before running this.
--
-- Wrapped in a transaction so it's all-or-nothing; safe to run again
-- afterwards (a no-op once there's only one row per name).

begin;

create temporary table _dupe_keepers as
select distinct on (lower(trim(name)))
  id as keeper_id, lower(trim(name)) as name_key
from public.companies
order by lower(trim(name)), created_at asc, id asc;

create temporary table _dupe_map as
select c.id as dupe_id, k.keeper_id
from public.companies c
join _dupe_keepers k on lower(trim(c.name)) = k.name_key
where c.id <> k.keeper_id;

select count(*) as duplicate_rows_to_remove from _dupe_map;

update public.companies keep set
  linkedin = coalesce(nullif(keep.linkedin, ''), (select nullif(d.linkedin, '') from public.companies d join _dupe_map m on m.dupe_id = d.id where m.keeper_id = keep.id and nullif(d.linkedin, '') is not null limit 1)),
  notes = coalesce(nullif(keep.notes, ''), (select nullif(d.notes, '') from public.companies d join _dupe_map m on m.dupe_id = d.id where m.keeper_id = keep.id and nullif(d.notes, '') is not null limit 1)),
  engagement_level = coalesce(nullif(keep.engagement_level, ''), (select nullif(d.engagement_level, '') from public.companies d join _dupe_map m on m.dupe_id = d.id where m.keeper_id = keep.id and nullif(d.engagement_level, '') is not null limit 1)),
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

commit;
