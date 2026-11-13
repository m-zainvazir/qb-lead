# Lead Generation Platform: Plain-Language Summary

As of 2026-11-12.

## The whole build in one minute

You are building one machine with two halves. The first half finds posts and messages from people who need work done, and understands each one once. The second half decides which agency should see each lead and helps write the proposal.

The build is split into 13 plans in three phases. The detailed plans are the `module-NN-*.md` files in this folder.

| Phase | Plans | What you have at the end | Rough time, solo and full-time |
| --- | --- | --- | --- |
| 1. Working core | 0 to 7 | A tool your own company uses every day to get leads and draft proposals | 10 to 13 weeks |
| 2. Product | 8 to 10 | Something safe to hand to other agencies, steered from your admin panel | 4 to 5 weeks |
| 3. Sellable | 11 and 12 | Something a stranger can sign up for and pay for | 3 to 4 weeks |

At half-time, roughly double those numbers. They are estimates, and the part most likely to run long is tuning lead quality, not writing code.

Each plan ends with two kinds of test: things you click through in the browser, and commands Claude Code runs in the terminal. A plan is finished when both pass, not when the code is written.

## Phase 1: the working core

Plans 0 to 7 give you a tool your own company can use every day. Nothing is sold yet.

### Plan 0 · Foundation

- **In plain words:** You set up the workshop before building anything. One project folder, one command that starts everything, automatic checks on every change, and guard rails for Claude Code.
- **What to expect:** Nothing a customer could see. An empty app that runs on your machine and on a test server.
- **How it helps:** Every later plan goes faster and safer. Slips such as saving a password into the code or wiping the database are blocked automatically.

### Plan 1 · Tenants, logins and isolation

- **In plain words:** The front door and the walls. People sign in, belong to a company, and see only that company's things. You and named admins hold a master key, and every use of it is recorded.
- **What to expect:** You can create two test agencies, invite teammates, and prove with commands that neither agency can see the other.
- **How it helps:** Every later table copies this pattern, so customer data stays separate without fresh effort each time. It is the reason you can sell to agencies that compete with each other and with you.

### Plan 2 · Service catalogue and onboarding profile

- **In plain words:** The questionnaire a new customer answers, plus a shared list of services, the problems they solve, and countries. The answers become a profile the machine follows.
- **What to expect:** Two customers who answer differently see different "here is what we will look for" previews. You can add a service, a country or a question by editing a list, not code.
- **How it helps:** Plans 3, 5 and 7 all read the profile: what to search for, who gets which lead, and how proposals sound.

### Plan 3 · Sources and ingestion

- **In plain words:** The collectors. Small programs fetch posts from Hacker News and web search on a timer. There is also an address where website forms and emails, including forwarded Upwork alerts, can be sent in.
- **What to expect:** A growing pile of raw posts with no repeats, and a running total of what each source costs. Nothing is judged yet, so most of the pile is noise.
- **How it helps:** It gives the next plan material to work on. The cost counter starts protecting your budget from this point.

### Plan 4 · Lead processing

- **In plain words:** The sorter. It cleans each item, removes repeats, throws out obvious junk cheaply, then asks a small AI model whether this is a real request, how urgent it is, for which service, and with what budget.
- **What to expect:** A list of real leads marked hot or warm, each with a reason. You also get a score for how often the sorter is right, measured against 150 examples you labelled by hand.
- **How it helps:** Lead quality is the product. Everything after this trusts these labels, and the score tells you whether a change made things better or worse.

### Plan 5 · Matching and scoring

- **In plain words:** The matchmaker. It compares each lead with each profile and decides who should get it, with a score and a written reason.
- **What to expect:** A voice-agent lead reaches the voice-agent agency and not the web agency. Raising a minimum budget or blocking a keyword changes who gets what.
- **How it helps:** This is what makes the system behave differently for each customer. The stored reasons are what the admin panel shows later.

### Plan 6 · Lead inbox and alerts

- **In plain words:** The customer's screen. A ranked inbox, a page per lead, a board for moving leads through stages, and alerts by Slack and email.
- **What to expect:** A hot lead reaches Slack within a minute. You can filter, take notes and assign leads to a teammate, from a phone as well.
- **How it helps:** This is the first point where the system is useful day to day. Your own company can start using it and telling you what is wrong.

### Plan 7 · Research and proposal agent

- **In plain words:** The writing assistant. It reads the buyer's website, picks your most relevant past work, drafts a proposal in your voice, and waits for your approval.
- **What to expect:** Press a button on a lead and get a specific draft in about a minute. Edit, approve, then copy or send. Nothing goes out without you.
- **How it helps:** It closes the loop from "someone needs help" to "proposal sent". It also ends phase 1: you have a tool worth using yourself and real results to show future customers.

## Phase 2: turning it into a product

Plans 8 to 10 make the tool safe to hand to other agencies, and put you in control of it.

