<script setup lang="ts">
import { onMounted } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "./store/auth";
import { useUiStore } from "./store/ui";
import { useBrandingStore } from "./store/branding";
import http from "./utils/http";
import FeedbackDialog from "./components/FeedbackDialog.vue";

const auth = useAuthStore();
const ui = useUiStore();
const branding = useBrandingStore();
const router = useRouter();

onMounted(async () => {
  void auth.fetchMe();
  await branding.fetchBranding();
});

async function logout(): Promise<void> {
  await http.post("/auth/logout");
  auth.reset();
  await router.push({ name: "signed-out" });
}
</script>

<template>
  <v-app>
    <v-app-bar :style="{ backgroundColor: branding.primaryColor || '#1A56DB', color: '#ffffff' }" density="comfortable">
      <v-app-bar-title>
        <router-link :to="{ name: 'dashboard' }" class="app-title-link">
          <img :src="branding.logoDataUrl || '/logo-mark-white.png'" alt="" class="app-logo mr-2" />
          {{ branding.companyName || 'Pumasi Sign' }}
        </router-link>
      </v-app-bar-title>
      <v-spacer />
      <template v-if="auth.me">
        <v-btn v-if="auth.canSend" variant="text" prepend-icon="mdi-send" :to="{ name: 'send' }">
          Send
        </v-btn>
        <v-btn
          v-if="auth.canSend"
          variant="text"
          prepend-icon="mdi-file-document-multiple-outline"
          :to="{ name: 'templates' }"
        >
          Templates
        </v-btn>
        <v-menu location="bottom end">
          <template #activator="{ props }">
            <v-btn variant="text" prepend-icon="mdi-cog-outline" v-bind="props">
              Settings
              <v-icon icon="mdi-chevron-down" end size="16" />
            </v-btn>
          </template>
          <v-list density="compact" min-width="200" elevation="2" rounded="lg">
            <v-list-item prepend-icon="mdi-palette-outline" title="Branding & Design" :to="{ name: 'branding' }" />
            <v-list-item v-if="auth.isAdmin" prepend-icon="mdi-account-group" title="Team & Users" :to="{ name: 'admin-users' }" />
          </v-list>
        </v-menu>
        <span class="mx-3 d-none d-sm-inline text-truncate app-username">{{ auth.me.name }}</span>
        <v-btn variant="text" prepend-icon="mdi-logout" @click="logout">Logout</v-btn>
      </template>
    </v-app-bar>
    <v-main>
      <router-view />
    </v-main>
    <FeedbackDialog />
    <v-snackbar v-model="ui.toastOpen" :color="ui.toastColor" :timeout="3500" location="bottom">
      {{ ui.toastMessage }}
    </v-snackbar>
  </v-app>
</template>

<style scoped>
.app-title-link {
  color: inherit;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
}

.app-logo {
  height: 24px;
  width: auto;
  display: block;
}

.app-username {
  max-width: 200px;
}
</style>
