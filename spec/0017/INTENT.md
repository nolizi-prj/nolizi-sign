# Persistent abuse limits

Email codes and document conversion are externally reachable, expensive, and
security-sensitive. Per-process counters are ineffective on an edge platform;
limits therefore live in Durable Object SQLite and survive Worker isolates.
