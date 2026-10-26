# Event lead cockpit: write-up

Pierre Park · 26 October 2026 · Cockpit: https://leads.193vbr.com (access code in the email)

## 1. What I built

**Ten events where GeneralMind's buyers go**, November 2026 to June 2027, mostly DACH. Dates were checked on the organisers' own sites.

| Event | Date | Where | Why |
|---|---|---|---|
| European Manufacturing & Supply Chain Strategies Summit | 3–4 Nov 2026 | Munich | Heads of supply chain and operations at manufacturers |
| BME-Symposium Einkauf und Logistik | 18–19 Nov 2026 | Berlin | Largest DACH procurement congress; GeneralMind is a start-up partner |
| Hamburger Logistiktage | 24–25 Feb 2027 | Hamburg | 300 invited logistics heads from retail, consumer goods and logistics |
| Hannover Messe | 5–8 Apr 2027 | Hannover | Exhibitors are manufacturers with order desks |
| Handelsblatt CPO-Summit | 6–7 Apr 2027 | Düsseldorf | CPOs of large DACH groups |
| BME EP&SCE Summit | 19–20 Apr 2027 | Berlin | Invitation-only, CPOs and supply chain chiefs |
| SSOW Europe | 10–13 May 2027 | Estoril | Heads of shared services, P2P and O2C |
| BME-eLÖSUNGSTAGE | 11–12 May 2027 | Düsseldorf | Digital procurement and P2P; AI invoice automation on the 2026 agenda |
| LOG Handelslogistik Kongress | 8–9 Jun 2027 | Cologne | Logistics heads at retailers and consumer brands |
| Procurement Summit | 23–24 Jun 2027 | Hamburg | In-house procurement, incl. wholesalers like Würth and Berner |

**The pipeline.** For each event it saves the public speaker, agenda, exhibitor and partner pages, extracts name, title, company and talk, and then a second, sceptical pass checks every lead against the saved page and removes what it can't find. Each company is classified (buyer, partner, competitor, vendor, other) and given an estimated industry, size, country and, where public, ERP. A rules-based score with visible reasons puts every contact and company in a lane. Result: **680 people (699 event listings) and 806 companies; 187 contacts on fast track, 255 for review.**

**The cockpit** is built for the person who goes and meets these people:
- **Review:** each lead has a five-second brief (who, why they matter, an opener for the event), the score's reasons, data confidence and the source link. Approve or reject with a reason, by click or keyboard. A do-not-contact list covers a person across every event.
- **Criteria:** every weight and keyword is visible and adjustable, with a live preview of how the ranking changes and how the change would have agreed with past decisions. Each save is a numbered version that can be reactivated; invalid settings are refused.
- **Playbooks:** the plain-language instructions the AI steps follow (finding events, sourcing leads, profiling companies), versioned the same way.
- **Copilot:** a chat that answers questions about the data and proposes changes as inactive versions, with a one-click Activate. It never changes what's live on its own.
- **Insights:** the funnel, decisions over time, versions compared by replaying every decision, and a feedback inbox. A Feedback button lets anyone point at part of the page and leave a note.
- **HubSpot:** approved leads go to HubSpot through the API (companies and contacts, linked, deduplicated by our own ids), with a connection light, or as CSV import files.

Two things stood out:
- **GeneralMind is exhibiting at the BME-Symposium on 18–19 November.** The cockpit has 62 fast-track contacts there, so the first use is filling the stand's calendar.
- **Exhibitor lists mean different things at different events.** At most congresses the exhibitors are vendors (much of the BME partner wall is lio, tacto, Pactum, Mercanis and others), so they're kept as market intel. At Hannover Messe and the Hamburger Logistiktage it's the other way round: the exhibitors are manufacturers and logistics firms with order desks, so the list is a prospect list for order-to-cash.

Choices on purpose: rules rather than a model (with no outcome data yet, a score people can read and argue with is more useful); speakers and exhibitors rather than attendees (attendee lists aren't public); no emails, no phone numbers and no LinkedIn; sites that block automated access are respected (transport logistic's directory does, so it was replaced).

## 2. From event cockpit to a full lead-generation system

