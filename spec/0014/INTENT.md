# Multi-document envelopes

An envelope must preserve the documents the sender selected instead of losing
their identities when it creates the signing rendition. Senders can select
several files together or add them in later picker operations, remove them,
and change their order before sending. The chosen order is the signing order.

The Cloudflare Worker remains compatible with old one-PDF clients while storing
each new envelope document independently with its filename and page range.
