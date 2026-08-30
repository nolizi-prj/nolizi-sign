<script setup lang="ts">
/**
 * Pumasi Sign — public authentication (sign in & sign up): Google or
 * Microsoft OAuth, or a passwordless 6-digit code emailed to the address.
 */
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import http from "../utils/http";
import { useAuthStore } from "../store/auth";
import { useUiStore } from "../store/ui";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const ui = useUiStore();

const activeTab = ref<"signin" | "signup">("signin");
const email = ref("");
const name = ref("");
const code = ref("");
const step = ref<"email" | "code">("email");
const sending = ref(false);
const verifying = ref(false);
const error = ref("");

const next = computed(() => {
  const raw = route.query.next;
  return typeof raw === "string" && raw.startsWith("/") && !raw.startsWith("//") ? raw : "/";
});

const googleSsoUrl = computed(() => `/api/auth/oauth/google?next=${encodeURIComponent(next.value)}`);
const msSsoUrl = computed(() => `/api/auth/oauth/microsoft?next=${encodeURIComponent(next.value)}`);

async function requestCode() {
  if (!email.value.trim() || !email.value.includes("@")) {
    error.value = "Please enter a valid email address.";
    return;
  }
  sending.value = true;
  error.value = "";

  try {
    await http.post<any>("/auth/login/request", {
      email: email.value.trim(),
      name: name.value.trim() || undefined,
    }, { skipAuthRedirect: true });

    step.value = "code";
    ui.toast("Verification code sent to your email!");
  } catch (err: any) {
    error.value = err.response?.data?.error || "Could not send verification code.";
  } finally {
    sending.value = false;
  }
}

async function verifyCode() {
  if (!code.value.trim()) {
    error.value = "Please enter the 6-digit verification code.";
    return;
  }
  verifying.value = true;
  error.value = "";

  try {
    const { data } = await http.post<any>("/auth/login/verify", {
      email: email.value.trim(),
      code: code.value.trim(),
      name: name.value.trim() || undefined,
    }, { skipAuthRedirect: true });

    if (data.user) {
      auth.me = data.user;
      ui.toast(`Welcome, ${data.user.name}!`);
      await router.push(next.value);
    }
  } catch (err: any) {
    error.value = err.response?.data?.error || "Invalid verification code.";
  } finally {
    verifying.value = false;
  }
}

function resetToEmail() {
  step.value = "email";
  code.value = "";
  error.value = "";
}
</script>

<template>
  <v-container class="d-flex justify-center pt-12 pb-16">
    <v-card max-width="480" width="100%" class="pa-6 pumasi-card border rounded-lg shadow-sm">
      <!-- Header with Pumasi Logo -->
      <div class="text-center pt-2 mb-2">
        <img src="/logo-mark.png" alt="Pumasi Sign" style="height: 48px; width: 48px;" class="mb-2" />
        <h1 class="text-h5 font-weight-bold text-slate-900">
          {{ activeTab === "signup" ? "Create your Pumasi account" : "Sign in to Pumasi Sign" }}
        </h1>
        <p class="text-caption text-medium-emphasis px-4">
          Simple, unmetered e-signatures with cryptographic tamper-evident certificates.
        </p>
      </div>

      <!-- Sign In / Sign Up Toggle -->
      <div class="mb-5">
        <v-btn-toggle v-model="activeTab" mandatory density="comfortable" color="primary" class="w-100 d-flex">
          <v-btn value="signin" class="flex-grow-1">Sign In</v-btn>
          <v-btn value="signup" class="flex-grow-1">Create Account</v-btn>
        </v-btn-toggle>
      </div>

      <v-alert v-if="error" type="error" density="compact" variant="tonal" class="mb-4">
        {{ error }}
      </v-alert>

      <!-- Step 1: OAuth + Email Input -->
      <div v-if="step === 'email'">
        <div class="d-flex flex-column gap-2 mb-2">
          <v-btn variant="outlined" size="large" block :href="googleSsoUrl" prepend-icon="mdi-google" class="border mb-2">
            Continue with Google
          </v-btn>
          <v-btn variant="outlined" size="large" block :href="msSsoUrl" prepend-icon="mdi-microsoft" class="border">
            Continue with Microsoft
          </v-btn>
        </div>

        <div class="d-flex align-center my-4">
          <v-divider />
          <span class="px-3 text-caption text-medium-emphasis">or continue with email</span>
          <v-divider />
        </div>

        <!-- Name field for Sign-Up mode -->
        <v-text-field
          v-if="activeTab === 'signup'"
          v-model="name"
          label="Your Full Name"
          placeholder="Jane Doe"
          prepend-inner-icon="mdi-account"
          density="comfortable"
          class="mb-3"
        />

        <v-text-field
          v-model="email"
          label="Email Address"
          placeholder="name@company.com"
          type="email"
          prepend-inner-icon="mdi-email-outline"
          density="comfortable"
          autofocus
          class="mb-3"
          @keyup.enter="requestCode"
        />

        <v-btn
          color="primary"
          size="large"
          block
          :loading="sending"
          :disabled="!email.trim()"
          @click="requestCode"
        >
          {{ activeTab === "signup" ? "Create Free Workspace" : "Send Magic Code" }}
        </v-btn>
      </div>

      <!-- Step 2: 6-Digit Code Verification -->
      <div v-else>
        <div class="text-center mb-4">
          <v-icon icon="mdi-email-check-outline" color="primary" size="40" class="mb-2" />
          <p class="text-body-2 mb-1">
            We sent a 6-digit verification code to <strong>{{ email }}</strong>.
          </p>
          <p class="text-caption text-medium-emphasis mb-0">
            It can take a minute to arrive — and check your spam folder. Marking it
            "Not spam" makes sure future codes land in your inbox.
          </p>
        </div>

        <v-otp-input
          v-model="code"
          length="6"
          type="number"
          class="mb-4"
          autofocus
          @finish="verifyCode"
        />

        <v-btn
          color="primary"
          size="large"
          block
          :loading="verifying"
          :disabled="code.length < 6"
          class="mb-3"
          @click="verifyCode"
        >
          Verify &amp; Continue
        </v-btn>

        <div class="text-center">
          <v-btn variant="text" size="small" :loading="sending" @click="requestCode">
            Resend code
          </v-btn>
          <v-btn variant="text" size="small" @click="resetToEmail">
            Use a different email
          </v-btn>
        </div>
      </div>

      <div class="text-center mt-6 pt-4 border-t">
        <span class="text-caption text-medium-emphasis">
          By continuing, you agree to Pumasi's
          <router-link to="/terms">Terms of Service</router-link> and
          <router-link to="/privacy">Privacy Policy</router-link>.
        </span>
      </div>
    </v-card>
  </v-container>
</template>
