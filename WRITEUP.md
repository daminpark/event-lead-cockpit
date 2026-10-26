# Event lead cockpit: write-up

Pierre Park · 26 October 2026 · Cockpit: {LINK}

## 1. What I built

**Ten events where GeneralMind's buyers go**, between November 2026 and June 2027, mostly in DACH. Dates were checked on the organisers' own sites.

| Event | Date | Where | Why |
|---|---|---|---|
| European Manufacturing & Supply Chain Strategies Summit | 3–4 Nov 2026 | Munich | Heads of supply chain and operations at manufacturers |
| BME-Symposium Einkauf und Logistik | 18–19 Nov 2026 | Berlin | Largest DACH procurement congress; GeneralMind is a start-up partner |
| Hannover Messe | 5–8 Apr 2027 | Hannover | Exhibitors are manufacturers with order desks |
| Handelsblatt CPO-Summit | 6–7 Apr 2027 | Düsseldorf | CPOs of large DACH groups |
| BME EP&SCE Summit | 19–20 Apr 2027 | Berlin | Invitation-only, CPOs and supply chain chiefs |
| transport logistic | 26–29 Apr 2027 | Munich | Exhibitors are logistics firms receiving orders by email and PDF |
| SSOW Europe | 10–13 May 2027 | Estoril | Heads of shared services, P2P and O2C |
| BME-eLÖSUNGSTAGE | 11–12 May 2027 | Düsseldorf | Digital procurement and P2P; AI invoice automation on the 2026 agenda |
| LOG Handelslogistik Kongress | 8–9 Jun 2027 | Cologne | Logistics heads at retailers and consumer brands |
| Procurement Summit | 23–24 Jun 2027 | Hamburg | In-house procurement, incl. wholesalers like Würth and Berner |

**A pipeline that sources the leads.** For each event it saves the public speaker, agenda, exhibitor and partner pages, extracts name, title, company and talk title, and then checks every lead against the saved page. A second pass removes anything it can't find there, so every lead in the cockpit links to the page it came from. Each company is then classified as buyer, partner, competitor, vendor or other, and given an estimated industry, size, country and (where it's public) ERP. A rules-based score, kept in one readable config file, gives every contact and account a fit score from 0 to 100 with its reasons, and puts it in a lane.

**The cockpit** shows the leads by lane (fast track, review, filtered, plus partners, competitors and existing customers kept apart), with the reasons behind each score, data confidence, and a link to the source. A reviewer approves or rejects with a reason, by click or keyboard. Every decision is stored with what the scoring had suggested, which feeds a Learning tab (agreement rate, approval by score band, what the reject reasons say about each rule). Approved leads export as two HubSpot import files, companies and contacts, linked by domain.

**In numbers:** {N_CONTACTS} named contacts and {N_ACCOUNTS} companies across the ten events; {N_FAST} contacts on fast track and {N_REVIEW} for review.

Two things stood out in the data:
- **GeneralMind is exhibiting at the BME-Symposium on 18–19 November.** The cockpit has {N_BME_FAST} fast-track contacts there, so the most useful thing it can do this month is fill the stand's calendar.
- **Exhibitor lists mean different things at different events.** At most congresses the exhibitors are vendors (half the BME partner wall is lio, tacto, Pactum, Mercanis and others), so they're kept as market intel, not leads. At transport logistic and Hannover Messe it's the other way round: the exhibitors are logistics firms and manufacturers with order desks, so the exhibitor list is a prospect list for order-to-cash.

