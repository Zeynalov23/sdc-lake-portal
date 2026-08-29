# 006 — Ownership invariants enforced by conditional writes

**Status:** Accepted · 2026-08

## Context

A space has exactly one owner and at most one deputy. Producers and consumers
are unbounded.

If roles are stored only as membership rows, "exactly one owner" is a rule
that application code has to check. Two concurrent requests can both read
"there is no deputy" and both write one. The window is small and the failure
is silent.

## Decision

`ownerOid` and `deputyOid` are attributes on the space metadata item, and the
membership row is written alongside them in a single `TransactWriteItems`.

* Creating a space: `attribute_not_exists(PK)` on the metadata item, so a
  duplicate space id fails atomically rather than in a check-then-write race.
* Assigning a deputy: `attribute_not_exists(deputyOid)`, so the second
  concurrent request fails at the database.
* Clearing a deputy: conditional on the deputy still being the one the request
  named, so a retried request cannot remove their replacement.

## Consequences

An attribute holds exactly one value, so "one owner" is a property of the
shape of the data rather than of a code path that has to be reached. Two
requests cannot both succeed no matter how they interleave.

The cost is deliberate duplication: the same fact lives on the metadata item
and on the membership row. The row is what keeps permission lookups and member
listing uniform — resolving a caller's access stays one `get_item`. The
transaction is what keeps the two copies from disagreeing.

Transactions are more expensive than single writes and can be cancelled under
contention. At this write volume that is irrelevant.

## Alternatives considered

**Roles only on membership rows** — simpler and fits member listing naturally,
but makes uniqueness a check rather than a guarantee.

**Owner and deputy only on the metadata item** — no duplication, but then
permission resolution needs two reads and member listing has to merge two
shapes.
