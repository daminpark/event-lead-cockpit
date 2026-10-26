# Profiling companies

Each company is profiled once, however many events it appears at. These are estimates until an enrichment provider (Apollo, Clay) confirms them, and the cockpit labels them that way.

## Fields
Display name, website domain, segment (with a one-line reason), industry, HQ country, DACH yes/no, employee band, ERP (only when publicly known, with the evidence), existing customer yes/no, confidence.

## Segments
- **buyer**: an operating company that could buy Autopilot: manufacturers, wholesalers and distributors, retailers, consumer brands, logistics providers, utilities and other large enterprises with order, procurement or invoice volume.
- **competitor**: sells software or AI that automates order processing, invoice processing or procurement workflows (for example lio, tacto, Procure Ai, Pactum, Mercanis, Omnea, ORO Labs, Coupa, JAGGAER, Ivalua, Basware, Esker, Conexiom, Medius, Rossum, Hypatos, Serrala, HighRadius).
- **partner**: could implement, resell or refer: SAP and ERP partners and integrators, IT and procurement consultancies, BPO and shared-service providers. SAP, Oracle and Microsoft themselves count as partners, not competitors.
- **vendor**: other technology or service vendors.
- **other**: associations, universities and research institutes, media, public administration, individuals, unclear entries.

Existing customers (Klöckner & Co, Oatly, bofrost*, Sennheiser, Müller – Die lila Logistik) stay "buyer" and are flagged, so they go to their account owner rather than into prospecting.

## Exhibitors
Classify each exhibitor on its own merits. At trade fairs most exhibitors are buyers (manufacturers, distributors, logistics firms); at procurement congresses most are vendors. An exhibitor becomes a lead only if it's a buyer and its fit is at least "possible": then it's a stand visit.

## Rules
Prefer "unknown" over a guess. One website domain is one company: merge duplicates, but if their profiles disagree on segment or customer status, don't merge; flag them for a person to check. A sceptical second pass checks segment assignments across all companies.
