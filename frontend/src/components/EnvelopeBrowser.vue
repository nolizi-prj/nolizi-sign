<script setup lang="ts">
/**
 * DocuSign-style envelope browser: a sidebar of views (Inbox, Sent,
 * Completed, Action required) over ONE table with identical columns and
 * actions everywhere, plus keyword search and status / sender / date
 * filters. Replaces the dashboard's two feature-mismatched lists ("My
 * signed documents", "Sent envelopes").
 *
 * Purely presentational over the two lists the dashboard already loads
 * (`mine=sign`, `mine=sent`), merged and deduped here — an envelope can be
 * both (the sender signing their own envelope). All filtering is
 * client-side; the API returns the user's full lists anyway.
 */
import { computed, ref } from "vue";
import {
  envelopeStatusColor,
  envelopeStatusLabel,
  formatDate,
  formatDateTime,
  signerStatusColor,
  signerStatusLabel,
} from "../utils/labels";
import {
  type EnvelopeRow as Row,
  type ViewKey,
  inView,
  matchesSearch,
  normalizeSearch,
  toRow,
} from "../utils/envelopes";
import http, { extractError } from "../utils/http";
import type { AuditEventOut, AuditEventType, SubmissionOut, SubmissionStatus, TemplateOut } from "../types";

const props = defineProps<{
  sign: SubmissionOut[];
  sent: SubmissionOut[];
  /** For the "From template" quick-send menu (names only are used). */
  templates: TemplateOut[];
  loading: boolean;
  canSend: boolean;
  myId: number | null;
}>();

const emit = defineEmits<{
  remind: [submission: SubmissionOut];
  cancel: [submission: SubmissionOut];
  archive: [submission: SubmissionOut];
  unarchive: [submission: SubmissionOut];
  send: [submission: SubmissionOut];
  copy: [submission: SubmissionOut];
  deleteDraft: [submission: SubmissionOut];
}>();

// --- row model (logic lives in utils/envelopes.ts, unit-tested) -------------

const rows = computed<Row[]>(() => {
  const byId = new Map<number, SubmissionOut>();
  for (const s of [...props.sign, ...props.sent]) byId.set(s.id, s);
  return [...byId.values()].map((s) => toRow(s, props.myId));
});

// --- views ------------------------------------------------------------------

const view = ref<ViewKey>("inbox");

const VIEWS: { key: ViewKey; title: string; icon: string; sendersOnly?: boolean }[] = [
  { key: "inbox", title: "Inbox", icon: "mdi-inbox-outline" },
  { key: "drafts", title: "Drafts", icon: "mdi-file-edit-outline", sendersOnly: true },
  { key: "sent", title: "Sent", icon: "mdi-send-outline", sendersOnly: true },
  { key: "completed", title: "Completed", icon: "mdi-check-circle-outline" },
  { key: "action", title: "Action required", icon: "mdi-draw-pen" },
  { key: "expiring", title: "Expiring soon", icon: "mdi-clock-alert-outline" },
  { key: "attention", title: "Needs attention", icon: "mdi-email-alert-outline", sendersOnly: true },
  { key: "archived", title: "Archived", icon: "mdi-archive-outline" },
];

const visibleViews = computed(() => VIEWS.filter((v) => !v.sendersOnly || props.canSend));

function viewCount(key: ViewKey): number {
  return rows.value.filter((r) => inView(r, key)).length;
}

// --- search + filters -------------------------------------------------------

// string | null: Vuetify's clearable ✕ sets the model to null, and calling
// .trim() on that crashed the whole dashboard — normalizeSearch tolerates it.
const search = ref<string | null>("");
const statusFilter = ref<SubmissionStatus | null>(null);
const senderFilter = ref<number | null>(null);
const dateFrom = ref("");
const dateTo = ref("");

const STATUS_ITEMS = (
  ["draft", "pending", "completed", "cancelled", "declined", "expired"] as SubmissionStatus[]
).map((status) => ({ title: envelopeStatusLabel(status), value: status }));

const senderItems = computed(() => {
  const seen = new Map<number, string>();
  for (const row of rows.value) seen.set(row.submission.sender.id, row.submission.sender.name);
  return [...seen.entries()]
    .map(([value, title]) => ({ title, value }))
    .sort((a, b) => a.title.localeCompare(b.title));
});

const filtersActive = computed(
  () =>
    normalizeSearch(search.value) !== "" ||
    statusFilter.value !== null ||
    senderFilter.value !== null ||
    dateFrom.value !== "" ||
    dateTo.value !== "",
);

function clearFilters(): void {
  search.value = "";
  statusFilter.value = null;
  senderFilter.value = null;
  dateFrom.value = "";
  dateTo.value = "";
}

