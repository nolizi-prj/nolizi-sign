<script setup lang="ts">
import { onMounted } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "./store/auth";
import { useUiStore } from "./store/ui";
import http from "./utils/http";
import FeedbackDialog from "./components/FeedbackDialog.vue";

const auth = useAuthStore();
const ui = useUiStore();
const router = useRouter();

onMounted(() => {
  void auth.fetchMe();
});

async function logout(): Promise<void> {
  await http.post("/auth/logout");
  auth.reset();
  await router.push({ name: "signed-out" });
}
</script>

<template>
  <v-app>
    <v-app-bar color="primary" density="comfortable">
      <v-app-bar-title>
        <router-link :to="{ name: 'dashboard' }" class="app-title-link">
          <img src="/logo-mark-white.png" alt="" class="app-logo mr-2" />
          Pumasi Sign
        </router-link>
      </v-app-bar-title>
      <v-spacer />
      <FeedbackDialog />
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
        <v-btn v-if="auth.isAdmin" variant="text" prepend-icon="mdi-account-group" :to="{ name: 'admin-users' }">
          Users
        </v-btn>
        <span class="mx-3 d-none d-sm-inline text-truncate app-username">{{ auth.me.name }}</span>
        <v-btn variant="text" prepend-icon="mdi-logout" @click="logout">Logout</v-btn>
      </template>
    </v-app-bar>
    <v-main>
      <router-view />
    </v-main>
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
