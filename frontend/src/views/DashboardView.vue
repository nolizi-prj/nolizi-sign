<script setup lang="ts">
/**
 * Home: an inbox first, an admin console second.
 *
 * Everyone sees their personal queue ("Waiting for my signature" action
 * cards) and the DocuSign-style envelope browser (EnvelopeBrowser: Inbox /
 * Sent / Completed / Action required views over one table with search and
 * filters), fed from `GET /submissions?mine=sign` and — for senders —
 * `?mine=sent`. Templates live on their own page (top-nav "Templates");
 * the dashboard only loads their names for the browser's "From template"
 * menu. Remind/cancel state and dialogs stay here; the browser emits.
 */
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import http, { extractError } from "../utils/http";
import { useAuthStore } from "../store/auth";
import { useUiStore } from "../store/ui";
import { displayRole, formatDate } from "../utils/labels";
import { actionRequired } from "../utils/envelopes";
import EnvelopeBrowser from "../components/EnvelopeBrowser.vue";
import type { SubmissionOut, TemplateOut } from "../types";

const auth = useAuthStore();
const ui = useUiStore();
const router = useRouter();

const loading = ref(true);
const errorMessage = ref<string | null>(null);

const signList = ref<SubmissionOut[]>([]);
const sentList = ref<SubmissionOut[]>([]);
const templates = ref<TemplateOut[]>([]);

// Same rule as the browser's "Action required" view (utils/envelopes.ts):
// pending, I'm a signer (not CC), it's my turn, and I haven't archived it —
// so the cards, the greeting count, and the sidebar badge always agree.
const waitingForSignature = computed(() => signList.value.filter(actionRequired));

const greeting = computed(() => {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
});

const firstName = computed(() => auth.me?.name.split(" ")[0] ?? "");

const queueSubtitle = computed(() => {
  const n = waitingForSignature.value.length;
  if (n === 0) return "You're all caught up — nothing needs your signature.";
  if (n === 1) return "1 document is waiting for your signature.";
  return `${n} documents are waiting for your signature.`;
});

function myFieldSummary(submission: SubmissionOut): string {
  const me = submission.submitters.find((s) => s.id === submission.my_submitter_id);
  if (!me) return "";
  // One-off envelopes have internal signer-N roles — never shown.
  const role = displayRole(submission.template, me.role);
  return role ? `as ${role}` : "";
}

async function loadAll(): Promise<void> {
  loading.value = true;
  errorMessage.value = null;
  try {
    const requests: [Promise<SubmissionOut[]>, Promise<SubmissionOut[]>, Promise<TemplateOut[]>] = [
      http.get<SubmissionOut[]>("/submissions", { params: { mine: "sign" } }).then((r) => r.data),
      auth.canSend
        ? http.get<SubmissionOut[]>("/submissions", { params: { mine: "sent" } }).then((r) => r.data)
        : Promise.resolve([]),
      auth.canSend ? http.get<TemplateOut[]>("/templates").then((r) => r.data) : Promise.resolve([]),
    ];
    const [sign, sent, tpl] = await Promise.all(requests);
    signList.value = sign;
    sentList.value = sent;
    templates.value = tpl;
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    loading.value = false;
  }
}

onMounted(loadAll);

// --- Sent envelopes: cancel / remind ---------------------------------------------------

const cancelTarget = ref<SubmissionOut | null>(null);
const cancelling = ref(false);
const cancelReason = ref("");

async function confirmCancel(): Promise<void> {
  if (!cancelTarget.value) return;
  cancelling.value = true;
  try {
    const reason = cancelReason.value.trim();
    await http.post(`/submissions/${cancelTarget.value.id}/cancel`, reason ? { reason } : {});
    cancelTarget.value = null;
    cancelReason.value = "";
    ui.toast("Envelope voided — everyone involved has been notified.");
    await loadAll();
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    cancelling.value = false;
  }
}

// --- archive (per-user hide) -------------------------------------------------

/** Archiving your own still-pending envelope prompts about voiding it too —
 *  signers would otherwise keep signing something you've hidden. */
