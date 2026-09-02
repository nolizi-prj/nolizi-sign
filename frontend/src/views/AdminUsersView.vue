<script setup lang="ts">
/** Workspace membership administration. Membership never implies access to
 * another person's envelopes or templates; those permissions are separate. */
import { onMounted, ref } from "vue";
import http, { extractError } from "../utils/http";
import { useAuthStore } from "../store/auth";
interface TeamMember {
  id: string;
  email: string;
  name: string;
  role: "owner" | "admin" | "member";
  status: "pending" | "accepted";
  created_at: string | null;
}

const auth = useAuthStore();

const users = ref<TeamMember[]>([]);
const loading = ref(true);
const errorMessage = ref<string | null>(null);
const updating = ref<string | null>(null);
// Vuetify's clearable ✕ sets the model to null, so the type must admit it.
const search = ref<string | null>("");
const archiveRecipients = ref<string[]>([]);
const savingArchiveRecipients = ref(false);
const archiveSaved = ref(false);
const inviteDialog = ref(false);
const inviteEmail = ref("");
const inviteRole = ref<"member" | "admin">("member");
const inviting = ref(false);

async function load(): Promise<void> {
  loading.value = true;
  errorMessage.value = null;
  try {
    const [usersRes, archiveRes] = await Promise.all([
      http.get<TeamMember[]>("/team/members"),
      http.get<string[]>("/admin/archive-recipients"),
    ]);
    users.value = usersRes.data;
    archiveRecipients.value = archiveRes.data;
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    loading.value = false;
  }
}

async function saveArchiveRecipients(): Promise<void> {
  savingArchiveRecipients.value = true;
  archiveSaved.value = false;
  errorMessage.value = null;
  try {
    const { data } = await http.put<string[]>("/admin/archive-recipients", { emails: archiveRecipients.value });
    archiveRecipients.value = data;
    archiveSaved.value = true;
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    savingArchiveRecipients.value = false;
  }
}

// The router already redirects non-admins; this belt-and-suspenders check
// (same pattern as TemplatesView's canSend gate) avoids a pointless fetch
// if the view is ever mounted another way.
onMounted(() => {
  if (auth.isAdmin) void load();
});

async function invite(): Promise<void> {
  inviting.value = true;
  try {
    await http.post("/team/members", { email: inviteEmail.value, role: inviteRole.value });
    inviteDialog.value = false;
    inviteEmail.value = "";
    inviteRole.value = "member";
    await load();
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    inviting.value = false;
  }
}

async function resend(member: TeamMember): Promise<void> {
  updating.value = member.id;
  try {
    await http.post(`/team/members/${member.id}/resend`);
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    updating.value = null;
  }
}

async function remove(member: TeamMember): Promise<void> {
  updating.value = member.id;
  try {
    await http.delete(`/team/members/${member.id}`);
    await load();
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    updating.value = null;
  }
}

async function changeRole(member: TeamMember, role: "admin" | "member"): Promise<void> {
  if (member.role === role) return;
  const previous = member.role;
  member.role = role;
  updating.value = member.id;
  errorMessage.value = null;
  try {
    const { data } = await http.put<TeamMember>(`/team/members/${member.id}`, { role });
    member.role = data.role;
  } catch (err) {
    member.role = previous;
    errorMessage.value = extractError(err);
  } finally {
    updating.value = null;
  }
}

const headers = [
  { title: "Name", key: "name" },
  { title: "Email", key: "email" },
  { title: "Role", key: "role" },
  { title: "Status", key: "status" },
  { title: "", key: "actions", sortable: false, align: "end" as const },
];
</script>

