<script setup lang="ts">
/**
 * Envelope detail: everything a sender needs to answer "where is this
 * stuck and what can I do about it" — per-signer status rows, the audit
 * timeline (GET /submissions/{id}/events, visible to any party to the
 * envelope), remind / cancel, a view of the underlying document at any
 * status (the unsigned PDF), the signed-PDF and certificate downloads,
 * and the retry-completion recovery banner for envelopes stuck "pending"
 * after everyone signed (a stamping failure — see backend
 * retry_completion docstring).
 *
 * Non-sender signers can open the page too (GET /submissions/{id} allows
 * it); they see the timeline and downloads, just not the admin actions.
 */
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import http, { extractError } from "../utils/http";
import { UPLOAD_ACCEPT } from "../utils/uploads";
import { useAuthStore } from "../store/auth";
import { useUiStore } from "../store/ui";
import {
  displayRole,
  envelopeStatusColor,
  envelopeStatusLabel,
  formatDate,
  formatDateTime,
  signerStatusColor,
  signerStatusLabel,
  timeAgo,
  userLabel,
} from "../utils/labels";
import type {
  AuditEventOut,
  FormDataOut,
  SubmissionOut,
  SubmitterOut,
  TemplateOut,
  User,
} from "../types";

const props = defineProps<{ id: string }>();
const auth = useAuthStore();
const ui = useUiStore();
const router = useRouter();

const loading = ref(true);
const errorMessage = ref<string | null>(null);
const submission = ref<SubmissionOut | null>(null);
const events = ref<AuditEventOut[]>([]);
const eventsAvailable = ref(false);

const isSender = computed(() => submission.value?.sender.id === auth.me?.id);
const canManage = computed(() => isSender.value || auth.isAdmin);
const isDraft = computed(() => submission.value?.status === "draft");
/** A draft whose deadline already passed can't be dispatched — the send
 *  endpoint 409s. Editing the draft clears/replaces the date. */
const draftExpiryPassed = computed(
  () =>
    isDraft.value &&
    !!submission.value?.expires_at &&
    new Date(submission.value.expires_at).getTime() <= Date.now(),
);
/** Title/message and signer corrections are only meaningful while nothing's final yet. */
const canCorrect = computed(
  () => (submission.value?.status === "pending" || isDraft.value) && canManage.value,
);

/** DocuSign's rule: the document can only be swapped while nobody has
 *  signed — a signature must never end up on a document its signer never saw. */
const canReplaceDocument = computed(
  () =>
    canCorrect.value &&
    !(submission.value?.submitters ?? []).some((s) => !s.is_cc && s.status === "completed"),
);

/** All signers done but the envelope never flipped to completed → stamping failed.
 *  CC rows never sign (their status stays pending), so they're ignored. */
const stuck = computed(() => {
  const s = submission.value;
  if (!s || s.status !== "pending") return false;
  const signers = s.submitters.filter((x) => !x.is_cc);
  return signers.length > 0 && signers.every((x) => x.status === "completed");
});

// --- signing order ----------------------------------------------------------

const isOrdered = computed(() => (submission.value?.submitters ?? []).some((s) => s.order_index > 0));

/** Submitters sorted for display: signing order first (stable for the unordered case). */
const displaySubmitters = computed(() =>
  (submission.value?.submitters ?? []).slice().sort((a, b) => a.order_index - b.order_index),
);

/** The order group whose turn it is (mirrors the backend's active_order: signers only). */
const activeOrderIndex = computed<number | null>(() => {
  const pending = (submission.value?.submitters ?? []).filter((s) => !s.is_cc && s.status !== "completed");
  return pending.length > 0 ? Math.min(...pending.map((s) => s.order_index)) : null;
});

function waitingForTurn(signer: SubmissionOut["submitters"][number]): boolean {
  return (
    isOrdered.value &&
    submission.value?.status === "pending" &&
    signer.status !== "completed" &&
    activeOrderIndex.value !== null &&
    signer.order_index > activeOrderIndex.value
  );
}

/** Status chip text for a CC row: what their copy is waiting on, if anything. */
function ccStatusLabel(cc: SubmissionOut["submitters"][number]): string {
  if (submission.value?.status === "completed") return "Received signed PDF";
  if (submission.value?.status === "draft") return "Not sent yet";
  if (cc.email_status != null) return "Copy sent";
  return "Copy queued";
}

// Sender/admin only (the API 403s recipients); fetched alongside the rest
// and simply absent for everyone else.
const formData = ref<FormDataOut | null>(null);

