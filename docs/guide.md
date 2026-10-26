# How the cockpit works

## What it's for
- Finds the people and companies worth meeting at upcoming events, with the reasons.
- A person approves the good ones and sends them to HubSpot. Nothing is approved or sent on its own.
- The next step with a lead is usually meeting them face to face at the event.

## The everyday flow
1. **Events**: choose where to go. Mark each one Going or Not going.
2. **Open an event**: its score, summary and meeting plan.
3. **Review its people**: approve or reject.
4. **Send to HubSpot** from the Approved tab.

- **People** lists everyone at the events you're going to (or all events), grouped by event, for working across events at once.
- Every screen has its own link (the address bar, or **Copy link**), so you can send a colleague straight to an event or a person's card. They need the access code.

## How events are judged
- Mainly on **the best people we could actually meet**, by their average fit. Time at the event is the limit, not the number of good names. Meetings left empty count as zero.
- No invitations (cold email isn't allowed in Germany), so speakers are met in the break after their talk.
- Where the timetable is out, the cockpit works out exactly who can be caught, break by break. Otherwise it estimates: people sent × days × a set number of conversations a day.
- Then **cost per meeting**: the vendor ticket, travel, hotel and each person's days (travel time included), divided by the conversations we'd get. Events with no ticket for vendors get no points here.
- Then **GeneralMind as a partner** there, **timing** (far enough ahead to book meetings, close enough to plan), and whether **this year's list** is out (not last year's).
- Events whose lists name only exhibiting companies are judged on those companies, met at their stands, for part of the credit.
- **Upcoming** and **Past** lists. Click a column to sort. ✓ and ✕ on each row mark Going or Not going.

## An event and its meeting plan
- **AI summary**: why go, who to meet, the main caveat.
- **Why it scored as it did**: each part of the score with its points.
- **Meeting plan**: who we'd send, how many of the best people we can catch and how good they are, and whether another colleague would be worth it.
- The number of people we'd send can be changed there. The default is one, or two where GeneralMind is a partner.
- With a timetable, it says who to catch in which break. Without one, it's an estimate.
- It also shows what attending costs, the cost per meeting, and how many people are approved out of the meetings possible.
- **Where the names come from**: under More, in About this event.
- Invitation-only events say so: you need an invitation before you can plan meetings there.
- Events that admit vendors only as paying partners (EMS-SCMS) say so too.
- Mark the event **Going** or **Not going** at the top.

## Reviewing people
- Below the event are its people, best fit first, each with a five-second brief.
- Four tabs: **To review**, **Approved**, **In HubSpot**, **Rejected**. Everyone starts in To review. Nothing is ever approved automatically.
- **A** approves.
- **R** rejects, then **1 to 6** picks the reason: wrong role, company too small, wrong industry, vendor or competitor, already a customer or in CRM, bad data.
- **U** undoes the last decision.
- **J** and **K** (or the up and down arrows) move between people.
- **O** opens the person's source page.
- **Esc** closes the list of reasons.
- **Unapprove** puts an approved person back in To review. **Restore** brings a rejected person back.
- Once someone is in HubSpot, their decision can't be changed here until the owner removes them from HubSpot.

## Suggestions
- The score suggests; it never decides.
- **Strong fit**: strong role and company fit, solid data.
- **Possible**: plausible but uncertain.
- **Low fit**: weak fit, or vendors, associations and universities. Listed last, in case you want to rescue one.
- Partners, competitors and existing customers are kept out of review by default. Tick **Partners, competitors & customers** to see them.
- **Partners**: SAP partners, integrators, consultancies. A referral and co-selling channel.
- **Competitors**: order, invoice and procurement automation vendors. Market intel.
- **Existing customers**: for their account owner.

## Scores
- 0 to 100 points from **role** (what they do, how senior; up to 45), **company** (operating company, industry, size, DACH, ERP; up to 40) and **event** (speaking or moderating, how soon, GeneralMind a partner there; up to 15).
- Every point shows as a reason.
- Company details are estimates until an enrichment provider confirms them.
- **Data confidence** drops when a list is from last year's edition, the company profile is uncertain, or the name wasn't found on the saved source page.

## Companies
- Each person's card shows their company: type (potential buyer, partner, competitor), industry, size, ERP where public, which events it exhibits at, and who else from it is on the lists.
- Approving a person brings their company along to HubSpot, linked.
- One website is one company, as in HubSpot. Names that share a website (DHL Global Forwarding and DHL Supply Chain, Mars and Mars Snacking) become one company, with everyone and every event under it.
- The name kept is the one already decided on or in HubSpot, else the surer profile, so it doesn't change as new lists arrive.
- Decisions stay as they were made, so if the two are later split, each gets its own back.
- If their profiles disagree on what the company is (partner, competitor, customer), they stay apart until the profiles are fixed.

## HubSpot: sending
- In **Approved**, tick people (or **Select all**), then **Send to HubSpot**.
- **Download CSV** gives the same list as a file.
- Sent people move to **In HubSpot**, with a link to their record.
- New people start with lifecycle stage Lead.
- Each send creates or updates companies and contacts, linked, and never duplicates. Every record carries the cockpit's own id (GM account id, GM lead id).
- A send looks for the record sent before, then for that id, then for one HubSpot already had, and creates a record only if none exists.

## HubSpot: the check before sending
- Before anything is sent, the Approved tab asks HubSpot what it already has, once per person (all their approved listings together, as the send takes them).
- Each person shows one line: **Already in HubSpot** (with lifecycle stage, owner and a link), **New to HubSpot**, or **Possible match in HubSpot** when it can't be sure.
- A company counts as the same only with the same website. A person counts as the same only with the same first and last name at one of their companies.
- Next to Send it says how many records will be created, how many already in HubSpot only get the GM fields, and how many possible matches stay unsent.
- If HubSpot can't be checked, the send still updates what the cockpit sent before but creates nothing new. It says which were not sent, so sending again later sends them.