const filteredRows = computed<Row[]>(() => {
  const needle = normalizeSearch(search.value);
  return rows.value.filter((row) => {
    if (!inView(row, view.value)) return false;
    if (needle && !matchesSearch(row, needle)) return false;
    if (statusFilter.value && row.submission.status !== statusFilter.value) return false;
    if (senderFilter.value !== null && row.submission.sender.id !== senderFilter.value) return false;
    // created_at is ISO with time; plain date inputs compare on the date part.
    const sentDate = row.submission.created_at.slice(0, 10);
    if (dateFrom.value && sentDate < dateFrom.value) return false;
    if (dateTo.value && sentDate > dateTo.value) return false;
    return true;
  });
});

// --- table ------------------------------------------------------------------

const headers = [
  { title: "Name", key: "title", value: (row: Row) => row.submission.title },
  { title: "Participants", key: "participants", sortable: false },
  { title: "Status", key: "status", value: (row: Row) => row.submission.status },
  { title: "Last change", key: "lastChange", value: (row: Row) => row.lastChange },
  // nowrap keeps the icon buttons on one line; the content column scrolls
  // horizontally as a last resort instead of clipping.
  { title: "", key: "actions", sortable: false, align: "end" as const, nowrap: true },
];

const EMPTY_TEXT: Record<ViewKey, string> = {
  inbox: "Envelopes sent to you will appear here.",
  drafts: "Envelopes you save as drafts wait here until you send them.",
  sent: "You haven't sent anything for signature yet.",
  completed: "Completed envelopes will appear here with their signed PDFs.",
  action: "You're all caught up — nothing needs your signature.",
  expiring: "Envelopes due within six days will appear here so deadlines don't slip.",
  attention: "Envelopes with a bounced email will appear here — fix the address, then resend.",
  archived: "Envelopes you archive are hidden from your other views and collected here.",
};

/** "Expires <date>" caption for open envelopes and drafts with a deadline —
 *  a draft's (possibly past) deadline will gate its own Send. */
function expiryHint(row: Row): string | null {
  const s = row.submission;
  if ((s.status !== "pending" && s.status !== "draft") || !s.expires_at) return null;
  return `Expires ${formatDate(s.expires_at)}`;
}

// --- download dialog (DocuSign-style "which files" picker) -------------------

const downloadTarget = ref<SubmissionOut | null>(null);
const dlDocument = ref(true);
const dlCertificate = ref(true);

const historyModalOpen = ref(false);
const historySubmission = ref<SubmissionOut | null>(null);
const historyLoading = ref(false);
const historyEvents = ref<AuditEventOut[]>([]);
const historyError = ref<string | null>(null);

let historySeq = 0;

async function openHistoryModal(submission: SubmissionOut): Promise<void> {
  const seq = ++historySeq;
  historySubmission.value = submission;
  historyEvents.value = [];
  historyModalOpen.value = true;
  historyLoading.value = true;
  historyError.value = null;
  try {
    const { data } = await http.get<AuditEventOut[]>(`/submissions/${submission.id}/events`);
    if (seq === historySeq) {
      historyEvents.value = data;
    }
  } catch (err) {
    if (seq === historySeq) {
      historyError.value = extractError(err);
      historyEvents.value = [];
    }
  } finally {
    if (seq === historySeq) {
      historyLoading.value = false;
    }
  }
}

function formatAuditLabel(evt: AuditEventType): string {
  switch (evt) {
    case "created": return "Created draft";
    case "sent": return "Sent envelope";
    case "opened": return "Viewed document";
    case "signed": return "Signed";
    case "completed": return "Completed";
    case "reminded": return "Sent reminder";
    case "cancelled": return "Voided envelope";
    case "declined": return "Declined to sign";
    case "corrected": return "Corrected details";
    case "expired": return "Expired";
    default: return evt;
  }
}

function openDownload(submission: SubmissionOut): void {
  dlDocument.value = true;
  dlCertificate.value = submission.has_certificate;
  downloadTarget.value = submission;
}

