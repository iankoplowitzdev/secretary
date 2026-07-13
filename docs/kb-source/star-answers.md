# STAR-Method Answers

Behavioral interview material grounding the agent's answers to "tell me about a time..." style
questions, plus supporting Q&A and technical reference material pulled from the same source.
Some entries are fully fleshed out; a few are still just topic notes — see **Needs more detail**
at the bottom rather than assuming those are complete.

## STAR Stories

### Modernizing the partner integration API

**Situation:** The team I worked with for 99% of my time at Bethesda had a very ambiguous way of
handling work. Unless it was a bug, tickets often came with slim guidance — something like "we
have an ask from our third party to update the process flow for our application system, needed
by X date." It was up to the dev to evaluate the system and work with the lead to determine the
best way forward. In this case, our application system was using an API that had originally been
built for gRPC calls (and lived in a separate repo), but had since been ported over to REST
inside our main repo — a bit of a Frankenstein setup. Separately, that same website API didn't
even have a `/v1` — a convention gap worth noting on its own.

**Task:** A third party needed the partner schema updated to house a seller ID, by a fixed
deadline. I needed to decide how to deliver that with the ambiguity in scope I'd been given.

**Action:** After evaluating the system, I determined we had enough runway before the deadline to
do more than the minimum ask — I updated the endpoints to `/v2`, which let us both conform the
API to our current repo's conventions and deliver the schema change the third party needed, in
one pass instead of two.

**Result:** Shipped the seller ID schema update on time, and left the API in a meaningfully better
state (versioned, consistent with repo conventions) instead of just patching the old
frankensteined implementation. The broader skill I took from this: be skeptical about everything
when given an ask — assume nothing already works the way it should, and evaluate from there.

### Building trust with a difficult teammate

**Situation:** I had a coworker, who was difficult to work with.

**Task:** I needed to find a way to collaborate with him effectively rather than let friction slow
the team down.

**Action:** I invested in getting to know him — not just professionally. We did 1:1 pair reviews so
I could understand how he thought through problems, and I made a point of running things by him
to get his input and show that his input mattered. I also got to know him outside of engineering
entirely — he was into pop punk and snowboarding, and I'd ask about specifics, like how a
snowboarding trip with his girlfriend went.

**Result:** All of it made dialogue with him substantially easier. Over time he came around to
taking my side in discussions and would reference ideas I'd raised when making his own case for
things — a real shift from where the relationship started.

### Handling disagreement productively: the CAB documentation gap

**Situation:** My general approach to disagreement is rooted in open communication and
collaboration — it comes up in PR reviews, design discussions, all kinds of contexts. I've learned
there's often not a single "right" way to do something, just a "righter" one, and if someone can
prove their way is that, I have no issue deferring. If I can't be convinced and still believe my
approach is better, I'll either decide the gap isn't significant enough to fight for and let it go,
or — rarely — raise the concern with a lead/manager, with the other person's knowledge, and let
them make the call.

A concrete case of this: a former manager called me out for running our CAB (Change Advisory Board) process
late.

**Task:** Address the process gap he'd flagged rather than treat it as a one-off criticism.

**Action:** I worked with him directly to refine the CAB documentation so the process itself was
clearer and less likely to run late going forward.

**Result:** Improved, clearer CAB documentation — and a resolved disagreement that reinforced the
working relationship rather than damaging it.

### Bundles launch: closing a data-persistence gap

**Situation:** While building out a project to introduce bundles, our service was consuming
messages from NATS without JetStream — meaning once a message was pushed to our service, there
was no persistence if anything downstream failed.

**Task:** I recognized this as a data-integrity risk for the bundles launch and needed to get the
team to address it before it became a real incident.

**Action:** I lobbied for the team to implement a data persistence strategy on our end. We huddled
as a team, and a member who'd recently implemented a system-events framework in Kafka pointed out
we could leverage that same framework here. We changed the flow so that as soon as messages were
received by our service, they were pushed into the Kafka pipeline and processed from there.

**Result:** Leveraging the Kafka persistance layer prevented data loss for roughly 300 users. We
ended up finding that there was a rare race condition that caused the writes to fail. Had we not
been storing the data in a persistance layer (which contained retry logic on failure), we would've
been subject to data loss, and a large manual effort to recover the lost data. Separately, in
the same project, I optimized a SQL query that had been looping over ~100 transactions
individually into a single batched query.

