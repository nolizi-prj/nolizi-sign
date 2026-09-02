<script setup lang="ts">
import { ref } from "vue";
import { useAuthStore } from "../store/auth";
import { useUiStore } from "../store/ui";
import http, { extractError } from "../utils/http";
import type { User } from "../types";

const auth = useAuthStore();
const ui = useUiStore();
const name = ref(auth.me?.name || "");
const saving = ref(false);
const error = ref<string | null>(null);

const roleLabel = () => auth.me?.role === "owner" ? "Owner" : auth.me?.role === "admin" ? "Admin" : "User";
const providerLabel = () => auth.me?.provider === "google" ? "Google" : auth.me?.provider === "microsoft" ? "Microsoft" : "Email verification code";

async function save(): Promise<void> {
  saving.value = true;
  error.value = null;
  try {
    const { data } = await http.put<User>("/profile", { name: name.value });
    auth.me = data;
    name.value = data.name;
    ui.toast("Profile updated.");
  } catch (err) {
    error.value = extractError(err);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <v-container class="profile-page py-8">
    <h1 class="text-h4 font-weight-bold mb-1">Profile &amp; personal settings</h1>
    <p class="text-medium-emphasis mb-6">Manage the identity shown when you send agreements.</p>
    <v-alert v-if="error" type="error" closable class="mb-4" @click:close="error = null">{{ error }}</v-alert>
    <v-card variant="flat" border>
      <v-card-title class="text-subtitle-1">Personal information</v-card-title>
      <v-card-text>
        <v-text-field v-model="name" label="Display name" maxlength="120" counter="120" />
        <div class="identity-panel" aria-label="Verified sign-in email">
          <div>
            <p class="text-caption text-medium-emphasis mb-1">Verified sign-in email</p>
            <p class="text-body-1 mb-0">{{ auth.me?.email }}</p>
          </div>
          <v-chip size="small" color="success" variant="tonal">Verified login</v-chip>
        </div>
        <p class="text-caption text-medium-emphasis mt-2 mb-0">
          This is your login ID and cannot be edited. Contact support if your organization must migrate to a different address.
        </p>
      </v-card-text>
      <v-card-actions class="px-4 pb-4"><v-spacer /><v-btn color="primary" variant="flat" :loading="saving" :disabled="name.trim().length < 2" @click="save">Save profile</v-btn></v-card-actions>
    </v-card>
    <v-card variant="flat" border class="mt-5">
      <v-card-title class="text-subtitle-1">Account access</v-card-title>
      <v-list lines="two">
        <v-list-item title="Workspace role" :subtitle="roleLabel()" />
        <v-list-item title="Sign-in method" :subtitle="providerLabel()" />
      </v-list>
    </v-card>
  </v-container>
</template>

<style scoped>
.profile-page { max-width: 760px; }
.identity-panel { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 16px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; background: rgba(var(--v-theme-on-surface), .025); }
</style>
