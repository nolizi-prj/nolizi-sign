# INTENT — spec/0009 · What the sign-in-with-Google button actually does, written down

**Written 2026-09-01 (UTC) by the coder seat of job `0080`, before the spec.**
Charter §2.1: one page, plain language, no clause numbers, no test IDs.

## What we understood you to want

Pumasi Sign has three ways in. Two of them are written down. The third — the
**Sign in with Google** and **Sign in with Microsoft** buttons — is not, and
until this job nothing in this repository had ever run it. Not one line. The
code that decides whether a person coming back from Google gets handed a
session cookie had no test on it at all.

You want it written down. Not changed — **written down**, so that the next
person to touch it can see what it does before they find out the hard way.

## Who it is for

The next person to edit that code, which is the person most likely to break
it. And the reviewer after them, who today has nothing to check a change
against except reading it twice and hoping.

It is also for anyone who reads a green test count off this product and takes
it as a statement about who can get in. Right now that count says nothing
about the sign-in buttons, because nothing was measuring them.

## What "working" will mean, in your terms

We write tests that walk the whole round trip the way a real person does:
press the button, get sent to Google, come back with a code, have the service
swap that code with Google for an identity, and either be let in or not. The
service's own database, its own routing, its own cookie. Only Google itself is
stood in for.

Then we write down what happens in each case, including the ones nobody plans
for: Google says no; Google's answer is garbled; the identity comes back
without an email address; the identity comes back saying the email is *not*
confirmed.

**And one case that is the reason this was ranked first.** If the identity
comes back with no statement either way about whether the email was
confirmed — the claim simply absent — **the person is let in.** We measured
it, and it is now written down.

## The thing we are deliberately not doing, and why

**We are not changing that behaviour in this job.** We found it, we recorded
it, we are handing it to whoever ranks the work.

That restraint is deliberate and it is worth a paragraph rather than a
footnote. Nobody has shown this can be exploited. The identity does not come
from the person signing in — it comes straight from Google's own servers over
an encrypted connection, which is real protection and not an excuse. Tightening
the check would be a change to who can get into the product, made by the same
job that wrote the test that justifies it, on a Friday, with no one having
asked for it. That is how a security fix becomes an outage.

So: measure first, decide second, and let the decision be somebody's job rather
than a side effect of this one.

## One other thing, which is honesty rather than engineering

There is a file in this project called `e2e-workflow.test.ts`. "E2E" means
end-to-end — the kind of test that drives the whole product the way a user
does. **It is not one.** It builds a PDF in memory and stamps it. It calls no
page, starts no server, and touches no database. It has had that name since the
file was created.

It matters because this project publishes its test numbers. A count that
includes something called *e2e-workflow* reads as a promise that somebody
drove the product end to end, and nobody did. We are renaming it to say what it
does. Nothing about the file's behaviour changes — same test, same assertions,
truer label.

## Does this take anything away from anyone?

No. Nothing a user can see changes, in either half. No page, no button, no
email, no stored record moves. This job adds tests and corrects a filename.

There is one small debit and it is to a record rather than to a person: a test
file changed its name, so anyone searching old notes for the old name will not
find the file. The old name is written into the new file's first paragraph, so
the trail still leads somewhere.

## What we are unsure about, with the answer we will assume

1. **Whether recording the absent-confirmation behaviour in a test amounts to
   endorsing it.** *Assumed: no, provided the test says so out loud.* This
   project already has a case that records a rule its own authors have not
   agreed to, and marks itself as such. We are copying that exactly.
2. **Whether the rename may touch an existing frozen test that names the old
   file.** *Assumed: yes, in the open.* One frozen test guards against files
   being quietly deleted, and it does that by listing two filenames. A rename
   is not a deletion, but it trips the list. We amend it in the open, we say
   what we changed, and we get it reviewed separately from the code.

   We also add one small thing to that guard while we are there, and it is
   worth saying exactly how small, because a first draft of this page claimed
   more and a reviewer caught it: the guard will now also refuse to let that
   folder drop below two test files, **whatever they are called**. That is
   all. It does not notice one file among seven going missing. What it stops
   is the version of this job that "fixes" the guard by deleting the list of
   names along with the files the list named.
