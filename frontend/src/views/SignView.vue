<script setup lang="ts">
/**
 * Signer-facing signing flow, guided DocuSeal-style: fields are visited in
 * reading order (page, then top-to-bottom) via a sticky dock with Back /
 * Next navigation that autoscrolls to the active field; field boxes show
 * done / active / to-do states; Finish opens a review-and-consent dialog
 * before POSTing /complete (one click should not legally bind anyone).
 *
 * Signature images are POSTed per field as captured (unchanged), so
 * everything but text/date/checkbox/name values is already persisted by
 * the time the review dialog confirms. Name fields are editable text
 * inputs prefilled with the signer's account name.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import axios from "axios";
import http, { extractError } from "../utils/http";
import { formatDate } from "../utils/labels";
import { nextTourIndex } from "../utils/tour";
import PdfPage from "../components/PdfPage.vue";
import SignaturePad from "../components/SignaturePad.vue";
import type { FieldDef, SignerViewOut, SubmissionOut } from "../types";

const props = defineProps<{ submitterId: string; external?: boolean }>();

type Phase = "loading" | "error" | "blocked" | "signing" | "success" | "declined";

const phase = ref<Phase>("loading");
const errorMessage = ref<string | null>(null);
const blockedReason = ref("");

const view = ref<SignerViewOut | null>(null);
const pdfUrl = ref<string | null>(null);
const accountSavedSignatureUrl = ref<string | null>(null);

function todayISODate(): string {
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

// --- Field state -------------------------------------------------------------

const fieldValues = reactive<Record<string, string | boolean>>({});
const fieldSignatureIds = reactive<Record<string, number>>({});
const signatureImageUrls = reactive<Record<string, string>>({});
/** Uploaded files for attachment fields: field id -> stored attachment. */
const fieldAttachments = reactive<Record<string, { id: number; filename: string }>>({});

const myFieldDefs = computed<FieldDef[]>(() => {
  if (!view.value) return [];
  const mine = new Set(view.value.my_fields);
  return view.value.template.fields.filter((f) => mine.has(f.id));
});

/** The guided tour: my fillable fields (name included — it's editable,
 *  prefilled with the account name) in reading order. */
const tourFields = computed<FieldDef[]>(() =>
  myFieldDefs.value.slice().sort((a, b) => a.page - b.page || a.y - b.y || a.x - b.x),
);

const currentIndex = ref(0);
const currentField = computed<FieldDef | null>(() => tourFields.value[currentIndex.value] ?? null);

// Mirrors the backend's format rules (signing.py `_validate_values`).
const TEXT_EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/;

/** Whether a text field's current value satisfies its `validation` format.
 *  Non-text fields are never "invalid text"; empty input is "not filled
 *  in", never "invalid". Values can be booleans (checkboxes), so never
 *  assume string. */
function textValid(field: FieldDef): boolean {
  if (field.type !== "text") return true;
  const raw = fieldValues[field.id];
  const text = typeof raw === "string" ? raw.trim() : "";
  if (!text || !field.validation) return true;
  if (field.validation === "email") return TEXT_EMAIL_RE.test(text);
  return !Number.isNaN(Number(text));
}

function fieldComplete(field: FieldDef): boolean {
  if (field.type === "signature" || field.type === "initials") return fieldSignatureIds[field.id] != null;
  if (field.type === "date") return !!fieldValues[field.id];
  if (field.type === "checkbox") return fieldValues[field.id] === true;
  if (field.type === "text") {
    return !!(fieldValues[field.id] as string | undefined)?.trim() && textValid(field);
  }
  if (field.type === "name") return !!(fieldValues[field.id] as string | undefined)?.trim();
  if (field.type === "dropdown" || field.type === "radio") return !!fieldValues[field.id];
  if (field.type === "attachment") return fieldAttachments[field.id] != null;
  return true;
}

const completedCount = computed(() => tourFields.value.filter(fieldComplete).length);

const FIELD_TYPE_LABELS: Record<string, string> = {
  signature: "Signature",
  initials: "Initials",
  date: "Date",
  text: "Text",
  checkbox: "Checkbox",
  name: "Name",
  dropdown: "Dropdown",
  radio: "Choice",
  attachment: "Attachment",
};

function seedDefaults(): void {
  for (const field of myFieldDefs.value) {
    if (field.type === "date" && !(field.id in fieldValues)) fieldValues[field.id] = todayISODate();
    if (field.type === "checkbox" && !(field.id in fieldValues)) {
      fieldValues[field.id] = field.default_value === "true";
    }
    if (field.type === "name" && !(field.id in fieldValues)) fieldValues[field.id] = view.value?.my_name ?? "";
    // Sender-provided prefill: seeded once, then the signer owns the value.
    if (field.type === "text" && !(field.id in fieldValues) && field.default_value) {
      fieldValues[field.id] = field.default_value;
    }
    // Selects need a real "" to show the Choose… placeholder; a sender/copy
    // prefill wins when it's still one of the options.
    if ((field.type === "dropdown" || field.type === "radio") && !(field.id in fieldValues)) {
      fieldValues[field.id] =
        field.default_value && (field.options ?? []).includes(field.default_value) ? field.default_value : "";
    }
  }
}

function fieldsForPage(page: number): { mine: FieldDef[]; others: FieldDef[]; labels: FieldDef[] } {
  if (!view.value) return { mine: [], others: [], labels: [] };
  const mine = new Set(view.value.my_fields);
  const onPage = view.value.template.fields.filter((f) => f.page === page);
  return {
    mine: onPage.filter((f) => mine.has(f.id)),
    // Labels are sender text shown to everyone — not anyone's field box.
    others: onPage.filter((f) => !mine.has(f.id) && f.type !== "label"),
    labels: onPage.filter((f) => f.type === "label"),
  };
}