## HubSpot: possible matches and same-name people
- A possible match is, say, a company with the same name but another or no website.
- A possible match is never linked or duplicated. That company and its people stay unsent until someone confirms it's the same.
- Same-name people also stay unsent until someone confirms: someone with the same name HubSpot already had at another company, or several people of that name at the company (someone chooses).

## HubSpot: what is and isn't overwritten
- A record HubSpot already had keeps its own name, title, owner, lifecycle stage and other standard fields. Corrections made by sales and customers' records are never overwritten.
- Only the cockpit's own fields (marked GM) are updated.
- A person HubSpot already had keeps their own company. They're linked to ours only if they had none.

## HubSpot: what goes across
- For a company: name, website, country, fit score and reasons, segment and events.
- For a person: first and last name, job title, company, lifecycle stage Lead, fit score and reasons, their role at the event (and, if the name comes from last year's list, that it does), their session and the source page.
- Someone listed at several events goes across with the title, company and score of their most recent approved listing (this year's over last year's).
- Once in HubSpot, they stay with the company they were sent with.
- The company is the name as listed, even when it sits under a larger company here.
- The GM fields are created in HubSpot on the first send.
- Emails are left empty on purpose. They should come from an enrichment provider with a proper legal basis.

## HubSpot: Remove from HubSpot (owner)
- For someone sent by mistake. The person (all their event listings) goes back to Approved here.
- Their record goes to HubSpot's recycle bin, restorable for 90 days, but only if the cockpit created it.
- A person HubSpot had before the cockpit is never deleted. Their record stays in HubSpot.
- Their company goes too only if the cockpit created it and nobody else from it is in HubSpot. Otherwise it stays.

## HubSpot: the connection
- The light in the header shows whether the connection is healthy.
- Clicking it opens Settings, which shows how many records are in HubSpot and the last send.

## Do not contact
- On any person's card, **Do not contact** keeps that person out of downloads and HubSpot, at every event they appear at.
- **Remove from do-not-contact** undoes it.

## Feedback and errors
- Click the **Feedback** button, then click the part of the page your note is about (or press Esc for a general note).
- The note is saved with what you were looking at and your last few actions, so it can be reproduced.
- The **Feedback** tab lists every note, from the button, the copilot or written there directly.
- On each note you can edit it, set its status (open, planned, done, won't do) and write down what was done. Only the owner can delete a note.
- You can also add a note directly in the tab.
- Errors in the page or on the server are recorded the same way and listed there too. They can be marked resolved.

## Playbooks: how leads are found and scored
- Four steps, in order: **finding events**, **sourcing people** from event pages, **profiling companies**, then **Scoring**.
- The first three are the plain-language instructions the AI follows. Open one to edit it.
- **Edit**: the text itself.
- **Changes**: the active version (or any older one) on the left and your draft on the right, side by side. Changed lines are highlighted.
- **History**: every version, to compare, load into the editor, or activate.
- **Discuss with the model** (on the right): ask about the playbook, or ask for a change. When it edits, the draft updates and Changes shows what it did. **Undo** takes it back.
- Nothing changes until you save with a short note, as a version or straight into use.
- Changes apply the next time sourcing runs.

## Scoring
- Scoring decides how much each thing the playbooks collect is worth. Its main levers are sliders.
- Events: the quality of the best people we could meet (the main driver), GeneralMind being a partner there, good timing, cheap per meeting, what a day of someone's time is worth (travel time included), and whether this year's list is out.
- Meeting plan: conversations a day per person at most, and minutes per conversation in a break.
- People: the strong-fit and possible thresholds; points for the main roles (order management or customer service, finance or accounts payable or shared services, procurement, supply chain or logistics); for seniority (C-level or board, head or director or VP); for a core industry; for a company based in DACH; and for speaking at the event.
- Move a slider and the preview shows how many people would be strong fit, possible and low fit, and the new order of events.
- Nothing changes until you save with a note. Everything is then rescored. Earlier versions can be switched back to.
- **All other settings**, folded away below the levers, holds every other setting: the words that recognise each role in a job title or talk, company size bands, the other role, company and event points, timing windows, cost per meeting bands, team sizes, the event thresholds, and how companies with no named person are scored.
- Every setting there is used by the scoring. There are no hidden ones.
- Scoring can only weigh what the playbooks collect. If a playbook starts collecting something new, it needs a weight here before it counts.

## The copilot
- A help assistant. Ask about what's in the cockpit ("who should we meet first at BME?", "why is this person scored 95?", "how many people are approved at the events we're going to?") or how the cockpit works.
- It answers from the cockpit's data (events, people, their status, counts) and links you straight to the right page.
- It can propose a small scoring change, saved as a version you check and switch on under Scoring.
- It can write down feedback.
- Choosing events, approving, rejecting or unapproving people and sending to HubSpot stay with you. It doesn't search the web. Playbooks are discussed in the playbook editor.
- The owner chooses its model and thinking effort in Settings.

## Settings (owner)
- Paste the HubSpot service key and the OpenRouter key (for the AI models).
- Choose the copilot's model and thinking effort. They apply to everyone.
- Keys are stored on the server and never shown again in full. Only the owner can change them.
- Anyone can set their name here. It's saved with their decisions and notes.

## Rules the cockpit follows
- Business information from public event pages only: name, title, company, talk.
- No emails or phone numbers are collected, no LinkedIn, and sites that block automated access are respected.
- In Germany cold email needs prior consent (UWG §7), so the first contact is best made at the event or through an introduction.