## Efficiency wins

Smaller, self-contained examples of "all about efficiency" — useful for questions about
performance optimization or attention to cost/resource usage:

- **Redundant auth calls:** Service calls were authenticating as part of every request. Since our JWTs
  had a 30-minute expiry and the task itself only ran for a couple of minutes, I reused the JWT
  across the task's lifetime instead of re-authenticating every call.
- **DB connection reuse:** Replaced repeated ad hoc database connections with a connection
  pool/batched approach instead of opening multiple individual connections.
- **Kafka retry logic:** Added retry handling in the Kafka consumer path for the bundles launch (see
  the bundles story above).
- **Query batching:** Converted a loop issuing ~100 individual SQL transactions into a single
  batched query (also part of the bundles project).

## Behavioral Q&A

**If this were your first annual review, what would I be telling you right now?**
Three separate team members praised me unprompted in 1:1s with my manager — feedback centered on
being highly collaborative and a scrupulous PR reviewer.

**Give an example of a time-management skill you've learned and applied at work.**
Managing scope creep — making sure I'm delivering incremental value rather than letting a piece of
work balloon before anything ships.

I was recently tasked with a compliance-related ask to gate 
underage users from accessing specific functionality within our service. After investigation, I
recognized two most viable approaches. The first involved adding middleware directly within 
the particular service that checked the user's age upon receiving a call, and denying it if the
user was underage. The second was implementing a new claims-based service at the edge, which would
use identifying characteristics from the incoming JWT to populate the token with claims that specified
what downstream actions a user could take.

After creating a proposal, I gave a presentation to our engineering leadership team and received
approval. I ultimately decided that, while it would address the issue at hand, the approach wouldn't
be best in the situation because we would be the only service using an edge-level claims system (which
would put a ton of unnecessary traffic/load into a brand new service), and making the changes directly
in the service (as part of the alternative approach) was so lightweight, that it could be removed
easily should we end up wanting to go with the edge approach down the line.


**What aspects of your work are most often criticized? What's a weakness?**
I got feedback a while back that I can talk a lot. I've put real work into countering that —
deliberately leaving space for other people to get their ideas out, and holding silence so people
have room to think instead of filling it myself.

**How would you come in and make an impact?**
The biggest impact a new hire makes early on is through culture and personality — showing I'm a
culture fit from day one matters, because coming across as a bad peer sets a bad precedent from the
outset. I'd bring new eyes: figure out the delta between the team's current state and what I can
bring in from previous experience. I'd likely spend a few days familiarizing myself with the existing products
and infrastructure, evaluate the system with fresh eyes, and make recommendations where I see
opportunities. I'd also try to get an early read on the level of ownership expected and calibrate
from there — looking at existing conventions and making recommendations, while staying
collaborative rather than prescriptive.

**Why would you do well on a small team with lots of ownership and ambiguity?**
See the "Modernizing the partner integration API" STAR story above — that's the concrete example.
The short version: my team at Bethesda operated with very ambiguous scoping most of the time, and
the skill I built from that is to be skeptical about everything when given an ask — assume nothing
already works the way it should, and evaluate from there.

## System & process reference

Not STAR stories, but useful grounding for "walk me through a system you built" or "how do you
approach incidents" style questions.

### Problem-solving philosophy

- It all starts with helping yourself — logging, telemetry, and alerts are your best friend.
- Fortify against regressions by adding former bugs to the test suite once they're fixed.

### Incident troubleshooting approach

1. Check logs.
2. Check transaction traces.
3. Check infrastructure metrics (DB CPU/memory usage, etc.).
4. Check recent deploys and whether their timing lines up with the issue.
5. Ahead of an anticipated launch or marketing event, walk the VIP flows in advance to get familiar
   with happy paths and the critical infra involved.
6. Load test.
7. Scale the system if needed to stop the bleeding.
8. Check third-party dependency status pages.
9. Prioritize communication, both internally and externally.
10. Run a post-incident MIR/RCA: why did this happen, can guardrails be added to the test suite,
    and does process need to change to prevent a repeat?