/**
 * Display label for another submitter's (read-only) field: their real name,
 * not the raw role string — for an ad-hoc envelope, `field.role` is an
 * internal `signer-N` id never meant to be user-facing. Falls back to the
 * role string only if it doesn't resolve to a name (shouldn't happen in
 * practice: every role on a submission's fields comes from a signer who was
 * mapped at send time — see `_validate_role_mapping` — but the fallback
 * keeps this label harmless rather than blank if that invariant is ever
 * violated).
 */
function otherFieldLabel(field: FieldDef): string {
  const name = view.value?.role_names[field.role] ?? field.role;
  return `${name}: ${field.type}`;
}

const missingRequiredCount = computed(
  () => myFieldDefs.value.filter((field) => field.required && !fieldComplete(field)).length,
);

/** Filled-but-invalid text inputs also block Finish (the server would 422). */
const invalidCount = computed(() => myFieldDefs.value.filter((field) => !textValid(field)).length);

const canFinish = computed(() => missingRequiredCount.value === 0 && invalidCount.value === 0);

// --- Guided navigation -------------------------------------------------------

function scrollToField(field: FieldDef, attempt = 0): void {
  void nextTick(() => {
    // Only the still-current target may scroll — a stale retry from a
    // previous Next click must never yank the view later.
    if (currentField.value?.id !== field.id) return;
    const el = document.querySelector(`[data-field-id="${field.id}"]`) as HTMLElement | null;
    // A field box on a page whose canvas hasn't rendered yet is
    // display:none (fieldStyle), and scrollIntoView on a hidden element is
    // a silent no-op — Next would advance the counter without moving the
    // screen. Scroll to the page wrapper (once — repeating it every retry
    // fights the user and the smooth scroll) so the view moves immediately,
    // then keep retrying until the box becomes visible: big documents can
    // take well over the old 3s budget to render a late page.
    if (!el || el.offsetParent === null) {
      if (attempt === 0) {
        const pageEl = document.querySelectorAll(".page-wrapper")[field.page];
        pageEl?.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      if (attempt < 50) window.setTimeout(() => scrollToField(field, attempt + 1), 200);
      return;
    }
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    // Put the keyboard where the user is looking (skip signature buttons —
    // focusing them would outline the box before the user acts).
    if (field.type === "text" || field.type === "date" || field.type === "name") {
      (el.querySelector("input") as HTMLInputElement | null)?.focus({ preventScroll: true });
    }
  });
}

function goToIndex(index: number): void {
  if (index < 0 || index >= tourFields.value.length) return;
  currentIndex.value = index;
  const field = tourFields.value[index];
  if (field) scrollToField(field);
}

function goNext(): void {
  // Cyclic search for the nearest incomplete field — including the current
  // one, so "Field 1 of 1" re-scrolls to the field instead of no-opping.
  const idx = nextTourIndex(
    tourFields.value.map((f) => fieldComplete(f)),
    currentIndex.value,
  );
  if (idx !== null) goToIndex(idx);
}

function goBack(): void {
  goToIndex(currentIndex.value - 1);
}

function setCurrentField(fieldId: string): void {
  const idx = tourFields.value.findIndex((f) => f.id === fieldId);
  if (idx !== -1) currentIndex.value = idx;
}

function startTour(): void {
  const firstIncomplete = tourFields.value.findIndex((f) => !fieldComplete(f));
  goToIndex(firstIncomplete === -1 ? 0 : firstIncomplete);
}

function fieldStateClass(field: FieldDef): string {
  if (field.id === currentField.value?.id) return "field-active";
  if (fieldComplete(field)) return "field-done";
  return field.required ? "field-todo-required" : "field-todo";
}

// --- Page rendering ------------------------------------------------------

const pageSizes = reactive<Record<number, { width: number; height: number; ptWidth: number; ptHeight: number }>>({});
const pageNumbers = computed(() => {
  const count = view.value?.template.page_count ?? 0;
  return Array.from({ length: count }, (_, i) => i);
});

function onRendered(page: number, widthPx: number, heightPx: number, widthPt: number, heightPt: number): void {
  pageSizes[page] = { width: widthPx, height: heightPx, ptWidth: widthPt, ptHeight: heightPt };
}

function onPdfError(message: string): void {
  errorMessage.value = `Couldn't display the PDF: ${message}`;
}

function fieldStyle(field: FieldDef, page: number): Record<string, string> {
  const size = pageSizes[page];
  if (!size) return { display: "none" };
  return {
    left: `${field.x * size.width}px`,
    top: `${field.y * size.height}px`,
    width: `${field.w * size.width}px`,
    height: `${field.h * size.height}px`,
  };
}

function fieldAriaLabel(field: FieldDef): string {
  const label = FIELD_TYPE_LABELS[field.type] ?? field.type;
  return `${label} field${field.required ? ", required" : ""}`;
}

/**
 * Prefilled fields (name = your account name, date = today) show up already
 * "done", which reads as locked — this hint, shown as the input's tooltip
 * and in the guided dock, says otherwise.
 */
function editHint(field: FieldDef): string | undefined {
  if (field.type === "name") return "Prefilled with your name — click to edit it.";
  if (field.type === "date") return "Prefilled with today's date — click to change it.";
  if (field.type === "text") {
    if (field.validation === "email") return "Enter an email address.";
    if (field.validation === "number") return "Enter a number.";
    return "Click to type.";
  }
  if (field.type === "dropdown" || field.type === "radio") return "Choose an option.";
  if (field.type === "attachment") return "Attach a PDF or image file (up to 10 MB).";
  return undefined;
}

// WYSIWYG text sizing: mirror of backend stamping (app/stamping.py) — font
// size clamp(0.6 * box_height_pt, 6, 14)pt with a 2pt left inset, shrunk
// further (floor 4pt) when the current value is wider than the box, then
// converted to on-screen px via the page's render scale — so the preview
// shows text at exactly the size and position it will be stamped.
const STAMP_FONT_FACTOR = 0.6;
const STAMP_MIN_FONT_PT = 6;
const STAMP_MAX_FONT_PT = 14;
const STAMP_ABS_MIN_FONT_PT = 4;
const STAMP_TEXT_INSET_PT = 2;

let measureCtx: CanvasRenderingContext2D | null = null;

/** Text width in pt for the stamping font (canvas px at `fontPt` ≈ pt; Arial
 *  stands in for PDF Helvetica with near-identical metrics). */
function textWidthPt(text: string, fontPt: number): number {
  measureCtx ??= document.createElement("canvas").getContext("2d");
  if (!measureCtx) return 0;
  measureCtx.font = `${fontPt}px Helvetica, Arial, sans-serif`;
  return measureCtx.measureText(text).width;
}

/** The current text a field would stamp — what the shrink-to-fit measures. */
function fieldPreviewText(field: FieldDef): string {
  if (field.type === "label") return field.default_value ?? "";
  const value = fieldValues[field.id];
  return typeof value === "string" ? value : "";
}

function fieldTextStyle(field: FieldDef, page: number): Record<string, string> {
  const size = pageSizes[page];
  if (!size || size.ptHeight <= 0) return {};
  const scale = size.height / size.ptHeight;
  const boxHeightPt = field.h * size.ptHeight;
  // Sender-set size (clamped to the box height) beats the auto formula.
  let fontPt = field.font_size
    ? Math.min(field.font_size, boxHeightPt)
    : Math.min(STAMP_MAX_FONT_PT, Math.max(STAMP_MIN_FONT_PT, boxHeightPt * STAMP_FONT_FACTOR));
  const text = fieldPreviewText(field);
  if (text) {
    const available = Math.max(field.w * size.ptWidth - 2 * STAMP_TEXT_INSET_PT, 1);
    const width = textWidthPt(text, fontPt);
    if (width > available) fontPt = Math.max(STAMP_ABS_MIN_FONT_PT, (fontPt * available) / width);
  }
  return {
    fontSize: `${fontPt * scale}px`,
    paddingLeft: `${STAMP_TEXT_INSET_PT * scale}px`,
    paddingRight: `${STAMP_TEXT_INSET_PT * scale}px`,
  };
}

// --- Signature capture -----------------------------------------------------

const padOpen = ref(false);
const activeSignatureFieldId = ref<string | null>(null);
/** Whether the open pad captures initials (small stamp) vs a full signature. */
const activeIsInitials = ref(false);
/** The initials captured earlier this session, offered for reuse on every
 *  subsequent initials field ("initial every page" without redrawing). */
const lastInitials = ref<{ id: number; url: string } | null>(null);

const activeSavedImageUrl = computed<string | null>(() => {
  if (!activeSignatureFieldId.value) return null;
  const own = signatureImageUrls[activeSignatureFieldId.value];
  if (own) return own;
  if (activeIsInitials.value) return lastInitials.value?.url ?? null;
  return accountSavedSignatureUrl.value ?? null;
});

/** "Jane Doe" -> "YY", for the initials pad's Type tab prefill. */
const myInitials = computed(() =>
  (view.value?.my_name ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join(""),
);

function openSignaturePad(fieldId: string, isInitials = false): void {
  activeSignatureFieldId.value = fieldId;
  activeIsInitials.value = isInitials;
  setCurrentField(fieldId);
  padOpen.value = true;
}

function handleUseSaved(): void {
  const fieldId = activeSignatureFieldId.value;
  if (!fieldId || !view.value) return;
  if (signatureImageUrls[fieldId]) return; // already captured for this field this session
  if (activeIsInitials.value) {
    if (lastInitials.value) {
      fieldSignatureIds[fieldId] = lastInitials.value.id;
      signatureImageUrls[fieldId] = lastInitials.value.url;
    }
    return;
  }
  if (view.value.saved_signature_id != null && accountSavedSignatureUrl.value) {
    fieldSignatureIds[fieldId] = view.value.saved_signature_id;
    signatureImageUrls[fieldId] = accountSavedSignatureUrl.value;
  }
}

async function handleSaveSignature(dataUrl: string): Promise<void> {
  const fieldId = activeSignatureFieldId.value;
  if (!fieldId) return;
  errorMessage.value = null;
  try {
    const { data } = await http.post<{ signature_id: number }>(
      `/sign/${props.submitterId}/signature`,
      { image: dataUrl },
      { skipAuthRedirect: props.external === true },
    );
    fieldSignatureIds[fieldId] = data.signature_id;
    signatureImageUrls[fieldId] = dataUrl;
    if (activeIsInitials.value) {
      lastInitials.value = { id: data.signature_id, url: dataUrl };
    }
  } catch (err) {
    errorMessage.value = extractError(err);
  }
}

// --- Attachment upload ------------------------------------------------------

const attachmentInputRef = ref<HTMLInputElement | null>(null);
const attachmentFieldId = ref<string | null>(null);
const uploadingAttachment = ref(false);

function openAttachmentPicker(fieldId: string): void {
  attachmentFieldId.value = fieldId;
  setCurrentField(fieldId);
  attachmentInputRef.value?.click();
}

async function onAttachmentChosen(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = ""; // allow re-picking the same file
  const fieldId = attachmentFieldId.value;
  if (!file || !fieldId) return;
  uploadingAttachment.value = true;
  errorMessage.value = null;
  try {
    const formData = new FormData();
    formData.append("file", file);
    const { data } = await http.post<{ attachment_id: number; filename: string }>(
      `/sign/${props.submitterId}/attachment`,
      formData,
      { skipAuthRedirect: props.external === true },
    );
    fieldAttachments[fieldId] = { id: data.attachment_id, filename: data.filename };
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    uploadingAttachment.value = false;
  }
}

// --- Load ------------------------------------------------------------------

async function loadAccountSavedSignature(signatureId: number): Promise<void> {
  try {
    const res = await http.get<Blob>(`/files/signature/${signatureId}`, {
      responseType: "blob",
      skipAuthRedirect: props.external === true,
    });
    accountSavedSignatureUrl.value = URL.createObjectURL(res.data);
  } catch {
    // If the stored preview can't be fetched, just skip the "use saved" shortcut — drawing still works.
    accountSavedSignatureUrl.value = null;
  }
}

async function load(): Promise<void> {
  phase.value = "loading";
  errorMessage.value = null;
  try {
    const signRes = await http.get<SignerViewOut>(`/sign/${props.submitterId}`, {
      skipAuthRedirect: props.external === true,
    });
    view.value = signRes.data;
    seedDefaults();

    // The current state of the document — earlier signers' values already
    // stamped (DocuSign-style), not the bare template.
    const pdf = await http.get<Blob>(`/files/document-preview/${signRes.data.submission.id}`, {
      responseType: "blob",
      skipAuthRedirect: props.external === true,
    });
    pdfUrl.value = URL.createObjectURL(pdf.data);

    const expiresAt = signRes.data.submission.expires_at;
    const expired = expiresAt != null && new Date(expiresAt).getTime() <= Date.now();
    if (signRes.data.my_status === "completed") {
      blockedReason.value = "You've already signed this document.";
      phase.value = "blocked";
    } else if (signRes.data.submission.status === "pending" && expired) {
      // Past-due but not yet swept: the server rejects /complete the same way.
      blockedReason.value = "This envelope reached its expiration date and can no longer be signed.";
      phase.value = "blocked";
    } else if (signRes.data.submission.status === "expired") {
      blockedReason.value = "This envelope reached its expiration date and can no longer be signed.";
      phase.value = "blocked";
    } else if (signRes.data.submission.status === "pending" && !signRes.data.my_turn) {
      blockedReason.value =
        "This envelope collects signatures in order — you'll get an email when it's your turn to sign.";
      phase.value = "blocked";
    } else if (signRes.data.submission.status === "declined") {
      blockedReason.value = "This envelope was declined and is no longer active.";
      phase.value = "blocked";
    } else if (signRes.data.submission.status !== "pending") {
      blockedReason.value = "This document is no longer active.";
      phase.value = "blocked";
    } else {
      if (signRes.data.saved_signature_id != null) {
        await loadAccountSavedSignature(signRes.data.saved_signature_id);
      }
      phase.value = "signing";
      startTour();
    }
  } catch (err) {
    if (axios.isAxiosError(err) && err.response?.status === 403) {
      errorMessage.value = "You don't have access to this signing link.";
    } else {
      errorMessage.value = extractError(err);
    }
    phase.value = "error";
  }
}

onMounted(load);
onBeforeUnmount(() => {
  if (pdfUrl.value) URL.revokeObjectURL(pdfUrl.value);
  if (accountSavedSignatureUrl.value) URL.revokeObjectURL(accountSavedSignatureUrl.value);
});

// --- Review & finish ---------------------------------------------------------

const reviewOpen = ref(false);
const consentGiven = ref(false);
const finishing = ref(false);

/** Post-completion submission state, for the success screen (who's still pending / PDF link).
 * Internal signers only — externals have no session to call GET /submissions/{id} with. */
const finishedSubmission = ref<SubmissionOut | null>(null);

/** Externals-only counterpart to `finishedSubmission?.status === 'completed'`: whether the
 * whole envelope is done, from the cookie-authorized GET /sign/{submitterId} (`SignerViewOut`). */
const externalEnvelopeCompleted = ref<boolean | null>(null);

/** Whether to show the "everyone's done, here's the download" success-card variant. */
const successCompleted = computed(() =>
  props.external ? externalEnvelopeCompleted.value === true : finishedSubmission.value?.status === "completed",
);

function openReview(): void {
  if (!canFinish.value) {
    // Jump the user to the first missing required field instead of refusing silently.
    const idx = tourFields.value.findIndex((f) => f.required && !fieldComplete(f));
    if (idx !== -1) goToIndex(idx);
    return;
  }
  consentGiven.value = false;
  reviewOpen.value = true;
}

function reviewValueText(field: FieldDef): string {
  if (field.type === "date") return (fieldValues[field.id] as string | undefined) ?? "—";
  if (field.type === "checkbox") return fieldValues[field.id] === true ? "Checked" : "Not checked";
  if (field.type === "text" || field.type === "name" || field.type === "dropdown" || field.type === "radio") {
    return (fieldValues[field.id] as string | undefined)?.trim() || "—";
  }
  if (field.type === "attachment") return fieldAttachments[field.id]?.filename ?? "—";
  return "";
}

function buildValues(): Record<string, unknown> {
  const values: Record<string, unknown> = {};
  for (const field of myFieldDefs.value) {
    if (field.type === "name") {
      // Send the (possibly edited) name; if somehow blank, omit it and let
      // the server fall back to the account name at stamping time.
      const name = (fieldValues[field.id] as string | undefined)?.trim();
      if (name) values[field.id] = name;
      continue;
    }
    if (field.type === "signature" || field.type === "initials") {
      const sigId = fieldSignatureIds[field.id];
      if (sigId != null) values[field.id] = sigId;
    } else if (field.type === "date") {
      values[field.id] = (fieldValues[field.id] as string | undefined) ?? todayISODate();
    } else if (field.type === "checkbox") {
      values[field.id] = fieldValues[field.id] === true;
    } else if (field.type === "text") {
      const text = (fieldValues[field.id] as string | undefined)?.trim();
      if (text) values[field.id] = text;
    } else if (field.type === "dropdown" || field.type === "radio") {
      const choice = fieldValues[field.id] as string | undefined;
      if (choice) values[field.id] = choice;
    } else if (field.type === "attachment") {
      const attachment = fieldAttachments[field.id];
      if (attachment) values[field.id] = attachment.id;
    }
  }
  return values;
}

async function finish(): Promise<void> {
  if (!canFinish.value || !consentGiven.value) return;
  finishing.value = true;
  errorMessage.value = null;
  try {
    await http.post(
      `/sign/${props.submitterId}/complete`,
      { values: buildValues() },
      { skipAuthRedirect: props.external === true },
    );
    reviewOpen.value = false;
    phase.value = "success";
    // Best-effort: find out whether everyone's done (download link) or who
    // we're still waiting on. Externals have no session for
    // GET /submissions/{id}, so re-poll the cookie-authorized sign view
    // instead — its submission.status reflects completion the same way.
    if (props.external) {
      try {
        const { data } = await http.get<SignerViewOut>(`/sign/${props.submitterId}`, { skipAuthRedirect: true });
        externalEnvelopeCompleted.value = data.submission.status === "completed";
      } catch {
        externalEnvelopeCompleted.value = false;
      }
    } else if (view.value) {
      try {
        const { data } = await http.get<SubmissionOut>(`/submissions/${view.value.submission.id}`);
        finishedSubmission.value = data;
      } catch {
        finishedSubmission.value = null;
      }
    }
  } catch (err) {
    if (axios.isAxiosError(err) && err.response?.status === 409) {
      reviewOpen.value = false;
      blockedReason.value = "This document is no longer active.";
      phase.value = "blocked";
    } else {
      errorMessage.value = extractError(err);
      reviewOpen.value = false;
    }
  } finally {
    finishing.value = false;
  }
}

const pendingOthers = computed(() =>
  (finishedSubmission.value?.submitters ?? []).filter((s) => !s.is_cc && s.status !== "completed"),
);

// --- Decline ---------------------------------------------------------------

const declineOpen = ref(false);
const declineReason = ref("");
const declining = ref(false);

async function decline(): Promise<void> {
  declining.value = true;
  errorMessage.value = null;
  try {
    await http.post(
      `/sign/${props.submitterId}/decline`,
      { reason: declineReason.value.trim() || null },
      { skipAuthRedirect: props.external === true },
    );
    declineOpen.value = false;
    phase.value = "declined";
  } catch (err) {
    errorMessage.value = extractError(err);
    declineOpen.value = false;
  } finally {
    declining.value = false;
  }
}
</script>

<template>
  <v-container fluid class="sign-view">
    <v-progress-linear v-if="phase === 'loading'" indeterminate class="mb-4" />

    <v-alert v-if="phase === 'error'" type="error">{{ errorMessage }}</v-alert>

    <v-card v-else-if="phase === 'blocked'" class="state-card" variant="flat" border>
      <v-card-text class="text-center py-8">
        <v-icon icon="mdi-file-lock-outline" size="48" class="mb-3 text-medium-emphasis" aria-hidden="true" />
        <p class="text-h6 mb-1">{{ blockedReason }}</p>
        <template v-if="view?.submission.status === 'completed'">
          <p class="text-medium-emphasis mb-4">Everyone has signed — the final document is ready.</p>
          <v-btn
            color="primary"
            variant="tonal"
            :href="`/api/files/signed-pdf/${view.submission.id}`"
            target="_blank"
            prepend-icon="mdi-file-pdf-box"
          >
            View signed PDF
          </v-btn>
        </template>
        <p v-if="props.external" class="text-medium-emphasis mt-4 mb-0">You can close this window.</p>
        <div v-else class="mt-4">
          <v-btn variant="text" :to="{ name: 'dashboard' }" prepend-icon="mdi-home">Back to home</v-btn>
        </div>
      </v-card-text>
    </v-card>

    <v-card v-else-if="phase === 'success'" class="state-card" variant="flat" border>
      <v-card-text class="text-center py-8">
        <v-icon icon="mdi-check-decagram" size="56" color="success" class="mb-3" aria-hidden="true" />
        <p class="text-h5 mb-1">Thanks — your part is done.</p>
        <template v-if="successCompleted">
          <p class="text-medium-emphasis mb-4">
            You were the last signer — "{{ view?.submission.title }}" is complete.
          </p>
          <v-btn
            color="primary"
            variant="flat"
            :href="`/api/files/signed-pdf/${view?.submission.id}`"
            target="_blank"
            prepend-icon="mdi-file-pdf-box"
          >
            Download signed PDF
          </v-btn>
        </template>
        <template v-else>
          <p class="text-medium-emphasis mb-1">
            You'll get an email with the final PDF once everyone has signed "{{ view?.submission.title }}".
          </p>
          <p v-if="pendingOthers.length > 0" class="text-body-2 text-medium-emphasis mb-4">
            Still waiting on {{ pendingOthers.map((s) => s.user.name).join(", ") }}.
          </p>
        </template>
        <p v-if="props.external" class="text-medium-emphasis mt-4 mb-0">You can close this window.</p>
        <div v-else class="mt-4">
          <v-btn variant="text" :to="{ name: 'dashboard' }" prepend-icon="mdi-home">Back to home</v-btn>
        </div>
      </v-card-text>
    </v-card>

    <v-card v-else-if="phase === 'declined'" class="state-card" variant="flat" border>
      <v-card-text class="text-center py-8">
        <v-icon icon="mdi-close-octagon-outline" size="56" color="error" class="mb-3" aria-hidden="true" />
        <p class="text-h5 mb-1">You declined to sign.</p>
        <p class="text-medium-emphasis">The sender has been notified.</p>
        <p v-if="props.external" class="text-medium-emphasis mt-4 mb-0">You can close this window.</p>
        <div v-else class="mt-4">
          <v-btn variant="text" :to="{ name: 'dashboard' }" prepend-icon="mdi-home">Back to home</v-btn>
        </div>
      </v-card-text>
    </v-card>

    <template v-else-if="phase === 'signing' && view">
      <div class="sign-header mb-3">
        <div class="d-flex align-center flex-wrap">
          <div class="mr-4">
            <h1 class="text-h6 mb-0">{{ view.submission.title }}</h1>
            <p v-if="view.submission.message" class="text-medium-emphasis text-body-2 mb-0">
              {{ view.submission.message }}
            </p>
          </div>
          <v-spacer />
          <v-chip
            v-if="view.submission.expires_at"
            size="small"
            variant="tonal"
            color="warning"
            prepend-icon="mdi-clock-alert-outline"
            class="mr-3"
          >
            Expires {{ formatDate(view.submission.expires_at) }}
          </v-chip>
          <span class="text-body-2 text-medium-emphasis">
            {{ completedCount }} of {{ tourFields.length }} fields done
          </span>
        </div>
        <v-progress-linear
          :model-value="tourFields.length === 0 ? 100 : (completedCount / tourFields.length) * 100"
          color="primary"
          height="6"
          rounded
          class="mt-2"
        />
      </div>

      <v-alert v-if="errorMessage" type="error" closable class="mb-4" @click:close="errorMessage = null">
        {{ errorMessage }}
      </v-alert>

      <!-- Floating DocuSign-Style Guided Tag -->
      <div v-if="tourFields.length > 0" class="pf-guided-tag-wrapper">
        <button
          type="button"
          class="pf-guided-tag"
          :class="{
            'pf-tag-start': completedCount === 0 && !canFinish,
            'pf-tag-next': completedCount > 0 && !canFinish,
            'pf-tag-finish': canFinish,
          }"
          :title="canFinish ? 'Review and finish document' : (completedCount === 0 ? 'Click to start signing' : 'Next required field')"
          aria-label="Guided signing navigation"
          @click="canFinish ? openReview() : (completedCount === 0 ? startTour() : goNext())"
        >
          <template v-if="completedCount === 0 && !canFinish">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" class="mr-1">
              <path d="M8 5v14l11-7z"/>
            </svg>
            <span>START</span>
          </template>
          <template v-else-if="!canFinish">
            <span>NEXT</span>
            <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" class="mx-1">
              <path d="M8 5v14l11-7z"/>
            </svg>
            <span class="pf-tag-badge" aria-live="polite">{{ missingRequiredCount }}</span>
          </template>
          <template v-else>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" class="mr-1">
              <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
            </svg>
            <span>REVIEW & FINISH</span>
          </template>
        </button>
      </div>

      <div v-for="page in pageNumbers" :key="page" class="page-wrapper mb-6">
        <PdfPage
          v-if="pdfUrl"
          :src="pdfUrl"
          :page="page"
          @rendered="(w: number, h: number, wPt: number, hPt: number) => onRendered(page, w, h, wPt, hPt)"
          @error="onPdfError"
        >
          <!-- Sender text: static, part of the document for everyone -->
          <div
            v-for="field in fieldsForPage(page).labels"
            :key="field.id"
            class="label-field"
            :style="{ ...fieldStyle(field, page), ...fieldTextStyle(field, page) }"
          >
            {{ field.default_value }}
          </div>

          <!-- Other signers' fields: read-only, greyed -->
          <div
            v-for="field in fieldsForPage(page).others"
            :key="field.id"
            class="other-field"
            :style="fieldStyle(field, page)"
          >
            <span>{{ otherFieldLabel(field) }}</span>
          </div>

          <!-- My fields: interactive, with done / active / to-do states -->
          <div
            v-for="field in fieldsForPage(page).mine"
            :key="field.id"
            class="my-field"
            :class="fieldStateClass(field)"
            :style="fieldStyle(field, page)"
            :data-field-id="field.id"
            @pointerdown="setCurrentField(field.id)"
          >
            <v-icon
              v-if="fieldComplete(field)"
              icon="mdi-check-circle"
              size="x-small"
              class="field-check"
              color="success"
              aria-hidden="true"
            />

            <!-- Accessible name must contain the visible "Click to sign" text
                 (WCAG 2.5.3 label-in-name); an aria-label that omits it makes
                 the button unfindable by its on-screen label. -->
            <button
              v-if="field.type === 'signature' || field.type === 'initials'"
              type="button"
              class="signature-slot"
              :aria-label="`${signatureImageUrls[field.id] ? `Your ${field.type}` : field.type === 'initials' ? 'Click to initial' : 'Click to sign'} — ${fieldAriaLabel(field)}`"
              @click="openSignaturePad(field.id, field.type === 'initials')"
            >
              <img
                v-if="signatureImageUrls[field.id]"
                :src="signatureImageUrls[field.id]"
                :alt="field.type === 'initials' ? 'Your initials' : 'Your signature'"
              />
              <span v-else>{{ field.type === "initials" ? "Initial" : "Click to sign" }}</span>
            </button>

            <input
              v-else-if="field.type === 'name'"
              v-model="fieldValues[field.id] as string"
              type="text"
              class="plain-input"
              :style="fieldTextStyle(field, page)"
              :aria-label="fieldAriaLabel(field)"
              :title="editHint(field)"
              @focus="setCurrentField(field.id)"
            />

            <input
              v-else-if="field.type === 'date'"
              v-model="fieldValues[field.id] as string"
              type="date"
              class="plain-input"
              :style="fieldTextStyle(field, page)"
              :aria-label="fieldAriaLabel(field)"
              :title="editHint(field)"
              @focus="setCurrentField(field.id)"
            />

            <input
              v-else-if="field.type === 'checkbox'"
              v-model="fieldValues[field.id] as unknown as boolean"
              type="checkbox"
              class="checkbox-input"
              :aria-label="fieldAriaLabel(field)"
              @focus="setCurrentField(field.id)"
            />

            <input
              v-else-if="field.type === 'text'"
              v-model="fieldValues[field.id] as string"
              type="text"
              class="plain-input"
              :class="{ 'input-invalid': !textValid(field) }"
              :style="fieldTextStyle(field, page)"
              :aria-label="fieldAriaLabel(field)"
              :aria-invalid="!textValid(field)"
              :title="editHint(field)"
              @focus="setCurrentField(field.id)"
            />

            <select
              v-else-if="field.type === 'dropdown' || field.type === 'radio'"
              v-model="fieldValues[field.id] as string"
              class="plain-input choice-input"
              :style="fieldTextStyle(field, page)"
              :aria-label="fieldAriaLabel(field)"
              :title="editHint(field)"
              @focus="setCurrentField(field.id)"
            >
              <option value="" disabled>Choose…</option>
              <option v-for="option in field.options ?? []" :key="option" :value="option">
                {{ option }}
              </option>
            </select>

            <button
              v-else-if="field.type === 'attachment'"
              type="button"
              class="signature-slot attachment-slot"
              :disabled="uploadingAttachment"
              :aria-label="`${fieldAttachments[field.id] ? `Attached: ${fieldAttachments[field.id].filename}` : 'Attach file'} — ${fieldAriaLabel(field)}`"
              :title="editHint(field)"
              @click="openAttachmentPicker(field.id)"
            >
              <v-icon icon="mdi-paperclip" size="x-small" class="mr-1" aria-hidden="true" />
              <span class="attachment-name">
                {{ fieldAttachments[field.id]?.filename ?? "Attach file" }}
              </span>
            </button>
          </div>
        </PdfPage>
      </div>

      <!-- One hidden picker shared by every attachment field. -->
      <input
        ref="attachmentInputRef"
        type="file"
        accept="application/pdf,image/png,image/jpeg"
        class="d-none"
        @change="onAttachmentChosen"
      />

      <!-- Guided dock -->
      <v-card class="finish-bar" elevation="8">
        <v-card-text class="d-flex align-center py-3 dock-row">
          <v-btn
            variant="text"
            icon="mdi-chevron-up"
            :disabled="currentIndex === 0"
            aria-label="Previous field"
            @click="goBack"
          />
          <div class="dock-info mx-2" role="status">
            <template v-if="currentField">
              <span class="font-weight-medium">
                {{ FIELD_TYPE_LABELS[currentField.type] }}
                <span v-if="currentField.required" class="text-medium-emphasis">(required)</span>
              </span>
              <span class="text-caption text-medium-emphasis d-block">
                Field {{ currentIndex + 1 }} of {{ tourFields.length }} · page {{ currentField.page + 1 }}
                <template v-if="missingRequiredCount > 0"> · {{ missingRequiredCount }} required left</template>
                <template v-if="editHint(currentField)"> · {{ editHint(currentField) }}</template>
              </span>
            </template>
            <span v-else class="text-medium-emphasis">No fields assigned to you.</span>
          </div>
          <v-spacer />
          <v-btn
            v-if="!canFinish"
            color="primary"
            variant="tonal"
            class="mr-2"
            append-icon="mdi-chevron-down"
            @click="goNext"
          >
            Next
          </v-btn>
          <v-btn variant="text" color="error" class="mr-2" @click="declineOpen = true">Decline</v-btn>
          <v-btn color="primary" variant="flat" :disabled="!canFinish" @click="openReview">
            Finish
          </v-btn>
        </v-card-text>
      </v-card>

      <SignaturePad
        v-model="padOpen"
        :saved-image-url="activeSavedImageUrl"
        :mode="activeIsInitials ? 'initials' : 'signature'"
        :typed-default="activeIsInitials ? myInitials : undefined"
        @save="handleSaveSignature"
        @use-saved="handleUseSaved"
      />

      <!-- Review & consent -->
      <v-dialog v-model="reviewOpen" max-width="560">
        <v-card>
          <v-card-title>Review before signing</v-card-title>
          <v-card-text>
            <v-list density="compact" class="review-list mb-2">
              <v-list-item v-for="field in tourFields" :key="field.id">
                <template #prepend>
                  <v-icon
                    :icon="fieldComplete(field) ? 'mdi-check-circle' : 'mdi-circle-outline'"
                    :color="fieldComplete(field) ? 'success' : 'grey'"
                    size="small"
                  />
                </template>
                <v-list-item-title class="text-body-2">
                  {{ FIELD_TYPE_LABELS[field.type] }} · page {{ field.page + 1 }}
                </v-list-item-title>
                <template #append>
                  <img
                    v-if="(field.type === 'signature' || field.type === 'initials') && signatureImageUrls[field.id]"
                    :src="signatureImageUrls[field.id]"
                    :alt="field.type === 'initials' ? 'Initials preview' : 'Signature preview'"
                    class="review-signature"
                  />
                  <span v-else class="text-body-2 text-medium-emphasis review-value">
                    {{ reviewValueText(field) }}
                  </span>
                </template>
              </v-list-item>
            </v-list>
            <v-checkbox
              v-model="consentGiven"
              density="compact"
              hide-details
              label="I agree that my electronic signature on this document is legally binding, the same as my handwritten signature."
            />
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="text" @click="reviewOpen = false">Keep editing</v-btn>
            <v-btn color="primary" variant="flat" :disabled="!consentGiven" :loading="finishing" @click="finish">
              Sign &amp; finish
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>

      <!-- Decline -->
      <v-dialog v-model="declineOpen" max-width="480">
        <v-card>
          <v-card-title>Decline to sign?</v-card-title>
          <v-card-text>
            <p class="mb-3">This voids the envelope for everyone. The sender will be notified.</p>
            <v-textarea v-model="declineReason" label="Reason (optional)" rows="3" counter="500" maxlength="500" />
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="text" @click="declineOpen = false">Keep signing</v-btn>
            <v-btn color="error" variant="flat" :loading="declining" @click="decline">Decline</v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>
    </template>
  </v-container>
</template>

<style scoped>
.sign-view {
  max-width: 980px;
}

.state-card {
  max-width: 560px;
  margin: 48px auto 0;
}

.sign-header {
  max-width: 900px;
  margin: 0 auto;
}

.page-wrapper {
  max-width: 900px;
  margin-left: auto;
  margin-right: auto;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.18);
}