async function load(): Promise<void> {
  loading.value = true;
  errorMessage.value = null;
  try {
    // Fetched together — the timeline depends only on the id. It's visible
    // to any party to the envelope (sender or signer, DocuSign-style); a
    // 403 for anyone else just hides the section. Same deal for form data
    // (sender/admin only, and 409 on drafts).
    const [submissionRes, eventsRes, formDataRes] = await Promise.allSettled([
      http.get<SubmissionOut>(`/submissions/${props.id}`),
      http.get<AuditEventOut[]>(`/submissions/${props.id}/events`),
      http.get<FormDataOut>(`/submissions/${props.id}/form-data`),
    ]);
    if (submissionRes.status === "rejected") throw submissionRes.reason;
    submission.value = submissionRes.value.data;
    eventsAvailable.value = eventsRes.status === "fulfilled";
    events.value = eventsRes.status === "fulfilled" ? eventsRes.value.data : [];
    formData.value = formDataRes.status === "fulfilled" ? formDataRes.value.data : null;
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    loading.value = false;
  }
}

onMounted(load);

// --- actions ---------------------------------------------------------------

const reminding = ref(false);
const retrying = ref(false);
const cancelDialog = ref(false);
const cancelling = ref(false);

async function remind(): Promise<void> {
  reminding.value = true;
  try {
    await http.post(`/submissions/${props.id}/remind`);
    ui.toast("Reminders sent to signers who haven't signed yet.");
    await load();
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    reminding.value = false;
  }
}

const copying = ref(false);

/** DocuSign-style "Copy": new draft with the same document,
 *  recipients, and settings — then jump to it for review-and-send. */
async function copyEnvelope(): Promise<void> {
  if (copying.value || !submission.value) return;
  copying.value = true;
  try {
    const { data } = await http.post<SubmissionOut>(`/submissions/${submission.value.id}/copy`);
    ui.toast("Copy created as a draft — review and edit it before sending.");
    await router.push({ name: "send-draft", params: { draftId: String(data.id) } });
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    copying.value = false;
  }
}

const savingTemplate = ref(false);

/** DocuSign "Save as Template": capture this envelope's document + fields as
 *  a reusable template, then open it in the builder for review. */
async function saveAsTemplate(): Promise<void> {
  if (savingTemplate.value || !submission.value) return;
  savingTemplate.value = true;
  try {
    const { data } = await http.post<TemplateOut>(`/submissions/${submission.value.id}/save-as-template`);
    ui.toast(`Template "${data.name}" created — review it before your next send.`);
    await router.push({ name: "template-builder", params: { id: String(data.id) } });
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    savingTemplate.value = false;
  }
}

const archiving = ref(false);

/** Personal filing: hides (or restores) this envelope in the viewer's own
 *  lists only — nothing changes for anyone else. */
async function toggleArchive(): Promise<void> {
  if (!submission.value) return;
  archiving.value = true;
  try {
    const action = submission.value.archived_by_me ? "unarchive" : "archive";
    await http.post(`/submissions/${props.id}/${action}`);
    ui.toast(action === "archive" ? "Envelope archived." : "Envelope restored.");
    await load();
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    archiving.value = false;
  }
}

const resendingId = ref<number | null>(null);

/** Re-send one recipient's invite; resets their reminder budget — the
 *  recovery path after a bounced address is corrected. */
async function resendInvite(signer: SubmitterOut): Promise<void> {
  resendingId.value = signer.id;
  try {
    await http.post(`/submissions/${props.id}/submitters/${signer.id}/resend`);
    ui.toast(`Invite re-sent to ${signer.user.name}.`);
    await load();
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    resendingId.value = null;
  }
}

async function retryCompletion(): Promise<void> {
  retrying.value = true;
  try {
    const { data } = await http.post<SubmissionOut>(`/submissions/${props.id}/retry-completion`);
    if (data.status === "completed") {
      ui.toast("Envelope completed — the signed PDF is ready.");
    } else {
      ui.toast("Completion failed again — check the server logs.", "error");
    }
    await load();
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    retrying.value = false;
  }
}

// --- drafts: send / delete ---------------------------------------------------

const sendingDraft = ref(false);
const deleteDraftDialog = ref(false);
const deletingDraft = ref(false);

async function sendNow(): Promise<void> {
  sendingDraft.value = true;
  try {
    await http.post(`/submissions/${props.id}/send`);
    ui.toast("Envelope sent — signers have been emailed.");
    await load();
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    sendingDraft.value = false;
  }
}

async function confirmDeleteDraft(): Promise<void> {
  deletingDraft.value = true;
  try {
    await http.delete(`/submissions/${props.id}`);
    ui.toast("Draft deleted.");
    await router.push({ name: "dashboard" });
  } catch (err) {
    errorMessage.value = extractError(err);
    deleteDraftDialog.value = false;
  } finally {
    deletingDraft.value = false;
  }
}

async function copyUid(): Promise<void> {
  if (!submission.value) return;
  await navigator.clipboard.writeText(submission.value.public_uid);
  ui.toast("Envelope ID copied.");
}

const cancelReason = ref("");

async function confirmCancel(): Promise<void> {
  cancelling.value = true;
  try {
    const reason = cancelReason.value.trim();
    await http.post(`/submissions/${props.id}/cancel`, reason ? { reason } : {});
    cancelDialog.value = false;
    cancelReason.value = "";
    ui.toast("Envelope voided — everyone involved has been notified.");
    await load();
  } catch (err) {
    errorMessage.value = extractError(err);
    cancelDialog.value = false;
  } finally {
    cancelling.value = false;
  }
}

