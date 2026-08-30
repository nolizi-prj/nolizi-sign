<script setup lang="ts">
/**
 * Send wizard, admin-only. Two paths through numbered steps:
 *
 * - Template:  1 Document (pick) → 2 Signers & message → 3 Review & send
 *   (POST /submissions)
 * - One-off:   1 Document (upload a PDF) → 2 Signers → 3 Place fields →
 *   4 Review & send (POST /submissions/adhoc with signers_json/fields_json)
 *
 * One-off documents are PDF-only: the file is rendered locally (blob URL,
 * never uploaded until Send) so fields can be placed before anything hits
 * the server. docx/xlsx need server-side conversion first — for those,
 * create a template instead.
 *
 * One-off recipients are person-first: the UI only ever asks "who signs?"
 * and shows names; the required role strings are generated as
 * signer-1..signer-N under the hood (the same convention the earlier
 * EnvelopeComposeView established, consolidated into this wizard).
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import axios from "axios";
import http, { extractBlobError, extractError } from "../utils/http";
import { useAuthStore } from "../store/auth";
import { useUiStore } from "../store/ui";
import { userLabel } from "../utils/labels";
import { roleColor, templateRoles } from "../utils/roleColors";
import { UPLOAD_ACCEPT } from "../utils/uploads";
import { useFieldPlacement } from "../composables/useFieldPlacement";
import PdfPage from "../components/PdfPage.vue";
import FieldBox from "../components/FieldBox.vue";
import FieldPropertiesPanel from "../components/FieldPropertiesPanel.vue";
import NewTemplateDialog from "../components/NewTemplateDialog.vue";
import { FIELD_TYPES, type FieldDef, type SubmissionOut, type TemplateOut, type User } from "../types";

const props = defineProps<{ templateId?: string; draftId?: string }>();
const router = useRouter();
const auth = useAuthStore();
const ui = useUiStore();

const loading = ref(true);
const submitting = ref(false);
const errorMessage = ref<string | null>(null);

const templates = ref<TemplateOut[]>([]);
const users = ref<User[]>([]);

/** "Create template" from step 1 — same dialog as the Templates page; on
 *  create it navigates into the field builder. */
const newTemplateDialog = ref(false);

type Mode = "template" | "adhoc";
const mode = ref<Mode>("template");
const step = ref(1);

const selectedTemplate = ref<TemplateOut | null>(null);
const title = ref("");
const message = ref("");
const roleAssignments = ref<Record<string, number | null>>({});

// --- envelope options (both modes) ------------------------------------------

/** Optional deadline (a plain date input; sent as end-of-day local time). */
const expiryDate = ref("");
const remindersEnabled = ref(true);
const reminderInterval = ref(3);
const REMINDER_INTERVAL_ITEMS = [1, 2, 3, 5, 7, 14].map((n) => ({
  title: `Every ${n} day${n === 1 ? "" : "s"}`,
  value: n,
}));

const todayIso = new Date().toISOString().slice(0, 10);
const expiryInPast = computed(() => expiryDate.value !== "" && expiryDate.value <= todayIso);

/** The chosen expiry as an ISO datetime (end of that day, local), or null. */
function expiresAtIso(): string | null {
  if (!expiryDate.value) return null;
  return new Date(`${expiryDate.value}T23:59:59`).toISOString();
}

// --- Routing order + CC rows ------------------------------------------------

/** When on, every recipient row shows an editable order number (DocuSign
 *  style): same number = reached in parallel, lower numbers first. */
const signInOrder = ref(false);

/** CC recipients ("receives a copy"): a person row with its own order
 *  number — they're emailed a copy when routing reaches their group and the
 *  final signed PDF at completion; they never sign and never block. */
const ccRows = ref<{ userId: number | null; orderNum: number }[]>([]);

/** Per-role order numbers for template mode (1-based, shown when ordered). */
const templateOrderNums = ref<Record<string, number>>({});
/** Per-row order numbers for one-off signers (parallel to adhocRecipients). */
const adhocOrderNums = ref<number[]>([1]);

function nextOrderNum(): number {
  const all = [
    ...Object.values(templateOrderNums.value),
    ...adhocOrderNums.value,
    ...ccRows.value.map((r) => r.orderNum),
  ];
  return all.length > 0 ? Math.max(...all) + 1 : 1;
}

function addCcRow(): void {
  ccRows.value.push({ userId: null, orderNum: signInOrder.value ? nextOrderNum() : 1 });
}

function removeCcRow(index: number): void {
  ccRows.value.splice(index, 1);
  ccComboboxResetTick.value.splice(index, 1);
}

/** 1-based UI order number -> 0-based backend order (0 for everyone when the toggle is off). */
function toOrder(orderNum: number): number {
  if (!signInOrder.value) return 0;
  return Math.max(0, Math.round(orderNum || 1) - 1);
}

// --- ad-hoc state ----------------------------------------------------------

const adhocFile = ref<File | null>(null);
const adhocPdfUrl = ref<string | null>(null);
const adhocPageCount = ref(0);
/** One entry per recipient; the internal role for index i is `signer-${i+1}`. */
const adhocRecipients = ref<(number | null)[]>([null]);
const adhocFields = ref<FieldDef[]>([]);

/** When editing an existing draft: its id — Task "send" deletes it after
 *  the replacement envelope is created (recreate-on-save; see the spec). */
const draftSourceId = ref<number | null>(null);
/** Set when the loaded draft's expiration had already passed. */
const draftExpiryCleared = ref(false);

function adhocRole(index: number): string {
  return `signer-${index + 1}`;
}

function adhocRecipientName(index: number): string {
  const user = users.value.find((u) => u.id === adhocRecipients.value[index]);
  return user?.name ?? `Recipient ${index + 1}`;
}

/** Person name for an internal signer-N role, for field labels and the review step. */
function displayNameForRole(role: string): string {
  if (mode.value !== "adhoc") return role;
  const idx = roles.value.indexOf(role);
  return idx === -1 ? role : adhocRecipientName(idx);
}

const stepTitles = computed<string[]>(() =>
  mode.value === "template"
    ? ["Document", "Signers & message", "Review & send"]
    : ["Document", "Signers", "Place fields", "Review & send"],
);

const roles = computed<string[]>(() => {
  if (mode.value === "adhoc") return adhocRecipients.value.map((_, i) => adhocRole(i));
  return selectedTemplate.value ? templateRoles(selectedTemplate.value) : [];
});

/** Roles (either mode) the backend would reject at send time because no field references them. */
const rolesWithoutFields = computed<string[]>(() => roles.value.filter((role) => fieldCountForRole(role) === 0));

const userItems = computed(() =>
  users.value.map((u) => ({ ...u, display: u.is_external ? `${userLabel(u)} · external` : userLabel(u) })),
);

function userName(userId: number | null): string {
  const user = users.value.find((u) => u.id === userId);
  return user ? userLabel(user) : "—";
}

function fieldCountForRole(role: string): number {
  const fields = mode.value === "adhoc" ? adhocFields.value : (selectedTemplate.value?.fields ?? []);
  return fields.filter((f) => f.role === role).length;
}

// --- step 1: document ------------------------------------------------------

