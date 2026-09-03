<script setup lang="ts">
/**
 * External signer entry: /sign/t/{accessUid}. Flow: landing (envelope title +
 * masked email) -> emailed 6-digit code -> the shared SignView (external
 * mode), authorized by the scoped sign_signer cookie the verify call set.
 * All requests skipAuthRedirect: there is no login to bounce to.
 */
import { onMounted, ref } from "vue";
import axios from "axios";
import http, { extractError } from "../utils/http";
import SignView from "./SignView.vue";
import type { SignTokenViewOut } from "../types";

const props = defineProps<{ accessUid: string }>();

type Phase = "loading" | "error" | "landing" | "retrieve" | "code" | "signing" | "closed";

const phase = ref<Phase>("loading");
const view = ref<SignTokenViewOut | null>(null);
const errorMessage = ref<string | null>(null);
const codeError = ref<string | null>(null);
const code = ref("");
const sending = ref(false);
const verifying = ref(false);
const submitterId = ref<number | null>(null);

// Keyed on the union rather than on `string` so that vue-tsc is the test: a
// status the worker learns to send without a message here becomes a type
// error instead of a blank card. spec/0007 §S3e.
const CLOSED_MESSAGES: Record<SignTokenViewOut["status"], string> = {
  open: "This envelope is waiting for your signature.",
  already_signed: "You've already signed this document.",
  completed: "Everyone has signed — this envelope is complete.",
  cancelled: "This envelope was voided by the sender.",
  declined: "This envelope was declined and is no longer active.",
  expired: "This envelope reached its expiration date and can no longer be signed.",
};

// Signed/completed envelopes still allow the code round-trip so a signer can
// come back later for the executed document; voided/declined don't.
const RETRIEVABLE = ["already_signed", "completed"];

async function load(): Promise<void> {
  phase.value = "loading";
  try {
    const { data } = await http.get<SignTokenViewOut>(`/sign/token/${props.accessUid}`, { skipAuthRedirect: true });
    view.value = data;
    if (data.status === "open") phase.value = "landing";
    else if (RETRIEVABLE.includes(data.status)) phase.value = "retrieve";
    else phase.value = "closed";
  } catch (err) {
    errorMessage.value =
      axios.isAxiosError(err) && err.response?.status === 404
        ? "This signing link isn't valid. Check that you opened the full link from your email."
        : extractError(err);
    phase.value = "error";
  }
}

onMounted(load);

async function requestCode(): Promise<void> {
  sending.value = true;
  codeError.value = null;
  try {
    await http.post(`/sign/token/${props.accessUid}/request-code`, null, { skipAuthRedirect: true });
    phase.value = "code";
  } catch (err) {
    // Stay on the current card: advancing to the code-entry form after a
    // failed send would invite typing a code that will never arrive.
    codeError.value = extractError(err);
  } finally {
    sending.value = false;
  }
}

async function verify(): Promise<void> {
  if (!code.value.trim()) return;
  verifying.value = true;
  codeError.value = null;
  try {
    const { data } = await http.post<{ submitter_id: number }>(
      `/sign/token/${props.accessUid}/verify`,
      { code: code.value.trim() },
      { skipAuthRedirect: true },
    );
    submitterId.value = data.submitter_id;
    phase.value = "signing";
  } catch (err) {
    codeError.value = extractError(err);
    code.value = "";
  } finally {
    verifying.value = false;
  }
}
</script>

<template>
  <SignView v-if="phase === 'signing' && submitterId != null" :submitter-id="String(submitterId)" external />

  <v-container v-else class="external-sign">
    <v-progress-linear v-if="phase === 'loading'" indeterminate class="mb-4" />

    <v-alert v-else-if="phase === 'error'" type="error">{{ errorMessage }}</v-alert>

    <v-card v-else-if="phase === 'closed' && view" class="state-card" variant="flat" border>
      <v-card-text class="text-center py-8">
        <v-icon icon="mdi-file-lock-outline" size="48" class="mb-3 text-medium-emphasis" aria-hidden="true" />
        <p class="text-h6 mb-1">{{ CLOSED_MESSAGES[view.status] }}</p>
        <p class="text-medium-emphasis mb-0">You can close this window.</p>
      </v-card-text>
    </v-card>

    <v-card v-else-if="view" class="state-card" variant="flat" border>
      <v-card-text class="py-8 px-6">
        <div class="d-flex align-center mb-4">
          <img
            :src="(view as any).branding?.logo_data_url || '/logo-mark.png'"
            :alt="(view as any).branding?.company_name || 'Nolizi Sign'"
            style="height: 36px; max-width: 140px; object-fit: contain;"
            class="mr-2"
          />
          <span class="text-subtitle-1 font-weight-bold" :style="{ color: (view as any).branding?.primary_color || '#1A56DB' }">
            {{ (view as any).branding?.company_name || 'Nolizi Sign' }}
          </span>
        </div>
        <p class="text-overline mb-1">
          {{ phase === "retrieve" ? "Signed document" : "Signature requested" }}
        </p>
        <h1 class="text-h5 mb-2">{{ view.title }}</h1>
        <p class="text-medium-emphasis mb-6">
          {{
            phase === "retrieve"
              ? CLOSED_MESSAGES[view.status]
              : `${view.sender_name} at ${(view as any).branding?.company_name || 'Nolizi'} has requested your signature.`
          }}
        </p>

        <template v-if="phase === 'landing'">
          <p class="mb-4">
            To verify it's you, we'll email a 6-digit code to <strong>{{ view.masked_email }}</strong>.
          </p>
          <v-alert v-if="codeError" type="error" density="compact" class="mb-4">{{ codeError }}</v-alert>
          <v-btn
            :style="{ backgroundColor: (view as any).branding?.primary_color || '#1A56DB', color: '#ffffff' }"
            variant="flat"
            :loading="sending"
            @click="requestCode"
          >
            Email me a code
          </v-btn>
        </template>

        <template v-else-if="phase === 'retrieve'">
          <p class="mb-4">
            To view the document, verify it's you — we'll email a 6-digit code to
            <strong>{{ view.masked_email }}</strong>.
          </p>
          <v-alert v-if="codeError" type="error" density="compact" class="mb-4">{{ codeError }}</v-alert>
          <v-btn color="primary" variant="flat" :loading="sending" @click="requestCode">Email me a code</v-btn>
        </template>

        <template v-else>
          <p class="mb-4">
            Enter the 6-digit code we sent to <strong>{{ view.masked_email }}</strong>. It expires in 10 minutes.
          </p>
          <v-alert v-if="codeError" type="error" density="compact" class="mb-4">{{ codeError }}</v-alert>
          <v-otp-input v-model="code" length="6" class="mb-4" @finish="verify" />
          <div class="d-flex align-center">
            <v-btn color="primary" variant="flat" :loading="verifying" :disabled="code.length < 6" @click="verify">
              Verify &amp; continue
            </v-btn>
            <v-btn variant="text" class="ml-2" :loading="sending" @click="requestCode">Resend code</v-btn>
          </div>
        </template>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<style scoped>
.external-sign {
  max-width: 640px;
}

.state-card {
  margin-top: 48px;
}
</style>
