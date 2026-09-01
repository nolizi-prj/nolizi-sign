# INTENT — spec/0008 · The message you wrote to your signers stays written

**Written 2026-09-01 (UTC) by the coder seat of job `0074`, before the spec.**
Charter §2.1: one page, plain language, no clause numbers, no test IDs.
Its 24-hour window is `pumasi/DECISIONS.md` Q-037.

## What we understood you to want

When somebody sends a document for signature, the app gives them a box for a
message to the people signing it — the covering note on the agreement.
*"Please sign by Friday."* *"This replaces the draft I sent Tuesday."* It is
shown to every recipient when they open the signing link, and it is often the
only explanation they get for what they are being asked to sign.

Elsewhere on the same screen there is a pencil labelled for expiration and
reminders. Opening it, changing nothing, and pressing save **deletes the
message.** The dialog then says *"Envelope settings updated."* and closes.
Nothing warns the sender, nothing asks, and nothing on the screen afterwards
says the message is gone — it simply is not there any more, for them and for
everybody who has not opened the link yet.

You want the covering note to survive a dialog that was never about it.

## Who it is for

The sender, who wrote the note and has no reason to think a settings dialog
would touch it. And every recipient after them, who opens a signing link and
finds a document with no explanation attached — with no way to know one was
ever written.

It matters most for exactly the people the product currently pushes hardest
into that dialog. An envelope whose deadline has passed shows the sender
*"Its expiration date has already passed — set a new one"* and draws the
pencil that opens it. So the app invites the sender into the one action that
destroys their own words.

## What "working" will mean, in your terms

- **Changing the expiration date or the reminder settings leaves the message
  alone.** That is the whole change.
- **A sender who wants the message gone can still remove it**, from the dialog
  that is actually about the title and the message, exactly as today.
- **The envelope's history says what changed.** If a correction changed the
  title or the message, the history line names them, the same way it already
  names the expiration date and the reminders.
- **Nothing else about the route changes.** The same people may correct the
  same envelopes at the same times, and a correction that is refused today is
  refused after this in the same words.

In one sentence: **a dialog that is not about your message does not delete
your message.**

## What we are deliberately not building

- **We are not adding the message box to the settings dialog.** Two dialogs
  edit two things and that is fine; the defect is not that one of them is
  missing a field, it is that it silently clears one it never showed.
- **No recovery of messages already deleted.** They were overwritten with
  nothing and there is nowhere to read them back from. This stops the next one
  and cannot undo the last one, and we would rather say so than imply
  otherwise.
- **No warning dialog, no confirmation step, no new screen.** After this
  change there is nothing to warn about.

## Does this take anything away from anyone?

**On the merits, no — it stops something being taken away.** Nobody has ever
asked the settings dialog to delete their message, and nobody could have been
relying on it doing so.

There is one honest debit, and it is about *records* rather than about people.
The envelope's history will start naming a title or message change where
before it named nothing at all. That is more truthful, not less, but it is a
change to what a past-facing document says about a correction, so it is stated
here rather than discovered in a diff.

**And one thing this change cannot do, said plainly.** Fixing this in the
source does not fix it for anybody using the product. `sign.pumasi.ai` runs a
build made before any of this, and it will keep deleting senders' messages
until somebody deploys. That is a separate act by a separate hand and this
page does not pretend to have done it.

## What we are unsure about, with the answer we will assume

1. **Whether leaving the message box empty in the *other* dialog should still
   clear the message.** *Assumed: yes.* A sender who empties the box and saves
   meant to empty it. The difference the service must learn is between a field
   nobody mentioned and a field somebody deliberately emptied.
2. **Whether the envelope's history should record a message change.**
   *Assumed: yes — and a title change with it.* The history already names
   which settings a correction touched and names nothing when the correction
   was to the words of the agreement, which is the wrong way round. See the
   spec for the reasoning; it is a decision this job was asked to make and
   made, not one it left open.
