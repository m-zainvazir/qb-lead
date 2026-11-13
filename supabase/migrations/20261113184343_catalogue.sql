-- Module 2: the shared catalogue and the questionnaire, stored as data.
--
-- Shared tables (no tenant_id). Every signed-in user can read the active rows; only the
-- platform admin path (system_db / service_role) can write. Adding a service, market,
-- signal or question is a data change, never a code change.

create extension if not exists vector with schema extensions;

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------
create table public.services (
  id          uuid primary key default gen_random_uuid(),
  slug        text not null unique check (slug ~ '^[a-z0-9][a-z0-9-]{1,59}$'),
  name        text not null check (char_length(btrim(name)) between 1 and 120 and name !~ '[[:cntrl:]]'),
  description text not null default '' check (char_length(description) <= 2000),
  is_active   boolean not null default true,
  sort_order  integer not null default 100,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create table public.problems (
  id              uuid primary key default gen_random_uuid(),
  service_id      uuid not null references public.services (id) on delete cascade,
  label           text not null check (char_length(btrim(label)) between 1 and 200),
  example_phrases text[] not null default '{}' check (cardinality(example_phrases) <= 30),
  is_active       boolean not null default true,
  sort_order      integer not null default 100,
  created_at      timestamptz not null default now()
);
create index problems_service_id_idx on public.problems (service_id, sort_order);

create table public.technologies (
  id         uuid primary key default gen_random_uuid(),
  slug       text not null unique check (slug ~ '^[a-z0-9][a-z0-9-]{1,59}$'),
  name       text not null check (char_length(btrim(name)) between 1 and 120),
  synonyms   text[] not null default '{}' check (cardinality(synonyms) <= 30),
  is_active  boolean not null default true,
  created_at timestamptz not null default now()
);

create table public.service_technologies (
  service_id    uuid not null references public.services (id) on delete cascade,
  technology_id uuid not null references public.technologies (id) on delete cascade,
  primary key (service_id, technology_id)
);
create index service_technologies_technology_idx on public.service_technologies (technology_id);

create table public.markets (
  id             uuid primary key default gen_random_uuid(),
  code           text not null unique check (code ~ '^[A-Z]{2}$'),  -- ISO 3166-1 alpha-2
  name           text not null check (char_length(btrim(name)) between 1 and 120),
  default_weight numeric(4, 2) not null default 1 check (default_weight between 0 and 1),
  is_active      boolean not null default true,
  sort_order     integer not null default 100,
  created_at     timestamptz not null default now()
);

create table public.signal_types (
  id             uuid primary key default gen_random_uuid(),
  key            text not null unique check (key ~ '^[a-z][a-z0-9_]{1,50}$'),
  label          text not null check (char_length(btrim(label)) between 1 and 120),
  description    text not null default '' check (char_length(description) <= 1000),
  temperature    text not null check (temperature in ('hot', 'warm')),
  default_weight numeric(4, 2) not null default 1 check (default_weight between 0 and 1),
  is_active      boolean not null default true,
  sort_order     integer not null default 100,
  created_at     timestamptz not null default now()
);

-- The questionnaire. `maps_to` names the profile field an answer fills, so the pipeline
-- reads named fields and never re-interprets free text.
create table public.onboarding_questions (
  id         uuid primary key default gen_random_uuid(),
  key        text not null unique check (key ~ '^[a-z][a-z0-9_]{1,50}$'),
  step       integer not null check (step between 1 and 20),
  sort_order integer not null default 100,
  type       text not null check (type in ('single_choice', 'multi_choice', 'number', 'text',
                                            'long_text', 'catalogue_services',
                                            'catalogue_markets', 'catalogue_signals')),
  label      text not null check (char_length(btrim(label)) between 1 and 300),
  help       text not null default '' check (char_length(help) <= 1000),
  options    jsonb not null default '[]'::jsonb check (jsonb_typeof(options) = 'array'),
  required   boolean not null default true,
  validation jsonb not null default '{}'::jsonb check (jsonb_typeof(validation) = 'object'),
  show_if    jsonb check (show_if is null or jsonb_typeof(show_if) = 'object'),
  maps_to    text not null check (maps_to in (
               'profile.type', 'profile.team_size', 'profile.min_budget_usd',
               'profile.client_sizes', 'profile.tone', 'profile.priorities',
               'profile.time_zone', 'profile.about', 'services', 'custom_services',
               'markets', 'signals', 'exclusions')),
  is_active  boolean not null default true,
  created_at timestamptz not null default now()
);
create index onboarding_questions_step_idx on public.onboarding_questions (step, sort_order);

create trigger services_touch before update on public.services
  for each row execute function private.touch_updated_at();

-- ---------------------------------------------------------------------------
-- Grants and row-level security: read for signed-in users, write for service_role only
-- ---------------------------------------------------------------------------
revoke all on public.services, public.problems, public.technologies,
              public.service_technologies, public.markets, public.signal_types,
              public.onboarding_questions
  from public, anon, authenticated, service_role;

grant select on public.services, public.problems, public.technologies,
                public.service_technologies, public.markets, public.signal_types,
                public.onboarding_questions
  to authenticated;
grant select, insert, update, delete on public.services, public.problems, public.technologies,
                public.service_technologies, public.markets, public.signal_types,
                public.onboarding_questions
  to service_role;

alter table public.services enable row level security;
alter table public.services force row level security;
alter table public.problems enable row level security;
alter table public.problems force row level security;
alter table public.technologies enable row level security;
alter table public.technologies force row level security;
alter table public.service_technologies enable row level security;
alter table public.service_technologies force row level security;
alter table public.markets enable row level security;
alter table public.markets force row level security;
alter table public.signal_types enable row level security;
alter table public.signal_types force row level security;
alter table public.onboarding_questions enable row level security;
alter table public.onboarding_questions force row level security;

create policy services_read on public.services for select to authenticated using (is_active);
create policy problems_read on public.problems for select to authenticated using (is_active);
create policy technologies_read on public.technologies for select to authenticated using (is_active);
create policy service_technologies_read on public.service_technologies for select to authenticated
  using (exists (select 1 from public.services s where s.id = service_id and s.is_active));
create policy markets_read on public.markets for select to authenticated using (is_active);
create policy signal_types_read on public.signal_types for select to authenticated using (is_active);
create policy onboarding_questions_read on public.onboarding_questions for select to authenticated
  using (is_active);

-- ---------------------------------------------------------------------------
-- Seed data (reference data every environment needs)
-- ---------------------------------------------------------------------------
insert into public.markets (code, name, default_weight, sort_order) values
  ('US', 'United States', 1.00, 10),
  ('GB', 'United Kingdom', 0.90, 20),
  ('CA', 'Canada', 0.85, 30),
  ('AU', 'Australia', 0.80, 40),
  ('FR', 'France', 0.70, 50),
  ('PT', 'Portugal', 0.70, 60);

insert into public.signal_types (key, label, description, temperature, default_weight, sort_order) values
  ('request_for_proposal', 'Asks for quotes or proposals',
   'The poster wants someone to do the work and is asking for offers.', 'hot', 1.00, 10),
  ('job_post', 'Hiring a freelancer or agency',
   'A job or contract post for the service.', 'hot', 0.95, 20),
  ('urgent_problem', 'Something is broken now',
   'An outage or a problem that costs money every day.', 'hot', 0.90, 30),
  ('budget_mentioned', 'Mentions a budget',
   'A budget or price range is stated.', 'hot', 0.85, 40),
  ('pain_complaint', 'Complains about a problem we solve',
   'Describes the pain but is not yet asking for help.', 'warm', 0.70, 50),
  ('tool_evaluation', 'Comparing tools or approaches',
   'Asks which tool, platform or approach to choose.', 'warm', 0.60, 60),
  ('vendor_dissatisfaction', 'Unhappy with a current provider',
   'Wants to replace an agency, freelancer or tool.', 'warm', 0.65, 70),
  ('growth_event', 'Growing or changing',
   'Funding, expansion, new location or launch that creates a need.', 'warm', 0.50, 80);

insert into public.services (slug, name, description, sort_order) values
  ('ai-automation', 'AI automation',
   'Automating repetitive business work with AI and integrations.', 10),
  ('voice-agents', 'Voice agents',
   'AI phone agents that answer, qualify and book callers.', 20),
  ('web-development', 'Web development',
   'Websites, web apps and online stores that bring in business.', 30);

insert into public.problems (service_id, label, example_phrases, sort_order)
select s.id, p.label, p.phrases, p.ord
from public.services s
join (values
  ('ai-automation', 'Manual data entry eats hours every week',
   array['we spend hours copying data', 'manual data entry is killing us', 'retyping the same info'], 10),
  ('ai-automation', 'Invoices and receipts processed by hand',
   array['processing invoices manually', 'accounts payable is all manual', 'typing receipts into the system'], 20),
  ('ai-automation', 'Leads are not followed up quickly',
   array['leads go cold', 'we forget to follow up', 'too slow to respond to inquiries'], 30),
  ('ai-automation', 'Support inbox is overloaded',
   array['drowning in support emails', 'same questions every day', 'support tickets piling up'], 40),
  ('ai-automation', 'Reports are built by hand in spreadsheets',
   array['weekly report takes a day', 'copy paste into excel', 'manual reporting'], 50),
  ('ai-automation', 'Tools do not talk to each other',
   array['our CRM and accounting are not connected', 'need an integration between', 'sync data between apps'], 60),
  ('ai-automation', 'Quotes take too long to prepare',
   array['quoting takes days', 'we lose deals because quotes are slow', 'automate proposals'], 70),
  ('ai-automation', 'Customer onboarding is paperwork-heavy',
   array['onboarding new clients takes forever', 'too many forms', 'chasing documents from clients'], 80),
  ('ai-automation', 'Document review takes too long',
   array['reviewing contracts manually', 'reading hundreds of documents', 'extract data from PDFs'], 90),
  ('ai-automation', 'The team answers the same internal questions',
   array['people keep asking the same questions', 'internal knowledge base', 'chatbot for our docs'], 100),
  ('voice-agents', 'Calls are missed after hours',
   array['we miss calls after hours', 'nobody answers the phone at night', 'missed calls cost us customers'], 10),
  ('voice-agents', 'Answering the phone costs too much',
   array['receptionist is too expensive', 'answering service costs', 'need someone to answer phones'], 20),
  ('voice-agents', 'Appointments are booked by phone by hand',
   array['booking appointments over the phone', 'scheduling calls take all day', 'phone booking system'], 30),
  ('voice-agents', 'The front desk is overwhelmed',
   array['front desk cannot keep up', 'phone rings nonstop', 'staff stuck on the phone'], 40),
  ('voice-agents', 'Callers wait on hold and hang up',
   array['customers hang up on hold', 'long hold times', 'call abandonment'], 50),
  ('voice-agents', 'Inbound leads need qualifying calls',
   array['qualify leads by phone', 'call every new lead', 'speed to lead calls'], 60),
  ('voice-agents', 'No-shows because nobody confirms appointments',
   array['too many no-shows', 'appointment reminder calls', 'confirm bookings by phone'], 70),
  ('voice-agents', 'Customers call to ask for order status',
   array['where is my order calls', 'status update calls', 'repetitive phone questions'], 80),
  ('voice-agents', 'Callers speak several languages',
   array['bilingual receptionist', 'callers speak spanish', 'multilingual phone support'], 90),
  ('voice-agents', 'Urgent after-hours calls need triage',
   array['emergency calls at night', 'after-hours dispatch', 'on-call routing'], 100),
  ('web-development', 'The website looks outdated',
   array['our website looks old', 'need a website redesign', 'site from 2010'], 10),
  ('web-development', 'The site is slow',
   array['website loads slowly', 'page speed is terrible', 'site is too slow on mobile'], 20),
  ('web-development', 'The site does not work on phones',
   array['not mobile friendly', 'site breaks on mobile', 'responsive design needed'], 30),
  ('web-development', 'Customers cannot book or buy online',
   array['need online booking', 'want to sell online', 'add a booking form'], 40),
  ('web-development', 'Updating the site needs a developer',
   array['cannot update our own website', 'need a CMS', 'every change needs the developer'], 50),
  ('web-development', 'The website brings in no leads',
   array['website gets no inquiries', 'site does not convert', 'need more leads from the website'], 60),
  ('web-development', 'An online store is needed',
   array['need an ecommerce store', 'set up a shopify store', 'online shop for our products'], 70),
  ('web-development', 'Checkout or forms are broken',
   array['checkout is broken', 'contact form not working', 'payments failing on the site'], 80),
  ('web-development', 'Nobody finds the site on Google',
   array['not ranking on google', 'need SEO help', 'site invisible in search'], 90),
  ('web-development', 'The site must move to a new platform',
   array['migrate from wix', 'move off wordpress', 'replatform our website'], 100)
) as p(slug, label, phrases, ord) on p.slug = s.slug;

insert into public.technologies (slug, name, synonyms) values
  ('openai', 'OpenAI', array['gpt', 'chatgpt', 'gpt-4', 'openai api']),
  ('claude', 'Claude', array['anthropic', 'claude api']),
  ('langchain', 'LangChain', array['langgraph']),
  ('zapier', 'Zapier', array['zaps']),
  ('make', 'Make', array['make.com', 'integromat']),
  ('n8n', 'n8n', array['n8n.io']),
  ('python', 'Python', array['py', 'fastapi', 'django']),
  ('twilio', 'Twilio', array['twilio voice']),
  ('vapi', 'Vapi', array['vapi.ai']),
  ('retell', 'Retell AI', array['retell', 'retellai']),
  ('elevenlabs', 'ElevenLabs', array['eleven labs']),
  ('bland', 'Bland AI', array['bland.ai']),
  ('react', 'React', array['reactjs', 'react.js']),
  ('nextjs', 'Next.js', array['nextjs', 'next js']),
  ('wordpress', 'WordPress', array['wp', 'woocommerce']),
  ('shopify', 'Shopify', array['shopify plus']),
  ('webflow', 'Webflow', array[]::text[]),
  ('laravel', 'Laravel', array['php']),
  ('nodejs', 'Node.js', array['node', 'nodejs', 'express']);

insert into public.service_technologies (service_id, technology_id)
select s.id, t.id
from (values
  ('ai-automation', 'openai'), ('ai-automation', 'claude'), ('ai-automation', 'langchain'),
  ('ai-automation', 'zapier'), ('ai-automation', 'make'), ('ai-automation', 'n8n'),
  ('ai-automation', 'python'),
  ('voice-agents', 'twilio'), ('voice-agents', 'vapi'), ('voice-agents', 'retell'),
  ('voice-agents', 'elevenlabs'), ('voice-agents', 'bland'), ('voice-agents', 'openai'),
  ('web-development', 'react'), ('web-development', 'nextjs'), ('web-development', 'wordpress'),
  ('web-development', 'shopify'), ('web-development', 'webflow'), ('web-development', 'laravel'),
  ('web-development', 'nodejs')
) as l(service, tech)
join public.services s on s.slug = l.service
join public.technologies t on t.slug = l.tech;

insert into public.onboarding_questions
  (key, step, sort_order, type, label, help, options, required, validation, show_if, maps_to)
values
  ('business_type', 1, 10, 'single_choice', 'Are you a freelancer or an agency?', '',
   '[{"value":"freelancer","label":"Freelancer"},{"value":"agency","label":"Agency"}]',
   true, '{}', null, 'profile.type'),
  ('team_size', 1, 20, 'number', 'How many people work on client projects?', '',
   '[]', true, '{"min":2,"max":5000}', '{"question":"business_type","equals":"agency"}',
   'profile.team_size'),
  ('services', 2, 10, 'catalogue_services', 'Which services do you offer?',
   'Pick everything you would like leads for.', '[]', true, '{"min_items":1,"max_items":10}',
   null, 'services'),
  ('custom_services', 2, 20, 'text', 'Anything else you offer? (optional)',
   'Comma separated. Only your company sees these.', '[]', false,
   '{"max_length":300,"max_items":5}', null, 'custom_services'),
  ('min_budget_usd', 3, 10, 'number', 'Smallest project you take on (USD)',
   'Leads below this are scored lower.', '[]', true, '{"min":0,"max":10000000}', null,
   'profile.min_budget_usd'),
  ('client_sizes', 3, 20, 'multi_choice', 'Which clients do you work with best?', '',
   '[{"value":"solo","label":"Solo founders"},{"value":"small","label":"Small businesses (2-50)"},{"value":"mid","label":"Mid-size (51-500)"},{"value":"enterprise","label":"Enterprise (500+)"}]',
   true, '{"min_items":1}', null, 'profile.client_sizes'),
  ('markets', 4, 10, 'catalogue_markets', 'Where are your clients?', '', '[]', true,
   '{"min_items":1}', null, 'markets'),
  ('time_zone', 4, 20, 'single_choice', 'Your time zone', 'Used for alert times.',
   '[{"value":"America/New_York","label":"US Eastern"},{"value":"America/Chicago","label":"US Central"},{"value":"America/Los_Angeles","label":"US Pacific"},{"value":"Europe/London","label":"UK"},{"value":"Europe/Paris","label":"Central Europe"},{"value":"Europe/Lisbon","label":"Portugal"},{"value":"Asia/Karachi","label":"Pakistan"},{"value":"Australia/Sydney","label":"Australia Eastern"}]',
   true, '{}', null, 'profile.time_zone'),
  ('signals', 5, 10, 'catalogue_signals', 'Which kinds of posts should we look for?',
   'Hot signals are people ready to buy; warm ones are earlier.', '[]', true,
   '{"min_items":1}', null, 'signals'),
  ('exclusions', 5, 20, 'long_text', 'Anything to avoid? (optional)',
   'One per line: industries, words or companies you never want.', '[]', false,
   '{"max_length":2000,"max_items":50}', null, 'exclusions'),
  ('tone', 6, 10, 'single_choice', 'How should proposals sound?', '',
   '[{"value":"friendly","label":"Friendly"},{"value":"professional","label":"Professional"},{"value":"direct","label":"Short and direct"}]',
   true, '{}', null, 'profile.tone'),
  ('priorities', 6, 20, 'multi_choice', 'What do clients pick you for?', '',
   '[{"value":"speed","label":"Speed"},{"value":"quality","label":"Quality"},{"value":"price","label":"Price"},{"value":"long_term","label":"Long-term support"}]',
   true, '{"min_items":1,"max_items":3}', null, 'profile.priorities'),
  ('about', 6, 30, 'long_text', 'Describe your work in a few sentences (optional)',
   'Used to tailor proposals. Never shown to leads as-is.', '[]', false,
   '{"max_length":2000}', null, 'profile.about');
