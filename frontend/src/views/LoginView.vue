<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute } from "vue-router";
import http, { loginRedirectUrl } from "../utils/http";

const route = useRoute();

const next = computed(() => {
  const raw = route.query.next;
  // Same-origin relative paths only; anything else falls back to the dashboard.
  return typeof raw === "string" && raw.startsWith("/") && !raw.startsWith("//") ? raw : "/";
});
const ssoUrl = computed(() => loginRedirectUrl(next.value));
const linkExpired = computed(() => route.query.error === "expired");

const email = ref("");
const sending = ref(false);
const sent = ref(false);
const sendFailed = ref(false);

async function requestLink() {
  if (!email.value.trim()) return;
  sending.value = true;
  sendFailed.value = false;
  try {
    await http.post(
      "/auth/email/request",
      { email: email.value.trim(), next: next.value },
      { skipAuthRedirect: true },
    );
    sent.value = true;
  } catch {
    sendFailed.value = true;
  } finally {
    sending.value = false;
  }
}
</script>

<template>
  <v-container class="d-flex justify-center pt-16">
    <v-card max-width="480" width="100%" class="pa-4">
      <div class="text-center pt-2">
        <img src="/logo-mark.png" alt="Pumasi" class="login-logo" />
      </div>
      <v-card-title class="text-center">Sign in to Pumasi Sign</v-card-title>
      <p class="text-subtitle-1 font-weight-medium text-primary text-center px-6 mb-2">
        Pumasi's e-signature service — send and sign documents efficiently and securely.
      </p>
      <v-card-text>
        <v-alert v-if="linkExpired" type="warning" variant="tonal" density="compact" class="mb-4">
          That sign-in link has expired or was already used. Request a new one below.
        </v-alert>

        <div class="text-center">
          <v-btn color="primary" variant="flat" :href="ssoUrl" prepend-icon="mdi-microsoft" block>
            Sign in with Microsoft
          </v-btn>
        </div>

        <div class="d-flex align-center my-5">
          <v-divider />
          <span class="text-caption text-medium-emphasis mx-3">or</span>
          <v-divider />
        </div>

        <template v-if="!sent">
          <form @submit.prevent="requestLink">
            <v-text-field
              v-model="email"
              label="Work email"
              type="email"
              autocomplete="email"
              density="comfortable"
              :disabled="sending"
            />
            <v-btn type="submit" variant="tonal" block :loading="sending" :disabled="!email.trim()">
              Email me a sign-in link
            </v-btn>
          </form>
          <p v-if="sendFailed" class="text-caption text-error mt-2 mb-0 text-center">
            Couldn't send the email. Please try again.
          </p>
        </template>
        <v-alert v-else type="success" variant="tonal" density="compact">
          If that address is eligible, a sign-in link is on its way. Check your inbox — the link
          expires in 15 minutes.
        </v-alert>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<style scoped>
.login-logo {
  height: 56px;
  width: auto;
}
</style>
