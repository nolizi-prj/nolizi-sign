<script setup lang="ts">
/**
 * Templates page (top-nav "Templates", senders only): the reusable-document
 * list that used to sit at the bottom of the dashboard — same table, same
 * Send / Edit fields / Archive actions, plus New template.
 */
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import http, { extractError } from "../utils/http";
import { useAuthStore } from "../store/auth";
import { useUiStore } from "../store/ui";
import NewTemplateDialog from "../components/NewTemplateDialog.vue";
import type { TemplateOut } from "../types";

const auth = useAuthStore();
const ui = useUiStore();
const router = useRouter();
const route = useRoute();

const loading = ref(true);
const errorMessage = ref<string | null>(null);
const templates = ref<TemplateOut[]>([]);
const archivedView = ref(false);

async function load(): Promise<void> {
  loading.value = true;
  errorMessage.value = null;
  try {
    const { data } = await http.get<TemplateOut[]>("/templates", {
      params: archivedView.value ? { archived: true } : undefined,
    });
    templates.value = data;
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  // Dashboard hero's "Create a template" deep-links straight into the dialog.
  if (route.query.new === "1") newTemplateDialog.value = true;
  void load();
});

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

async function restoreTemplate(template: TemplateOut): Promise<void> {
  try {
    await http.post(`/templates/${template.id}/unarchive`);
    ui.toast("Template restored.");
    await load();
  } catch (err) {
    errorMessage.value = extractError(err);
  }
}

const emptyCopy = computed(() => archivedView.value
  ? "Archived templates are collected here and can be restored whenever you need them."
  : "Templates are reusable documents with signature fields — upload a PDF or Word file to create one.");

function goSend(template: TemplateOut): void {
  void router.push({ name: "send", params: { templateId: String(template.id) } });
}

function goBuild(template: TemplateOut): void {
  void router.push({ name: "template-builder", params: { id: String(template.id) } });
}

/** Edit/archive/share are owner-or-admin actions; shared templates from
 *  someone else are send-only (the server enforces this regardless). */
function isMine(template: TemplateOut): boolean {
  return template.owner.id === auth.me?.id;
}

interface TemplateShare { email: string; permission: "use"; status: "pending" | "accepted"; created_at: string }
const shareTarget = ref<TemplateOut | null>(null);
const shareEmails = ref<string[]>([]);
const shareRows = ref<TemplateShare[]>([]);
const loadingShares = ref(false);
const savingShares = ref(false);

async function openShare(template: TemplateOut): Promise<void> {
  shareTarget.value = template;
  loadingShares.value = true;
  try {
    const { data } = await http.get<TemplateShare[]>(`/templates/${template.id}/sharing`);
    shareRows.value = data;
    shareEmails.value = data.map((share) => share.email);
  } catch (err) {
    errorMessage.value = extractError(err);
    shareTarget.value = null;
  } finally {
    loadingShares.value = false;
  }
}

async function saveShares(): Promise<void> {
  if (!shareTarget.value) return;
  savingShares.value = true;
  try {
    await http.put(`/templates/${shareTarget.value.id}/sharing`, { emails: shareEmails.value });
    ui.toast(shareEmails.value.length ? "Template access updated." : "Template is private again.");
    shareTarget.value = null;
    await load();
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    savingShares.value = false;
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
          <v-btn-toggle
            v-model="archivedView"
            mandatory
            density="compact"
            variant="outlined"
            class="mr-3"
            @update:model-value="load"
          >
            <v-btn :value="false">Active</v-btn>
            <v-btn :value="true" prepend-icon="mdi-archive-outline">Archived</v-btn>
          </v-btn-toggle>
          <v-btn v-if="!archivedView" color="primary" prepend-icon="mdi-plus" @click="newTemplateDialog = true">New template</v-btn>
        </v-card-title>
        <v-card-text v-if="!loading && templates.length === 0" class="empty-state">
          <v-icon icon="mdi-file-document-plus-outline" size="40" class="mb-2" aria-hidden="true" />
          <p class="mb-2">
            {{ emptyCopy }}
          </p>
          <v-btn v-if="!archivedView" color="primary" variant="tonal" @click="newTemplateDialog = true">
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
            <v-chip v-if="isMine(item)" size="small" :color="item.shared ? 'primary' : undefined" variant="tonal">
              {{ item.shared ? "Shared with specific people" : "Private" }}
            </v-chip>
            <v-chip v-else size="small" variant="tonal" prepend-icon="mdi-account-outline">
              Shared by {{ item.owner.name }}
            </v-chip>
          </template>

          <template #item.actions="{ item }">
            <v-btn v-if="archivedView" size="small" variant="text" color="primary" prepend-icon="mdi-archive-arrow-up-outline" @click="restoreTemplate(item)">Restore</v-btn>
            <template v-else>
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
              <v-btn size="small" variant="text" prepend-icon="mdi-share-variant-outline" @click="openShare(item)">Share</v-btn>
              <v-btn size="small" variant="text" @click="goBuild(item)">Edit fields</v-btn>
              <v-btn size="small" variant="text" color="error" @click="archiveTarget = item">Archive</v-btn>
            </template>
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

    <v-dialog :model-value="shareTarget !== null" max-width="560" @update:model-value="(v: boolean) => { if (!v) shareTarget = null }">
      <v-card v-if="shareTarget">
        <v-card-title>Share “{{ shareTarget.name }}”</v-card-title>
        <v-card-text>
          <p class="text-body-2 text-medium-emphasis mb-4">
            Only the email addresses below can use this template. They cannot edit or delete the original, and they will not see your envelopes.
          </p>
          <v-combobox
            v-model="shareEmails"
            label="People to share with"
            placeholder="name@company.com"
            multiple chips closable-chips clearable
            :loading="loadingShares"
            :counter="50"
            hint="Type an email address and press Enter. Remove an address to revoke future use."
            persistent-hint
          />
          <v-alert type="info" variant="tonal" density="compact" class="mt-4">
            People without an account will be invited. Access is bound to the verified email address entered here.
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="shareTarget = null">Cancel</v-btn>
          <v-btn color="primary" variant="flat" :loading="savingShares" :disabled="loadingShares" @click="saveShares">Save access</v-btn>
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