function selectTemplate(template: TemplateOut): void {
  mode.value = "template";
  selectedTemplate.value = template;
  title.value = template.name;
  message.value = "";
  // Templates built with emails as role names look pre-assigned on the
  // signers step even though nobody is — pre-assign the matching user when
  // a role name is exactly an existing user's email (still editable).
  roleAssignments.value = Object.fromEntries(
    templateRoles(template).map((role) => [
      role,
      users.value.find((u) => u.email.toLowerCase() === role.trim().toLowerCase())?.id ?? null,
    ]),
  );
  templateOrderNums.value = Object.fromEntries(templateRoles(template).map((role, i) => [role, i + 1]));
  errorMessage.value = null;
  step.value = 2;
}

/** The raw files the user picked (before any merge); `adhocFile` below is the single PDF actually sent. */
const adhocSourceFiles = ref<File[]>([]);
const preparingDocument = ref(false);
// Guards against a stale merge response landing after the user re-picked files.
let adhocPickGen = 0;

function fileStem(name: string): string {
  return name.replace(/\.[^.]+$/, "");
}

async function onAdhocFilesChosen(picked: File | File[] | null): Promise<void> {
  const files = (Array.isArray(picked) ? picked : picked ? [picked] : []).filter(Boolean);
  const gen = ++adhocPickGen;
  clearAdhocPdf();
  adhocFile.value = null;
  adhocSourceFiles.value = files;
  if (files.length === 0) return;

  mode.value = "adhoc";
  // Envelope name auto-generated from the (first) file's name, still editable.
  if (!title.value.trim()) title.value = fileStem(files[0].name);
  adhocFields.value = [];
  adhocPage.value = 0;

  const singlePdf = files.length === 1 && /\.pdf$/i.test(files[0].name);
  if (singlePdf) {
    adhocFile.value = files[0];
    adhocPdfUrl.value = URL.createObjectURL(files[0]);
    return;
  }

  // Multiple files (or an office format): the backend converts and merges
  // them into the one PDF fields get placed on — in the order picked.
  preparingDocument.value = true;
  errorMessage.value = null;
  try {
    const formData = new FormData();
    for (const file of files) formData.append("files", file);
    const { data } = await http.post<Blob>("/submissions/adhoc/merged-document", formData, {
      responseType: "blob",
    });
    if (gen !== adhocPickGen) return; // user re-picked while merging
    const merged = new File([data], `${fileStem(files[0].name)}.pdf`, { type: "application/pdf" });
    adhocFile.value = merged;
    adhocPdfUrl.value = URL.createObjectURL(merged);
  } catch (err) {
    if (gen === adhocPickGen) {
      // extractError can't read a blob response's detail — surface it manually.
      errorMessage.value = await extractBlobError(err);
    }
  } finally {
    if (gen === adhocPickGen) preparingDocument.value = false;
  }
}

/** Move a picked file up/down and re-run the merge with the new order.
 *  Reuses `onAdhocFilesChosen` so the stale-merge generation guard applies. */
function moveSourceFile(index: number, delta: number): void {
  const files = [...adhocSourceFiles.value];
  const target = index + delta;
  if (target < 0 || target >= files.length) return;
  const moved = files.splice(index, 1)[0];
  if (!moved) return;
  files.splice(target, 0, moved);
  void onAdhocFilesChosen(files);
}

function removeSourceFile(index: number): void {
  void onAdhocFilesChosen(adhocSourceFiles.value.filter((_, i) => i !== index));
}

function clearAdhocPdf(): void {
  if (adhocPdfUrl.value) URL.revokeObjectURL(adhocPdfUrl.value);
  adhocPdfUrl.value = null;
  adhocPageCount.value = 0;
}

onBeforeUnmount(clearAdhocPdf);

function onAdhocPdfLoaded(count: number): void {
  adhocPageCount.value = count;
}

function onAdhocPdfError(msg: string): void {
  errorMessage.value = `Couldn't display that PDF: ${msg}`;
  adhocFile.value = null;
  adhocSourceFiles.value = [];
  clearAdhocPdf();
}

// --- step gating ------------------------------------------------------------

const canLeaveStep1 = computed(() => {
  if (mode.value === "template") return selectedTemplate.value !== null;
  return adhocFile.value !== null && title.value.trim().length > 0;
});

const ccRowsComplete = computed(() => ccRows.value.every((row) => row.userId != null));

const signersComplete = computed(() => {
  if (expiryInPast.value) return false;
  if (!ccRowsComplete.value) return false;
  if (mode.value === "template") {
    return (
      roles.value.length > 0 &&
      rolesWithoutFields.value.length === 0 &&
      title.value.trim().length > 0 &&
      roles.value.every((r) => roleAssignments.value[r] != null)
    );
  }
  return adhocRecipients.value.length > 0 && adhocRecipients.value.every((uid) => uid != null);
});

/** Why the signers step's Continue is disabled, in words — or null when it isn't.
 *  Roles-without-fields and no-roles-at-all already have their own alert/message
 *  on the page, so they return null here rather than saying it twice. */
const signersBlocker = computed<string | null>(() => {
  if (signersComplete.value) return null;
  if (expiryInPast.value) return "The expiration date must be in the future.";
  if (!ccRowsComplete.value) return "Pick a person for every CC row to continue.";
  if (mode.value === "template") {
    if (roles.value.length === 0 || rolesWithoutFields.value.length > 0) return null;
    if (title.value.trim().length === 0) return "Enter a title to continue.";
    return "Assign a person to every signer role to continue.";
  }
  return "Pick a person for every signer to continue.";
});

/** Ad-hoc: `rolesWithoutFields` as person names, for the placement step's caption. */
const recipientsMissingFields = computed<string[]>(() =>
  mode.value === "adhoc" ? rolesWithoutFields.value.map((role) => displayNameForRole(role)) : [],
);

const reviewStep = computed(() => stepTitles.value.length);

function canProceedFrom(current: number): boolean {
  if (current === 1) return canLeaveStep1.value;
  if (current === 2) return signersComplete.value;
  if (current === 3 && mode.value === "adhoc") return recipientsMissingFields.value.length === 0;
  return true;
}

// --- ad-hoc recipient management --------------------------------------------

function addRecipient(): void {
  adhocRecipients.value.push(null);
  adhocOrderNums.value.push(signInOrder.value ? nextOrderNum() : 1);
}

function removeRecipient(index: number): void {
  adhocOrderNums.value.splice(index, 1);
  const removedRole = adhocRole(index);
  // Drop the removed recipient's fields, then shift later recipients'
  // internal roles down so signer-N always matches the recipient list.
  adhocFields.value = adhocFields.value
    .filter((f) => f.role !== removedRole)
    .map((f) => {
      const i = roles.value.indexOf(f.role);
      return i > index ? { ...f, role: adhocRole(i - 1) } : f;
    });
  adhocRecipients.value.splice(index, 1);
  comboboxResetTick.value.splice(index, 1);
}

// --- ad-hoc field placement (shared gesture logic with the builder) ---------

const adhocPage = ref(0);
const placementRole = ref<string | null>("signer-1");
const pageWidthPx = ref(0);
const pageHeightPx = ref(0);