### Plan 8 · Permissions and automation modes

- **In plain words:** The switchboard. You decide which features each customer may use. Each customer then decides which of those to turn on, and whether a step runs by itself or waits for approval.
- **What to expect:** Lock a feature for one agency and its button disappears or turns grey, your choice per feature. A customer can let research run automatically while proposals still wait for a human.
- **How it helps:** This is how you build different plans and prices later without new code. It is also the flexibility you asked for: you offer many automations, and each customer picks.

### Plan 9 · Admin panel

- **In plain words:** Your control room. One place to see every customer, every lead, every source and every dollar spent, and to change the lists and settings that drive the system.
- **What to expect:** You can answer "why did this agency get this lead, and why did that one miss it?" in a few clicks. You can look inside any customer's account in read-only mode, and each look is recorded with your reason.
- **How it helps:** Support, debugging and tuning stop needing a developer. Changing markets, signals, services and permissions becomes a settings job.

### Plan 10 · Costs, monitoring and reliability

- **In plain words:** The safety net. Spending limits that stop the machine before the bill grows, alarms when something breaks, and backups you have actually restored once.
- **What to expect:** A Slack warning at 80 percent of budget and a hard stop at 100 percent. One message when a source fails, not thirty. A tested way to get the data back after a disaster.
- **How it helps:** It keeps the running cost near your 150 dollar target and lets you sleep. Customers will not tolerate lost data or silent outages, so this comes before selling.

## Phase 3: making it sellable

Plans 11 and 12 add the outbound feature and everything needed to take money from strangers.

### Plan 11 · Prospecting mode

- **In plain words:** The hunter. A customer says who they sell to and where. The system finds those businesses, reads their websites for visible proof they need the service, and drafts a message that opens with that proof.
- **What to expect:** A list such as "eight dental clinics in Austin that only take bookings by phone", each with the exact sentence and page that shows it, a score, and a ready draft. Businesses that already solved the problem score low.
- **How it helps:** Customers no longer depend on someone posting a request. It is the same idea as the Ottermind example, but it runs for many customers at once, with limits, costs and country rules built in.

### Plan 12 · Billing and launch readiness

- **In plain words:** The shop counter and the final inspection. Plans and payments, legal pages, a way for customers to export or delete their data, and one complete security pass.
- **What to expect:** A stranger signs up, pays, answers the questionnaire and sees leads within 10 minutes, with no help from you. One command re-runs every security test from every plan.
- **How it helps:** It turns a working system into income. The quiet launch with a few friendly agencies gives you the reply and win numbers that sell the product to everyone after them.

## What to expect along the way

The code is the easier part. Most of your thinking will go into lead quality, access to sources, and a few decisions that are cheaper to make early.

### Decisions to make early

| Decision | Needed by | Why it cannot wait |
| --- | --- | --- |
| Hosting: Hetzner with Coolify, or Railway | Plan 0 | The deploy path is built in the first week |
| How Upwork leads come in | Plan 3 | Forwarded job-alert emails work today; an API key needs Upwork's approval for a stated use |
| Hidden or greyed out, as the default for locked features | Plan 8 | It is a setting per feature, but the default shapes the interface |
| Who takes payments: a merchant of record, or a company abroad with Stripe | Start of phase 2 | Account approval takes time, and Stripe does not accept businesses registered in Pakistan |
| Which countries may receive unrequested email | Plan 11 | It needs legal advice, which takes longer than the code |

### What will probably surprise you

- The first lead lists will be noisy. That is normal. The hand-labelled examples in plan 4, topped up every week, are how the sorter improves.
- Sources change their rules. The source register and risk levels exist so that losing one source does not hurt the product.
- Costs creep through searches and AI calls, not servers. The counter from plan 3 and the caps in plan 10 deal with that.
- The admin panel is the largest single plan when you work alone. It goes much faster once plan 8 is finished.
- Code written by an AI tends to pass the tests the same AI wrote. That is why you click through the manual tests yourself and why the terminal tests check the running app from outside.

### How the checks and tools help you

- **Manual tests** tell you a feature does what a customer expects.
- **Terminal tests** tell you that an attacker, or a curious competitor, cannot do what they should not. The most important one repeats in every plan: Agency A tries to read Agency B's data and gets nothing.
- **Skills and plugins** turn each check into one command: `/security-review` before merging, `rls-test` after any table change, `llm-eval` after any prompt change, `design-check` at the end of a plan.
- **Hooks** stop the costly mistakes while you are not watching, such as leaked keys or a wiped database.

### What you can say after each phase

| After | You can honestly say |
| --- | --- |
| Phase 1 | "My company gets qualified leads every day and sends proposals in minutes." |
| Phase 2 | "Any agency can use it safely, and I control what each one gets." |
| Phase 3 | "People pay for it without speaking to me first." |
