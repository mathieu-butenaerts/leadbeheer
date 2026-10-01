-- One-time wipe of all companies and contacts, for replacing the current
-- (test/partial) data with a real migration. IRREVERSIBLE — there is no
-- undo once this commits. Back up first:
--   - Right now, with no setup needed: click "Exporteren" in the app.
--   - Or, once the daily-backup workflow's secrets are set (see README.md's
--     "Daily database backup" section): Actions > Daily Database Backup >
--     Run workflow, then pull the fresh backups/leadbeheer-export.xlsx.
--
-- Deleting every row from companies cascades automatically (every other
-- table's company_id has `on delete cascade`) to also delete:
--   - every contact (contacts.company_id)
--   - every company-tag assignment (company_tags.company_id)
--   - all SuperScore history (company_superscore_history.company_id)
-- The `tags` table itself (the tag NAMES, not their assignments) is left
-- alone — only mentioned here because it's easy to assume "contacts" means
-- "everything", and tags are exactly the thing this does NOT touch, so
-- existing tag names are still there to reuse once the real data lands.
--
-- Preview first — run this on its own and read the number before touching
-- anything:
--   select count(*) as companies_to_delete from public.companies;
--   select count(*) as contacts_to_delete from public.contacts;

begin;

delete from public.companies;

commit;
