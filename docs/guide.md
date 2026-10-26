# How the cockpit works

## What it's for
It finds the people and companies worth meeting at upcoming events, explains why each one matters, and lets you approve the good ones and send them to HubSpot. The next step with a lead is usually meeting them face to face at the event.

## The everyday flow
1. Open **Contacts**. The **Fast track** and **Review** tiles are selected by default: the leads worth a look, best first.
2. Read the brief on each row: who they are, why they matter, and an opener for the event. Click a row for the full picture.
3. **Approve** (A) or **Reject** (R, then a reason 1–6). The next lead is selected automatically. **U** undoes the last decision.
4. In **HubSpot**, push the approved leads (or download the CSV files).

## Lanes
- **Fast track**: strong role and company fit, solid data. Suggested approve.
- **Review**: plausible but uncertain. You decide.
- **Filtered**: low fit, or vendors, associations and universities. Still there in case you want to rescue one.
- **Partners**: SAP partners, integrators, consultancies. A different motion (referrals, co-selling).
- **Competitors**: order, invoice and procurement automation vendors. Market intel, not leads.
- **Customers**: existing GeneralMind customers. For their account owner, not for prospecting.

Click a tile to show only that lane. Cmd/Ctrl-click to combine lanes.

## Scores
Each contact gets 0–100 points: **role** (what they do and how senior), **company** (operating company, industry, size, DACH, ERP), and **event** (speaking or moderating, how soon, whether GeneralMind has a stand). Every point shows up as a reason. Company details are estimates until an enrichment provider confirms them. **Data confidence** drops when a list is from last year's edition, the company profile is uncertain, or the name wasn't found on the saved source page.

## Accounts
The same review at company level: every company seen at a target event, its contacts, and why it scored as it did. Approving a contact also brings its company along to HubSpot.

## Events
The ten events with dates, why they matter, their source pages, and how many good leads each produced.

## Changing how leads are scored (Criteria)
Every weight and keyword is a slider or a list. As you change something, the preview shows how many leads would move between lanes, who would enter or leave fast track, and how well the change agrees with past decisions. Nothing changes until you **Save and activate**. Every save is a numbered version with a note; any older version can be activated again. Settings that would break the scoring are refused.

## Changing how leads are found (Playbooks)
The plain-language instructions the AI steps follow when finding events, sourcing leads from event pages and profiling companies. Edit, save with a note, and switch versions the same way. Changes apply the next time sourcing runs.

## The copilot
Ask it anything about the leads, events, scores or playbooks ("who should we meet first at BME?", "why is this lead in review?"). It can propose changes to the criteria or playbooks; they're saved as inactive versions with an **Activate** button, so a person always decides. The owner chooses the model in Settings.

## Insights
The funnel from sourced to HubSpot, decisions over time, the change log, which events and industries give the best leads, how each scoring version compares on past decisions, the feedback inbox and recorded errors.

## Feedback and errors
Click **Feedback**, then click the part of the page your note is about (or press Esc for a general note). The note is saved with what you were looking at and your last few actions, so it can be reproduced. Errors in the page or on the server are recorded the same way. Both appear under **Insights**, with their status.

## Do not contact
On any contact or account, **Do not contact** keeps that person (across every event) or company out of exports and HubSpot.

## HubSpot
The light in the header shows whether the connection is healthy. Each push creates or updates companies and contacts, linked, and never duplicates: every record carries the cockpit's own id. Emails are left empty on purpose; they should come from an enrichment provider with a proper legal basis.

## Settings (owner)
Paste the HubSpot private app token and the OpenRouter key, and choose the copilot's model. Keys are stored on the server and never shown again in full.

## Rules the cockpit follows
Business information from public event pages only: name, title, company, talk. No emails or phone numbers are collected, no LinkedIn, and sites that block automated access are respected. In Germany cold email needs prior consent (UWG §7), so the first contact is best made at the event or through an introduction.
