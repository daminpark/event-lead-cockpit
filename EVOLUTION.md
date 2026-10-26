# How this evolved

I built this on 26 October 2026 with Claude Code, which wrote most of the code. The ideas are mine unless a note says otherwise, and each linked change has a one-line "Why".

## Start: the whole loop once (17:51)
- Ten events, their people, scores with reasons, a review screen and HubSpot ([c6974de]).
- **A person decides.** Nothing is approved automatically; each decision records its scoring version ([c39d8aa]).
- **Visible and versioned.** Rules and AI instructions can be read, changed and rolled back ([879088e]).
- **Quick to improve.** Feedback from any page, and a chat for questions ([34a9baf]).
- **Legal.** Public business information only. A site that blocked automated access was replaced, not worked around ([9f9ac39]).

## Who it's for (18:54)
- The colleague who meets these people face to face, so every lead has a five-second brief and an opener ([8c6c391]).

## Events first (19:58)
- Time at the event is the limit: choose the events first, then who to meet ([c8d1e2b], [27d08cc]).
- Events are judged on the best people we could actually meet: at about eight meetings a day, 32 excellent names beat 200 mediocre ones ([0150f56]).

## Cutting back (20:33)
- The event-finding button went: a strong model finds events for now, an agent later ([43b63ca]).
- The chat became a help assistant: the model isn't reliable enough to change things itself ([48ffa46]).
- A setting is on the page or not used. Insights and the tutorial tab went ([0150f56], [6481672], [782fa8b]).
- Criteria became Scoring, the last step of Playbooks: playbooks decide what we collect, scoring what it's worth ([ef8e594]).

## HubSpot fits in (22:21)
- Check HubSpot before sending; nothing it already has is overwritten ([e091c77], [bba7ead]).
- Only sure matches are linked; otherwise a person decides ([4009bf6], [8c49cec]).
- One company per website, one current title per person ([8e831c0]).

## Meeting people (23:16)
- No cold email: in Germany it needs prior consent, even between businesses. So no invitations; speakers are caught as they come off stage ([41e0cbc]).
- With a timetable, an event is scored on who we can actually catch ([f325ab0]).
- Cost per meeting replaced travel points: ticket, travel, hotel and people's days, per conversation ([8ac79c8]).
- The playbooks now follow this, so the next run judges events as I would ([46978c6]).

## Why it's public
- So the steps can be followed, not just the result ([8ef8c6f], [6072851]).
- People's names are removed from the whole history.

[c6974de]: https://github.com/daminpark/event-lead-cockpit/commit/c6974de
[c39d8aa]: https://github.com/daminpark/event-lead-cockpit/commit/c39d8aa
[879088e]: https://github.com/daminpark/event-lead-cockpit/commit/879088e
[34a9baf]: https://github.com/daminpark/event-lead-cockpit/commit/34a9baf
[9f9ac39]: https://github.com/daminpark/event-lead-cockpit/commit/9f9ac39
[8c6c391]: https://github.com/daminpark/event-lead-cockpit/commit/8c6c391
[c8d1e2b]: https://github.com/daminpark/event-lead-cockpit/commit/c8d1e2b
[27d08cc]: https://github.com/daminpark/event-lead-cockpit/commit/27d08cc
[0150f56]: https://github.com/daminpark/event-lead-cockpit/commit/0150f56
[43b63ca]: https://github.com/daminpark/event-lead-cockpit/commit/43b63ca
[48ffa46]: https://github.com/daminpark/event-lead-cockpit/commit/48ffa46
[6481672]: https://github.com/daminpark/event-lead-cockpit/commit/6481672
[782fa8b]: https://github.com/daminpark/event-lead-cockpit/commit/782fa8b
[ef8e594]: https://github.com/daminpark/event-lead-cockpit/commit/ef8e594
[e091c77]: https://github.com/daminpark/event-lead-cockpit/commit/e091c77
[bba7ead]: https://github.com/daminpark/event-lead-cockpit/commit/bba7ead
[4009bf6]: https://github.com/daminpark/event-lead-cockpit/commit/4009bf6
[8c49cec]: https://github.com/daminpark/event-lead-cockpit/commit/8c49cec
[8e831c0]: https://github.com/daminpark/event-lead-cockpit/commit/8e831c0
[41e0cbc]: https://github.com/daminpark/event-lead-cockpit/commit/41e0cbc
[f325ab0]: https://github.com/daminpark/event-lead-cockpit/commit/f325ab0
[8ac79c8]: https://github.com/daminpark/event-lead-cockpit/commit/8ac79c8
[46978c6]: https://github.com/daminpark/event-lead-cockpit/commit/46978c6
[8ef8c6f]: https://github.com/daminpark/event-lead-cockpit/commit/8ef8c6f
[6072851]: https://github.com/daminpark/event-lead-cockpit/commit/6072851
