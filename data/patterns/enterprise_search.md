# Pattern: Enterprise Search

One search experience across many existing systems (file shares, ticketing, CRM, intranet,
databases) so people stop hunting system-by-system. Often raised when information is
fragmented across tools and nobody knows where the "source of truth" is.

## Typical Business Goals
- One entry point to find information regardless of which system holds it
- Reduce time wasted searching multiple tools; reduce duplicate work
- Improve consistency by pointing everyone at the same results

## Common Stakeholders
- Owners of each source system (and their access/security teams)
- IT/security, data protection officer, end users across departments
- An executive sponsor (cross-departmental scope usually needs one)

## Common Risks
- Permissions/access: surfacing results a user is not allowed to see
- Source systems with poor or inconsistent metadata → weak relevance
- Scope sprawl: "index everything" instead of the few systems that matter
- Ongoing connector maintenance as source systems change

## Common Assumptions (to validate)
- That the priority systems are known and their owners will grant access
- That existing metadata is good enough for useful ranking
- That a single relevance model fits very different content types

## Common Pitfalls (experience — validate)
- **Access control across systems** is frequently the hardest part — far more than search
  quality — and is often underestimated early.
- "Index everything" commonly dilutes relevance; starting with 2–3 high-value sources
  usually works better.
- Often the felt problem is **fragmentation/ownership** of information, not search itself.

## Success Factors
- Start with the few highest-value source systems, expand later
- Resolve the access/permission model before scaling scope
- Define what "good result" means with real users before tuning relevance