.label-field {
  position: absolute;
  display: flex;
  align-items: center;
  overflow: hidden;
  white-space: pre-wrap;
  pointer-events: none;
  font-family: Helvetica, Arial, sans-serif;
  color: #1a1a1a;
  box-sizing: border-box;
}

.other-field {
  position: absolute;
  border: 1px dashed #666;
  background: rgba(102, 102, 102, 0.15);
  opacity: 0.4;
  pointer-events: none;
  box-sizing: border-box;
  font-size: 10px;
  line-height: 1.2;
  overflow: hidden;
  padding: 1px 2px;
  color: #333;
}

.my-field {
  position: absolute;
  box-sizing: border-box;
  border-radius: 2px;
  transition: box-shadow 0.15s ease, border-color 0.15s ease;
}

.my-field.field-todo {
  border: 1.5px solid #90a4ae;
  background: rgba(144, 164, 174, 0.08);
}

.my-field.field-todo-required {
  border: 1.5px solid rgb(var(--v-theme-warning));
  background: rgba(var(--v-theme-warning), 0.07);
}

.my-field.field-done {
  border: 1.5px solid rgb(var(--v-theme-success));
  background: rgba(var(--v-theme-success), 0.06);
}

.my-field.field-active {
  border: 2px solid rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.08);
  box-shadow: 0 0 0 4px rgba(var(--v-theme-primary), 0.2);
}

