<script setup lang="ts">
/**
 * Nolizi Sign — Public Standalone Marketing Landing Page
 *
 * Designed to communicate value, transparent limitations, and the stage
 * `roadmap/STAGE.md` records, to unauthenticated visitors with direct
 * zero-friction CTAs.
 *
 * This file writes no stage word of its own and no competitor figure of its
 * own. The stage comes from `../stage` (one place, checked against
 * `roadmap/STAGE.md`); the competitor prices and limits below are the ones
 * `roadmap/MARKET.md` read off each vendor's own pricing page on the date
 * cited under the table. See `spec/0001/SPEC.md`.
 */
import { computed } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../store/auth";
import { STAGE_BADGE, STAGE_LABEL } from "../stage";

const router = useRouter();
const auth = useAuthStore();

const isAuthenticated = computed(() => !!auth.me);

function goToDashboard() {
  router.push({ name: "dashboard" });
}

function goToSignUp() {
  router.push({ name: "login", query: { tab: "signup" } });
}

function goToSignIn() {
  router.push({ name: "login" });
}
</script>

<template>
  <div class="landing-page">
    <!-- Top Announcement Banner: Stage & Transparency -->
    <div class="stage-banner bg-slate-900 text-white py-2 px-4 text-center text-caption d-flex align-center justify-center gap-2">
      <v-chip size="x-small" color="primary" variant="flat" class="font-weight-bold uppercase" data-testid="stage-badge">{{ STAGE_BADGE }}</v-chip>
      <span>Nolizi Sign is in active {{ STAGE_LABEL }} — Unmetered PDF stamping &amp; SHA-256 audit certificates under Apache-2.0.</span>
    </div>

    <!-- Navigation Header -->
    <v-container class="py-4 d-flex align-center justify-space-between">
      <div class="d-flex align-center gap-2 cursor-pointer" @click="router.push('/')">
        <img src="/logo-mark.png" alt="Nolizi Sign" style="height: 36px; width: 36px;" />
        <span class="text-h6 font-weight-bold text-slate-900">Nolizi Sign</span>
      </div>

      <div class="d-flex align-center gap-3">
        <v-btn
          variant="text"
          href="https://github.com/nolizi-prj/nolizi-sign"
          target="_blank"
          prepend-icon="mdi-github"
          class="text-none"
        >
          GitHub
        </v-btn>
        <template v-if="isAuthenticated">
          <v-btn color="primary" variant="flat" class="text-none" @click="goToDashboard">
            Go to Dashboard
          </v-btn>
        </template>
        <template v-else>
          <v-btn variant="text" class="text-none" @click="goToSignIn">Sign In</v-btn>
          <v-btn color="primary" variant="flat" class="text-none" @click="goToSignUp">
            Create Free Account
          </v-btn>
        </template>
      </div>
    </v-container>

    <!-- Hero Section -->
    <v-container class="pt-12 pb-16 text-center">
      <v-chip color="primary" variant="tonal" class="mb-4 font-weight-medium">
        Zero Per-Seat Fees • Unmetered Envelopes • 100% Apache-2.0
      </v-chip>
      <h1 class="hero-title text-h2 font-weight-black text-slate-900 mb-6">
        Legally-Binding E-Signatures.<br />
        <span class="text-primary">Without the DocuSign Tax.</span>
      </h1>
      <p class="hero-subtitle text-h6 text-medium-emphasis mx-auto mb-8" style="max-width: 720px; line-height: 1.6;">
        Deterministic coordinate PDF stamping, cryptographic SHA-256 tamper-evident certificates, and frictionless zero-login recipient signing. Free forever to self-host.
      </p>

      <div class="d-flex justify-center gap-4 mb-12">
        <v-btn
          color="primary"
          size="x-large"
          class="text-none px-8 font-weight-bold"
          prepend-icon="mdi-arrow-right-circle"
          @click="isAuthenticated ? goToDashboard() : goToSignUp()"
        >
          {{ isAuthenticated ? "Open Your Dashboard" : "Start Signing Free" }}
        </v-btn>
        <v-btn
          variant="outlined"
          size="x-large"
          class="text-none px-6"
          prepend-icon="mdi-file-document-outline"
          href="#features"
        >
          Explore Capabilities
        </v-btn>
      </div>

      <!-- Hero Dashboard Preview Screenshot -->
      <v-card max-width="1000" class="mx-auto border rounded-xl shadow-lg overflow-hidden">
        <v-img src="/screenshots/sign-dashboard.png" alt="Nolizi Sign Interface Preview" cover />
      </v-card>
    </v-container>

    <!-- Feature Grid Section -->
    <section id="features" class="bg-slate-50 py-16 border-t border-b">
      <v-container>
        <div class="text-center mb-12">
          <h2 class="text-h4 font-weight-bold text-slate-900 mb-3">Engineered for Complete Compliance &amp; Speed</h2>
          <p class="text-body-1 text-medium-emphasis">Everything businesses require from DocuSign and SignWell, running at the edge.</p>
        </div>

        <v-row>
          <v-col cols="12" md="4">
            <v-card class="pa-6 h-100 border rounded-lg" elevation="0">
              <v-icon icon="mdi-shield-check-outline" color="primary" size="36" class="mb-4" />
              <h3 class="text-h6 font-weight-bold mb-2">Cryptographic Audit Certificates</h3>
              <p class="text-body-2 text-medium-emphasis mb-0">
                Every completed document automatically seals a SHA-256 certificate logging signer IP, user agent, verification timestamps, and document hashes under the ESIGN Act and eIDAS.
              </p>
            </v-card>
          </v-col>

          <v-col cols="12" md="4">
            <v-card class="pa-6 h-100 border rounded-lg" elevation="0">
              <v-icon icon="mdi-vector-selection" color="primary" size="36" class="mb-4" />
              <h3 class="text-h6 font-weight-bold mb-2">Deterministic Coordinate Stamping</h3>
              <p class="text-body-2 text-medium-emphasis mb-0">
                Normalized coordinates place signatures, initials, dates, names, text fields, and checkmarks directly onto PDF vectors with pixel-perfect precision.
              </p>
            </v-card>
          </v-col>

          <v-col cols="12" md="4">
            <v-card class="pa-6 h-100 border rounded-lg" elevation="0">
              <v-icon icon="mdi-email-fast-outline" color="primary" size="36" class="mb-4" />
              <h3 class="text-h6 font-weight-bold mb-2">Zero-Login Recipient Flow</h3>
              <p class="text-body-2 text-medium-emphasis mb-0">
                Counterparties execute agreements in seconds via secure tokenized links with 6-digit email verification codes. No account creation or software download required.
              </p>
            </v-card>
          </v-col>
        </v-row>
      </v-container>
    </section>

    <!-- Comparison Table vs Incumbents -->
    <v-container class="py-16">
      <div class="text-center mb-12">
        <h2 class="text-h4 font-weight-bold text-slate-900 mb-3">Honest Comparison vs. Incumbents</h2>
        <p class="text-body-1 text-medium-emphasis">Why developers and businesses choose Nolizi Sign.</p>
      </div>

      <v-table class="border rounded-lg shadow-sm">
        <thead>
          <tr class="bg-slate-50">
            <th class="font-weight-bold text-left py-4">Capability</th>
            <th class="font-weight-bold text-primary text-center py-4">Nolizi Sign</th>
            <th class="font-weight-bold text-medium-emphasis text-center py-4">DocuSign</th>
            <th class="font-weight-bold text-medium-emphasis text-center py-4">SignWell</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td class="font-weight-medium">Per-Seat Subscription</td>
            <td class="text-center font-weight-bold text-primary">$0 (Unmetered)</td>
            <td class="text-center text-medium-emphasis">
              $11 / mo (Personal)<br />$30 – $45 / user / mo (Standard, Business Pro)
            </td>
            <td class="text-center text-medium-emphasis">
              $10 – $12 / sender / mo (Light)<br />$30 – $36 / mo for 3 senders (Business)
            </td>
          </tr>
          <tr>
            <td class="font-weight-medium">Envelope / Document Limits</td>
            <td class="text-center font-weight-bold text-primary">Unlimited</td>
            <td class="text-center text-medium-emphasis">
              5 / mo (Personal)<br />100 / user / yr (Standard, Business Pro)
            </td>
            <td class="text-center text-medium-emphasis">
              3 / mo (Free)<br />Unlimited documents on paid tiers
            </td>
          </tr>
          <tr>
            <td class="font-weight-medium">SHA-256 Audit Certificates</td>
            <td class="text-center font-weight-bold text-primary">Included on all envelopes</td>
            <td class="text-center text-medium-emphasis">Included</td>
            <td class="text-center text-medium-emphasis">Included</td>
          </tr>
          <tr>
            <td class="font-weight-medium">Multi-Tenant Brand Customization</td>
            <td class="text-center font-weight-bold text-primary">Included (Logo, Title, Theme)</td>
            <td class="text-center text-medium-emphasis">Enterprise tier only</td>
            <td class="text-center text-medium-emphasis">Business tier only</td>
          </tr>
          <tr>
            <td class="font-weight-medium">License &amp; Source Code</td>
            <td class="text-center font-weight-bold text-primary">Apache-2.0 (Open Source)</td>
            <td class="text-center text-medium-emphasis">Proprietary Closed Source</td>
            <td class="text-center text-medium-emphasis">Proprietary Closed Source</td>
          </tr>
        </tbody>
      </v-table>

      <!--
        S2e: scoped deliberately to pricing and limits. Two rows above -- the
        audit-certificate row and the branding row -- are feature claims that
        roadmap/MARKET.md does not cover, and a blanket "sources" line would
        read as sourcing them. See spec/0001/SPEC.md S4.
      -->
      <p class="text-caption text-medium-emphasis mt-4">
        Competitor <strong>pricing and limits</strong> above are as published on each vendor's own pricing page,
        read <strong>2026-08-31</strong> —
        <a href="https://ecom.docusign.com/plans-and-pricing/esignature" target="_blank" rel="noopener">DocuSign</a>
        and
        <a href="https://www.signwell.com/pricing/" target="_blank" rel="noopener">SignWell</a>.
        The figures as read, with their sources, are recorded in
        <a href="https://github.com/nolizi-prj/nolizi-sign/blob/main/roadmap/MARKET.md" target="_blank" rel="noopener">roadmap/MARKET.md</a>.
        Prices move; the date is part of the claim.
      </p>

      <!-- Transparent Stage Limitation Disclosure -->
      <v-alert type="info" variant="tonal" class="mt-8">
        <strong>Transparency &amp; Legal Scope:</strong> Cryptographic audit certificates verify document integrity, signer identity, and UTC timestamps under the U.S. ESIGN Act and European eIDAS (Advanced Electronic Signature). Qualified Electronic Signatures (QES) requiring government hardware smartcards/tokens are not currently supported.
      </v-alert>
    </v-container>

    <!-- Footer CTA -->
    <footer class="bg-slate-900 text-white py-12 text-center">
      <v-container>
        <h3 class="text-h4 font-weight-bold mb-4">Start Sending &amp; Signing Documents Today</h3>
        <p class="text-body-1 text-slate-300 mb-6">Deploy to your own Cloudflare account or create a free workspace in seconds.</p>
        <v-btn color="primary" size="large" class="text-none font-weight-bold px-8" @click="goToSignUp">
          Create Free Account
        </v-btn>
        <div class="mt-8 text-caption text-slate-400">
          Part of <a href="https://nolizi.com" class="text-slate-300">Nolizi</a> • A connected collection of practical software.
        </div>
      </v-container>
    </footer>
  </div>
</template>

<style scoped>
.hero-title {
  letter-spacing: -0.03em;
}
.gap-2 { gap: 8px; }
.gap-3 { gap: 12px; }
.gap-4 { gap: 16px; }
.bg-slate-900 { background-color: #0f172a; }
.bg-slate-50 { background-color: #f8fafc; }
.text-slate-900 { color: #0f172a; }
.text-slate-300 { color: #cbd5e1; }
.text-slate-400 { color: #94a3b8; }
.cursor-pointer { cursor: pointer; }
</style>