const adhocFieldsOnPage = computed(() => adhocFields.value.filter((f) => f.page === adhocPage.value));

const placementRoleItems = computed(() =>
  adhocRecipients.value.map((_, i) => ({ title: adhocRecipientName(i), value: adhocRole(i) })),
);

// --- add-signer-by-email (recipients who have never logged in) --------------

const recipientError = ref<string | null>(null);

// Mirrors the backend's anchored regex (backend/app/schemas.py UserCreate):
// requires a real-looking local part, domain, and a 2+ char TLD.
const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/;

// "Add signer" dialog: the only place a new user can be created from this
// view. Opened for any free-typed combobox value that isn't an exact match
// to an existing user — never assigns or POSTs until Confirm is clicked.
const addSignerOpen = ref(false);
const addSignerEmail = ref("");
const addSignerName = ref("");
const addSignerNameRequired = ref(false);
const addSignerSubmitting = ref(false);
const pendingSignerIndex = ref<number | null>(null);
/** Whether the pending add-by-email dialog targets a CC row (vs a signer row). */
const pendingIsCc = ref(false);
/** Template mode: the role the pending add-by-email dialog targets (vs an index). */
const pendingRole = ref<string | null>(null);

// Bumped whenever a row's dialog closes, to force that row's v-combobox to
// remount — Vuetify keeps free-typed search text internally even after the
// controlled model-value reverts to null, so without this the input would
// still visually show the abandoned text after Cancel.
const comboboxResetTick = ref<number[]>([]);
function bumpComboboxReset(index: number): void {
  comboboxResetTick.value[index] = (comboboxResetTick.value[index] ?? 0) + 1;
}

const ccComboboxResetTick = ref<number[]>([]);
function bumpCcComboboxReset(index: number): void {
  ccComboboxResetTick.value[index] = (ccComboboxResetTick.value[index] ?? 0) + 1;
}

const roleComboboxResetTick = ref<Record<string, number>>({});
function bumpRoleComboboxReset(role: string): void {
  roleComboboxResetTick.value[role] = (roleComboboxResetTick.value[role] ?? 0) + 1;
}

const addSignerEmailTrimmed = computed(() => addSignerEmail.value.trim());
const addSignerEmailValid = computed(() => EMAIL_PATTERN.test(addSignerEmailTrimmed.value.toLowerCase()));
const addSignerEmailInvalidShown = computed(
  () => addSignerEmailTrimmed.value.length > 0 && !addSignerEmailValid.value,
);
const canConfirmAddSigner = computed(
  () =>
    !addSignerSubmitting.value &&
    addSignerEmailValid.value &&
    (!addSignerNameRequired.value || addSignerName.value.trim().length > 0),
);

type UserItem = User & { display: string };

/** The picker item for a recipient row's current value (VCombobox wants the object, not the id).
 *  Looked up in the memoized `userItems` so the combobox sees a stable identity between renders. */
function adhocUserItem(userId: number | null): UserItem | null {
  return userItems.value.find((u) => u.id === userId) ?? null;
}

/** Assign `user` to row `i` unless some other row already has them. */
function assignRecipient(index: number, user: User): void {
  const otherIdx = adhocRecipients.value.findIndex((uid, i) => i !== index && uid === user.id);
  if (otherIdx !== -1) {
    recipientError.value = `${user.name} is already signer ${otherIdx + 1}.`;
    return;
  }
  adhocRecipients.value[index] = user.id;
}

/** Template-mode counterpart of `assignRecipient`: one person per role. */
function assignRoleRecipient(role: string, user: User): void {
  const otherRole = Object.entries(roleAssignments.value).find(([r, uid]) => r !== role && uid === user.id);
  if (otherRole) {
    recipientError.value = `${user.name} is already assigned to ${otherRole[0]}.`;
    return;
  }
  roleAssignments.value[role] = user.id;
}

/** CC-row counterpart of `assignRecipient`: no duplicate CC rows for one person. */
function assignCcRecipient(index: number, user: User): void {
  const otherIdx = ccRows.value.findIndex((row, i) => i !== index && row.userId === user.id);
  if (otherIdx !== -1) {
    recipientError.value = `${user.name} is already CC'd.`;
    return;
  }
  const row = ccRows.value[index];
  if (row) row.userId = user.id;
}

/**
 * A combobox emits a picked item as the object, but free-typed text (someone
 * not in the users list yet, or a partial email still being typed when the
 * field loses focus) as a plain string on Enter/blur. We only ever assign a
 * row automatically for an exact case-insensitive match to an existing
 * user's email; anything else — valid-looking or not — opens the "Add
 * signer" dialog prefilled with the typed text so a human confirms the
 * email (and, for external addresses, supplies a name) before any user is
 * created. This function never calls POST /users itself.
 */
async function onPickAdhocRecipient(index: number, picked: UserItem | string | null): Promise<void> {
  recipientError.value = null;
  if (picked == null) {
    adhocRecipients.value[index] = null;
    return;
  }
  if (typeof picked !== "string") {
    assignRecipient(index, picked);
    return;
  }

  const typed = picked.trim();
  if (!typed) return;
  const known = users.value.find((u) => u.email.toLowerCase() === typed.toLowerCase());
  if (known) {
    assignRecipient(index, known);
    return;
  }
  // VCombobox can emit a second commit when its menu closes after an item
  // pick, carrying the item's *display* string rather than an email. Treat a
  // display-string match like the item pick it echoes — never a new-signer
  // request — or a phantom "Add signer" dialog opens over the wizard.
  const displayed = userItems.value.find((u) => u.display === typed);
  if (displayed) {
    assignRecipient(index, displayed);
    return;
  }

  pendingSignerIndex.value = index;
  pendingRole.value = null;
  pendingIsCc.value = false;
  addSignerEmail.value = typed;
  addSignerName.value = "";
  addSignerNameRequired.value = false;
  addSignerOpen.value = true;
}

/** Template-mode counterpart of `onPickAdhocRecipient` — same commit
 *  semantics (object pick, exact email match, display-string echo, else the
 *  add-by-email dialog), targeting `roleAssignments[role]`. This is what
 *  lets a template be sent to a brand-new (e.g. external) signer without
 *  abandoning the template for a one-off envelope. */
async function onPickRoleRecipient(role: string, picked: UserItem | string | null): Promise<void> {
  recipientError.value = null;
  if (picked == null) {
    roleAssignments.value[role] = null;
    return;
  }
  if (typeof picked !== "string") {
    assignRoleRecipient(role, picked);
    return;
  }
  const typed = picked.trim();
  if (!typed) return;
  const known = users.value.find((u) => u.email.toLowerCase() === typed.toLowerCase());
  if (known) {
    assignRoleRecipient(role, known);
    return;
  }
  const displayed = userItems.value.find((u) => u.display === typed);
  if (displayed) {
    assignRoleRecipient(role, displayed);
    return;
  }

  pendingSignerIndex.value = null;
  pendingRole.value = role;
  pendingIsCc.value = false;
  addSignerEmail.value = typed;
  addSignerName.value = "";
  addSignerNameRequired.value = false;
  addSignerOpen.value = true;
}