/** Same-origin attachment download without leaving the page. */
function triggerDownload(url: string): void {
  const a = document.createElement("a");
  a.href = url;
  a.download = "";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

async function startDownload(): Promise<void> {
  const s = downloadTarget.value;
  if (!s) return;
  if (dlDocument.value) triggerDownload(`/api/files/signed-pdf/${s.id}`);
  if (dlCertificate.value && s.has_certificate) {
    // Browsers drop a second programmatic click fired in the same tick.
    if (dlDocument.value) await new Promise((resolve) => setTimeout(resolve, 400));
    triggerDownload(`/api/files/certificate/${s.id}`);
  }
  downloadTarget.value = null;
}
</script>

<template>
  <v-card variant="flat" border>
    <v-card-title class="d-flex align-center text-subtitle-1">
      <span>Envelopes</span>
      <v-spacer />
      <template v-if="canSend">
        <v-btn color="primary" variant="text" prepend-icon="mdi-send" :to="{ name: 'send' }">
          New envelope
        </v-btn>
        <v-menu>
          <template #activator="{ props: menuProps }">
            <v-btn
              variant="text"
              prepend-icon="mdi-file-document-outline"
              append-icon="mdi-menu-down"
              v-bind="menuProps"
            >
              From template
            </v-btn>
          </template>
          <v-list density="compact">
            <v-list-item
              v-for="template in templates"
              :key="template.id"
              :title="template.name"
              :to="{ name: 'send', params: { templateId: String(template.id) } }"
            />
            <v-list-item
              v-if="templates.length === 0"
              title="No templates yet"
              disabled
            />
            <v-divider />
            <v-list-item
              prepend-icon="mdi-file-document-multiple-outline"
              title="Manage templates"
              :to="{ name: 'templates' }"
            />
          </v-list>
        </v-menu>
      </template>
    </v-card-title>

    <div class="d-flex browser-body">
      <!-- Sidebar views -->
      <nav class="view-rail" aria-label="Envelope views">
        <v-list density="compact" nav>
          <v-list-item
            v-for="v in visibleViews"
            :key="v.key"
            :prepend-icon="v.icon"
            :title="v.title"
            :active="view === v.key"
            color="primary"
            @click="view = v.key"
          >
            <template #append>
              <span class="text-caption text-medium-emphasis">{{ viewCount(v.key) }}</span>
            </template>
          </v-list-item>
        </v-list>
      </nav>

      <div class="flex-grow-1 browser-content">
        <!-- Search + filters -->
        <div class="d-flex flex-wrap align-center filter-bar">
          <v-text-field
            v-model="search"
            placeholder="Search by title, person, or envelope ID"
            prepend-inner-icon="mdi-magnify"
            density="compact"
            hide-details
            clearable
            class="filter-search"
          />
          <v-select
            v-model="statusFilter"
            :items="STATUS_ITEMS"
            label="Status"
            density="compact"
            hide-details
            clearable
            class="filter-select"
          />
          <v-select
            v-model="senderFilter"
            :items="senderItems"
            label="Sender"
            density="compact"
            hide-details
            clearable
            class="filter-select"
          />
          <v-text-field
            v-model="dateFrom"
            type="date"
            label="Sent from"
            density="compact"
            hide-details
            class="filter-date"
          />
          <v-text-field
            v-model="dateTo"
            type="date"
            label="Sent to"
            density="compact"
            hide-details
            class="filter-date"
          />
          <v-btn v-if="filtersActive" variant="text" size="small" @click="clearFilters">Clear all</v-btn>
        </div>

        <v-card-text v-if="!loading && filteredRows.length === 0" class="empty-state">
          <v-icon icon="mdi-email-open-outline" size="40" class="mb-2" aria-hidden="true" />
          <p class="mb-2">
            {{ filtersActive ? "Nothing matches your search or filters." : EMPTY_TEXT[view] }}
          </p>
          <!-- Distinct label from the header's "New envelope": two identically
               named links on one page trip strict accessible-name lookups. -->
          <v-btn
            v-if="!filtersActive && canSend && ['inbox', 'drafts', 'sent', 'completed'].includes(view)"
            color="primary"
            variant="tonal"
            prepend-icon="mdi-send"
            :to="{ name: 'send' }"
          >
            Send your first envelope
          </v-btn>
        </v-card-text>

        <v-data-table
          v-else
          :headers="headers"
          :items="filteredRows"
          :loading="loading"
          :sort-by="[{ key: 'lastChange', order: 'desc' }]"
          item-value="submission.id"
          density="comfortable"
        >
          <template #item.title="{ item }">
            <router-link
              class="envelope-link"
              :to="{ name: 'envelope-detail', params: { id: String(item.submission.id) } }"
            >
              {{ item.submission.title }}
            </router-link>
            <v-chip
              v-if="item.isSender && item.hasBounced"
              color="error"
              size="x-small"
              variant="tonal"
              class="ml-2"
              prepend-icon="mdi-email-alert"
            >
              Needs attention
            </v-chip>
            <div class="text-caption text-medium-emphasis">
              From {{ item.submission.sender.name }}
              <template v-if="expiryHint(item)"> · {{ expiryHint(item) }}</template>
            </div>
          </template>

          <template #item.participants="{ item }">
            <v-chip
              v-for="submitter in item.submission.submitters"
              :key="submitter.id"
              :color="submitter.is_cc ? undefined : signerStatusColor(submitter.status)"
              size="small"
              variant="tonal"
              class="mr-1 mb-1"
            >
              {{ submitter.user.name }} ·
              {{ submitter.is_cc ? "CC" : signerStatusLabel(submitter.status, item.submission.status) }}
            </v-chip>
          </template>

          <template #item.status="{ item }">
            <v-chip v-if="item.waitingOnMe" color="warning" size="small" variant="tonal">
              Waiting on you
            </v-chip>
            <v-chip v-else-if="item.waitingForTurn" size="small" variant="tonal">
              Waiting for turn
            </v-chip>
            <v-chip v-else :color="envelopeStatusColor(item.submission.status)" size="small" variant="tonal">
              {{ envelopeStatusLabel(item.submission.status) }}
            </v-chip>
          </template>

          <template #item.lastChange="{ item }">
            <span :title="formatDateTime(item.lastChange)">{{ formatDate(item.lastChange) }}</span>
          </template>

          <template #item.actions="{ item }">
            <!-- canSend: a sender whose permission was later revoked keeps
                 Delete (backend allows cleaning up own drafts) but loses
                 Send/Edit/Copy, matching the detail page's gating. -->
            <template v-if="item.isSender && canSend && item.submission.status === 'draft'">
              <v-btn size="small" color="primary" variant="flat" @click="emit('send', item.submission)">
                Send
              </v-btn>
              <v-btn
                size="small"
                variant="text"
                prepend-icon="mdi-pencil"
                :to="{ name: 'send-draft', params: { draftId: String(item.submission.id) } }"
              >
                Edit
              </v-btn>
            </template>
            <v-btn
              v-else-if="item.waitingOnMe"
              size="small"
              color="primary"
              variant="flat"
              :to="{ name: 'sign', params: { submitterId: String(item.submission.my_submitter_id) } }"
            >
              Sign now
            </v-btn>
            <v-btn
              v-else-if="item.submission.status === 'completed'"
              size="small"
              variant="tonal"
              color="primary"
              prepend-icon="mdi-download"
              :aria-label="`Download ${item.submission.title}`"
              @click="openDownload(item.submission)"
            >
              Download
            </v-btn>
            <v-tooltip text="History & details">
              <template #activator="{ props: tipProps }">
                <v-btn
                  icon="mdi-history"
                  size="small"
                  variant="text"
                  :to="{ name: 'envelope-detail', params: { id: String(item.submission.id) } }"
                  :aria-label="`History for ${item.submission.title}`"
                  v-bind="tipProps"
                />
              </template>
            </v-tooltip>
            <v-menu>
              <template #activator="{ props: menuProps }">
                <v-btn
                  icon="mdi-dots-vertical"
                  size="small"
                  variant="text"
                  :aria-label="`More actions for ${item.submission.title}`"
                  v-bind="menuProps"
                />
              </template>
              <v-list density="compact">
                <v-list-item
                  prepend-icon="mdi-file-eye-outline"
                  title="View document"
                  :href="`/api/files/document-preview/${item.submission.id}`"
                  target="_blank"
                />
                <v-list-item
                  prepend-icon="mdi-history"
                  title="Audit history"
                  @click="openHistoryModal(item.submission)"
                />
                <v-list-item
                  v-if="item.isSender && canSend"
                  prepend-icon="mdi-content-copy"
                  title="Copy"
                  @click="emit('copy', item.submission)"
                />
                <v-list-item
                  v-if="!item.submission.archived_by_me"
                  prepend-icon="mdi-archive-outline"
                  title="Archive"
                  @click="emit('archive', item.submission)"
                />
                <v-list-item
                  v-else
                  prepend-icon="mdi-archive-arrow-up-outline"
                  title="Unarchive"
                  @click="emit('unarchive', item.submission)"
                />
                <template v-if="item.isSender && item.submission.status === 'pending'">
                  <v-list-item
                    prepend-icon="mdi-bell-ring-outline"
                    title="Remind signers"
                    @click="emit('remind', item.submission)"
                  />
                  <v-list-item
                    prepend-icon="mdi-cancel"
                    title="Void envelope"
                    class="text-error"
                    @click="emit('cancel', item.submission)"
                  />
                </template>
                <template v-if="item.isSender && item.submission.status === 'draft'">
                  <v-list-item
                    prepend-icon="mdi-delete-outline"
                    title="Delete draft"
                    class="text-error"
                    @click="emit('deleteDraft', item.submission)"
                  />
                </template>
              </v-list>
            </v-menu>
          </template>
        </v-data-table>
      </div>
    </div>

    <!-- Download picker: which files, DocuSign-style. Combined-PDF and zip
         delivery are Phase 3 (docs/ux/similar-ux-plan.md). -->
    <v-dialog
      :model-value="downloadTarget !== null"
      max-width="440"
      @update:model-value="(v: boolean) => { if (!v) downloadTarget = null }"
    >
      <v-card v-if="downloadTarget">
        <v-card-title>Download "{{ downloadTarget.title }}"</v-card-title>
        <v-card-text class="pb-0">
          <v-checkbox v-model="dlDocument" label="Signed document (PDF)" density="compact" hide-details />
          <v-checkbox
            v-model="dlCertificate"
            label="Certificate of completion (PDF)"
            density="compact"
            hide-details
            :disabled="!downloadTarget.has_certificate"
          />
          <p v-if="!downloadTarget.has_certificate" class="text-caption text-medium-emphasis mt-1 mb-0">
            This envelope's certificate page is inside the signed PDF itself.
          </p>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="downloadTarget = null">Cancel</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            prepend-icon="mdi-download"
            :disabled="!dlDocument && !(dlCertificate && downloadTarget.has_certificate)"
            @click="startDownload"
          >
            Download
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Audit History In-Modal Timeline -->
    <v-dialog
      :model-value="historyModalOpen"
      max-width="560"
      @update:model-value="(v: boolean) => { if (!v) historyModalOpen = false }"
    >
      <v-card v-if="historySubmission">
        <v-card-title class="d-flex align-center">
          <v-icon icon="mdi-history" class="mr-2" color="primary" />
          <span>Audit History: "{{ historySubmission.title }}"</span>
        </v-card-title>
        <v-card-text>
          <v-progress-linear v-if="historyLoading" indeterminate class="mb-3" />
          <v-alert v-if="historyError" type="error" density="compact" class="mb-3">{{ historyError }}</v-alert>
          <div v-else-if="!historyLoading && historyEvents.length === 0" class="text-caption text-medium-emphasis text-center py-4">
            No audit events recorded yet.
          </div>
          <v-list v-else density="compact" class="history-event-list">
            <v-list-item
              v-for="(event, idx) in historyEvents"
              :key="idx"
              :title="formatAuditLabel(event.event)"
              :subtitle="`${formatDateTime(event.created_at)}${event.actor ? ` · ${event.actor.name}` : ''}`"
            >
              <template #prepend>
                <v-icon
                  :icon="event.event === 'opened' ? 'mdi-eye' : event.event === 'sent' ? 'mdi-send' : event.event === 'declined' ? 'mdi-close-circle' : event.event === 'created' ? 'mdi-file-plus' : 'mdi-circle-small'"
                  :color="event.event === 'opened' ? 'primary' : event.event === 'declined' || event.event === 'cancelled' ? 'error' : 'medium-emphasis'"
                  size="small"
                />
              </template>
            </v-list-item>
          </v-list>
        </v-card-text>
        <v-card-actions class="pa-3">
          <v-spacer />
          <v-btn variant="text" :to="{ name: 'envelope-detail', params: { id: String(historySubmission.id) } }" prepend-icon="mdi-open-in-new">
            Full Details
          </v-btn>
          <v-btn color="primary" variant="tonal" @click="historyModalOpen = false">Close</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<style scoped>
.browser-body {
  align-items: flex-start;
}

.view-rail {
  width: 190px;
  flex: none;
  border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  align-self: stretch;
}

.browser-content {
  min-width: 0;
  overflow-x: auto;
}

.filter-bar {
  gap: 8px;
  padding: 12px 16px 4px;
}

.filter-search {
  min-width: 180px;
  flex: 1 1 180px;
}

.filter-select {
  width: 132px;
  flex: none;
}

.filter-date {
  width: 148px;
  flex: none;
}

.empty-state {
  text-align: center;
  color: rgba(var(--v-theme-on-surface), 0.6);
  padding-top: 24px;
  padding-bottom: 24px;
}

.envelope-link {
  color: rgb(var(--v-theme-primary));
  text-decoration: none;
  font-weight: 500;
}

.envelope-link:hover {
  text-decoration: underline;
}

/* Sidebar collapses to a chip row on small screens. */
@media (max-width: 700px) {
  .browser-body {
    flex-direction: column;
  }

  .view-rail {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  }

  .view-rail :deep(.v-list) {
    display: flex;
    flex-wrap: wrap;
  }
}
</style>
