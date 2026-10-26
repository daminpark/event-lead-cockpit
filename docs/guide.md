# How the cockpit works

## What it's for
It finds the people and companies worth meeting at upcoming events, explains why each one matters, and lets you approve the good ones and send them to HubSpot. The next step with a lead is usually meeting them face to face at the event.

## The everyday flow
1. **Events: choose where to go.** Time limits how many people we can meet, so each event is judged on the **best people we could actually meet there**, by their average fit. There are no invitations (cold email isn't allowed in Germany), so speakers are met in the break after their talk. Where the timetable is out, the cockpit works out exactly who can be caught, break by break; otherwise it estimates people sent × days × a set number of conversations a day. Then whether GeneralMind is a partner there, timing, travel and whether this year's list is out. The list is split into **Upcoming** and **Past**; columns sort with a click; ✓ and ✕ on each row mark it Going or Not going.
2. **Open an event.** See a short **AI summary** (why go, who to meet, the main caveat), **why it scored as it did** (each part of the score with its points), the **meeting plan** (who we'd send, how many of the best people we can catch and how good they are, whether another colleague would be worth it, and, where the timetable is out, who to catch in which break), and where its names come from. Invitation-only events say so: you need an invitation before you can plan meetings there. Some events admit vendors only as paying partners (EMS-SCMS); that is shown too. Mark it **Going** or **Not going**.
3. **Choose who to meet.** Below the event are its people, best fit first, each with a five-second brief. **Approve** (A) or **Reject** (R, then a reason 1–6); **U** undoes. Nothing is ever approved automatically.
4. **Send to HubSpot.** In **Approved**, tick the people (or Select all) and click **Send to HubSpot**; **Download CSV** gives the same list as a file. Sent people move to **In HubSpot**, with a link to their record. The owner can **Remove from HubSpot** if someone was sent by mistake (HubSpot keeps it in its recycle bin for 90 days).

**People** shows everyone at the events you're going to (or every event), grouped by event, for working across events at once.

Every screen has its own link (the address bar, or **Copy link**), so you can send a colleague straight to an event or one person's card. They'll need the access code.

## Suggestions
The score suggests, it never decides:
- **Strong fit**: strong role and company fit, solid data.
- **Possible**: plausible but uncertain.
- **Low fit**: weak fit, or vendors, associations and universities. Listed last, in case you want to rescue one.

**Partners** (SAP partners, integrators, consultancies: a referral and co-selling channel), **competitors** (order, invoice and procurement automation vendors: market intel) and **existing customers** (for their account owner) are kept out of review by default. Tick "Partners, competitors & customers" to see them.

## Scores
Each person gets 0–100 points: **role** (what they do and how senior), **company** (operating company, industry, size, DACH, ERP), and **event** (speaking or moderating, how soon, whether GeneralMind is a partner there). Every point shows up as a reason. Company details are estimates until an enrichment provider confirms them. **Data confidence** drops when a list is from last year's edition, the company profile is uncertain, or the name wasn't found on the saved source page.

## Companies
Each person's card shows their company: type (potential buyer, partner, competitor), industry, size, ERP where public, which events it exhibits at, and who else from it is on the lists. Approving a person brings their company along to HubSpot, linked.

## Playbooks: how leads are found and scored
Four steps, in order. The first three are the plain-language instructions the AI follows: **finding events**, **sourcing people** from event pages and **profiling companies**. The fourth, **Scoring**, decides how much each thing they collect is worth.

Open one of the first three to edit it:
- **Edit**: the text itself.
- **Changes**: the active version (or any older one) on the left and your draft on the right, side by side; changed lines are highlighted.
- **History**: every version, to compare, load into the editor, or activate.
- **Discuss with the model** (on the right): ask about the playbook, or ask for a change. When it edits, the draft updates and Changes shows what it did; **Undo** takes it back.

Nothing changes until you save with a short note, as a version or straight into use. Changes apply the next time sourcing runs.

**Scoring** shows the main levers: how much the quality of the best people counts for an event, GeneralMind being a partner there, timing, travel, the meeting assumptions, the strong-fit and possible thresholds, and how much each role, seniority and company trait counts. Move a slider and the preview shows how many people would change suggestion and the new order of events. Nothing changes until you save with a note; earlier versions can be switched back to. Every other setting (the keyword lists, size bands, company points, lane rules) is under **All other settings**, folded away below the levers. Every setting there is used by the scoring; there are no hidden ones. Scoring can only weigh what the playbooks collect: if a playbook starts collecting something new, it needs a weight here before it counts.

## The copilot
A help assistant. Ask it about what's in the cockpit ("who should we meet first at BME?", "why is this person scored 95?", "how many people are approved at the events we're going to?") or how the cockpit works. It answers from the cockpit's data and links you straight to the right page. It can also propose a small scoring change (saved as a version you check and activate) and write down feedback. Choosing events, approving people and sending to HubSpot stay with you. The owner chooses the model and its thinking effort in Settings.

## Feedback and errors
Click the **Feedback** button, then click the part of the page your note is about (or press Esc for a general note). The note is saved with what you were looking at and your last few actions, so it can be reproduced. The **Feedback** tab lists every note: edit it, set its status (open, planned, done, won't do), write down what was done, or add a note directly. Errors in the page or on the server are recorded the same way and listed there too.

## Do not contact
On any person's card, **Do not contact** keeps that person out of exports and HubSpot, across every event they appear at.

## HubSpot
The light in the header shows whether the connection is healthy; clicking it opens Settings, which shows how many records are in HubSpot and the last push. Each push creates or updates companies and contacts, linked, and never duplicates: every record carries the cockpit's own id (GM account id, GM lead id). A push looks for the record sent before, then for that id, then for one HubSpot already had, and creates a record only if none exists. A record HubSpot already has keeps its own name, title, owner, lifecycle stage and other standard fields, so corrections made by sales and customers' records are never overwritten; only the GM fields are updated. New people start with lifecycle stage Lead. Once someone is in HubSpot their decision can't be changed in the cockpit until the owner removes them from HubSpot.

Before anything is sent, the Approved tab asks HubSpot what it already has, once per person (all their approved listings together, as the send takes them). A company counts as the same only with the same domain; a person only with the same first and last name at one of their companies. Each person shows one line: "Already in HubSpot" with the lifecycle stage, owner and a link, "New to HubSpot", or "Possible match in HubSpot" when it can't be sure, say a company with the same name but another or no domain. A possible match is never linked or duplicated: the send leaves that company and its people unsent until someone confirms it. Next to Send it says how many records will be created, how many existing ones only get the GM fields, and how many possible matches stay unsent. If HubSpot can't be checked, the send still updates what the cockpit sent before but creates nothing new, and says which were not sent, so sending again later sends them. Remove from HubSpot never deletes a person HubSpot had before the cockpit.

What goes across: for a company, its name, domain, country, fit score and reasons, segment and events; for a person, first and last name, job title, company, lifecycle stage Lead, their role at the event (and, if the name comes from last year's list, that it does), their session and the source page. The GM properties are created in HubSpot on the first push. Emails are left empty on purpose; they should come from an enrichment provider with a proper legal basis.

## Settings (owner)
Paste the HubSpot service key and the OpenRouter key, and choose the copilot's model and thinking effort. Keys are stored on the server and never shown again in full.

## Rules the cockpit follows
Business information from public event pages only: name, title, company, talk. No emails or phone numbers are collected, no LinkedIn, and sites that block automated access are respected. In Germany cold email needs prior consent (UWG §7), so the first contact is best made at the event or through an introduction.