// --- correct title/message --------------------------------------------------
//
// All three correction dialogs below (title/message, contact info, replace
// signer) follow the same discipline as SendView's "Add signer" dialog:
// `persistent` (no scrim/Escape dismiss — the explicit Cancel button, kept
// enabled only while not submitting, is the only early way out), a
// `*Submitting` ref that blocks re-entry (guards a double-Enter or double
// click firing the request twice), and the id/target captured into a local
// before the `await` so a stale in-flight request — if the underlying data
// changed out from under it — can't clobber the wrong row on return.

// --- replace document (DocuSign-style Correct) -------------------------------

const replaceDocDialog = ref(false);
const replaceDocFile = ref<File | null>(null);
const replaceDocSubmitting = ref(false);
const replaceDocError = ref<string | null>(null);

function openReplaceDocDialog(): void {
  replaceDocFile.value = null;
  replaceDocError.value = null;
  replaceDocDialog.value = true;
}

async function confirmReplaceDoc(): Promise<void> {
  if (replaceDocSubmitting.value || !replaceDocFile.value) return;
  replaceDocSubmitting.value = true;
  replaceDocError.value = null;
  try {
    const formData = new FormData();
    formData.append("file", replaceDocFile.value);
    await http.post(`/submissions/${props.id}/replace-document`, formData);
    replaceDocDialog.value = false;
    ui.toast(isDraft.value ? "Document replaced in the draft." : "Document replaced — signers will see the new version.");
    await load();
  } catch (err) {
    replaceDocError.value = extractError(err);
  } finally {
    replaceDocSubmitting.value = false;
  }
}

const correctDialog = ref(false);
const correctSubmitting = ref(false);
const correctError = ref<string | null>(null);
const correctTitle = ref("");
const correctMessage = ref("");

function openCorrectDialog(): void {
  if (!submission.value) return;
  correctTitle.value = submission.value.title;
  correctMessage.value = submission.value.message ?? "";
  correctError.value = null;
  correctDialog.value = true;
}

async function confirmCorrect(): Promise<void> {
  if (correctSubmitting.value || !submission.value) return;
  const submissionId = submission.value.id;
  const title = correctTitle.value.trim();
  const message = correctMessage.value.trim();
  correctSubmitting.value = true;
  correctError.value = null;
  try {
    await http.patch(`/submissions/${submissionId}`, { title, message: message || null });
    correctDialog.value = false;
    ui.toast("Envelope updated.");
    await load();
  } catch (err) {
    correctError.value = extractError(err);
  } finally {
    correctSubmitting.value = false;
  }
}

// --- correct expiration & reminders (DocuSign correct's "advanced options") --

const settingsDialog = ref(false);
const settingsSubmitting = ref(false);
const settingsError = ref<string | null>(null);
/** Plain date input, same as SendView's; sent as end-of-day local time. */
const settingsExpiryDate = ref("");
const settingsRemindersEnabled = ref(true);
const settingsReminderInterval = ref(3);
const REMINDER_INTERVAL_ITEMS = [1, 2, 3, 5, 7, 14].map((n) => ({
  title: `Every ${n} day${n === 1 ? "" : "s"}`,
  value: n,
}));
const todayIso = new Date().toISOString().slice(0, 10);
const settingsExpiryInPast = computed(
  () => settingsExpiryDate.value !== "" && settingsExpiryDate.value <= todayIso,
);

function openSettingsDialog(): void {
  const s = submission.value;
  if (!s) return;
  settingsExpiryDate.value = s.expires_at ? s.expires_at.slice(0, 10) : "";
  settingsRemindersEnabled.value = s.reminders_enabled;
  settingsReminderInterval.value = s.reminder_interval_days;
  settingsError.value = null;
  settingsDialog.value = true;
}

async function confirmSettings(): Promise<void> {
  if (settingsSubmitting.value || !submission.value) return;
  const submissionId = submission.value.id;
  const expiresAt = settingsExpiryDate.value
    ? new Date(`${settingsExpiryDate.value}T23:59:59`).toISOString()
    : null;
  settingsSubmitting.value = true;
  settingsError.value = null;
  try {
    await http.patch(`/submissions/${submissionId}`, {
      expires_at: expiresAt,
      reminders_enabled: settingsRemindersEnabled.value,
      reminder_interval_days: settingsReminderInterval.value,
    });
    settingsDialog.value = false;
    ui.toast("Envelope settings updated.");
    await load();
  } catch (err) {
    settingsError.value = extractError(err);
  } finally {
    settingsSubmitting.value = false;
  }
}

// --- form data (DocuSign "Form Data") ----------------------------------------