.field-check {
  position: absolute;
  top: -7px;
  right: -7px;
  background: #fff;
  border-radius: 50%;
  z-index: 1;
}

.signature-slot {
  width: 100%;
  height: 100%;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: rgb(var(--v-theme-primary));
  font-weight: 600;
}

.signature-slot img {
  max-width: 100%;
  max-height: 100%;
}

.plain-input {
  width: 100%;
  height: 100%;
  border: none;
  background: transparent;
  padding: 0 4px;
  font-family: Helvetica, Arial, sans-serif;
  /* Fallback until the page reports its size; fieldTextStyle() then applies
     the stamped-PDF-equivalent font size and inset inline. */
  font-size: 12px;
  box-sizing: border-box;
  cursor: text;
}

/* Prefilled fields land in the green "done" state immediately, which reads
   as locked — the hover/focus tint says "this is an input you can change". */
.plain-input:hover {
  background: rgba(var(--v-theme-primary), 0.07);
}

.plain-input:focus {
  outline: none;
  background: rgba(var(--v-theme-primary), 0.1);
}

.checkbox-input {
  width: 100%;
  height: 100%;
  min-width: 16px;
  min-height: 16px;
  cursor: pointer;
  accent-color: rgb(var(--v-theme-primary));
}

.input-invalid {
  background: rgba(var(--v-theme-error), 0.08);
  outline: 1.5px solid rgb(var(--v-theme-error));
}