const archivePrompt = ref<SubmissionOut | null>(null);
const archiving = ref(false);

function onArchive(submission: SubmissionOut): void {
  const isMyPending = submission.status === "pending" && submission.sender.id === auth.me?.id;
  if (isMyPending) {
    archivePrompt.value = submission;
  } else {
    void archiveEnvelope(submission, false);
  }
}

async function archiveEnvelope(submission: SubmissionOut, alsoVoid: boolean): Promise<void> {
  archiving.value = true;
  try {
    if (alsoVoid) await http.post(`/submissions/${submission.id}/cancel`);
    await http.post(`/submissions/${submission.id}/archive`);
    archivePrompt.value = null;
    ui.toast(alsoVoid ? "Envelope voided and archived." : "Envelope archived.");
    await loadAll();
  } catch (err) {
    errorMessage.value = extractError(err);
    archivePrompt.value = null;
  } finally {
    archiving.value = false;
  }
}

async function unarchiveEnvelope(submission: SubmissionOut): Promise<void> {
  try {
    await http.post(`/submissions/${submission.id}/unarchive`);
    ui.toast("Envelope restored to your lists.");
    await loadAll();
  } catch (err) {
    errorMessage.value = extractError(err);
  }
}

async function remind(submission: SubmissionOut): Promise<void> {
  try {
    await http.post(`/submissions/${submission.id}/remind`);
    ui.toast("Reminders sent to signers who haven't signed yet.");
    await loadAll();
  } catch (err) {
    errorMessage.value = extractError(err);
  }
}

// --- Copy (same behavior as the detail page's Copy button) -------------------

const copying = ref(false);

/** DocuSign-style "Copy" from the row menu: new draft with the same document,
 *  recipients, and settings — then jump to the wizard to review and send. */
async function copyEnvelope(submission: SubmissionOut): Promise<void> {
  if (copying.value) return;
  copying.value = true;
  try {
    const { data } = await http.post<SubmissionOut>(`/submissions/${submission.id}/copy`);
    ui.toast("Copy created as a draft — review and edit it before sending.");
    await router.push({ name: "send-draft", params: { draftId: String(data.id) } });
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    copying.value = false;
  }
}

// --- drafts: send / delete ---------------------------------------------------

async function sendDraft(submission: SubmissionOut): Promise<void> {
  try {
    await http.post(`/submissions/${submission.id}/send`);
    ui.toast("Envelope sent — signers have been emailed.");
    await loadAll();
  } catch (err) {
    errorMessage.value = extractError(err);
  }
}

const deleteDraftTarget = ref<SubmissionOut | null>(null);
const deletingDraft = ref(false);

async function confirmDeleteDraft(): Promise<void> {
  if (!deleteDraftTarget.value) return;
  deletingDraft.value = true;
  try {
    await http.delete(`/submissions/${deleteDraftTarget.value.id}`);
    deleteDraftTarget.value = null;
    ui.toast("Draft deleted.");
    await loadAll();
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    deletingDraft.value = false;
  }
}
</script>

