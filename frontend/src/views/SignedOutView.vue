<script setup lang="ts">
import { loginPageUrl } from "../utils/http";

// The SPA login page, not a server route: `/api/auth/login` exists only in
// backend/, and the worker that serves sign.pumasi.ai answers it 404 (#7).
const signInUrl = loginPageUrl("/");
// Ends the browser's Microsoft SSO session too; without this, "Sign in
// again" completes silently for the same account.
const microsoftLogoutUrl = "https://login.microsoftonline.com/common/oauth2/v2.0/logout";
</script>

<template>
  <v-container class="d-flex justify-center pt-16 pb-16">
    <v-card max-width="480" width="100%" class="pa-6 text-center pumasi-card border rounded-lg shadow-sm">
      <div class="text-center pt-2 mb-2">
        <div class="d-flex justify-center mb-2">
          <img src="/logo-mark.png" alt="Pumasi Sign" style="height: 44px; width: auto; max-width: 100%; object-fit: contain;" />
        </div>
      </div>
      <h1 class="text-h5 font-weight-bold text-slate-900 mb-2">You've signed out</h1>
      <v-card-text class="pt-0">
        <p class="text-body-1 text-slate-700 mb-3">
          Your Pumasi Sign session has ended securely.
        </p>
        <p class="text-caption text-medium-emphasis mb-0">
          You're still signed in to your single sign-on provider in this browser. To switch accounts,
          <a :href="microsoftLogoutUrl">sign out of Microsoft</a> first.
        </p>
      </v-card-text>
      <v-card-actions class="justify-center pt-3 pb-2">
        <v-btn color="primary" variant="flat" size="large" :href="signInUrl" prepend-icon="mdi-login" class="px-6 text-none font-weight-bold">
          Sign in again
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-container>
</template>
