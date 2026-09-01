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

const activeTab = ref<"signin" | "signup">(route.query.tab === "signup" ? "signup" : "signin");
const email = ref("");
const name = ref("");
const code = ref("");
const step = ref<"email" | "code">("email");
const sending = ref(false);
const verifying = ref(false);
const error = ref("");

const next = computed(() => {
  const raw = route.query.next;
  return typeof raw === "string" && raw.startsWith("/") && !raw.startsWith("//") && raw !== "/" ? raw : "/dashboard";
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
        <div class="d-flex justify-center mb-2">
          <img src="/logo-mark.png" alt="Pumasi Sign" style="height: 44px; width: auto; max-width: 100%; object-fit: contain;" />
        </div>
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
          <v-btn variant="outlined" size="large" block :href="googleSsoUrl" class="border mb-2 text-none font-weight-medium">
            <template #prepend>
              <svg width="18" height="18" viewBox="0 0 24 24" class="mr-2" style="display:inline-block;vertical-align:middle">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
              </svg>
            </template>
            Continue with Google
          </v-btn>
          <v-btn variant="outlined" size="large" block :href="msSsoUrl" class="border text-none font-weight-medium">
            <template #prepend>
              <svg width="18" height="18" viewBox="0 0 23 23" class="mr-2" style="display:inline-block;vertical-align:middle">
                <path fill="#f35325" d="M1 1h10v10H1z"/>
                <path fill="#81bc06" d="M12 1h10v10H12z"/>
                <path fill="#05a6f0" d="M1 12h10v10H1z"/>
                <path fill="#ffba08" d="M12 12h10v10H12z"/>
              </svg>
            </template>
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
