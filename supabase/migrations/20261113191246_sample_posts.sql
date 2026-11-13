-- Module 2: a small fixed set of sample posts used by the profile preview
-- ("here is what we will look for"). Shared data: readable by signed-in users, written
-- only through the platform admin path. The worker caches one embedding per model.

create table public.sample_posts (
  id              uuid primary key default gen_random_uuid(),
  source          text not null check (source in ('reddit', 'web_search', 'job_boards')),
  market_code     text check (market_code ~ '^[A-Z]{2}$'),
  title           text not null check (char_length(btrim(title)) between 1 and 200),
  body            text not null check (char_length(body) between 1 and 2000),
  signal_key      text references public.signal_types (key) on update cascade,
  embedding_model text,
  embedding       extensions.vector(384),
  is_active       boolean not null default true,
  created_at      timestamptz not null default now()
);

revoke all on public.sample_posts from public, anon, authenticated, service_role;
grant select (id, source, market_code, title, body, signal_key, is_active, created_at)
  on public.sample_posts to authenticated;
grant select, insert, update, delete on public.sample_posts to service_role;

alter table public.sample_posts enable row level security;
alter table public.sample_posts force row level security;
create policy sample_posts_read on public.sample_posts for select to authenticated using (is_active);

insert into public.sample_posts (source, market_code, title, body, signal_key) values
  ('reddit', 'US', 'Missing calls after 6pm is killing my plumbing business',
   'We miss every call after hours and those people just call the next plumber. Is there something that can answer the phone and book jobs at night? Happy to pay someone to set it up.',
   'request_for_proposal'),
  ('reddit', 'GB', 'Receptionist quit, phones ringing nonstop at our clinic',
   'Our front desk cannot keep up with the phone. Has anyone used an AI phone agent to book appointments? Looking for recommendations.',
   'tool_evaluation'),
  ('job_boards', 'CA', 'Contract: build a voice agent for appointment reminders',
   'Dental group needs a contractor to build an AI voice agent that calls patients to confirm appointments and reduce no-shows. Budget $3,000.',
   'job_post'),
  ('reddit', 'US', 'Our website looks like it is from 2010',
   'Small landscaping company here. The site is slow, not mobile friendly and nobody finds us on Google. Who should we hire for a redesign?',
   'request_for_proposal'),
  ('job_boards', 'US', 'Looking for a Next.js developer to rebuild our store',
   'We need an agency to move our online store off Wix to Next.js with Shopify checkout. Budget around $15k.',
   'job_post'),
  ('reddit', 'AU', 'Checkout broke after the last plugin update',
   'Payments are failing on our WooCommerce site since yesterday and we are losing sales. Need someone urgently.',
   'urgent_problem'),
  ('reddit', 'US', 'We spend 10 hours a week copying invoices into QuickBooks',
   'Is there a way to automate reading supplier invoices and entering them? Open to paying a freelancer to build it.',
   'request_for_proposal'),
  ('reddit', 'GB', 'Zapier vs Make vs n8n for syncing our CRM and accounting?',
   'Our CRM and accounting tool do not talk to each other and we retype everything. Which tool should we pick?',
   'tool_evaluation'),
  ('web_search', 'FR', 'Startup raises seed round to expand customer support',
   'The company plans to automate its support inbox, which receives hundreds of repetitive questions every day.',
   'growth_event'),
  ('reddit', 'US', 'Best crypto trading bot developer?',
   'Looking for someone to build an automated crypto trading bot with AI signals.',
   'request_for_proposal'),
  ('reddit', 'PT', 'Unhappy with our current web agency',
   'They take weeks for small changes and we cannot update the site ourselves. Thinking of switching agencies.',
   'vendor_dissatisfaction'),
  ('reddit', 'US', 'Anyone know a good wedding photographer in Austin?',
   'Getting married next spring and looking for recommendations.',
   null);
