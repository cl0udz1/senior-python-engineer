# Lookup compatibility
FastLookup is passed wherever Lookup is accepted. Repair it while preserving Lookup.get's contract:
all hashable keys are accepted, missing keys return the supplied default unchanged (None by default),
and present values are returned unchanged including None. Constructor takes a mapping. Keep the
public class names and signatures. You may simplify internals. Avoid unrelated dependencies. Write
the contract rationale and actual checks in response.md.
