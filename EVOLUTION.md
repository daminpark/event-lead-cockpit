# How this evolved

I built this on 26 October 2026 with Claude Code, which wrote most of the code. The ideas are mine unless a note says otherwise, and each linked change has a one-line "Why".

## Start: the whole loop once (17:51)
- Ten events, their people, scores with reasons, a review screen and HubSpot ([aef8c02]).
- **A person decides.** Nothing is approved automatically; each decision records its scoring version ([574b4a8]).
- **Visible and versioned.** Rules and AI instructions can be read, changed and rolled back ([3b555b6]).
- **Quick to improve.** Feedback from any page, and a chat for questions ([969de6a]).
- **Legal.** Public business information only. A site that blocked automated access was replaced, not worked around ([cf02a11]).

## Who it's for (18:54)
- The colleague who meets these people face to face, so every lead has a five-second brief and an opener ([026b845]).

## Events first (19:58)
- Time at the event is the limit: choose the events first, then who to meet ([04af383], [ec40b36]).
- Events are judged on the best people we could actually meet: at about eight meetings a day, 32 excellent names beat 200 mediocre ones ([7c220ba]).

## Cutting back (20:33)
- The event-finding button went: a strong model finds events for now, an agent later ([0bb4bec]).
- The chat became a help assistant: the model isn't reliable enough to change things itself ([2e8fb62]).
- A setting is on the page or not used. Insights and the tutorial tab went ([7c220ba], [c108991], [71d47e6]).
- Criteria became Scoring, the last step of Playbooks: playbooks decide what we collect, scoring what it's worth ([fa61042]).

## HubSpot fits in (22:21)
- Check HubSpot before sending; nothing it already has is overwritten ([e1b14b7], [38a9dd5]).
- Only sure matches are linked; otherwise a person decides ([fe0e7cb], [9d98f20]).
- One company per website, one current title per person ([cb0016d]).

## Meeting people (23:16)
- No cold email: in Germany it needs prior consent, even between businesses. So no invitations; speakers are caught as they come off stage ([222efbb]).
- With a timetable, an event is scored on who we can actually catch ([6071070]).
- Cost per meeting replaced travel points: ticket, travel, hotel and people's days, per conversation ([083b971]).
- The playbooks now follow this, so the next run judges events as I would ([ff90810]).

## Why it's public
- So the steps can be followed, not just the result ([9d6edf9], [958dbe7]).
- People's names are removed from the whole history.

[aef8c02]: https://github.com/daminpark/event-lead-cockpit/commit/aef8c02
[574b4a8]: https://github.com/daminpark/event-lead-cockpit/commit/574b4a8
[3b555b6]: https://github.com/daminpark/event-lead-cockpit/commit/3b555b6
[969de6a]: https://github.com/daminpark/event-lead-cockpit/commit/969de6a
[cf02a11]: https://github.com/daminpark/event-lead-cockpit/commit/cf02a11
[026b845]: https://github.com/daminpark/event-lead-cockpit/commit/026b845
[04af383]: https://github.com/daminpark/event-lead-cockpit/commit/04af383
[ec40b36]: https://github.com/daminpark/event-lead-cockpit/commit/ec40b36
[7c220ba]: https://github.com/daminpark/event-lead-cockpit/commit/7c220ba
[0bb4bec]: https://github.com/daminpark/event-lead-cockpit/commit/0bb4bec
[2e8fb62]: https://github.com/daminpark/event-lead-cockpit/commit/2e8fb62
[c108991]: https://github.com/daminpark/event-lead-cockpit/commit/c108991
[71d47e6]: https://github.com/daminpark/event-lead-cockpit/commit/71d47e6
[fa61042]: https://github.com/daminpark/event-lead-cockpit/commit/fa61042
[e1b14b7]: https://github.com/daminpark/event-lead-cockpit/commit/e1b14b7
[38a9dd5]: https://github.com/daminpark/event-lead-cockpit/commit/38a9dd5
[fe0e7cb]: https://github.com/daminpark/event-lead-cockpit/commit/fe0e7cb
[9d98f20]: https://github.com/daminpark/event-lead-cockpit/commit/9d98f20
[cb0016d]: https://github.com/daminpark/event-lead-cockpit/commit/cb0016d
[222efbb]: https://github.com/daminpark/event-lead-cockpit/commit/222efbb
[6071070]: https://github.com/daminpark/event-lead-cockpit/commit/6071070
[083b971]: https://github.com/daminpark/event-lead-cockpit/commit/083b971
[ff90810]: https://github.com/daminpark/event-lead-cockpit/commit/ff90810
[9d6edf9]: https://github.com/daminpark/event-lead-cockpit/commit/9d6edf9
[958dbe7]: https://github.com/daminpark/event-lead-cockpit/commit/958dbe7