.choice-input {
  cursor: pointer;
  appearance: auto;
}

.attachment-slot {
  font-weight: 500;
  padding: 0 2px;
}

.attachment-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.finish-bar {
  position: sticky;
  bottom: 12px;
  max-width: 900px;
  margin: 0 auto 24px;
  border-radius: 10px;
}

.dock-row {
  flex-wrap: wrap;
  gap: 4px;
}

.dock-info {
  min-width: 0;
}

.review-list {
  max-height: 260px;
  overflow-y: auto;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 8px;
}

.review-signature {
  max-height: 28px;
  max-width: 120px;
}

.review-value {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Floating Guided Tag */
.pf-guided-tag-wrapper {
  position: fixed;
  top: 80px;
  right: 24px;
  z-index: 700;
}

.pf-guided-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 9999px;
  font-size: 0.86rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  border: 1px solid rgba(255, 255, 255, 0.3);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.2), 0 2px 6px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  user-select: none;
  transition: transform 0.18s ease, box-shadow 0.18s ease, filter 0.18s ease;
}

.pf-guided-tag:hover {
  transform: translateY(-2px) scale(1.03);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.28);
}

.pf-guided-tag:active {
  transform: translateY(0) scale(0.98);
}

.pf-tag-start {
  background: linear-gradient(135deg, #D97706 0%, #B45309 100%);
  color: #ffffff;
  animation: pf-pulse 2.2s infinite ease-in-out;
}

.pf-tag-next {
  background: linear-gradient(135deg, #1A56DB 0%, #1E40AF 100%);
  color: #ffffff;
}

.pf-tag-finish {
  background: linear-gradient(135deg, #059669 0%, #047857 100%);
  color: #ffffff;
}

.pf-tag-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.25);
  border-radius: 9999px;
  padding: 1px 7px;
  font-size: 0.76rem;
  margin-left: 2px;
}

@keyframes pf-pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(217, 119, 6, 0.6);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(217, 119, 6, 0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .pf-guided-tag {
    transition: none !important;
    animation: none !important;
  }
}

@media (max-width: 600px) {
  .pf-guided-tag-wrapper {
    top: auto;
    bottom: 84px;
    right: 16px;
  }
}
</style>
