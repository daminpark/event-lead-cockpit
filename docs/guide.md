# How the cockpit works

## What it's for
It finds the people and companies worth meeting at upcoming events, explains why each one matters, and lets you approve the good ones and send them to HubSpot. The next step with a lead is usually meeting them face to face at the event.

## The everyday flow
1. **Events (step 1).** Each event has a score with its reasons: how many strong-fit people its lists name, how much of the list is worth a look, whether GeneralMind already has a stand, timing, travel, and whether this year's list is out. Mark the events you'll attend as **Going** (or **Not going**). Click ▾ for details, including companies exhibiting there with no named person yet.
2. **People (step 2).** By default you see the people at the events you're going to. Everyone starts in **To review**, best fit first. Read the five-second brief, click a row for the full picture, then **Approve** (A) or **Reject** (R, then a reason 1–6). **U** undoes. Nothing is ever approved automatically.
3. **Approved.** Tick the people to send (or Select all) and click **Send to HubSpot**, usually one event at a time. You can unapprove anyone here; they go back to To review. **Download CSV** gives the same list as a file.
4. **In HubSpot.** Sent people move here, with a link to their HubSpot record. From then on, the work happens in HubSpot.

People are always grouped by event. The list on the left shows each event with its counts (to review, approved, in HubSpot); pick one to work on just that event. People from events you're not going to aren't deleted: they're under "Other events".

Every screen has its own link (the address bar, or **Copy link** on events and people), so you can send a colleague straight to an event's approved list or one person's card. They'll need the access code.

## Suggestions
The score suggests, it never decides:
- **Strong fit**: strong role and company fit, solid data.
- **Possible**: plausible but uncertain.
- **Low fit**: weak fit, or vendors, associations and universities. Listed last, in case you want to rescue one.

**Partners** (SAP partners, integrators, consultancies: a referral and co-selling channel), **competitors** (order, invoice and procurement automation vendors: market intel) and **existing customers** (for their account owner) are kept out of review by default. Tick "Partners, competitors & customers" to see them.

## Scores
Each contact gets 0–100 points: **role** (what they do and how senior), **company** (operating company, industry, size, DACH, ERP), and **event** (speaking or moderating, how soon, whether GeneralMind has a stand). Every point shows up as a reason. Company details are estimates until an enrichment provider confirms them. **Data confidence** drops when a list is from last year's edition, the company profile is uncertain, or the name wasn't found on the saved source page.

## Companies
Each person's card shows their company: type (potential buyer, partner, competitor), industry, size, ERP where public, which events it exhibits at, and who else from it is on the lists. Approving a person brings their company along to HubSpot, linked.

## Changing how leads are scored (Criteria)
Every weight and keyword is a slider or a list. As you change something, the preview shows how many leads would move between lanes, who would enter or leave fast track, and how well the change agrees with past decisions. Nothing changes until you **Save and activate**. Every save is a numbered version with a note; any older version can be activated again. Settings that would break the scoring are refused.

## Changing how leads are found (Playbooks)
The plain-language instructions the AI steps follow when finding events, sourcing leads from event pages and profiling companies. Edit, save with a note, and switch versions the same way. Changes apply the next time sourcing runs.

## The copilot
Ask it anything about the leads, events, scores or playbooks ("who should we meet first at BME?", "why is this lead in review?"). It can propose changes to the criteria or playbooks; they're saved as inactive versions with an **Activate** button, so a person always decides. The owner chooses the model and its thinking effort in Settings.

## Insights
The funnel from sourced to HubSpot, decisions over time, the change log, which events and industries give the best leads, how each scoring version compares on past decisions, the feedback inbox and recorded errors.

## Feedback and errors
Click **Feedback**, then click the part of the page your note is about (or press Esc for a general note). The note is saved with what you were looking at and your last few actions, so it can be reproduced. Errors in the page or on the server are recorded the same way. Both appear under **Insights**, with their status.

## Do not contact
On any person's card, **Do not contact** keeps that person out of exports and HubSpot, across every event they appear at.

## HubSpot
The light in the header shows whether the connection is healthy. Each push creates or updates companies and contacts, linked, and never duplicates: every record carries the cockpit's own id. Emails are left empty on purpose; they should come from an enrichment provider with a proper legal basis.

## Settings (owner)
Paste the HubSpot service key and the OpenRouter key, and choose the copilot's model and thinking effort. Keys are stored on the server and never shown again in full.

## Rules the cockpit follows
Business information from public event pages only: name, title, company, talk. No emails or phone numbers are collected, no LinkedIn, and sites that block automated access are respected. In Germany cold email needs prior consent (UWG §7), so the first contact is best made at the event or through an introduction.