<template>
  <v-container class="dashboard">
    <v-alert v-if="errorMessage" type="error" closable class="mb-4" @click:close="errorMessage = null">
      {{ errorMessage }}
    </v-alert>

    <v-progress-linear v-if="loading" indeterminate class="mb-4" />

    <!-- Greeting + personal queue -->
    <div class="mb-2 mt-2">
      <h1 class="text-h5">{{ greeting }}{{ firstName ? `, ${firstName}` : "" }}</h1>
      <p class="text-medium-emphasis mb-0">{{ queueSubtitle }}</p>
    </div>

    <v-row v-if="waitingForSignature.length > 0" class="mb-2 mt-1">
      <v-col v-for="submission in waitingForSignature" :key="submission.id" cols="12" md="6">
        <v-card variant="outlined" class="queue-card">
          <v-card-item>
            <v-card-title class="text-subtitle-1">{{ submission.title }}</v-card-title>
            <v-card-subtitle>
              From {{ submission.sender.name }} · sent {{ formatDate(submission.created_at) }}
              <template v-if="myFieldSummary(submission)"> · {{ myFieldSummary(submission) }}</template>
            </v-card-subtitle>
          </v-card-item>
          <v-card-actions>
            <v-chip color="warning" size="small" variant="tonal">Waiting on you</v-chip>
            <v-spacer />
            <v-btn
              color="primary"
              variant="flat"
              :to="{ name: 'sign', params: { submitterId: String(submission.my_submitter_id) } }"
            >
              Review &amp; sign
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>

    <!-- Envelope browser: one DocuSign-style table for inbox + sent + completed -->
    <EnvelopeBrowser
      class="mb-6 mt-4"
      :sign="signList"
      :sent="sentList"
      :templates="templates"
      :loading="loading"
      :can-send="auth.canSend"
      :my-id="auth.me?.id ?? null"
      @remind="remind"
      @cancel="cancelTarget = $event"
      @archive="onArchive"
      @unarchive="unarchiveEnvelope"
      @send="sendDraft"
      @copy="copyEnvelope"
      @delete-draft="deleteDraftTarget = $event"
    />

    <!-- Cancel confirmation -->
    <v-dialog :model-value="cancelTarget !== null" max-width="480" @update:model-value="(v: boolean) => { if (!v) cancelTarget = null }">
      <v-card v-if="cancelTarget">
        <v-card-title>Void envelope?</v-card-title>
        <v-card-text>
          <p class="mb-3">
            This will void "{{ cancelTarget.title }}" for all signers — no further signing is
            possible. Everyone who was contacted will be notified. This can't be undone.
          </p>
          <v-textarea
            v-model="cancelReason"
            label="Reason (optional)"
            hint="Shared with recipients and kept in the envelope history."
            persistent-hint
            rows="2"
            auto-grow
            counter="500"
            maxlength="500"
            :disabled="cancelling"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="cancelTarget = null">Back</v-btn>
          <v-btn color="error" :loading="cancelling" @click="confirmCancel">Void envelope</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete-draft confirmation -->
    <v-dialog :model-value="deleteDraftTarget !== null" max-width="440" @update:model-value="(v: boolean) => { if (!v) deleteDraftTarget = null }">
      <v-card v-if="deleteDraftTarget">
        <v-card-title>Delete draft?</v-card-title>
        <v-card-text>
          "{{ deleteDraftTarget.title }}" hasn't been sent to anyone. Deleting it removes the
          draft entirely — this can't be undone.
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" :disabled="deletingDraft" @click="deleteDraftTarget = null">Back</v-btn>
          <v-btn color="error" :loading="deletingDraft" @click="confirmDeleteDraft">Delete draft</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Archive-a-pending-envelope prompt: hide only, or void it too -->
    <v-dialog :model-value="archivePrompt !== null" max-width="520" @update:model-value="(v: boolean) => { if (!v) archivePrompt = null }">
      <v-card v-if="archivePrompt">
        <v-card-title>Archive this envelope?</v-card-title>
        <v-card-text>
          "{{ archivePrompt.title }}" is still in progress. Archiving only hides it from your own
          lists — signers can keep signing. You can also void it first so no further signing is
          possible.
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" :disabled="archiving" @click="archivePrompt = null">Back</v-btn>
          <v-btn
            color="error"
            variant="text"
            :loading="archiving"
            @click="archiveEnvelope(archivePrompt, true)"
          >
            Void &amp; archive
          </v-btn>
          <v-btn color="primary" variant="flat" :loading="archiving" @click="archiveEnvelope(archivePrompt, false)">
            Archive only
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<style scoped>
.dashboard {
  max-width: 1400px;
}

.queue-card {
  border-color: rgba(180, 83, 9, 0.4);
}

.empty-state {
  text-align: center;
  color: rgba(var(--v-theme-on-surface), 0.6);
  padding-top: 24px;
  padding-bottom: 24px;
}

</style>
