<script setup lang="ts">
import { loginRedirectUrl } from "../utils/http";

const signInUrl = loginRedirectUrl("/");
// Ends the browser's Microsoft SSO session too; without this, "Sign in
// again" completes silently for the same account.
const microsoftLogoutUrl = "https://login.microsoftonline.com/common/oauth2/v2.0/logout";
</script>

<template>
  <v-container class="d-flex justify-center pt-16">
    <v-card max-width="480" class="pa-4 text-center">
      <div class="text-center pt-2 mb-2">
        <img src="/logo-mark.png" alt="Pumasi" style="height: 48px; width: 48px;" />
      </div>
      <v-card-title>You've signed out</v-card-title>
      <v-card-text>
        Your Pumasi Sign session has ended.
        <p class="text-caption text-medium-emphasis mt-3 mb-0">
          You're still signed in to Microsoft in this browser, so signing in
          again won't ask for a password. To switch accounts,
          <a :href="microsoftLogoutUrl">sign out of Microsoft</a> first.
        </p>
      </v-card-text>
      <v-card-actions class="justify-center">
        <v-btn color="primary" variant="flat" :href="signInUrl" prepend-icon="mdi-login">Sign in again</v-btn>
      </v-card-actions>
    </v-card>
  </v-container>
</template>
