<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useDisplay } from "vuetify";
import { useAuthStore } from "./store/auth";
import { useUiStore } from "./store/ui";
import { useBrandingStore } from "./store/branding";
import http from "./utils/http";
import FeedbackDialog from "./components/FeedbackDialog.vue";
import { APP_VERSION } from "./version";

const auth = useAuthStore();
const ui = useUiStore();
const branding = useBrandingStore();
const route = useRoute();
const router = useRouter();
const { mdAndUp } = useDisplay();
const mobileDrawer = ref(false);
const helpOpen = ref(false);

const publicLayout = computed(() => route.meta.layout === "public");
const focusLayout = computed(() => route.meta.layout === "focus");
const workspaceLayout = computed(() => Boolean(auth.me) && !publicLayout.value && !focusLayout.value);
const brandColor = computed(() => branding.primaryColor || "#1A56DB");
const initials = computed(() => (auth.me?.name || auth.me?.email || "P")
  .split(/\s+/).slice(0, 2).map((part) => part[0]?.toUpperCase()).join(""));

const primaryNav = computed(() => [
  { title: "Home", icon: "mdi-home-outline", to: { name: "dashboard" }, names: ["dashboard", "agreements", "envelope-detail"] },
  ...(auth.canSend ? [{ title: "Templates", icon: "mdi-file-document-multiple-outline", to: { name: "templates" }, names: ["templates"] }] : []),
]);

const settingsNav = computed(() => [
  { title: "Branding", icon: "mdi-palette-outline", to: { name: "branding" } },
  ...(auth.isAdmin ? [{ title: "Team", icon: "mdi-account-group-outline", to: { name: "admin-users" } }] : []),
]);

function navActive(names: string[]): boolean {
  return names.includes(String(route.name));
}

watch(() => route.fullPath, () => { mobileDrawer.value = false; });

onMounted(async () => {
  if (!auth.fetched) await auth.fetchMe();
  if (auth.me) await branding.fetchBranding();
});

async function logout(): Promise<void> {
  await http.post("/auth/logout");
  auth.reset();
  await router.push({ name: "signed-out" });
}
</script>

