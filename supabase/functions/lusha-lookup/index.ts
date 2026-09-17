// Supabase Edge Function: proxies contact/company lookups to Lusha's v3
// Search & Enrich API, so the Lusha API key never reaches the browser.
//
// Contract verified directly against Lusha's published OpenAPI spec
// (https://docs.lusha.com/_bundle/apis/@v3/openapi.json) on 2026-09 — see
// README.md's "Lusha lookups" section for the field references this was
// checked against.
//
// Called from index.html as:
//   supabase.functions.invoke("lusha-lookup", { body: { type, query } })
// `type` is "contact" or "company"; `query` is passed through almost as-is
// as one entry in Lusha's `contacts`/`companies` array (see CONTACT_FIELDS/
// COMPANY_FIELDS below for exactly which keys are allowed through).
//
// Deploy:
//   supabase functions deploy lusha-lookup
//   supabase secrets set LUSHA_API_KEY=your-key-here
// (see README.md for the full one-time setup, including the CLI install
// and project link, if you haven't used the Supabase CLI before)

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const LUSHA_API_KEY = Deno.env.get("LUSHA_API_KEY");
const SUPABASE_URL = Deno.env.get("SUPABASE_URL");
const SUPABASE_ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY");

// Auth happens on the Supabase JWT below, not on origin, so a permissive
// CORS policy here is fine — it only controls which pages' JS is ALLOWED to
// read the response, not who can authenticate.
const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

// Only these identifier fields are forwarded to Lusha, matching what
// V3ContactSearchItem / V3CompanySearchItem accept — anything else in the
// request body is dropped rather than passed through blind.
const CONTACT_FIELDS = ["id", "linkedinUrl", "email", "firstName", "lastName", "companyName", "companyDomain"];
const COMPANY_FIELDS = ["id", "name", "domain"];

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
  });
}

function pick(obj: Record<string, unknown>, keys: string[]) {
  const out: Record<string, unknown> = {};
  for (const k of keys) if (obj?.[k] != null && obj[k] !== "") out[k] = obj[k];
  return out;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS_HEADERS });
  if (req.method !== "POST") return json({ error: "Use POST" }, 405);

  if (!LUSHA_API_KEY) {
    return json({ error: "LUSHA_API_KEY is not configured on this Edge Function (see README.md)" }, 500);
  }

  // Require a signed-in Leadbeheer user — same trust model as the rest of
  // the app (any authenticated account, gated by Supabase Auth, same as the
  // companies/contacts RLS policies), rather than open to anyone who finds
  // the function URL.
  const authHeader = req.headers.get("Authorization");
  if (!authHeader) return json({ error: "Not signed in" }, 401);
  const supabase = createClient(SUPABASE_URL!, SUPABASE_ANON_KEY!, {
    global: { headers: { Authorization: authHeader } },
  });
  const { data: userData, error: authError } = await supabase.auth.getUser();
  if (authError || !userData?.user) return json({ error: "Not signed in" }, 401);

  let body: { type?: string; query?: Record<string, unknown> };
  try {
    body = await req.json();
  } catch {
    return json({ error: "Request body must be JSON" }, 400);
  }

  if (body.type === "contact") {
    const contact = pick(body.query ?? {}, CONTACT_FIELDS);
    if (!Object.keys(contact).length) return json({ error: "No contact identifiers given" }, 400);
    return await callLusha("https://api.lusha.com/v3/contacts/search-and-enrich", {
      contacts: [{ clientReferenceId: "leadbeheer", ...contact }],
      reveal: ["emails", "phones"],
      options: { includePartialProfiles: true },
    });
  }

  if (body.type === "company") {
    const company = pick(body.query ?? {}, COMPANY_FIELDS);
    if (!Object.keys(company).length) return json({ error: "No company identifiers given" }, 400);
    return await callLusha("https://api.lusha.com/v3/companies/search-and-enrich", {
      companies: [{ clientReferenceId: "leadbeheer", ...company }],
      options: { includePartialProfiles: true },
    });
  }

  return json({ error: "body.type must be 'contact' or 'company'" }, 400);
});

async function callLusha(url: string, payload: unknown) {
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", api_key: LUSHA_API_KEY! },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    console.error("Lusha request failed:", err);
    return json({ error: "Could not reach Lusha" }, 502);
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) console.error("Lusha returned", res.status, data);
  return json(data, res.status);
}
