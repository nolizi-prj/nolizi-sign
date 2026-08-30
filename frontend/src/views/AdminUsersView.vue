<script setup lang="ts">
/**
 * Admin console: list every user and toggle their admin flag via
 * PUT /users/{id}. The switch is disabled on the caller's own row so the
 * backend's self-demotion 409 (see routers/users.py) is never actually hit
 * through this UI — but the generic error handling below still covers it
 * (and any other failure) if it ever is.
 */
import { onMounted, ref } from "vue";
import http, { extractError } from "../utils/http";
import { useAuthStore } from "../store/auth";
import type { User } from "../types";

const auth = useAuthStore();

const users = ref<User[]>([]);
const loading = ref(true);
const errorMessage = ref<string | null>(null);
const updating = ref<number | null>(null);
// Vuetify's clearable ✕ sets the model to null, so the type must admit it.
const search = ref<string | null>("");

async function load(): Promise<void> {
  loading.value = true;
  errorMessage.value = null;
  try {
    const { data } = await http.get<User[]>("/users");
    users.value = data;
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    loading.value = false;
  }
}

// The router already redirects non-admins; this belt-and-suspenders check
// (same pattern as TemplatesView's canSend gate) avoids a pointless fetch
// if the view is ever mounted another way.
onMounted(() => {
  if (auth.isAdmin) void load();
});

async function toggleAdmin(user: User, value: boolean): Promise<void> {
  const previous = user.is_admin;
  user.is_admin = value; // optimistic
  updating.value = user.id;
  errorMessage.value = null;
  try {
    const { data } = await http.put<User>(`/users/${user.id}`, { is_admin: value });
    user.is_admin = data.is_admin;
  } catch (err) {
    user.is_admin = previous;
    errorMessage.value = extractError(err);
  } finally {
    updating.value = null;
  }
}

async function toggleCanSend(user: User, value: boolean): Promise<void> {
  const previous = user.can_send;
  user.can_send = value; // optimistic
  updating.value = user.id;
  errorMessage.value = null;
  try {
    const { data } = await http.put<User>(`/users/${user.id}`, { can_send: value });
    user.can_send = data.can_send;
  } catch (err) {
    user.can_send = previous;
    errorMessage.value = extractError(err);
  } finally {
    updating.value = null;
  }
}

const headers = [
  { title: "Name", key: "name" },
  { title: "Email", key: "email" },
  { title: "Type", key: "is_external", sortable: false },
  { title: "Can send", key: "can_send", sortable: false, align: "end" as const },
  { title: "Admin", key: "is_admin", sortable: false, align: "end" as const },
];
</script>

<template>
  <v-container>
    <h1 class="text-h5 mb-4">Users</h1>

    <v-alert v-if="!auth.isAdmin" type="warning" variant="tonal">
      Only admins can manage users.
    </v-alert>
    <template v-else>
    <v-alert v-if="errorMessage" type="error" closable class="mb-4" @click:close="errorMessage = null">
      {{ errorMessage }}
    </v-alert>

    <v-card>
      <v-card-text class="pb-0">
        <v-text-field
          v-model="search"
          label="Search by name or email"
          prepend-inner-icon="mdi-magnify"
          density="compact"
          variant="outlined"
          hide-details
          clearable
        />
      </v-card-text>
      <v-data-table :headers="headers" :items="users" :loading="loading" :search="search ?? ''" item-value="id">
        <template #item.is_external="{ item }">
          <v-chip v-if="item.is_external" size="small" color="warning" variant="tonal">External</v-chip>
          <span v-else class="text-medium-emphasis">Employee</span>
        </template>
        <template #item.can_send="{ item }">
          <!-- align: "end" on the header only sets text-align, which flex
               containers like v-switch ignore — justify it to match. -->
          <!-- Externals can never send: always show OFF, even if a stale row
               still stores can_send=true (pre-backfill data). -->
          <v-switch
            class="d-flex justify-end"
            :model-value="item.can_send && !item.is_external"
            :disabled="updating === item.id || item.is_external"
            :title="item.is_external ? 'External signers cannot send' : undefined"
            color="primary"
            hide-details
            density="compact"
            @update:model-value="(v: boolean | null) => toggleCanSend(item, v === true)"
          />
        </template>
        <template #item.is_admin="{ item }">
          <!-- align: "end" on the header only sets text-align, which flex
               containers like v-switch ignore — justify it to match. -->
          <v-switch
            class="d-flex justify-end"
            :model-value="item.is_admin && !item.is_external"
            :disabled="updating === item.id || item.id === auth.me?.id || item.is_external"
            :title="
              item.is_external
                ? 'External signers cannot be admins'
                : item.id === auth.me?.id
                  ? 'You cannot remove your own admin access'
                  : undefined
            "
            color="primary"
            hide-details
            density="compact"
            @update:model-value="(v: boolean | null) => toggleAdmin(item, v === true)"
          />
        </template>
      </v-data-table>
    </v-card>
    </template>
  </v-container>
</template>