<template>
  <v-app>
    <template v-if="workspaceLayout">
      <v-navigation-drawer v-if="mdAndUp" class="workspace-nav" permanent width="244">
        <router-link :to="{ name: 'dashboard' }" class="workspace-brand">
          <span class="brand-mark" :class="{ 'brand-mark-custom': branding.logoDataUrl }" :style="branding.logoDataUrl ? undefined : { backgroundColor: brandColor }"><img :src="branding.logoDataUrl || '/logo-mark-white.png'" alt="" /></span>
          <span class="brand-copy"><strong>{{ branding.companyName || 'Nolizi Sign' }}</strong><small>eSignature workspace</small></span>
        </router-link>
        <div class="px-3 pb-3" v-if="auth.canSend"><v-btn block color="primary" size="large" prepend-icon="mdi-plus" :to="{ name: 'send' }">Get signatures</v-btn></div>
        <v-list nav density="comfortable" class="px-2">
          <v-list-item v-for="item in primaryNav" :key="item.title" :prepend-icon="item.icon" :title="item.title" :to="item.to" :active="navActive(item.names)" color="primary" rounded="lg" />
        </v-list>
        <template #append>
          <div class="px-2 pb-3">
            <p class="nav-section-label px-3 mb-1">Workspace</p>
            <v-list nav density="compact">
              <v-list-item v-for="item in settingsNav" :key="item.title" :prepend-icon="item.icon" :title="item.title" :to="item.to" color="primary" rounded="lg" />
            </v-list>
            <p class="app-version px-3 mt-2 mb-0">Nolizi Sign v{{ APP_VERSION }}</p>
          </div>
        </template>
      </v-navigation-drawer>

      <v-navigation-drawer v-model="mobileDrawer" temporary width="280">
        <div class="workspace-brand">
          <span class="brand-mark" :class="{ 'brand-mark-custom': branding.logoDataUrl }" :style="branding.logoDataUrl ? undefined : { backgroundColor: brandColor }"><img :src="branding.logoDataUrl || '/logo-mark-white.png'" alt="" /></span>
          <span class="brand-copy"><strong>{{ branding.companyName || 'Nolizi Sign' }}</strong><small>eSignature workspace</small></span>
        </div>
        <div class="px-3 pb-3" v-if="auth.canSend"><v-btn block color="primary" prepend-icon="mdi-plus" :to="{ name: 'send' }">Get signatures</v-btn></div>
        <v-list nav>
          <v-list-item v-for="item in primaryNav" :key="item.title" :prepend-icon="item.icon" :title="item.title" :to="item.to" color="primary" />
          <v-divider class="my-2" />
          <v-list-item v-for="item in settingsNav" :key="item.title" :prepend-icon="item.icon" :title="item.title" :to="item.to" color="primary" />
        </v-list>
        <p class="app-version px-5 mt-2">Nolizi Sign v{{ APP_VERSION }}</p>
      </v-navigation-drawer>

      <v-app-bar color="surface" elevation="0" border="b" height="64">
        <v-app-bar-nav-icon class="d-md-none" aria-label="Open navigation" @click="mobileDrawer = true" />
        <v-app-bar-title class="workspace-title">{{ route.meta.title || 'Workspace' }}</v-app-bar-title>
        <v-spacer />
        <v-btn icon="mdi-help-circle-outline" variant="text" aria-label="Help" @click="helpOpen = true" />
        <v-menu location="bottom end">
          <template #activator="{ props }">
            <v-btn class="account-button ml-1 mr-3" variant="text" v-bind="props" aria-label="Open account menu">
              <v-avatar size="34" color="primary" class="mr-2"><span class="text-caption font-weight-bold">{{ initials }}</span></v-avatar>
              <span class="account-name d-none d-sm-inline">{{ auth.me?.name }}</span><v-icon icon="mdi-chevron-down" size="18" />
            </v-btn>
          </template>
          <v-list min-width="250" density="compact" rounded="lg">
            <v-list-item :title="auth.me?.name" :subtitle="auth.me?.email" /><v-divider class="my-1" />
            <v-list-item prepend-icon="mdi-account-outline" title="Profile & personal settings" :to="{ name: 'profile' }" />
            <v-list-item prepend-icon="mdi-palette-outline" title="Branding & design" :to="{ name: 'branding' }" />
            <v-list-item prepend-icon="mdi-logout" title="Sign out" @click="logout" />
          </v-list>
        </v-menu>
      </v-app-bar>
    </template>

    <v-app-bar v-else-if="focusLayout" color="surface" elevation="0" border="b" height="60">
      <router-link :to="auth.me ? { name: 'dashboard' } : { name: 'landing' }" class="focus-brand ml-4">
        <span class="brand-mark brand-mark-small" :class="{ 'brand-mark-custom': branding.logoDataUrl }" :style="branding.logoDataUrl ? undefined : { backgroundColor: brandColor }"><img :src="branding.logoDataUrl || '/logo-mark-white.png'" alt="" /></span>
        <strong>{{ branding.companyName || 'Nolizi Sign' }}</strong>
      </router-link>
      <v-spacer /><span class="focus-context d-none d-sm-inline">{{ route.meta.title }}</span>
      <v-btn v-if="auth.me" variant="text" class="mx-2" :to="{ name: 'dashboard' }">Exit</v-btn>
    </v-app-bar>

    <v-main :class="{ 'workspace-main': workspaceLayout }"><router-view /></v-main>
    <p v-if="!workspaceLayout" class="public-app-version">Nolizi Sign v{{ APP_VERSION }}</p>
    <FeedbackDialog />
    <v-dialog v-model="helpOpen" max-width="560">
      <v-card>
        <v-card-title class="d-flex align-center">
          <span>Help &amp; quick start</span><v-spacer />
          <v-btn icon="mdi-close" variant="text" aria-label="Close help" @click="helpOpen = false" />
        </v-card-title>
        <v-card-text>
          <v-list lines="two">
            <v-list-item prepend-icon="mdi-send-outline" title="Send for signature" subtitle="Choose Get signatures, add documents and recipients, place fields, preview, then send." />
            <v-list-item prepend-icon="mdi-file-document-multiple-outline" title="Reuse a workflow" subtitle="Create a template when the same document and signer roles will be used again." />
            <v-list-item prepend-icon="mdi-message-alert-outline" title="Report a problem" subtitle="Use the Feedback button at bottom-right. Diagnostics and screenshots can be reviewed before submission." />
          </v-list>
          <v-alert type="info" variant="tonal" density="compact" class="mt-3">
            Feedback can be submitted with Ctrl+Enter (Cmd+Enter on macOS).
          </v-alert>
        </v-card-text>
        <v-card-actions><v-spacer /><v-btn color="primary" variant="flat" @click="helpOpen = false">Got it</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
    <v-snackbar v-model="ui.toastOpen" :color="ui.toastColor" :timeout="3500" location="bottom">{{ ui.toastMessage }}</v-snackbar>
  </v-app>
</template>

<style scoped>
.workspace-nav { border-right-color: #e7ebf0; }
.workspace-brand, .focus-brand { color: var(--fg); text-decoration: none; display: flex; align-items: center; gap: 11px; }
.workspace-brand { min-height: 76px; padding: 14px 16px; }
.workspace-brand:hover, .focus-brand:hover { text-decoration: none; }
.brand-mark { width: 38px; height: 38px; border-radius: 10px; display: inline-grid; place-items: center; flex: none; }
.brand-mark img { display: block; max-width: 24px; max-height: 24px; }
.brand-mark-custom { width: auto; min-width: 38px; max-width: 112px; padding: 0; border-radius: 0; background: transparent; }
.brand-mark-custom img { max-width: 112px; max-height: 38px; object-fit: contain; }
.brand-mark-small { width: 32px; height: 32px; border-radius: 8px; }
.brand-mark-small img { max-width: 20px; max-height: 20px; }
.brand-mark-small.brand-mark-custom { width: auto; min-width: 32px; max-width: 96px; border-radius: 0; }
.brand-mark-small.brand-mark-custom img { max-width: 96px; max-height: 32px; }
.brand-copy { min-width: 0; display: flex; flex-direction: column; line-height: 1.2; }
.brand-copy strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.brand-copy small { color: var(--muted); font-size: 11px; margin-top: 3px; }
.nav-section-label { color: var(--muted); font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.workspace-title { font-size: 17px; font-weight: 650; }
.account-button { text-transform: none; letter-spacing: 0; }
.account-name { max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.focus-context { color: var(--muted); font-size: 14px; }
.app-version { color: var(--muted); font-size: 10px; letter-spacing: .02em; }
.public-app-version { position: fixed; z-index: 5; left: 12px; bottom: 8px; margin: 0; color: var(--muted); font-size: 10px; }
.workspace-main { background: #f7f8fa; }
</style>
