<script setup lang="ts">
/**
 * Terms of service. Plain language,
 * one page. Public route.
 */
</script>

<template>
  <v-container class="legal-page py-10">
    <div class="mx-auto" style="max-width: 720px">
      <router-link to="/login" class="text-decoration-none text-caption">‹ Pumasi Sign</router-link>
      <h1 class="text-h4 font-weight-bold mt-2 mb-1">Terms of Service</h1>
      <p class="text-caption text-medium-emphasis mb-6">
        In force for everyone using this service. Version 1.0, effective 2026-08-30.
      </p>

      <h2 class="text-h6 mt-6 mb-2">What this is</h2>
      <p>
        Pumasi Sign is an electronic-signature service: you upload a document, name who must
        sign, and the service collects their signatures, seals the result, and gives everyone
        the executed copy with a signature certificate. These terms govern its use by account
        holders. People who only sign a document sent to them are covered by the
        <router-link to="/privacy">privacy notice</router-link> rather than these terms.
      </p>
      <p>
        Operator: <strong>ATX APPLE LLC</strong>, a Texas limited liability company, United
        States. Governing law: the laws of the State of <strong>Texas</strong>, excluding its
        conflict-of-law rules. Disputes go to the state and federal courts sitting in Texas.
      </p>

      <h2 class="text-h6 mt-6 mb-2">The account</h2>
      <p>
        You are responsible for what happens under your account and for the accuracy of the
        address you sign in with. Sign-in codes and signing links are credentials — do not
        share them. You must not use the service to send unsolicited bulk email, to harass
        anyone, to obtain signatures by deception, or to break the law of any place that
        applies to you. We may suspend an account that does, and will say why.
      </p>

      <h2 class="text-h6 mt-6 mb-2">Electronic signatures</h2>
      <p>
        The service records who signed, when, from which address, and seals the completed
        document with cryptographic hashes so later tampering is detectable. Electronic
        signatures are legally effective for many agreement types in many jurisdictions
        (for example under the U.S. ESIGN Act and the EU's eIDAS regulation), but
        <strong>whether a particular document may be signed electronically in your
        jurisdiction is your responsibility</strong>, not something this service can decide
        for you. Some documents (wills, certain notarised deeds) commonly cannot.
      </p>

      <h2 class="text-h6 mt-6 mb-2">Your documents, and your signers' data</h2>
      <p>
        Documents you upload remain yours. For the personal data of the people you ask to
        sign, you are the controller and we are your processor: we hold it on your
        instructions. You are responsible for having a lawful basis to request the
        signatures you request, and for answering your signers' requests about their data,
        with our help.
      </p>

      <h2 class="text-h6 mt-6 mb-2">Availability, and what we do not promise</h2>
      <p>
        The service is provided <strong>as is</strong>, without warranties of any kind, and
        may change or be interrupted. To the maximum extent the law allows, our total
        liability for any claim arising out of the service is limited to the amount you paid
        us for it in the twelve months before the claim — which, while the service is free,
        is zero. Nothing here limits liability that cannot lawfully be limited.
      </p>

      <h2 class="text-h6 mt-6 mb-2">Changes</h2>
      <p>
        We may amend these terms; material changes will be dated here and the version number
        moved. Continuing to use the service after a change takes effect is acceptance of it.
      </p>

      <p class="text-caption text-medium-emphasis mt-8">
        Questions: admin@pumasi.ai — that address reaches the people who run the service.
      </p>
    </div>
  </v-container>
</template>

<style scoped>
.legal-page p { margin-bottom: 12px; line-height: 1.65; }
</style>