Choices I made on purpose: rules rather than a model (with no outcome data yet, a score people can read and argue with is more useful); speakers and exhibitors rather than attendees (attendee lists aren't public); no emails or phone numbers and no LinkedIn scraping. Company details are AI estimates and labelled that way.

## 2. From event cockpit to a full lead-generation system

The cockpit is the middle of the system. Sources feed it, enrichment fills the gaps, people review, HubSpot receives, and outcomes flow back into the scoring.

**Sources and signals.** Events are one source. The stronger ones show the pain directly, or show that something is about to change:
- *Hiring:* companies advertising for *Sachbearbeiter Auftragsabwicklung*, *Kreditorenbuchhaltung* or *Vertriebsinnendienst* are paying people to do by hand what Autopilot does. Several open roles at once is the strongest single signal I can think of.
- *ERP change:* SAP ECC mainstream maintenance ends in 2027, so many companies are redesigning order and invoice processes as they move to S/4HANA. Announcements, job ads for S/4 roles and partner case studies show who.
- *E-invoicing:* larger German companies have to send B2B e-invoices from January 2027, which puts accounts-payable processes on the agenda this year.
- *Lookalikes* of current customers (Kloeckner, Oatly, bofrost*, Sennheiser, Müller lila Logistik): same industry, size and ERP.
- *Partners:* SAP partners and implementation consultancies know who's migrating. They have their own lane in the cockpit for that reason.
- *Champions moving:* a pilot user who changes jobs is the warmest lead there is.

**ICP and scoring.** Two parts. *Fit* is fairly stable: industry (manufacturing, wholesale and distribution, retail and consumer goods, logistics), size (roughly 500 to 20,000 employees), DACH first, ERP, and the persona (order management, AP and shared services, procurement, supply chain, with heads and directors as buyers and team leads as champions). *Timing* comes from signals and fades over time. Priority goes to high fit with a recent signal. Hard rules route competitors out, consultancies to the partner track, and existing customers or open deals to their owner.

**Enrichment.** Cheap data first, expensive data last. Firmographics for every account, then contacts and verified business emails only for accounts that pass the fit threshold, using a waterfall of providers (for example Apollo first, a second one when it misses), orchestrated in Clay. This keeps the cost per qualified lead down.

**Review with feedback.** The same loop as Autopilot. At the start a person reviews everything. Each decision is stored with the score's suggestion, and the reject reasons map to rules ("wrong role" is a title rule, "too small" a size threshold). Once a score band reaches high agreement over enough decisions (say 90% over 50), it skips review and goes straight to HubSpot, one band and one source at a time. Before any scoring change goes live, it's replayed against past decisions, the same way a pilot replays 30–50 real cases.

**HubSpot.** Push through the API instead of CSVs. Check existing records first (customers, open deals, owners), so a known company gets a new signal attached rather than a duplicate. Upsert companies by domain and contacts by email, set the fit score, reasons and source as properties, assign an owner by segment or territory, and enrol the contact in a sequence that matches the signal (meeting request before an event, e-invoicing, S/4 migration). Meetings and deal stages sync back, so the scoring can learn from outcomes and not only from reviewers.

**Measuring.** A funnel per source and segment: sourced, approved, contacted, replied, meeting, pilot, customer. Plus cost per meeting by source, reviewer agreement, and review time per lead. Every few weeks, move effort towards the sources and segments that turn into pilots, and stop the ones that don't. Test two or three messages per segment on small lists rather than one big send.

**GDPR and German law.** Business contact data from public sources can be processed under legitimate interest, with a documented balancing test, the source stored for every lead (the cockpit already does this), people informed at first contact, a suppression list shared across tools, and unused leads deleted after a set period. One DACH-specific point: under §7 UWG, advertising by email needs the recipient's prior consent even when the recipient is a business, while a phone call to a business needs at least presumed consent. So in Germany the first touch is better made in person at the event, through a partner introduction, or by phone with a clear business reason, rather than by cold email. That's one more reason event-led outreach suits this market. I'd confirm the details with counsel.

## 3. What v1 leaves out, and what I'd build next

v1 is deliberately small. Six of the ten events haven't published their 2027 lists yet, so those use the previous edition's speakers and say so. The trade-fair lists are capped at about 100 DACH companies each. Company data is estimated, and ERP is mostly unknown. Sourcing ran once rather than on a schedule, and there's no login.

With more time, in this order:
1. Push approved leads to HubSpot through the API, with the duplicate check against existing records.
2. Re-run the event sources weekly, so 2027 speaker lists flow in as they're published.
3. Add the hiring signal for DACH as the second source.
4. Enrichment for fast-track accounts: the right persona and a verified email.
5. Feed meetings and pilots back into the scoring.