/** Rows worth showing: only signers who completed have values to read. */
const formDataRows = computed(() =>
  (formData.value?.entries ?? []).filter((entry) => entry.signed_at !== null),
);

function formDataValue(value: string | boolean | null): string {
  if (value === true) return "Yes";
  if (value === false) return "No";
  if (value === null || value === "") return "—";
  return value;
}

// --- per-signer corrections --------------------------------------------------

/** External-only, and only while the signer hasn't already completed — matches the backend's own gates. */
function canCorrectContact(signer: SubmitterOut): boolean {
  return signer.user.is_external && signer.status !== "completed";
}

/** Any submitter that hasn't completed yet can be swapped for a different person. */
function canReplaceSigner(signer: SubmitterOut): boolean {
  return signer.status !== "completed";
}

// GET /users is fetched lazily (once) the first time a "Replace signer…"
// dialog opens — this view otherwise never needs the full user list.
const users = ref<User[]>([]);
const usersLoaded = ref(false);

async function ensureUsersLoaded(): Promise<void> {
  if (usersLoaded.value) return;
  try {
    const { data } = await http.get<User[]>("/users");
    users.value = data;
    usersLoaded.value = true;
  } catch (err) {
    replaceError.value = extractError(err);
  }
}

const contactDialog = ref(false);
const contactSubmitting = ref(false);
const contactError = ref<string | null>(null);
const contactSubmitter = ref<SubmitterOut | null>(null);
const contactName = ref("");
const contactEmail = ref("");

function openContactDialog(signer: SubmitterOut): void {
  contactSubmitter.value = signer;
  contactName.value = signer.user.name;
  contactEmail.value = signer.user.email;
  contactError.value = null;
  contactDialog.value = true;
}

async function confirmContact(): Promise<void> {
  if (contactSubmitting.value || !contactSubmitter.value) return;
  const userId = contactSubmitter.value.user.id;
  const name = contactName.value.trim();
  const email = contactEmail.value.trim().toLowerCase();
  contactSubmitting.value = true;
  contactError.value = null;
  try {
    await http.put(`/users/${userId}`, { name, email });
    contactDialog.value = false;
    ui.toast("Contact info updated.");
    await load();
  } catch (err) {
    contactError.value = extractError(err);
  } finally {
    contactSubmitting.value = false;
  }
}

const replaceDialog = ref(false);
const replaceSubmitting = ref(false);
const replaceError = ref<string | null>(null);
const replaceSubmitter = ref<SubmitterOut | null>(null);
const replaceUserId = ref<number | null>(null);

/** Everyone already on the envelope is excluded — picking one would just 409 as a duplicate. */
const replaceCandidates = computed(() => {
  const existingIds = new Set((submission.value?.submitters ?? []).map((s) => s.user.id));
  return users.value
    .filter((u) => !existingIds.has(u.id))
    .map((u) => ({ ...u, display: u.is_external ? `${userLabel(u)} · external` : userLabel(u) }));
});

async function openReplaceDialog(signer: SubmitterOut): Promise<void> {
  replaceSubmitter.value = signer;
  replaceUserId.value = null;
  replaceError.value = null;
  replaceDialog.value = true;
  await ensureUsersLoaded();
}

async function confirmReplace(): Promise<void> {
  if (replaceSubmitting.value || !replaceSubmitter.value || !submission.value || replaceUserId.value == null) return;
  const submissionId = submission.value.id;
  const submitterId = replaceSubmitter.value.id;
  const userId = replaceUserId.value;
  replaceSubmitting.value = true;
  replaceError.value = null;
  try {
    await http.put(`/submissions/${submissionId}/submitters/${submitterId}`, { user_id: userId });
    replaceDialog.value = false;
    ui.toast(
      isDraft.value
        ? "Signer replaced — they'll be emailed when you send the draft."
        : "Signer replaced — a new sign request has been emailed.",
    );
    await load();
  } catch (err) {
    replaceError.value = extractError(err);
  } finally {
    replaceSubmitting.value = false;
  }
}

// --- timeline presentation --------------------------------------------------

function signerForEvent(event: AuditEventOut): SubmitterOut | null {
  const submitterId = event.detail?.submitter_id;
  if (typeof submitterId !== "number" || !submission.value) return null;
  return submission.value.submitters.find((s) => s.id === submitterId) ?? null;
}

