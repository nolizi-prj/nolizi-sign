<script setup lang="ts">
/**
 * Templates page (top-nav "Templates", senders only): the reusable-document
 * list that used to sit at the bottom of the dashboard — same table, same
 * Send / Edit fields / Archive actions, plus New template.
 */
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import http, { extractError } from "../utils/http";
import { useAuthStore } from "../store/auth";
import { useUiStore } from "../store/ui";
import NewTemplateDialog from "../components/NewTemplateDialog.vue";
import type { TemplateOut } from "../types";

const auth = useAuthStore();
const ui = useUiStore();
const router = useRouter();

const loading = ref(true);
const errorMessage = ref<string | null>(null);
const templates = ref<TemplateOut[]>([]);

async function load(): Promise<void> {
  loading.value = true;
  errorMessage.value = null;
  try {
    const { data } = await http.get<TemplateOut[]>("/templates");
    templates.value = data;
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    loading.value = false;
  }
}

onMounted(load);

const archiveTarget = ref<TemplateOut | null>(null);
const archiving = ref(false);

async function confirmArchive(): Promise<void> {
  if (!archiveTarget.value) return;
  archiving.value = true;
  try {
    await http.post(`/templates/${archiveTarget.value.id}/archive`);
    archiveTarget.value = null;
    ui.toast("Template archived.");
    await load();
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    archiving.value = false;
  }
}

function goSend(template: TemplateOut): void {
  void router.push({ name: "send", params: { templateId: String(template.id) } });
}

function goBuild(template: TemplateOut): void {
  void router.push({ name: "template-builder", params: { id: String(template.id) } });
}

/** Edit/archive/share are owner-or-admin actions; shared templates from
 *  someone else are send-only (the server enforces this regardless). */
function isMine(template: TemplateOut): boolean {
  return template.owner.id === auth.me?.id || auth.isAdmin;
}

const togglingShareId = ref<number | null>(null);

async function toggleShared(template: TemplateOut): Promise<void> {
  togglingShareId.value = template.id;
  try {
    await http.put(`/templates/${template.id}/sharing`, { shared: !template.shared });
    ui.toast(
      template.shared
        ? "Template unshared — only you can send from it now."
        : "Template shared — every sender can now send from it.",
    );
    await load();
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    togglingShareId.value = null;
  }
}

const copyingId = ref<number | null>(null);

/** Copy any visible template (shared ones included) into a private
 *  "Copy of X" owned by the caller, then open its field builder. */
async function copyTemplate(template: TemplateOut): Promise<void> {
  copyingId.value = template.id;
  try {
    const { data } = await http.post<TemplateOut>(`/templates/${template.id}/copy`);
    ui.toast(`Created "${data.name}".`);
    void router.push({ name: "template-builder", params: { id: String(data.id) } });
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    copyingId.value = null;
  }
}

const newTemplateDialog = ref(false);

const headers = [
  { title: "Name", key: "name" },
  { title: "Pages", key: "page_count" },
  { title: "Sharing", key: "sharing", sortable: false },
  { title: "", key: "actions", sortable: false, align: "end" as const },
];
</script>

<template>
  <v-container class="templates-page">
    <v-alert v-if="!auth.canSend && !loading" type="error">
      You don't have permission to manage templates.
    </v-alert>

    <template v-else>
      <v-alert v-if="errorMessage" type="error" closable class="mb-4" @click:close="errorMessage = null">
        {{ errorMessage }}
      </v-alert>

      <v-card variant="flat" border>
        <v-card-title class="d-flex align-center text-subtitle-1">
          <span>Templates</span>
          <v-spacer />
          <v-btn color="primary" prepend-icon="mdi-plus" @click="newTemplateDialog = true">New template</v-btn>
        </v-card-title>
        <v-card-text v-if="!loading && templates.length === 0" class="empty-state">
          <v-icon icon="mdi-file-document-plus-outline" size="40" class="mb-2" aria-hidden="true" />
          <p class="mb-2">
            Templates are reusable documents with signature fields — upload a PDF or Word file to create one.
          </p>
          <v-btn color="primary" variant="tonal" @click="newTemplateDialog = true">
            Create your first template
          </v-btn>
        </v-card-text>
        <v-data-table
          v-else
          :headers="headers"
          :items="templates"
          :loading="loading"
          item-value="id"
          density="comfortable"
        >
          <template #item.sharing="{ item }">
            <v-switch
              v-if="isMine(item)"
              :model-value="item.shared"
              :label="item.shared ? 'Shared' : 'Private'"
              color="primary"
              density="compact"
              hide-details
              :loading="togglingShareId === item.id"
              :disabled="togglingShareId === item.id"
              @update:model-value="toggleShared(item)"
            />
            <v-chip v-else size="small" variant="tonal" prepend-icon="mdi-account-outline">
              Shared by {{ item.owner.name }}
            </v-chip>
          </template>

          <template #item.actions="{ item }">
            <v-btn size="small" variant="text" @click="goSend(item)">Send</v-btn>
            <v-btn
              size="small"
              variant="text"
              :loading="copyingId === item.id"
              @click="copyTemplate(item)"
            >
              Copy
            </v-btn>
            <template v-if="isMine(item)">
              <v-btn size="small" variant="text" @click="goBuild(item)">Edit fields</v-btn>
              <v-btn size="small" variant="text" color="error" @click="archiveTarget = item">Archive</v-btn>
            </template>
          </template>
        </v-data-table>
      </v-card>
    </template>

    <!-- Archive confirmation -->
    <v-dialog :model-value="archiveTarget !== null" max-width="480" @update:model-value="(v: boolean) => { if (!v) archiveTarget = null }">
      <v-card v-if="archiveTarget">
        <v-card-title>Archive template?</v-card-title>
        <v-card-text>
          "{{ archiveTarget.name }}" will no longer be available to send. Existing envelopes are unaffected.
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="archiveTarget = null">Back</v-btn>
          <v-btn color="error" :loading="archiving" @click="confirmArchive">Archive</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <NewTemplateDialog v-model="newTemplateDialog" />
  </v-container>
</template>

<style scoped>
.templates-page {
  max-width: 1000px;
}

.empty-state {
  text-align: center;
  color: rgba(var(--v-theme-on-surface), 0.6);
  padding-top: 24px;
  padding-bottom: 24px;
}
</style>