/** CC-row counterpart of `onPickAdhocRecipient` — same commit semantics
 *  (object pick, exact email match, display-string echo, else the
 *  add-by-email dialog), targeting `ccRows` instead of the signer list. */
async function onPickCcRecipient(index: number, picked: UserItem | string | null): Promise<void> {
  recipientError.value = null;
  if (picked == null) {
    const row = ccRows.value[index];
    if (row) row.userId = null;
    return;
  }
  if (typeof picked !== "string") {
    assignCcRecipient(index, picked);
    return;
  }
  const typed = picked.trim();
  if (!typed) return;
  const known = users.value.find((u) => u.email.toLowerCase() === typed.toLowerCase());
  if (known) {
    assignCcRecipient(index, known);
    return;
  }
  const displayed = userItems.value.find((u) => u.display === typed);
  if (displayed) {
    assignCcRecipient(index, displayed);
    return;
  }

  pendingSignerIndex.value = index;
  pendingRole.value = null;
  pendingIsCc.value = true;
  addSignerEmail.value = typed;
  addSignerName.value = "";
  addSignerNameRequired.value = false;
  addSignerOpen.value = true;
}

/**
 * Confirm handler for the "Add signer" dialog: the sole POST /users call in
 * this view. The dialog is `persistent` (no scrim/Escape dismiss) so the
 * only way out besides this is the explicit Cancel button, but a
 * double-Enter (both fields have @keyup.enter) could still fire this twice
 * concurrently — `addSignerSubmitting` blocks re-entry — and Cancel/Confirm
 * on a re-opened dialog for a different row could let a stale in-flight
 * call land after the await; the index capture + post-await re-check guard
 * against both.
 */
async function confirmAddSigner(): Promise<void> {
  if (addSignerSubmitting.value) return;
  const index = pendingSignerIndex.value;
  const role = pendingRole.value;
  if ((index == null && role == null) || !canConfirmAddSigner.value) return;
  const email = addSignerEmailTrimmed.value.toLowerCase();
  const name = addSignerName.value.trim();
  const stillCurrent = (): boolean =>
    addSignerOpen.value && pendingSignerIndex.value === index && pendingRole.value === role;
  addSignerSubmitting.value = true;
  try {
    const { data } = await http.post<User>("/users", name ? { email, name } : { email });
    if (!users.value.some((u) => u.id === data.id)) users.value.push(data);
    // If the dialog closed (or was reopened for another row) while this
    // request was in flight, the user now exists server-side and in
    // `users.value` (harmless, reusable next time) but this stale call must
    // not assign or reopen anything.
    if (stillCurrent()) {
      if (role != null) assignRoleRecipient(role, data);
      else if (pendingIsCc.value) assignCcRecipient(index as number, data);
      else assignRecipient(index as number, data);
      closeAddSignerDialog();
    }
  } catch (err) {
    if (!stillCurrent()) return; // stale; abort silently
    if (axios.isAxiosError(err) && err.response?.data?.detail === "External signer requires a name") {
      addSignerNameRequired.value = true;
      return;
    }
    recipientError.value = extractError(err);
    closeAddSignerDialog();
  } finally {
    addSignerSubmitting.value = false;
  }
}

/** Cancel (or post-error close): leaves the row unassigned — never partially applies a pick. */
function closeAddSignerDialog(): void {
  const index = pendingSignerIndex.value;
  const role = pendingRole.value;
  const wasCc = pendingIsCc.value;
  addSignerOpen.value = false;
  pendingSignerIndex.value = null;
  pendingRole.value = null;
  pendingIsCc.value = false;
  if (role != null) {
    bumpRoleComboboxReset(role);
  } else if (index != null) {
    if (wasCc) bumpCcComboboxReset(index);
    else bumpComboboxReset(index);
  }
}

/** True if `userId` refers to an external (non-Pumasi) user. */
function isExternalId(userId: number | null): boolean {
  return users.value.find((u) => u.id === userId)?.is_external ?? false;
}

// Keep the placement target valid when recipients are removed.
watch(roles, (next) => {
  if (mode.value === "adhoc" && (!placementRole.value || !next.includes(placementRole.value))) {
    placementRole.value = next[0] ?? null;
  }
});

function onPageRendered(w: number, h: number): void {
  pageWidthPx.value = w;
  pageHeightPx.value = h;
}

const { placingType, togglePlacing, onPlacementPointerDown, onPlacementPointerMove, onPlacementPointerUp } =
  useFieldPlacement({
    currentPage: adhocPage,
    pageWidthPx,
    pageHeightPx,
    selectedRole: placementRole,
    fields: adhocFields,
    docLoaded: computed(() => adhocPdfUrl.value !== null),
  });

function updateAdhocField(updated: FieldDef): void {
  const idx = adhocFields.value.findIndex((f) => f.id === updated.id);
  if (idx !== -1) adhocFields.value[idx] = updated;
}

function deleteAdhocField(id: string): void {
  adhocFields.value = adhocFields.value.filter((f) => f.id !== id);
  if (selectedFieldId.value === id) selectedFieldId.value = null;
}

// --- selected-field properties panel (DocuSign-style) -----------------------

const selectedFieldId = ref<string | null>(null);
const selectedField = computed(() => adhocFields.value.find((f) => f.id === selectedFieldId.value) ?? null);

// A selected field on another page would be edited invisibly — deselect on paging.
watch(adhocPage, () => {
  selectedFieldId.value = null;
});

// --- load -------------------------------------------------------------------

async function load(): Promise<void> {
  loading.value = true;
  errorMessage.value = null;
  try {
    const [templatesRes, usersRes] = await Promise.all([
      http.get<TemplateOut[]>("/templates"),
      http.get<User[]>("/users"),
    ]);
    templates.value = templatesRes.data;
    users.value = usersRes.data;

    if (props.draftId) {
      await loadDraft(props.draftId);
    } else if (props.templateId) {
      const found = templatesRes.data.find((t) => String(t.id) === props.templateId);
      if (found) {
        selectTemplate(found);
      } else {
        errorMessage.value = "That template couldn't be found (it may have been archived).";
      }
    }
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    loading.value = false;
  }
}

/** Hydrate the wizard from an existing draft (recreate-on-save model).
 *  The draft's roles — template names or signer-N — are remapped to this
 *  wizard's own signer-N-by-row-index convention so the fields and the
 *  signers_json the wizard eventually submits agree. */
