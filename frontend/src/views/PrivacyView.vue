<script setup lang="ts">
/**
 * Privacy notice. Who holds what
 * in which role, the complete list of what is stored, and every sub-processor
 * a document can transit. Public route.
 */
</script>

<template>
  <v-container class="legal-page py-10">
    <div class="mx-auto" style="max-width: 720px">
      <router-link to="/login" class="text-decoration-none text-caption">‹ Nolizi Sign</router-link>
      <h1 class="text-h4 font-weight-bold mt-2 mb-1">Privacy</h1>
      <p class="text-caption text-medium-emphasis mb-6">
        In force for everyone using this service. Version 1.0, effective 2026-08-30.
      </p>

      <h2 class="text-h6 mt-6 mb-2">Who holds what, and in which role</h2>
      <p>
        Two relationships run through an e-signature service, and they carry different
        duties. For <strong>account holders</strong> (the people who send documents) we are
        the controller of the account itself: the address you sign in with, your name, your
        settings. For <strong>signers</strong> — everyone asked to sign a document — we are a
        processor acting for the account holder who sent it. They chose to collect your
        signature; we hold it on their behalf. If you signed something and want to talk
        about your data, the sender is the controller, but you may also contact us at
        admin@nolizi.com and we will help.
      </p>
      <p>
        Operator: <strong>ATX APPLE LLC</strong>, a Texas limited liability company, United
        States.
      </p>

      <h2 class="text-h6 mt-6 mb-2">What is collected</h2>
      <p>This is the complete list of what the service stores about a person.</p>
      <p>
        <strong>If you hold an account:</strong> your email address and display name; your
        workspace branding; the recipients you add (their name and email); the envelopes you
        create and their documents.
      </p>
      <p>
        <strong>If you sign a document:</strong> your name and email address (entered by the
        sender); the signature image you draw; the values you type into the document's
        fields; and — because a signature certificate is the point of the product — the
        <strong>time you signed, the IP address, and the browser identification</strong> of
        the device you signed from. These appear on the tamper-evident certificate attached
        to the executed document, which every party to the document receives.
      </p>
      <p>
        <strong>Verification codes</strong> sent to your email are stored only until used or
        expired (15 minutes). Sign-in sessions expire after 30 days, signer sessions after
        24 hours.
      </p>

      <h2 class="text-h6 mt-6 mb-2">Where it lives, and who else touches it</h2>
      <p>
        The service runs on <strong>Cloudflare</strong> (Workers and R2 storage, encrypted at
        rest); all traffic uses TLS. Email — verification codes, signing invitations,
        completion notices — is delivered through <strong>Google</strong> (Gmail API, as
        admin@nolizi.com). If you upload a Word, PowerPoint, or Excel file, it is converted
        to PDF through <strong>Microsoft's</strong> conversion service: the file transits a
        OneDrive owned by the operator and is deleted immediately after conversion. Those
        three are the complete list of sub-processors; there are no analytics or advertising
        trackers.
      </p>

      <h2 class="text-h6 mt-6 mb-2">Retention and deletion</h2>
      <p>
        Envelopes and their documents are kept until the account holder deletes them —
        signed agreements are records both parties may need for years, so we do not expire
        them on our own. Draft envelopes can be deleted by their sender at any time, which
        also deletes the stored document. To remove an account and everything in it, email
        admin@nolizi.com from the account's address.
      </p>

      <h2 class="text-h6 mt-6 mb-2">What we never do</h2>
      <p>
        We do not sell personal data, read your documents beyond what the software must do
        to render and seal them, or use their contents for anything else — including
        training models.
      </p>

      <p class="text-caption text-medium-emphasis mt-8">
        Questions about anything on this page: admin@nolizi.com.
      </p>
    </div>
  </v-container>
</template>

<style scoped>
.legal-page p { margin-bottom: 12px; line-height: 1.65; }
</style>
