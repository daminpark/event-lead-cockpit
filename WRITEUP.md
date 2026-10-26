# Event lead cockpit for GeneralMind

Pierre Park, 26 October 2026  
Cockpit: https://leads.193vbr.com (access code in the email) · Code and how it evolved: https://github.com/daminpark/event-lead-cockpit

# Part 1: What I built

## The idea

- Event leads are for meeting people face to face, and time at the event is the limit.
- So choose the events first, then the people and companies worth meeting there.
- A person decides at every step. Nothing is approved or sent on its own.

## The cockpit

- **10 events**, November 2026 to June 2027, nine in Germany. Each is scored on the best people we could actually meet there, what a meeting costs (tickets, travel, hotel and people's days), timing, whether GeneralMind is a partner, and whether this year's list is out.
- **699 listings** (680 people, mostly speakers) and **786 companies** from public speaker, programme, partner and exhibitor pages. A second AI pass removed any name it couldn't find on the saved page.
- **Every person and company has a score with its reasons**: role, company fit and the event. 241 are suggested as a strong fit, 159 as possible.
- **A meeting plan per event.** Where the timetable is out (BME, Procurement Summit), the cockpit places the best people at the moment they come off stage, up to eight conversations a day per colleague, and scores the event on that plan. Elsewhere it's an estimate until the agenda appears.
- **Review per event**: To review → Approved → In HubSpot, or Rejected. Undecided means no.
- **HubSpot**: approved people go with their company, linked. The cockpit checks HubSpot first; records it already has keep their own details and only get our fields (score, reasons, event, source).
- **Playbooks**: the plain-language steps the AI follows (find events → source people → profile companies → score). Versioned, compared side by side, with a model to discuss changes.

## Where to go
| Event | When | Cost per meeting | Recommendation |
|---|---|---|---|
| BME-Symposium, Berlin | 18–19 Nov | €254 | **Go.** GeneralMind is a Start-up Partner, pitching on 18 Nov at 16:10 |
| BME-eLÖSUNGSTAGE | 11–12 May | €261 | **Go.** The closest topic: digital procure-to-pay |
| Handelsblatt CPO-Summit | 6–7 Apr | €265 | **Go, if they accept a vendor.** CPOs of large DACH groups; registrations are vetted, so ask first |
| Procurement Summit | 23–24 Jun | €163 | **Go.** The best value; any attendee can book meetings in its app |
| Hannover Messe | 5–8 Apr | €117 | **A day of stand visits.** 108 manufacturers worth walking up to |
| SSOW Europe, Estoril | 10–13 May | €411 | Decide in January: the right buyers, but a €4,099 ticket and abroad |
| LOG Handelslogistik | 8–9 Jun | €214 | Skip unless the 2027 list is stronger |
| BME EP&SCE | 19–20 Apr | no ticket | Only as a sponsor |
| EMS-SCMS | 3–4 Nov | no ticket | Skip: 8 days away, vendors only as paying partners |
| Hamburger Logistiktage | 24–25 Feb | no ticket | Skip: invitation only |

Cost per meeting is approximate: the vendor ticket, travel, hotel and each person's days (€500 a day, travel time included), divided by the conversations we could have.

## How the meetings happen

- **No cold email.** In Germany it needs prior consent, between businesses too (§7 Abs. 2 Nr. 2 UWG). So no invitation campaigns.
- **Speakers**: catch them as they come off stage, in the break or at the stage exit.
- **Exhibitors**: walk up to their stand. This matters at trade fairs; at congresses most exhibitors are vendors.
- **The very best few**: through the event's own app where it allows it, or an introduction.
- **Follow-up email** only once they've agreed.

## Left out on purpose

- Automatic approval, cold email, LinkedIn, phone numbers.
- Company data is estimated until enrichment, and 405 listings come from last year's lists (marked as such).

# Part 2: From events to a full lead-generation system

## One loop for every source
Events are only the first source. Every lead, whatever its source, goes through the same five steps:

1. **A source finds it, with a reason**: "speaking at BME on 18 November", or "hiring two order-processing clerks since October".
2. **The same criteria judge it.** One description of a good customer (company type, size, industry, DACH, ERP, and the person's role) and one set of scores, visible and versioned under Playbooks → Scoring. The source only adds its reason and how fresh it is.
3. **Enrichment fills the gaps.** Public pages give estimates and no contact details. A data provider (Apollo, or a DACH provider, possibly through Clay) confirms size, industry and ERP and finds the right person, such as the head of order management. Lookups cost money, so only for leads that pass the criteria. Contact details are used only with a legal basis, for example once someone has agreed to hear from us.
4. **A person reviews it** in the cockpit, with an optional reason for every decision.
5. **HubSpot receives it; outcomes come back.** Met, follow-up, deal flow back into the cockpit and show which sources and criteria work.

## Sources, in the order I'd add them

- **Events** (built): who is on stage or at a stand.
- **Hiring signals**: companies advertising for a *Sachbearbeiter Auftragsabwicklung* or *Kreditorenbuchhaltung* pay people to do by hand what Autopilot does. New ones every week, all year.
- **Timing signals**: SAP ECC mainstream maintenance ends in 2027, and larger German companies must send e-invoices from 2027. Both put order and invoice processes on the table.
- **Lookalikes** of current customers (Kloeckner, Oatly, bofrost*, Sennheiser, Müller lila Logistik): same industry, size and ERP.
- **Partners**: SAP partners and integrators know who is migrating.

## Built, and what's next
**Built**: events as the first source, scoring with reasons, the meeting plan from the timetable (BME, Procurement Summit), review per event, HubSpot with a check before every send, versioned playbooks and scoring, and feedback from any page.

**Not built yet**

- **A reason on every decision**, optional and one click, so we learn how people actually choose.
- **Each colleague's timetable**: approving people fills it, and when two come off stage at the same moment the cockpit asks which matters more.
- **Exhibitors as stand visits**: companies rated possible or better become leads to approve.
- **Outcomes back from HubSpot**: met, follow-up, deal, per event, source and person.
- **A scheduled agent** that keeps event pages and timetables current and proposes new events for a person to accept.
- **Hiring signals**, then the other sources one at a time, each judged on meetings per hour spent.
- **Enrichment**, only for leads that pass the criteria.
- **Suggestions from outcomes** once there is enough data: the system proposes a new version with its evidence, and a person switches it on.

**First, with the people who sell**: review BME's 73 strong and possible names before 18 November. Their reasons are the first real data on how we choose.

**Why not more self-learning now**: ten events a year give too few outcomes to learn from automatically, or to A/B test. Hiring signals bring the volume.

## HubSpot, done carefully

- Look up before sending; never overwrite.
- Unsure matches wait as "possible match". Not built yet: an AI says whether it's likely the same person or company, and a person confirms.
- People we stop pursuing are marked, not deleted.

## GDPR

- Public business information only. The basis is legitimate interest, with a documented balancing test, and the source is stored for each lead.
- People are told within a month of collection (Article 14).
- Do not contact keeps a person out everywhere, and objections in HubSpot flow back into it.

# A parallel

- It's Autopilot's pattern: score each item, let a person handle the uncertain ones, learn from their decisions.
- My guesthouse system works the same way (https://demo.thetachbrook.com/?tour). Changes are first tested on 117 real past conversations. More than 80% of guest messages now go out with nobody involved.

*Built with Claude Code: Python, FastAPI, SQLite and one HTML page, deployed from GitHub.*