Sources feed the cockpit, enrichment fills the gaps, people review, HubSpot receives, and outcomes flow back into the scoring.

**Sources and signals.** Events are one source. The stronger ones show the pain directly, or that something is about to change:
- *Hiring:* companies advertising for *Sachbearbeiter Auftragsabwicklung*, *Kreditorenbuchhaltung* or *Vertriebsinnendienst* pay people to do by hand what Autopilot does. Several open roles at once is the strongest single signal I can think of.
- *ERP change:* SAP ECC mainstream maintenance ends in 2027, so many companies are redesigning order and invoice processes as they move to S/4HANA.
- *E-invoicing:* larger German companies must send B2B e-invoices from January 2027, which puts accounts payable on the agenda this year.
- *Lookalikes* of current customers (Kloeckner, Oatly, bofrost*, Sennheiser, Müller lila Logistik): same industry, size and ERP.
- *Partners:* SAP partners and integrators know who is migrating; they have their own lane for that reason.
- *Champions moving:* a pilot user who changes jobs is the warmest lead there is.

**ICP and scoring.** *Fit* is fairly stable: industry, size (roughly 500 to 20,000 employees), DACH first, ERP, and the persona (order management, AP and shared services, procurement, supply chain; heads as buyers, team leads as champions). *Timing* comes from signals and fades. Priority goes to high fit with a recent signal. Competitors are routed out, consultancies to the partner track, customers and open deals to their owner.

**Enrichment.** Cheap data first, expensive last: firmographics for every account; contacts and verified business emails only for accounts above the fit threshold, through a waterfall of providers (for example Apollo, then a second one when it misses), orchestrated in Clay.

**Review with feedback.** The same loop as Autopilot. At first a person reviews everything. Each decision stores the score's suggestion and the settings version. Reject reasons map to rules ("wrong role" is a title rule, "too small" a size threshold). When a score band reaches high agreement over enough decisions (say 90% over 50), it skips review, one band and one source at a time. Every settings change is replayed against past decisions before it goes live, the same way a pilot replays 30–50 real cases. Decisions don't change the scoring on their own; they produce suggestions a person accepts as a new version.

**HubSpot.** Check existing records first (customers, open deals, owners) so a known company gets a new signal rather than a duplicate. Upsert companies by domain and contacts by email once enriched, assign an owner by segment or territory, and enrol the contact in a sequence matching the signal (meeting request before an event, e-invoicing, S/4 migration). Meetings and deal stages sync back so the scoring learns from outcomes, not only from reviewers.

**Measuring.** A funnel per source, segment and settings version: sourced, approved, contacted, replied, meeting, pilot, customer. Plus cost per meeting by source and review time per lead. Every few weeks, move effort to what turns into pilots and stop what doesn't. Test two or three messages per segment on small lists rather than one big send.

**GDPR and German law.** Business contact data from public sources under legitimate interest, with a documented balancing test, the source stored per lead (the cockpit does this), people informed at first contact, a shared suppression list, and unused leads deleted after a set period. Under §7 UWG, advertising by email needs the recipient's prior consent even when the recipient is a business, and a phone call to a business needs at least presumed consent. So in Germany the first touch is better made in person at the event, through a partner, or by phone with a clear business reason. That's one more reason event-led outreach suits this market. I'd confirm the details with counsel.

## 3. What v1 leaves out, and what I'd build next

Six events haven't published 2027 lists yet, so they use the previous edition's speakers and say so. Trade-fair lists are capped at about 100 DACH companies. Company data is estimated and ERP is mostly unknown. Sourcing ran once, not on a schedule.

Next, in order:
1. A daily run that re-checks the event pages and adds new speakers as 2027 lists appear.
2. The hiring signal for DACH as the second source.
3. Enrichment for fast-track accounts: the right persona and a verified email.
4. Outcomes synced back from HubSpot, so versions and sources are compared on meetings and pilots.

*How it was built: Python, FastAPI, SQLite and one HTML page, on a small server at home, deployed from GitHub. Extraction, checking, profiling and briefs were done by AI agents, each checked by a second agent; the scoring itself is plain rules in a config file. Built in an afternoon with Claude Code.*
