# INTENT — spec/0010 · The thing this product is *for* had never been run

**Written 2026-09-01 (UTC), before the spec — by hand, outside the queue, and
found uncommitted in the tree; adopted by coder job `0099` after verification
(`SPEC.md` §S0). The reasoning below is the found text, unedited.**
Charter §2.1: one page, plain language, no clause numbers, no test IDs.

## What we understood you to want

Pumasi Sign exists to turn a document and some signatures into **one executed
PDF with a certificate page stapled to the back**. That artefact is the
product. Everything else — the invitations, the codes, the dashboard — is
plumbing that leads to it.

Nothing in this repository had ever produced one and looked at it.

There are two tests that mention stamping. Both build a PDF in memory, hand it
straight to the stamping function, and then check three things: the result is
longer than what went in, it has two pages, and two hashes are different. They
never go near the service. They never go near a signer. And — this is the part
that matters — **they never read a single word of what was stamped.** A change
that put the wrong person's name on every signature line, or dropped the
document's own text, or stamped page 3 onto page 1, would pass all three
checks.

You want the real path run, from a signer pressing *Finish* to the executed
document coming back down the wire, and you want somebody to actually **read
the output**.

## Who it is for

The next person to change how documents get stamped — which, given this is the
one code path every customer's legal record passes through, is the change
nobody should make blind.

And the person who reads a test count off this product and assumes it means the
signing works. Until now that count said the stamping function returns
something bigger than it was given.

## What "working" will mean, in your terms

We drive the whole thing: a sender signs in, an envelope with a real PDF and
real fields goes out, a signer confirms their emailed code, draws a signature,
fills the boxes and finishes. The service's own database, its own routing, its
own file download. Then we open the PDF that comes back and **read the text off
every page**, and check it says what it should:

- the sender's document is still there, word for word, and the certificate is
  exactly one page added to the back — not a replacement;
- what the signer typed is on the page they typed it on;
- the certificate names this envelope, this document's title, and a fingerprint
  of the original file that we compute ourselves and compare;
- each signer gets their own block with their own email, their own timestamp
  and the IP address their own request arrived from;
- the file the service hands back is byte-for-byte the file the certificate
  claims to be about.

## Three things we found by looking, which we are writing down and not fixing

**One.** If a signer's only box is an *initials* box, the signature they drew
is thrown away and their **full typed name** is printed there instead. Draw
your initials, get "Jonathan Reginald Whitmore" in the box.

**Two.** If a signer has both a signature box and an initials box, the *same
full signature image* is stamped into both. The initials box gets a signature.

**Three, and it is the one worth reading twice.** If the document itself cannot
be retrieved when the last signature lands — the file store is unreachable, or
the record points at a file that is not there — **the envelope is marked
completed anyway.** Everyone gets the "fully signed" email. The dashboard says
done. And there is no executed document at all: the download answers *not
available*. Nothing anywhere says the certificate was never made. The only
trace is that one row in the audit log is missing its two fingerprints, and
nothing reads that row.

We are recording all three. We are not changing any of them, for the reason
this project keeps giving and keeps being right about: the job that finds a
thing should not also be the job that decides what to do about it. A wrong fix
to the third one, made on the same afternoon it was found, is how you turn a
missing PDF into a stuck envelope nobody can finish.

## Does this take anything away from anyone?

No. Not one line of the service changes. No page, no button, no email, no
stored record moves. A user could not tell this job happened.

The cost is machine time: the suite now builds and stamps real PDFs, so it is
slower than it was. Seconds, not minutes.

## What we are unsure about, with the answer we will assume

1. **Whether reading text out of a PDF makes the tests brittle.** *Assumed:
   worth it anyway.* If the stamping library changes how it writes text, these
   tests go red and somebody has to look. That is the correct outcome — it is
   the only mechanism this product has that would notice the certificate
   silently going blank. We keep the reader small, in one file, and say in it
   what it does not claim.
2. **Whether standing in for the document store counts as not testing it.**
   *Assumed: the opposite.* The real store is Cloudflare's R2 and cannot be
   reached from a test machine. We supply a bucket that behaves like one, which
   is the first time any test in this project has executed the storage wrapper
   at all. We say plainly that it is a stand-in and what that means.
3. **Whether writing down the three findings above amounts to endorsing them.**
   *Assumed: no, provided the test says so out loud.* This project already has
   cases that record a rule their authors have not agreed to and mark
   themselves as such. We copy that exactly.