async function loadDraft(draftId: string): Promise<void> {
  const { data: draft } = await http.get<SubmissionOut>(`/submissions/${draftId}`);
  if (draft.status !== "draft") {
    ui.toast("That envelope is no longer a draft.");
    await router.push({ name: "envelope-detail", params: { id: draftId } });
    return;
  }
  const [{ data: template }, pdfRes] = await Promise.all([
    http.get<TemplateOut>(`/templates/${draft.template.id}`),
    http.get<Blob>(`/files/template-pdf/${draft.template.id}`, { responseType: "blob" }),
  ]);

  mode.value = "adhoc";
  draftSourceId.value = draft.id;
  title.value = draft.title;
  message.value = draft.message ?? "";
  remindersEnabled.value = draft.reminders_enabled;
  reminderInterval.value = draft.reminder_interval_days;
  if (draft.expires_at) {
    const iso = draft.expires_at.slice(0, 10);
    if (iso <= todayIso) {
      draftExpiryCleared.value = true; // deadline already passed — start fresh
    } else {
      expiryDate.value = iso;
    }
  }

  const signers = draft.submitters
    .filter((s) => !s.is_cc)
    .sort((a, b) => a.order_index - b.order_index || a.id - b.id);
  const ccs = draft.submitters.filter((s) => s.is_cc);
  adhocRecipients.value = signers.map((s) => s.user.id);
  adhocOrderNums.value = signers.map((s) => s.order_index + 1);
  ccRows.value = ccs.map((s) => ({ userId: s.user.id, orderNum: s.order_index + 1 }));
  signInOrder.value = draft.submitters.some((s) => s.order_index > 0);

  // Old role name -> this wizard's signer-N for that row.
  const roleMap = new Map(signers.map((s, i) => [s.role, adhocRole(i)]));
  adhocFields.value = template.fields.map((f) => ({
    ...f,
    role: roleMap.get(f.role) ?? f.role,
  }));

  const file = new File([pdfRes.data], `${title.value || "document"}.pdf`, { type: "application/pdf" });
  adhocFile.value = file;
  adhocSourceFiles.value = [file];
  adhocPdfUrl.value = URL.createObjectURL(file);
  step.value = 1;
}

onMounted(load);

// --- send -------------------------------------------------------------------

const savingDraft = ref(false);

async function send(asDraft = false): Promise<void> {
  if (submitting.value || savingDraft.value) return;
  (asDraft ? savingDraft : submitting).value = true;
  errorMessage.value = null;
  try {
    let created: SubmissionOut;
    if (mode.value === "template" && selectedTemplate.value) {
      const ccEntries = ccRows.value.map((row) => ({
        user_id: row.userId,
        order: toOrder(row.orderNum),
        is_cc: true,
      }));
      const { data } = await http.post<SubmissionOut>("/submissions", {
        template_id: selectedTemplate.value.id,
        title: title.value.trim(),
        message: message.value.trim() || null,
        expires_at: expiresAtIso(),
        reminders_enabled: remindersEnabled.value,
        reminder_interval_days: reminderInterval.value,
        draft: asDraft,
        signers: [
          ...roles.value.map((role) => ({
            role,
            user_id: roleAssignments.value[role],
            order: toOrder(templateOrderNums.value[role] ?? 1),
          })),
          ...ccEntries,
        ],
      });
      created = data;
    } else if (mode.value === "adhoc" && adhocFile.value) {
      const ccEntries = ccRows.value.map((row) => ({
        user_id: row.userId,
        order: toOrder(row.orderNum),
        is_cc: true,
      }));
      const formData = new FormData();
      formData.append("title", title.value.trim());
      formData.append(
        "signers_json",
        JSON.stringify([
          ...adhocRecipients.value.map((userId, i) => ({
            role: adhocRole(i),
            user_id: userId,
            order: toOrder(adhocOrderNums.value[i] ?? 1),
          })),
          ...ccEntries,
        ]),
      );
      formData.append("fields_json", JSON.stringify(adhocFields.value));
      if (message.value.trim()) formData.append("message", message.value.trim());
      const expiresAt = expiresAtIso();
      if (expiresAt) formData.append("expires_at", expiresAt);
      formData.append("reminders_enabled", String(remindersEnabled.value));
      formData.append("reminder_interval_days", String(reminderInterval.value));
      if (asDraft) formData.append("draft", "true");
      formData.append("file", adhocFile.value);
      const { data } = await http.post<SubmissionOut>("/submissions/adhoc", formData);
      created = data;
    } else {
      return;
    }
    // Recreate-on-save: the freshly created envelope supersedes the draft we
    // loaded from. Delete it only after the create succeeded; if the delete
    // fails the leftover draft is harmless and user-deletable.
    if (draftSourceId.value !== null) {
      await http.delete(`/submissions/${draftSourceId.value}`).catch(() => {});
      draftSourceId.value = null;
    }
    if (asDraft) {
      ui.toast("Draft saved — send it whenever you're ready.");
    } else {
      ui.toast(
        signInOrder.value
          ? "Envelope sent — the first signer has been emailed; the rest follow in order."
          : "Envelope sent — signers have been emailed.",
      );
    }
    await router.push({ name: "envelope-detail", params: { id: String(created.id) } });
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    (asDraft ? savingDraft : submitting).value = false;
  }
}
</script>