function eventText(event: AuditEventOut): string {
  const signer = signerForEvent(event);
  const signerName = signer?.user.name;
  switch (event.event) {
    case "created":
      return `Envelope created by ${event.actor?.name ?? "someone"}`;
    case "sent": {
      // CC rows are never asked to sign — describing their routing as a
      // "sign request" misreports what the system did (user feedback).
      if (signer?.is_cc) {
        return signerName ? `${signerName} CC'd — receives a copy` : "CC recipient added";
      }
      return signerName ? `Sign request sent to ${signerName}` : "Sign requests sent";
    }
    case "opened":
      return `${event.actor?.name ?? signerName ?? "A signer"} opened the document`;
    case "signed":
      return `${event.actor?.name ?? signerName ?? "A signer"} signed`;
    case "reminded":
      return signerName ? `Reminder sent to ${signerName}` : "Reminder sent";
    case "completed":
      return "Everyone signed — envelope completed and PDF sealed";
    case "cancelled":
      return `Envelope voided by ${event.actor?.name ?? "someone"}${event.detail?.reason ? ` — "${event.detail.reason}"` : ""}`;
    case "expired":
      return "Envelope expired — its deadline passed before everyone signed";
    case "declined":
      return `Declined by ${event.actor?.name ?? "someone"}${event.detail?.reason ? ` — "${event.detail.reason}"` : ""}`;
    case "corrected": {
      const detail = event.detail as
        | { changed?: string[]; from?: { email?: string | null }; to?: { email?: string | null } }
        | null;
      const actorName = event.actor?.name ?? "Someone";
      if (detail?.from || detail?.to) {
        return `Corrected — ${actorName} replaced signer ${detail?.from?.email ?? "unknown"} → ${detail?.to?.email ?? "unknown"}`;
      }
      if (detail?.changed?.length) {
        return `Corrected — ${actorName} updated the ${detail.changed.join(" and ")}`;
      }
      return `Corrected by ${actorName}`;
    }
    default:
      return event.event;
  }
}

const EVENT_ICONS: Record<string, string> = {
  created: "mdi-file-plus-outline",
  sent: "mdi-send",
  opened: "mdi-email-open-outline",
  signed: "mdi-draw-pen",
  reminded: "mdi-bell-ring-outline",
  completed: "mdi-check-decagram",
  cancelled: "mdi-cancel",
  declined: "mdi-close-octagon",
  corrected: "mdi-pencil",
  expired: "mdi-clock-alert-outline",
};

</script>

