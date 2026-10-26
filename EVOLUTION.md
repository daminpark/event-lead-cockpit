# How this evolved

I built this on 26 October 2026 with Claude Code, which wrote most of the code. The direction and most of the ideas below are mine, with the reasons; where an idea came from the first plan, the commit says so. Each commit that carries an idea has a one-line "Why". For the earlier commits I added those lines afterwards, from the conversation we had while building.

## Start: the whole loop once (17:51)
Ten events, the people on their public pages, a score with reasons, a review screen and HubSpot ([08d5125]). Then the principles I kept to:
- **A person decides.** Nothing is approved automatically, and decisions don't change the scoring on their own. A change is tested against past decisions first ([d756e96]).
- **Visible and versioned.** The rules and the agents' instructions can be read, changed and rolled back ([bb356d6]).
- **Quick to improve.** Feedback by pointing at the page, and a chat that answers questions ([90dbe76]).
- **Legal.** Public business information only; when an event's site blocked automated access, we replaced the event rather than work around it ([ef52986]).

## Who it's for
The person who goes to the event and meets these people face to face. So each lead got a five-second brief and an opener ([352f2d8]).

## What's the core?
The review happens in the cockpit; HubSpot gets only the people someone approved, when they choose to send them. Time at an event is the real limit, so the first decision is which events to go to, then who to meet there ([7386c4d], [5849e38]).

## Choosing events
Each event got a page with why it scored as it did, and the list became sortable by date, travel and fit ([21bca4b], [7253fc5]). Then the score changed: one person can meet about eight people a day, so 32 excellent names beat 200 mediocre ones. Events are judged on the best people we could actually meet ([b5de7a3]).

## Cutting back
- The event-finding button went: either it becomes a proper agent that runs on its own, or a strong model finds the events ([b42042b]).
- The chat became a help assistant, because the model isn't reliable enough to change things on its own ([a274926]).
- Playbook changes got their own editor, where you see exactly what changes ([cfd10bf]).
- Insights and most settings went: too much on screen that nobody would act on ([b5de7a3]). A setting is either on the page or not used ([b2f2f92]).
- No tutorial tab: the screens should explain themselves, and the assistant answers questions ([bc1ef55]).

## Why the repo is public
So the steps can be followed, not just the result. Everything that names a person is removed from the whole history; the live cockpit keeps the full data behind an access code.

[08d5125]: https://github.com/daminpark/event-lead-cockpit/commit/08d5125
[d756e96]: https://github.com/daminpark/event-lead-cockpit/commit/d756e96
[bb356d6]: https://github.com/daminpark/event-lead-cockpit/commit/bb356d6
[90dbe76]: https://github.com/daminpark/event-lead-cockpit/commit/90dbe76
[ef52986]: https://github.com/daminpark/event-lead-cockpit/commit/ef52986
[352f2d8]: https://github.com/daminpark/event-lead-cockpit/commit/352f2d8
[7386c4d]: https://github.com/daminpark/event-lead-cockpit/commit/7386c4d
[5849e38]: https://github.com/daminpark/event-lead-cockpit/commit/5849e38
[21bca4b]: https://github.com/daminpark/event-lead-cockpit/commit/21bca4b
[7253fc5]: https://github.com/daminpark/event-lead-cockpit/commit/7253fc5
[b5de7a3]: https://github.com/daminpark/event-lead-cockpit/commit/b5de7a3
[b42042b]: https://github.com/daminpark/event-lead-cockpit/commit/b42042b
[a274926]: https://github.com/daminpark/event-lead-cockpit/commit/a274926
[cfd10bf]: https://github.com/daminpark/event-lead-cockpit/commit/cfd10bf
[b2f2f92]: https://github.com/daminpark/event-lead-cockpit/commit/b2f2f92
[bc1ef55]: https://github.com/daminpark/event-lead-cockpit/commit/bc1ef55