<template>
  <v-container class="send-view">
    <v-btn variant="text" prepend-icon="mdi-arrow-left" class="mb-2 px-0" :to="{ name: 'dashboard' }">Home</v-btn>
    <h1 class="text-h5 mb-4">Send for signature</h1>

    <v-alert v-if="!auth.canSend && !loading" type="error">You don't have permission to send documents.</v-alert>

    <template v-else>
      <v-alert v-if="errorMessage" type="error" closable class="mb-4" @click:close="errorMessage = null">
        {{ errorMessage }}
      </v-alert>
      <v-progress-linear v-if="loading" indeterminate class="mb-4" />

      <!-- Step header -->
      <div class="step-header mb-5" role="list">
        <div
          v-for="(stepTitle, i) in stepTitles"
          :key="stepTitle"
          class="step-item"
          role="listitem"
          :class="{ done: step > i + 1, on: step === i + 1 }"
        >
          <span class="step-n">
            <v-icon v-if="step > i + 1" icon="mdi-check" size="x-small" aria-hidden="true" />
            <template v-else>{{ i + 1 }}</template>
          </span>
          {{ stepTitle }}
        </div>
      </div>

      <!-- Step 1: Document -->
      <template v-if="step === 1 && !loading">
        <v-row>
          <!-- One-off first: it's the common case; templates are the secondary path. -->
          <v-col cols="12" md="7">
            <v-card variant="flat" border>
              <v-card-title class="text-subtitle-1">One-off document</v-card-title>
              <v-card-text>
                <p class="text-body-2 text-medium-emphasis mb-3">
                  Send a document once without saving it as a template. You'll place the signature
                  fields in the next steps.
                </p>
                <v-file-input
                  :model-value="adhocSourceFiles"
                  label="Documents (PDF, Office files, images, and more)"
                  :accept="UPLOAD_ACCEPT"
                  prepend-icon="mdi-file-document-multiple-outline"
                  multiple
                  hint="Pick one or more files — they're combined into one document, in the order below."
                  persistent-hint
                  @update:model-value="onAdhocFilesChosen"
                />
                <v-list v-if="adhocSourceFiles.length > 0" density="compact" class="source-file-list mt-1">
                  <v-list-item
                    v-for="(file, i) in adhocSourceFiles"
                    :key="`${file.name}-${i}`"
                    :title="`${i + 1}. ${file.name}`"
                    class="px-1"
                  >
                    <template #append>
                      <v-btn
                        icon="mdi-arrow-up"
                        size="x-small"
                        variant="text"
                        :disabled="i === 0"
                        :aria-label="`Move ${file.name} up`"
                        @click="moveSourceFile(i, -1)"
                      />
                      <v-btn
                        icon="mdi-arrow-down"
                        size="x-small"
                        variant="text"
                        :disabled="i === adhocSourceFiles.length - 1"
                        :aria-label="`Move ${file.name} down`"
                        @click="moveSourceFile(i, 1)"
                      />
                      <v-btn
                        icon="mdi-close"
                        size="x-small"
                        variant="text"
                        :aria-label="`Remove ${file.name}`"
                        @click="removeSourceFile(i)"
                      />
                    </template>
                  </v-list-item>
                </v-list>
                <v-progress-linear v-if="preparingDocument" indeterminate class="mt-2" />
                <p v-if="preparingDocument" class="text-caption text-medium-emphasis mt-1 mb-0">
                  Preparing document…
                </p>
                <v-text-field v-if="adhocFile" v-model="title" label="Title" class="mt-1" />
                <v-btn
                  v-if="adhocFile"
                  color="primary"
                  variant="flat"
                  block
                  class="mt-2"
                  :disabled="!canLeaveStep1"
                  @click="step = 2"
                >
                  Continue
                </v-btn>
              </v-card-text>
            </v-card>
          </v-col>
          <v-col cols="12" md="5">
            <v-card variant="flat" border>
              <v-card-title class="text-subtitle-1">Use a template</v-card-title>
              <v-card-text v-if="templates.length === 0" class="text-medium-emphasis">
                No templates yet — templates are reusable documents with saved signature fields, for
                documents you send repeatedly.
              </v-card-text>
              <v-list v-else>
                <v-list-item
                  v-for="template in templates"
                  :key="template.id"
                  :title="template.name"
                  :subtitle="
                    template.owner.id !== auth.me?.id
                      ? `${template.page_count} page(s) · shared by ${template.owner.name}`
                      : `${template.page_count} page(s)`
                  "
                  @click="selectTemplate(template)"
                >
                  <template #append>
                    <v-icon icon="mdi-chevron-right" aria-hidden="true" />
                  </template>
                </v-list-item>
              </v-list>
              <v-card-actions class="pt-0">
                <v-btn variant="text" color="primary" prepend-icon="mdi-plus" @click="newTemplateDialog = true">
                  Create template
                </v-btn>
                <v-btn variant="text" prepend-icon="mdi-file-document-multiple-outline" :to="{ name: 'templates' }">
                  Manage templates
                </v-btn>
              </v-card-actions>
            </v-card>
          </v-col>
        </v-row>
      </template>

      <!-- Step 2: Signers (& message for template mode) -->
      <v-card v-else-if="step === 2" variant="flat" border>
        <v-card-title class="text-subtitle-1">
          {{ mode === "template" ? `${selectedTemplate?.name} — signers & message` : "Who needs to sign?" }}
        </v-card-title>
        <v-card-text>
          <template v-if="mode === 'template'">
            <v-text-field v-model="title" label="Title" class="mb-2" />
            <v-textarea v-model="message" label="Message to signers (optional)" rows="3" class="mb-4" />
            <p v-if="roles.length === 0" class="text-medium-emphasis">
              This template has no signable fields — add fields in the template builder before sending.
            </p>
            <template v-else>
              <v-alert v-if="rolesWithoutFields.length > 0" type="warning" variant="tonal" class="mb-4">
                No fields placed yet for: {{ rolesWithoutFields.join(", ") }}. Add fields for them in the
                template builder before sending.
              </v-alert>
              <v-alert
                v-if="recipientError"
                type="warning"
                variant="tonal"
                closable
                class="mb-3"
                @click:close="recipientError = null"
              >
                {{ recipientError }}
              </v-alert>
              <div class="d-flex align-center mb-2">
                <p class="text-subtitle-2 mb-0">Signers</p>
                <v-spacer />
                <v-switch
                  v-model="signInOrder"
                  label="Collect signatures in order"
                  color="primary"
                  density="compact"
                  hide-details
                />
              </div>
              <p v-if="signInOrder" class="text-caption text-medium-emphasis mb-2">
                The number sets each recipient's turn — lower numbers go first, and recipients with the
                same number are reached together.
              </p>
              <div v-for="role in roles" :key="role" class="d-flex align-start mb-2">
                <v-text-field
                  v-if="signInOrder"
                  v-model.number="templateOrderNums[role]"
                  type="number"
                  min="1"
                  max="99"
                  density="compact"
                  hide-details
                  class="order-input mr-3 mt-1"
                  :aria-label="`Signing order for ${role}`"
                />
                <v-combobox
                  :key="`role-${role}-${roleComboboxResetTick[role] ?? 0}`"
                  :model-value="adhocUserItem(roleAssignments[role] ?? null)"
                  :items="userItems"
                  item-title="display"
                  item-value="id"
                  :label="`${role} · signs ${fieldCountForRole(role)} field${fieldCountForRole(role) === 1 ? '' : 's'}`"
                  placeholder="Pick a person or type an email"
                  :disabled="rolesWithoutFields.includes(role)"
                  clearable
                  class="flex-grow-1"
                  @update:model-value="(v: unknown) => onPickRoleRecipient(role, v as UserItem | string | null)"
                />
              </div>
            </template>
          </template>

          <template v-else>
            <v-alert
              v-if="recipientError"
              type="warning"
              variant="tonal"
              closable
              class="mb-3"
              @click:close="recipientError = null"
            >
              {{ recipientError }}
            </v-alert>
            <div class="d-flex align-center mb-2">
              <v-spacer />
              <v-switch
                v-model="signInOrder"
                label="Collect signatures in order"
                color="primary"
                density="compact"
                hide-details
              />
            </div>
            <p v-if="signInOrder" class="text-caption text-medium-emphasis mb-2">
              The number sets each recipient's turn — lower numbers go first, and recipients with the same
              number are reached together.
            </p>
            <div v-for="(userId, i) in adhocRecipients" :key="i" class="d-flex align-start signer-row mb-2">
              <v-text-field
                v-if="signInOrder"
                v-model.number="adhocOrderNums[i]"
                type="number"
                min="1"
                max="99"
                density="compact"
                hide-details
                class="order-input mr-3 mt-1"
                :aria-label="`Signing order for ${adhocRecipientName(i)}`"
              />
              <span class="role-swatch mt-4 mr-3" :style="{ backgroundColor: roleColor(adhocRole(i), roles) }" />
              <v-combobox
                :key="`signer-${i}-${comboboxResetTick[i] ?? 0}`"
                :model-value="adhocUserItem(userId)"
                :items="userItems"
                item-title="display"
                item-value="id"
                :label="`Signer ${i + 1}`"
                placeholder="Pick a person or type an email"
                density="comfortable"
                hide-details
                clearable
                class="flex-grow-1"
                @update:model-value="(v: unknown) => onPickAdhocRecipient(i, v as UserItem | string | null)"
              />
              <v-btn
                icon="mdi-close"
                variant="text"
                size="small"
                class="mt-2 ml-1"
                :disabled="adhocRecipients.length === 1"
                :aria-label="`Remove ${adhocRecipientName(i)}`"
                @click="removeRecipient(i)"
              />
            </div>
            <v-btn variant="text" color="primary" prepend-icon="mdi-plus" @click="addRecipient">Add signer</v-btn>
            <v-textarea v-model="message" label="Message to signers (optional)" rows="3" class="mt-4" />
          </template>

          <!-- CC rows (both modes): a person + order number who receives a copy,
               DocuSign-style — never a signer, never blocking the routing. -->
          <div class="d-flex align-center mt-2 mb-1">
            <p class="text-subtitle-2 mb-0">CC — receives a copy</p>
            <v-spacer />
            <v-btn variant="text" color="primary" size="small" prepend-icon="mdi-plus" @click="addCcRow">
              Add CC
            </v-btn>
          </div>
          <p v-if="ccRows.length === 0" class="text-caption text-medium-emphasis mb-0">
            CC recipients are emailed a copy when their turn in the order comes, and the signed PDF when
            everyone's done.
          </p>
          <div v-for="(row, i) in ccRows" :key="`cc-row-${i}`" class="d-flex align-start signer-row mb-2">
            <v-text-field
              v-if="signInOrder"
              v-model.number="row.orderNum"
              type="number"
              min="1"
              max="99"
              density="compact"
              hide-details
              class="order-input mr-3 mt-1"
              :aria-label="`Order for CC ${i + 1}`"
            />
            <v-chip size="small" variant="tonal" class="mt-3 mr-3" prepend-icon="mdi-email-outline">CC</v-chip>
            <v-combobox
              :key="`cc-${i}-${ccComboboxResetTick[i] ?? 0}`"
              :model-value="adhocUserItem(row.userId)"
              :items="userItems"
              item-title="display"
              item-value="id"
              :label="`CC ${i + 1}`"
              placeholder="Pick a person or type an email"
              density="comfortable"
              hide-details
              clearable
              class="flex-grow-1"
              @update:model-value="(v: unknown) => onPickCcRecipient(i, v as UserItem | string | null)"
            />
            <v-btn
              icon="mdi-close"
              variant="text"
              size="small"
              class="mt-2 ml-1"
              :aria-label="`Remove CC ${i + 1}`"
              @click="removeCcRow(i)"
            />
          </div>

          <!-- Envelope options: deadline + reminder cadence (DocuSign-style) -->
          <p class="text-subtitle-2 mt-4 mb-1">Options</p>
          <div class="d-flex flex-wrap align-center options-row">
            <v-text-field
              v-model="expiryDate"
              type="date"
              label="Expiration date (optional)"
              density="compact"
              hide-details
              clearable
              class="option-date"
              :min="todayIso"
            />
            <v-switch
              v-model="remindersEnabled"
              label="Automatic reminders"
              color="primary"
              density="compact"
              hide-details
              class="ml-1"
            />
            <v-select
              v-if="remindersEnabled"
              v-model="reminderInterval"
              :items="REMINDER_INTERVAL_ITEMS"
              label="Remind"
              density="compact"
              hide-details
              class="option-select"
            />
          </div>
          <p v-if="draftExpiryCleared" class="text-caption text-warning mb-0">
            This draft's previous expiration date had already passed, so it was cleared —
            pick a new one or leave it empty.
          </p>
          <p v-if="expiryInPast" class="text-caption text-error mt-1 mb-0">
            The expiration date must be in the future.
          </p>
          <p v-else class="text-caption text-medium-emphasis mt-1 mb-0">
            <template v-if="expiryDate">
              Signers are warned 2 days before the deadline; after it passes the envelope can no
              longer be signed.
            </template>
            <template v-else>Without an expiration date, the envelope stays open until completed or voided.</template>
          </p>
        </v-card-text>
        <v-card-actions>
          <v-btn variant="text" @click="step = 1">Back</v-btn>
          <v-spacer />
          <span v-if="signersBlocker" class="text-caption text-medium-emphasis mr-3">{{ signersBlocker }}</span>
          <v-btn color="primary" variant="flat" :disabled="!canProceedFrom(2)" @click="step = 3">Continue</v-btn>
        </v-card-actions>
      </v-card>

      <!-- Step 3 (ad-hoc only): Place fields -->
      <v-card v-else-if="step === 3 && mode === 'adhoc'" variant="flat" border>
        <v-card-title class="text-subtitle-1 d-flex align-center flex-wrap">
          <span>Place fields on the document</span>
          <v-spacer />
          <span v-if="recipientsMissingFields.length > 0" class="text-caption text-warning">
            Every signer needs at least one field: {{ recipientsMissingFields.join(", ") }}
          </span>
        </v-card-title>
        <v-card-text>
          <div class="d-flex flex-wrap align-center mb-3 placement-toolbar">
            <v-select
              v-model="placementRole"
              :items="placementRoleItems"
              label="Fields for"
              density="compact"
              hide-details
              class="toolbar-select mr-3"
            />
            <v-btn
              v-for="ft in FIELD_TYPES"
              :key="ft"
              size="small"
              class="mr-1 mb-1 text-capitalize"
              :variant="placingType === ft ? 'flat' : 'tonal'"
              :color="placingType === ft ? 'primary' : undefined"
              @click="togglePlacing(ft)"
            >
              {{ ft }}
            </v-btn>
          </div>
          <p v-if="placingType" class="text-caption text-medium-emphasis mb-2">
            Click and drag on the page to place a {{ placingType }} field for
            {{ placementRole ? displayNameForRole(placementRole) : "—" }}.
          </p>

          <div class="d-flex placement-layout">
            <div class="flex-grow-1 placement-page" @pointerdown="selectedFieldId = null">
              <div class="d-flex align-center mb-2">
                <v-btn
                  icon="mdi-chevron-left"
                  size="small"
                  :disabled="adhocPage === 0"
                  aria-label="Previous page"
                  @click="adhocPage--"
                />
                <span class="mx-2">Page {{ adhocPage + 1 }} / {{ adhocPageCount || "?" }}</span>
                <v-btn
                  icon="mdi-chevron-right"
                  size="small"
                  :disabled="adhocPage >= adhocPageCount - 1"
                  aria-label="Next page"
                  @click="adhocPage++"
                />
              </div>

              <PdfPage
                v-if="adhocPdfUrl"
                :src="adhocPdfUrl"
                :page="adhocPage"
                @rendered="onPageRendered"
                @loaded="onAdhocPdfLoaded"
                @error="onAdhocPdfError"
              >
                <div
                  class="placement-catcher"
                  :class="{ active: placingType }"
                  @pointerdown="onPlacementPointerDown"
                  @pointermove="onPlacementPointerMove"
                  @pointerup="onPlacementPointerUp"
                  @pointercancel="onPlacementPointerUp"
                >
                  <FieldBox
                    v-for="field in adhocFieldsOnPage"
                    :key="field.id"
                    :field="field"
                    :page-width="pageWidthPx"
                    :page-height="pageHeightPx"
                    :color="field.type === 'label' ? '#616161' : roleColor(field.role, roles)"
                    :role-label="displayNameForRole(field.role)"
                    :selected="field.id === selectedFieldId"
                    @select="selectedFieldId = $event"
                    @update:field="updateAdhocField"
                    @delete="deleteAdhocField"
                  />
                </div>
              </PdfPage>
            </div>

            <div class="props-col">
              <FieldPropertiesPanel
                v-if="selectedField"
                :field="selectedField"
                :owner-label="displayNameForRole(selectedField.role)"
                :color="selectedField.type === 'label' ? '#616161' : roleColor(selectedField.role, roles)"
                @update:field="updateAdhocField"
                @delete="deleteAdhocField"
              />
              <v-card v-else variant="flat" border>
                <v-card-text class="text-caption text-medium-emphasis">
                  Select a field on the page to edit its properties — required, font size, prefill text.
                </v-card-text>
              </v-card>
            </div>
          </div>
        </v-card-text>
        <v-card-actions>
          <v-btn variant="text" @click="step = 2">Back</v-btn>
          <v-spacer />
          <v-btn color="primary" variant="flat" :disabled="!canProceedFrom(3)" @click="step = 4">Continue</v-btn>
        </v-card-actions>
      </v-card>

      <!-- Review & send -->
      <v-card v-else-if="step === reviewStep" variant="flat" border>
        <v-card-title class="text-subtitle-1">Review &amp; send</v-card-title>
        <v-card-text>
          <v-list density="compact">
            <v-list-item prepend-icon="mdi-file-document-outline" :title="title">
              <template #subtitle>
                {{ mode === "template" ? `Template: ${selectedTemplate?.name}` : `One-off PDF: ${adhocFile?.name}` }}
              </template>
            </v-list-item>
            <v-list-item v-if="message.trim()" prepend-icon="mdi-message-text-outline">
              <v-list-item-title class="text-body-2 message-preview">{{ message }}</v-list-item-title>
            </v-list-item>
            <v-list-item
              v-for="(role, i) in roles"
              :key="role"
              prepend-icon="mdi-account-outline"
              :subtitle="
                mode === 'template'
                  ? `${role} · ${fieldCountForRole(role)} field${fieldCountForRole(role) === 1 ? '' : 's'}`
                  : `${fieldCountForRole(role)} field${fieldCountForRole(role) === 1 ? '' : 's'}`
              "
            >
              <template #title>
                <template v-if="signInOrder">
                  {{ mode === "template" ? (templateOrderNums[role] ?? 1) : (adhocOrderNums[i] ?? 1) }}.
                </template>
                {{ mode === "template" ? userName(roleAssignments[role] ?? null) : userName(adhocRecipients[i] ?? null) }}
                <v-chip
                  v-if="mode === 'template' ? isExternalId(roleAssignments[role] ?? null) : isExternalId(adhocRecipients[i] ?? null)"
                  size="x-small"
                  color="warning"
                  variant="tonal"
                  class="ml-2"
                >
                  External
                </v-chip>
              </template>
            </v-list-item>
            <v-list-item
              v-for="(row, i) in ccRows"
              :key="`cc-review-${i}`"
              prepend-icon="mdi-email-outline"
              subtitle="CC · receives a copy"
            >
              <template #title>
                <template v-if="signInOrder">{{ row.orderNum }}. </template>
                {{ userName(row.userId) }}
              </template>
            </v-list-item>
            <v-list-item prepend-icon="mdi-clock-outline">
              <v-list-item-title class="text-body-2">
                {{ expiryDate ? `Expires ${expiryDate}` : "No expiration date" }}
                · reminders {{ remindersEnabled ? `every ${reminderInterval} day${reminderInterval === 1 ? "" : "s"}` : "off" }}
              </v-list-item-title>
            </v-list-item>
          </v-list>
          <v-alert type="info" variant="tonal" density="compact" class="mt-2">
            <template v-if="signInOrder">
              Recipients are emailed by their order number, lowest first — signers get their signing link
              when it's their turn, and CC recipients get a copy when the routing reaches them.
            </template>
            <template v-else>
              Each signer gets an email with their personal signing link — signing can happen in any order.
              CC recipients get a copy right away and the signed PDF when everyone's done.
            </template>
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-btn variant="text" @click="step = reviewStep - 1">Back</v-btn>
          <v-spacer />
          <v-btn
            variant="tonal"
            :loading="savingDraft"
            :disabled="submitting"
            prepend-icon="mdi-content-save-outline"
            @click="send(true)"
          >
            Save as draft
          </v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :loading="submitting"
            :disabled="savingDraft"
            prepend-icon="mdi-send"
            @click="send(false)"
          >
            Send envelope
          </v-btn>
        </v-card-actions>
      </v-card>

      <NewTemplateDialog v-model="newTemplateDialog" />

      <v-dialog v-model="addSignerOpen" max-width="440" persistent>
        <v-card>
          <v-card-title>Add signer</v-card-title>
          <v-card-text>
            <v-text-field
              v-model="addSignerEmail"
              label="Email"
              autofocus
              :disabled="addSignerSubmitting"
              :error="addSignerEmailInvalidShown"
              :hint="addSignerEmailInvalidShown ? 'Enter a full email address (name@company.com).' : undefined"
              persistent-hint
              @keyup.enter="confirmAddSigner"
            />
            <v-text-field
              v-model="addSignerName"
              label="Full name"
              class="mt-3"
              :disabled="addSignerSubmitting"
              :error="addSignerNameRequired && !addSignerName.trim()"
              :hint="
                addSignerNameRequired
                  ? 'This person is outside Pumasi. Their name appears on the signed document and certificate, so enter it exactly.'
                  : 'Optional for Pumasi accounts.'
              "
              persistent-hint
              @keyup.enter="confirmAddSigner"
            />
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="text" :disabled="addSignerSubmitting" @click="closeAddSignerDialog">Cancel</v-btn>
            <v-btn
              color="primary"
              variant="flat"
              :disabled="!canConfirmAddSigner"
              :loading="addSignerSubmitting"
              @click="confirmAddSigner"
            >
              Add signer
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>
    </template>
  </v-container>
