# How the cockpit works

## What it's for
It finds the people and companies worth meeting at upcoming events, explains why each one matters, and lets you approve the good ones and send them to HubSpot. The next step with a lead is usually meeting them face to face at the event.

## The everyday flow
1. **Events: choose where to go.** Time limits how many people we can meet, so each event is judged on the **best people we could actually meet there**: the average fit of the best N, where N is the meetings possible (people sent × days × meetings a day). Then whether GeneralMind is a partner there, timing, travel and whether this year's list is out. The list is split into **Upcoming** and **Past**; columns sort with a click; ✓ and ✕ on each row mark it Going or Not going.
2. **Open an event.** See a short **AI summary** (why go, who to meet, the main caveat), **why it scored as it did** (each part of the score with its points), the **meeting plan** (people we'd send × days × meetings a day, the quality of the best people for those meetings, whether another person would be worth it, and how many to invite), and where its names come from. Invitation-only events say so: you need an invitation before you can plan meetings there. Some events admit vendors only as paying partners (EMS-SCMS); that is shown too. Mark it **Going** or **Not going**.
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
Each person's card shows their company: type (potential buyer, partner, competitor), industry, size, ERP where public, which events it exhibits at, and who else from it is on the lists. Approving a person brings their company along to HubSpot, linked. One website is one company, as in HubSpot: names that share a domain (DHL Global Forwarding and DHL Supply Chain, Mars and Mars Snacking) are kept as the one with the most people, with everyone and every event under it.

## Changing how events and people are scored (Criteria)
One page with the main levers: how much the quality of the best people counts for an event, GeneralMind being a partner there, timing, travel, the meeting assumptions, the strong-fit and possible thresholds, and how much each role, seniority and company trait counts. Move a slider and the preview shows how many people would change suggestion and the new order of events. Nothing changes until you save with a note; earlier versions can be switched back to. Every other setting (the keyword lists, size bands, company points, lane rules) is under **All other settings**, folded away below the levers, and saved the same way. Every setting there is used by the scoring; there are no hidden ones.

## Changing how leads are found (Playbooks)
The plain-language instructions the AI steps follow when finding events, sourcing people from event pages and profiling companies. Open a playbook to edit it:
- **Edit**: the text itself.
- **Changes**: exactly what differs from the active version (or any older one), line by line: added in green, removed in red.
- **History**: every version, to compare, load into the editor, or activate.
- **Discuss with the model** (on the right): ask about the playbook, or ask for a change. When it edits, the draft updates and Changes shows what it did; **Undo** takes it back.

Nothing changes until you save with a short note, as a version or straight into use. Changes apply the next time sourcing runs.

## The copilot
A help assistant. Ask it about what's in the cockpit ("who should we meet first at BME?", "why is this person scored 95?", "how many people are approved at the events we're going to?") or how the cockpit works. It answers from the cockpit's data and links you straight to the right page. It can also propose a small scoring change (saved as a version you check and activate) and write down feedback. Choosing events, approving people and sending to HubSpot stay with you. The owner chooses the model and its thinking effort in Settings.

## Feedback and errors
Click the **Feedback** button, then click the part of the page your note is about (or press Esc for a general note). The note is saved with what you were looking at and your last few actions, so it can be reproduced. The **Feedback** tab lists every note: edit it, set its status (open, planned, done, won't do), write down what was done, or add a note directly. Errors in the page or on the server are recorded the same way and listed there too.

## Do not contact
On any person's card, **Do not contact** keeps that person out of exports and HubSpot, across every event they appear at.

## HubSpot
The light in the header shows whether the connection is healthy; clicking it opens Settings, which shows how many records are in HubSpot and the last push. Each push creates or updates companies and contacts, linked, and never duplicates: every record carries the cockpit's own id (GM account id, GM lead id). A push looks for the record sent before, then for that id, then (for companies) for the domain, and creates a record only if none exists. A record HubSpot already has keeps its own name, title and other standard fields, so corrections made by sales and customers' records are never overwritten; only the GM fields are updated. New people start with lifecycle stage Lead. Once someone is in HubSpot their decision can't be changed in the cockpit until the owner removes them from HubSpot.

What goes across: for a company, its name, domain, country, fit score and reasons, segment and events; for a person, first and last name, job title, company, lifecycle stage Lead, their role at the event (and, if the name comes from last year's list, that it does), their session and the source page. Someone listed at several events goes across with the title and company of their most recent list (this year's over last year's). The GM properties are created in HubSpot on the first push. Emails are left empty on purpose; they should come from an enrichment provider with a proper legal basis.

## Settings (owner)
Paste the HubSpot service key and the OpenRouter key, and choose the copilot's model and thinking effort. Keys are stored on the server and never shown again in full.

## Rules the cockpit follows
Business information from public event pages only: name, title, company, talk. No emails or phone numbers are collected, no LinkedIn, and sites that block automated access are respected. In Germany cold email needs prior consent (UWG §7), so the first contact is best made at the event or through an introduction.