<template>
  <v-container>
    <h1 class="text-h5 mb-4">Team</h1>

    <v-alert v-if="!auth.isAdmin" type="warning" variant="tonal">
      Only admins can manage users.
    </v-alert>
    <template v-else>
    <v-alert v-if="errorMessage" type="error" closable class="mb-4" @click:close="errorMessage = null">
      {{ errorMessage }}
    </v-alert>

    <v-card class="mb-5" variant="flat" border>
      <v-card-title class="d-flex align-center text-subtitle-1">
        <span>Workspace users</span>
        <v-spacer />
        <v-btn color="primary" prepend-icon="mdi-account-plus-outline" @click="inviteDialog = true">Invite member</v-btn>
      </v-card-title>
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
        <template #item.role="{ item }">
          <v-chip v-if="item.role === 'owner'" size="small" color="primary" variant="tonal">Owner</v-chip>
          <v-menu v-else location="bottom start">
            <template #activator="{ props }">
              <v-btn
                v-bind="props"
                class="role-button text-none"
                size="small"
                variant="tonal"
                rounded="pill"
                :color="item.role === 'admin' ? 'primary' : undefined"
                :loading="updating === item.id"
                :disabled="updating === item.id || item.email === auth.me?.email"
                :title="item.email === auth.me?.email ? 'Ask another admin to change your role' : 'Change role'"
              >
                {{ item.role === "admin" ? "Admin" : "User" }}
                <span class="role-caret" aria-hidden="true">▾</span>
              </v-btn>
            </template>
            <v-list density="compact" min-width="180" aria-label="Choose role">
              <v-list-item title="User" subtitle="Can create and send their own agreements" @click="changeRole(item, 'member')" />
              <v-list-item title="Admin" subtitle="Can manage team members" @click="changeRole(item, 'admin')" />
            </v-list>
          </v-menu>
        </template>
        <template #item.status="{ item }">
          <v-chip size="small" :color="item.status === 'accepted' ? 'success' : 'warning'" variant="tonal" class="text-capitalize">
            {{ item.status }}
          </v-chip>
        </template>
        <template #item.actions="{ item }">
          <v-btn v-if="item.status === 'pending'" size="small" variant="text" :loading="updating === item.id" @click="resend(item)">Resend</v-btn>
          <v-btn v-if="item.role !== 'owner'" size="small" variant="text" color="error" :disabled="updating === item.id" @click="remove(item)">Remove</v-btn>
        </template>
      </v-data-table>
    </v-card>

    <v-dialog v-model="inviteDialog" max-width="500">
      <v-card>
        <v-card-title>Invite a team member</v-card-title>
        <v-card-text>
          <p class="text-body-2 text-medium-emphasis mb-4">
            Membership lets this person use the workspace, but does not share anyone else's envelopes or templates.
          </p>
          <v-text-field v-model="inviteEmail" type="email" label="Email address" autofocus />
          <v-select
            v-model="inviteRole"
            label="Role"
            :items="[{ title: 'User', value: 'member' }, { title: 'Admin', value: 'admin' }]"
            hint="Admins can invite and remove team members. Neither role automatically receives document access."
            persistent-hint
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="inviteDialog = false">Cancel</v-btn>
          <v-btn color="primary" variant="flat" :loading="inviting" :disabled="!inviteEmail.trim()" @click="invite">Send invitation</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-card variant="flat" border>
      <v-card-title class="text-subtitle-1">Automatic completed-envelope copies</v-card-title>
      <v-card-text>
        <p class="text-body-2 text-medium-emphasis mb-3">
          Add records, legal, or compliance addresses that should receive the completed signed PDF and certificate for every envelope.
          These recipients are disclosed to the sender before sending and recorded in the envelope audit trail.
        </p>
        <v-combobox
          v-model="archiveRecipients"
          label="Copy completed envelopes to"
          placeholder="records@company.com"
          multiple
          chips
          closable-chips
          clearable
          :counter="10"
          hint="Type an email address and press Enter. Up to 10 addresses."
          persistent-hint
          @update:model-value="archiveSaved = false"
        />
      </v-card-text>
      <v-card-actions class="px-4 pb-4">
        <span v-if="archiveSaved" class="text-caption text-success">Saved</span>
        <v-spacer />
        <v-btn color="primary" variant="flat" :loading="savingArchiveRecipients" @click="saveArchiveRecipients">
          Save copy recipients
        </v-btn>
      </v-card-actions>
    </v-card>
    </template>
  </v-container>
</template>

<style scoped>
.role-button { min-width: 96px; justify-content: space-between; border: 1px solid rgba(var(--v-border-color), .45); }
.role-caret { margin-left: 10px; font-size: 17px; line-height: 1; opacity: .9; transform: translateY(-1px); }
</style>