</template>

<style scoped>
.send-view {
  max-width: 1000px;
}

.step-header {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  font-size: 0.85rem;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

.step-item {
  display: flex;
  align-items: center;
  gap: 7px;
}

.step-item.on {
  color: rgb(var(--v-theme-on-surface));
  font-weight: 600;
}

.step-n {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 1.5px solid rgba(var(--v-theme-on-surface), 0.25);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.72rem;
  font-weight: 700;
}

.step-item.on .step-n {
  border-color: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-primary));
}

.step-item.done .step-n {
  background: rgb(var(--v-theme-success));
  border-color: rgb(var(--v-theme-success));
  color: #fff;
}

.role-swatch {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 2px;
  flex: none;
}

.order-input {
  flex: none;
  width: 76px;
}

.options-row {
  gap: 12px;
}

.option-date {
  flex: none;
  width: 220px;
}

.option-select {
  flex: none;
  width: 170px;
}

.toolbar-select {
  max-width: 220px;
}

.placement-layout {
  gap: 12px;
  flex-wrap: wrap;
}

.placement-page {
  min-width: 0;
  flex-basis: 480px;
}

.props-col {
  width: 250px;
  flex: none;
}

.placement-catcher {
  position: absolute;
  inset: 0;
  pointer-events: none;
  touch-action: none;
}

.placement-catcher.active {
  pointer-events: auto;
  cursor: crosshair;
}

.message-preview {
  white-space: pre-wrap;
}
</style>