<template>
  <v-container class="envelope-detail">
    <v-btn variant="text" prepend-icon="mdi-arrow-left" class="mb-2 px-0" :to="{ name: 'dashboard' }">Home</v-btn>

    <v-alert v-if="errorMessage" type="error" closable class="mb-4" @click:close="errorMessage = null">
      {{ errorMessage }}
    </v-alert>
    <v-progress-linear v-if="loading" indeterminate class="mb-4" />

    <template v-if="submission">
      <div class="d-flex align-center flex-wrap mb-1">
        <h1 class="text-h5 mr-1">{{ submission.title }}</h1>
        <v-btn
          v-if="canCorrect"
          icon="mdi-pencil"
          size="x-small"
          variant="text"
          density="comfortable"
          aria-label="Correct title and message"
          class="mr-2"
          @click="openCorrectDialog"
        />
        <v-chip :color="envelopeStatusColor(submission.status)" size="small" variant="tonal">
          {{ envelopeStatusLabel(submission.status) }}
        </v-chip>
        <v-chip
          v-if="submission.archived_by_me"
          size="small"
          variant="tonal"
          prepend-icon="mdi-archive-outline"
          class="ml-1"
        >
          Archived
        </v-chip>
        <v-spacer />
        <v-btn
          variant="text"
          :loading="archiving"
          :prepend-icon="submission.archived_by_me ? 'mdi-archive-arrow-up-outline' : 'mdi-archive-outline'"
          @click="toggleArchive"
        >
          {{ submission.archived_by_me ? "Unarchive" : "Archive" }}
        </v-btn>
        <template v-if="canManage && (submission.status === 'pending' || isDraft) && !stuck">
          <v-btn
            v-if="canReplaceDocument"
            variant="text"
            prepend-icon="mdi-file-swap-outline"
            @click="openReplaceDocDialog"
          >
            Replace document
          </v-btn>
          <template v-if="!isDraft">
            <v-btn variant="text" :loading="reminding" prepend-icon="mdi-bell-ring-outline" @click="remind">
              Remind
            </v-btn>
            <v-btn variant="text" color="error" prepend-icon="mdi-cancel" @click="cancelDialog = true">
              Void envelope
            </v-btn>
          </template>
        </template>
        <v-btn
          v-if="canManage && (auth.canSend || auth.isAdmin)"
          variant="text"
          :loading="copying"
          prepend-icon="mdi-content-duplicate"
          @click="copyEnvelope"
        >
          Copy
        </v-btn>
        <v-btn
          v-if="canManage && (auth.canSend || auth.isAdmin)"
          variant="text"
          :loading="savingTemplate"
          prepend-icon="mdi-content-save-plus-outline"
          @click="saveAsTemplate"
        >
          Save as template
        </v-btn>
        <v-btn
          variant="tonal"
          :href="`/api/files/document-preview/${submission.id}`"
          target="_blank"
          prepend-icon="mdi-file-eye-outline"
        >
          View document
        </v-btn>
        <v-btn
          v-if="submission.status === 'completed'"
          color="primary"
          variant="tonal"
          :href="`/api/files/signed-pdf/${submission.id}`"
          target="_blank"
          prepend-icon="mdi-file-pdf-box"
          class="ml-2"
        >
          Signed PDF
        </v-btn>
        <v-btn
          v-if="submission.status === 'completed' && submission.has_certificate"
          variant="tonal"
          :href="`/api/files/certificate/${submission.id}`"
          target="_blank"
          prepend-icon="mdi-certificate-outline"
          class="ml-2"
        >
          Certificate
        </v-btn>
      </div>
      <p class="text-medium-emphasis text-body-2 mb-0">
        {{ isDraft ? "Created by" : "Sent by" }} {{ submission.sender.name }} · {{ formatDateTime(submission.created_at) }}
        <template v-if="submission.completed_at"> · completed {{ formatDateTime(submission.completed_at) }}</template>
        <template v-if="submission.expires_at && (submission.status === 'pending' || isDraft)">
          · expires {{ formatDate(submission.expires_at) }}
        </template>
        <template v-if="canManage && (submission.status === 'pending' || isDraft)">
          · reminders: {{ submission.reminders_enabled ? `every ${submission.reminder_interval_days} day${submission.reminder_interval_days === 1 ? "" : "s"}` : "off" }}
        </template>
        <v-btn
          v-if="canCorrect"
          icon="mdi-pencil"
          size="x-small"
          variant="text"
          density="comfortable"
          aria-label="Edit expiration and reminders"
          @click="openSettingsDialog"
        />
      </p>
      <p class="text-medium-emphasis text-body-2 mb-4">
        Envelope ID: <span style="font-family: monospace">{{ submission.public_uid }}</span>
        <v-btn
          icon="mdi-content-copy"
          size="x-small"
          variant="text"
          density="comfortable"
          aria-label="Copy envelope ID"
          @click="copyUid"
        />
      </p>

      <v-alert v-if="isDraft && canManage" type="info" class="mb-4" prominent icon="mdi-file-edit-outline">
        This envelope is a draft — recipients haven't been notified. Edit it to change the
        document, signers, fields, or settings before sending.
        <template v-if="draftExpiryPassed">
          <br />Its expiration date has already passed — set a new one (pencil next to the expiry
          date above) or edit the draft before sending.
        </template>
        <template #append>
          <v-btn
            color="primary"
            variant="flat"
            prepend-icon="mdi-pencil"
            :to="{ name: 'send-draft', params: { draftId: String(submission.id) } }"
          >
            Edit draft
          </v-btn>
          <v-btn
            color="primary"
            variant="tonal"
            class="ml-2"
            :loading="sendingDraft"
            :disabled="draftExpiryPassed"
            @click="sendNow"
          >
            Send now
          </v-btn>
          <v-btn
            color="error"
            variant="text"
            class="ml-2"
            :disabled="sendingDraft"
            @click="deleteDraftDialog = true"
          >
            Delete
          </v-btn>
        </template>
      </v-alert>

      <v-alert v-if="stuck && canManage" type="warning" class="mb-4" prominent>
        Everyone has signed, but the final PDF couldn't be produced. This usually means a temporary
        storage or stamping error.
        <template #append>
          <v-btn color="warning" variant="flat" :loading="retrying" @click="retryCompletion">
            Retry completion
          </v-btn>
        </template>
      </v-alert>

      <v-row>
        <v-col cols="12" md="7">
          <v-card variant="flat" border>
            <v-card-title class="text-subtitle-1">
              Signers · {{ isOrdered ? "in order" : "any order" }}
            </v-card-title>
            <v-list lines="two">
              <v-list-item
                v-for="signer in displaySubmitters"
                :key="signer.id"
                :title="isOrdered ? `${signer.order_index + 1}. ${signer.user.name}` : signer.user.name"
              >
                <template #subtitle>
                  <template v-if="signer.is_cc">CC · receives a copy</template>
                  <!-- One-off envelopes have internal signer-N roles — never shown. -->
                  <template v-else>{{ displayRole(submission.template, signer.role) ?? signer.user.email }}</template>
                  <template v-if="signer.status === 'completed' && signer.signed_at">
                    · signed {{ formatDateTime(signer.signed_at) }}
                  </template>
                  <template v-else-if="signer.last_reminded_at">
                    · reminded {{ timeAgo(signer.last_reminded_at) }}
                    ({{ signer.reminder_count }}×)
                  </template>
                </template>
                <template #append>
                  <v-chip
                    v-if="signer.email_status === 'failed'"
                    color="error"
                    size="small"
                    variant="tonal"
                    class="mr-2"
                    prepend-icon="mdi-email-alert"
                  >
                    Email bounced
                  </v-chip>
                  <v-chip v-if="signer.is_cc" size="small" variant="tonal" prepend-icon="mdi-email-outline">
                    {{ ccStatusLabel(signer) }}
                  </v-chip>
                  <v-chip v-else-if="waitingForTurn(signer)" size="small" variant="tonal">
                    Waiting for turn
                  </v-chip>
                  <v-chip v-else :color="signerStatusColor(signer.status)" size="small" variant="tonal">
                    {{ signerStatusLabel(signer.status, submission.status) }}
                  </v-chip>
                  <v-menu v-if="canCorrect && canReplaceSigner(signer)">
                    <template #activator="{ props: menuProps }">
                      <v-btn
                        icon="mdi-dots-vertical"
                        size="small"
                        variant="text"
                        class="ml-1"
                        :aria-label="`Actions for ${signer.user.name}`"
                        v-bind="menuProps"
                      />
                    </template>
                    <v-list density="compact">
                      <v-list-item
                        v-if="!isDraft"
                        prepend-icon="mdi-email-sync-outline"
                        :title="signer.email_status === 'failed' ? 'Resend invite (bounced)…' : 'Resend invite…'"
                        :disabled="resendingId === signer.id"
                        @click="resendInvite(signer)"
                      />
                      <v-list-item
                        v-if="canCorrectContact(signer)"
                        prepend-icon="mdi-account-edit-outline"
                        title="Correct contact info…"
                        @click="openContactDialog(signer)"
                      />
                      <v-list-item
                        prepend-icon="mdi-account-switch-outline"
                        title="Replace signer…"
                        @click="openReplaceDialog(signer)"
                      />
                    </v-list>
                  </v-menu>
                </template>
              </v-list-item>
            </v-list>
          </v-card>

          <v-card v-if="submission.message" variant="flat" border class="mt-4">
            <v-card-title class="text-subtitle-1">Message to signers</v-card-title>
            <v-card-text class="text-body-2">{{ submission.message }}</v-card-text>
          </v-card>

          <!-- DocuSign-style Form Data: what recipients typed, without reading the PDF. -->
          <v-card v-if="formData && formDataRows.length > 0" variant="flat" border class="mt-4">
            <v-card-title class="d-flex align-center text-subtitle-1">
              Form data
              <v-spacer />
              <v-btn
                variant="text"
                size="small"
                prepend-icon="mdi-download"
                :href="`/api/submissions/${submission.id}/form-data?format=csv`"
              >
                Download CSV
              </v-btn>
            </v-card-title>
            <v-table density="compact" class="form-data-table">
              <thead>
                <tr>
                  <th>Recipient</th>
                  <th>Field</th>
                  <th>Value</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="entry in formDataRows" :key="`${entry.submitter_id}-${entry.field_id}`">
                  <td>{{ entry.recipient.name }}</td>
                  <td class="text-capitalize">{{ entry.field_type }} · p.{{ entry.page + 1 }}</td>
                  <td>{{ formDataValue(entry.value) }}</td>
                </tr>
              </tbody>
            </v-table>
          </v-card>
        </v-col>

        <v-col v-if="eventsAvailable" cols="12" md="5">
          <v-card variant="flat" border>
            <v-card-title class="text-subtitle-1">Activity</v-card-title>
            <v-card-text>
              <v-timeline density="compact" side="end" truncate-line="both">
                <v-timeline-item
                  v-for="event in events"
                  :key="event.id"
                  :dot-color="
                    event.event === 'completed' ? 'success' : event.event === 'cancelled' || event.event === 'declined' ? 'error' : 'primary'
                  "
                  size="x-small"
                >
                  <div class="text-body-2">{{ eventText(event) }}</div>
                  <div class="text-caption text-medium-emphasis">
                    <v-icon :icon="EVENT_ICONS[event.event] ?? 'mdi-circle-small'" size="x-small" class="mr-1" aria-hidden="true" />
                    {{ formatDateTime(event.created_at) }}
                  </div>
                </v-timeline-item>
              </v-timeline>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </template>

    <v-dialog v-model="deleteDraftDialog" max-width="440">
      <v-card>
        <v-card-title>Delete draft?</v-card-title>
        <v-card-text>
          "{{ submission?.title }}" hasn't been sent to anyone. Deleting it removes the draft
          entirely — this can't be undone.
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" :disabled="deletingDraft" @click="deleteDraftDialog = false">Back</v-btn>
          <v-btn color="error" :loading="deletingDraft" @click="confirmDeleteDraft">Delete draft</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="cancelDialog" max-width="480">
      <v-card>
        <v-card-title>Void envelope?</v-card-title>
        <v-card-text>
          <p class="mb-3">
            This will void "{{ submission?.title }}" for all signers — no further signing is
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
          <v-btn variant="text" @click="cancelDialog = false">Back</v-btn>
          <v-btn color="error" :loading="cancelling" @click="confirmCancel">Void envelope</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="replaceDocDialog" max-width="500" persistent>
      <v-card>
        <v-card-title>Replace document</v-card-title>
        <v-card-text>
          <p class="text-body-2 text-medium-emphasis mb-3">
            <template v-if="isDraft">
              The new file replaces this draft's document; all signature fields keep their current
              positions. Nobody is notified — the draft hasn't been sent.
            </template>
            <template v-else>
              The new file replaces the document for everyone; all signature fields keep their
              current positions. Only possible while nobody has signed yet.
            </template>
          </p>
          <v-alert v-if="replaceDocError" type="error" density="compact" class="mb-3">
            {{ replaceDocError }}
          </v-alert>
          <v-file-input
            v-model="replaceDocFile"
            label="New document"
            :accept="UPLOAD_ACCEPT"
            prepend-icon="mdi-file-upload"
            :disabled="replaceDocSubmitting"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" :disabled="replaceDocSubmitting" @click="replaceDocDialog = false">
            Cancel
          </v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :loading="replaceDocSubmitting"
            :disabled="!replaceDocFile"
            @click="confirmReplaceDoc"
          >
            Replace
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="correctDialog" max-width="480" persistent>
      <v-card>
        <v-card-title>Correct envelope</v-card-title>
        <v-card-text>
          <v-alert v-if="correctError" type="error" density="compact" class="mb-3">{{ correctError }}</v-alert>
          <v-text-field v-model="correctTitle" label="Title" :disabled="correctSubmitting" autofocus />
          <v-textarea
            v-model="correctMessage"
            label="Message to signers (optional)"
            rows="3"
            class="mt-2"
            :disabled="correctSubmitting"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" :disabled="correctSubmitting" @click="correctDialog = false">Cancel</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :loading="correctSubmitting"
            :disabled="!correctTitle.trim()"
            @click="confirmCorrect"
          >
            Save
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="settingsDialog" max-width="480" persistent>
      <v-card>
        <v-card-title>Expiration &amp; reminders</v-card-title>
        <v-card-text>
          <v-alert v-if="settingsError" type="error" density="compact" class="mb-3">
            {{ settingsError }}
          </v-alert>
          <v-text-field
            v-model="settingsExpiryDate"
            type="date"
            label="Expiration date (optional)"
            :min="todayIso"
            clearable
            :disabled="settingsSubmitting"
          />
          <p v-if="settingsExpiryInPast" class="text-caption text-error mt-1 mb-2">
            The expiration date must be in the future.
          </p>
          <p v-else class="text-caption text-medium-emphasis mt-1 mb-2">
            <template v-if="settingsExpiryDate">
              Signers are warned 2 days before the deadline; changing it re-arms that warning.
            </template>
            <template v-else>Without an expiration date, the envelope stays open until completed or voided.</template>
          </p>
          <v-switch
            v-model="settingsRemindersEnabled"
            label="Automatic reminders"
            color="primary"
            density="compact"
            hide-details
            :disabled="settingsSubmitting"
          />
          <v-select
            v-if="settingsRemindersEnabled"
            v-model="settingsReminderInterval"
            :items="REMINDER_INTERVAL_ITEMS"
            label="Remind"
            density="compact"
            class="mt-2"
            hide-details
            :disabled="settingsSubmitting"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" :disabled="settingsSubmitting" @click="settingsDialog = false">Cancel</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :loading="settingsSubmitting"
            :disabled="settingsExpiryInPast"
            @click="confirmSettings"
          >
            Save
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="contactDialog" max-width="440" persistent>
      <v-card>
        <v-card-title>Correct contact info</v-card-title>
        <v-card-text>
          <v-alert v-if="contactError" type="error" density="compact" class="mb-3">{{ contactError }}</v-alert>
          <v-text-field v-model="contactName" label="Full name" :disabled="contactSubmitting" autofocus />
          <v-text-field v-model="contactEmail" label="Email" class="mt-2" :disabled="contactSubmitting" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" :disabled="contactSubmitting" @click="contactDialog = false">Cancel</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :loading="contactSubmitting"
            :disabled="!contactName.trim() || !contactEmail.trim()"
            @click="confirmContact"
          >
            Save
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="replaceDialog" max-width="480" persistent>
      <v-card>
        <v-card-title>Replace signer</v-card-title>
        <v-card-text>
          <p class="text-body-2 text-medium-emphasis mb-3">
            <template v-if="isDraft">
              Replacing "{{ replaceSubmitter?.user.name }}" updates who will be asked to sign when you
              send this draft. Nothing is emailed until then.
            </template>
            <template v-else>
              Replacing "{{ replaceSubmitter?.user.name }}" sends a fresh sign request to the new signer
              and invalidates the old signing link.
            </template>
          </p>
          <v-alert v-if="replaceError" type="error" density="compact" class="mb-3">{{ replaceError }}</v-alert>
          <v-autocomplete
            v-model="replaceUserId"
            :items="replaceCandidates"
            item-title="display"
            item-value="id"
            label="Replace with"
            :disabled="replaceSubmitting"
            clearable
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" :disabled="replaceSubmitting" @click="replaceDialog = false">Cancel</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :loading="replaceSubmitting"
            :disabled="replaceUserId == null"
            @click="confirmReplace"
          >
            Replace
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<style scoped>
.envelope-detail {
  max-width: 1100px;
}
</style>
