<script setup lang="ts">
/**
 * Template builder: place signable fields on a template's PDF pages.
 *
 * Placement flow is unchanged (arm a field type, press-and-drag to drop,
 * FieldBox handles move/resize). What's new versus the original:
 *
 * - Autosave: field edits debounce into PUT /templates/{id}/fields with a
 *   visible "Saving… / All changes saved / Couldn't save" state. A
 *   generation counter (not a suppress flag) decides whether the state
 *   can flip back to "saved" — edits made while a save is in flight keep
 *   the state dirty and re-schedule.
 * - Leaving with unsaved work flushes a save first (route guard +
 *   beforeunload); Send is a navigation, so it flushes too.
 * - Page thumbnail rail instead of blind chevron paging (PdfPage's
 *   document cache makes N thumbnails share one pdf.js document).
 * - Preview-as-signer dialog: all pages with read-only field boxes.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { onBeforeRouteLeave, useRouter } from "vue-router";
import http, { extractError } from "../utils/http";
import PdfPage from "../components/PdfPage.vue";
import PageThumbRail from "../components/PageThumbRail.vue";
import FieldBox from "../components/FieldBox.vue";
import FieldPropertiesPanel from "../components/FieldPropertiesPanel.vue";
import FieldPalette from "../components/FieldPalette.vue";
import { useFieldPlacement } from "../composables/useFieldPlacement";
import { roleColor as sharedRoleColor, templateRoles } from "../utils/roleColors";
import { type FieldDef, type TemplateOut } from "../types";

const props = defineProps<{ id: string }>();
const router = useRouter();

// --- Load ------------------------------------------------------------------

const template = ref<TemplateOut | null>(null);
const pdfUrl = ref<string | null>(null);
const loading = ref(true);
const errorMessage = ref<string | null>(null);

const roles = ref<string[]>([]);
const selectedRole = ref<string | null>(null);

function seedRoles(t: TemplateOut): void {
  // No placeholder role for a fresh template: now that roles persist, an
  // auto-seeded "Signer 1" would stick around as a fieldless role and
  // block sending.
  roles.value = templateRoles(t);
  if (!selectedRole.value || !roles.value.includes(selectedRole.value)) {
    selectedRole.value = roles.value[0] ?? null;
  }
}

async function load(): Promise<void> {
  loading.value = true;
  errorMessage.value = null;
  try {
    const [templateRes, pdfRes] = await Promise.all([
      http.get<TemplateOut>(`/templates/${props.id}`),
      http.get<Blob>(`/files/template-pdf/${props.id}`, { responseType: "blob" }),
    ]);
    template.value = templateRes.data;
    pdfUrl.value = URL.createObjectURL(pdfRes.data);
    seedRoles(templateRes.data);
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    loading.value = false;
  }
}

// --- Autosave ---------------------------------------------------------------

type SaveState = "saved" | "dirty" | "saving" | "error";
const saveState = ref<SaveState>("saved");

const SAVE_DEBOUNCE_MS = 1200;
let editGen = 0;
let saveTimer: number | null = null;
let currentSave: Promise<boolean> | null = null;

function scheduleSave(): void {
  if (saveTimer !== null) window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(() => {
    saveTimer = null;
    void save();
  }, SAVE_DEBOUNCE_MS);
}

/** Persist the current field list. Resolves true when this attempt saved cleanly. */
function save(): Promise<boolean> {
  if (!template.value) return Promise.resolve(true);
  if (currentSave) return currentSave;
  const gen = editGen;
  saveState.value = "saving";
  currentSave = http
    .put<TemplateOut>(`/templates/${props.id}/fields`, { fields: template.value.fields, roles: roles.value })
    .then(() => {
      // Edits made while the request was in flight already re-scheduled;
      // only a save that covers the latest edit may claim "saved".
      if (editGen === gen) saveState.value = "saved";
      return editGen === gen;
    })
    .catch((err: unknown) => {
      saveState.value = "error";
      errorMessage.value = extractError(err);
      return false;
    })
    .finally(() => {
      currentSave = null;
    });
  return currentSave;
}

/** Flush any pending/debounced changes; true when everything is persisted. */
async function ensureSaved(): Promise<boolean> {
  if (saveTimer !== null) {
    window.clearTimeout(saveTimer);
    saveTimer = null;
  }
  if (currentSave) {
    const ok = await currentSave;
    if (saveState.value === "saved") return ok;
  }
  if (saveState.value === "saved") return true;
  return save();
}

const SAVE_STATE_TEXT: Record<SaveState, string> = {
  saved: "All changes saved",
  dirty: "Unsaved changes…",
  saving: "Saving…",
  error: "Couldn't save — retrying on next change",
};

function onFieldsEdited(): void {
  editGen++;
  if (saveState.value !== "saving") saveState.value = "dirty";
  scheduleSave();
}

/**
 * Guards the edit watchers below until the initial load has populated
 * `template`/`roles`, so that first assignment doesn't count as an edit.
 * The watchers themselves are registered synchronously in setup — creating
 * them after `await load()` would detach them from the component instance,
 * leaking a deep watcher (and the whole field list it closes over) on
 * every visit to the builder.
 */
const loaded = ref(false);

// Deep-watching just the fields array keeps renames/moves/deletes covered
// without reacting to unrelated template metadata; roles are watched too
// since adding a (still fieldless) role touches nothing in the fields
// array but must persist all the same.
watch(
  () => template.value?.fields,
  () => {
    if (loaded.value) onFieldsEdited();
  },
  { deep: true },
);
watch(
  roles,
  () => {
    if (loaded.value) onFieldsEdited();
  },
  { deep: true },
);

onMounted(async () => {
  await load();
  // Let the load's own watcher jobs flush before arming edit tracking.
  await nextTick();
  loaded.value = true;
});

function onBeforeUnload(event: BeforeUnloadEvent): void {
  if (saveState.value !== "saved") {
    event.preventDefault();
  }
}

onMounted(() => window.addEventListener("beforeunload", onBeforeUnload));
onBeforeUnmount(() => {
  window.removeEventListener("beforeunload", onBeforeUnload);
  if (pdfUrl.value) URL.revokeObjectURL(pdfUrl.value);
});

onBeforeRouteLeave(async () => {
  const ok = await ensureSaved();
  if (!ok) {
    return window.confirm("Your latest field changes couldn't be saved. Leave anyway and lose them?");
  }
  return true;
});

// --- Pages -------------------------------------------------------------

const currentPage = ref(0);
const pageWidthPx = ref(0);
const pageHeightPx = ref(0);

const pageNumbers = computed(() => {
  const count = template.value?.page_count ?? 0;
  return Array.from({ length: count }, (_, i) => i);
});

const fieldsOnCurrentPage = computed<FieldDef[]>(
  () => template.value?.fields.filter((f) => f.page === currentPage.value) ?? [],
);

/** Per-page field counts in one pass — the thumbnail rail reads this several
 *  times per thumbnail per render (and re-renders on every drag move). */
const fieldCounts = computed<number[]>(() => {
  const counts: number[] = [];
  for (const field of template.value?.fields ?? []) {
    counts[field.page] = (counts[field.page] ?? 0) + 1;
  }
  return counts;
});

function onRendered(widthPx: number, heightPx: number): void {
  pageWidthPx.value = widthPx;
  pageHeightPx.value = heightPx;
}

/** PdfPage failed to load/render the current page (corrupt PDF, network error, ...). */
function onPdfError(message: string): void {
  errorMessage.value = `Couldn't display the PDF: ${message}`;
}

// --- Roles ---------------------------------------------------------------

function roleColor(role: string): string {
  return sharedRoleColor(role, roles.value);
}

const newRoleName = ref("");

function addRole(): void {
  const name = newRoleName.value.trim();
  if (!name) return;
  if (roles.value.includes(name)) {
    errorMessage.value = `Role "${name}" already exists.`;
    return;
  }
  roles.value.push(name);
  if (!selectedRole.value) selectedRole.value = name;
  newRoleName.value = "";
}

/** Roles that would be lost as assignable signers because no field references them yet. */
const rolesWithoutFields = computed<string[]>(() => {
  const fieldRoles = new Set((template.value?.fields ?? []).map((f) => f.role));
  return roles.value.filter((role) => !fieldRoles.has(role));
});

function deleteRole(role: string): void {
  const fieldCount = template.value?.fields.filter((f) => f.role === role).length ?? 0;
  if (fieldCount > 0 && !window.confirm(`Delete role "${role}" and its ${fieldCount} field(s)?`)) {
    return;
  }
  roles.value = roles.value.filter((r) => r !== role);
  if (template.value) {
    template.value.fields = template.value.fields.filter((f) => f.role !== role);
  }
  if (selectedRole.value === role) selectedRole.value = roles.value[0] ?? null;
}

const editingRole = ref<string | null>(null);
const editingRoleName = ref("");

function startRename(role: string): void {
  editingRole.value = role;
  editingRoleName.value = role;
}

function commitRename(role: string): void {
  if (editingRole.value !== role) return;
  const name = editingRoleName.value.trim();
  editingRole.value = null;
  if (!name || name === role) return;
  if (roles.value.includes(name)) {
    errorMessage.value = `Role "${name}" already exists.`;
    return;
  }
  const idx = roles.value.indexOf(role);
  if (idx === -1) return;
  roles.value[idx] = name;
  if (template.value) {
    template.value.fields = template.value.fields.map((f) => (f.role === role ? { ...f, role: name } : f));
  }
  if (selectedRole.value === role) selectedRole.value = name;
}

// --- Field placement (shared gesture logic; see composables/useFieldPlacement.ts) ---

const { placingType, togglePlacing, onPlacementPointerDown, onPlacementPointerMove, onPlacementPointerUp } =
  useFieldPlacement({
    currentPage,
    pageWidthPx,
    pageHeightPx,
    selectedRole,
    fields: computed(() => template.value?.fields ?? []),
    docLoaded: computed(() => template.value !== null),
  });

function updateField(updated: FieldDef): void {
  if (!template.value) return;
  const idx = template.value.fields.findIndex((f) => f.id === updated.id);
  if (idx === -1) return;
  template.value.fields[idx] = updated;
}

function deleteField(id: string): void {
  if (!template.value) return;
  template.value.fields = template.value.fields.filter((f) => f.id !== id);
  if (selectedFieldId.value === id) selectedFieldId.value = null;
}

/** Floating-toolbar Duplicate: same field, new id, nudged so both stay visible. */
function duplicateField(id: string): void {
  if (!template.value) return;
  const source = template.value.fields.find((f) => f.id === id);
  if (!source) return;
  const copy: FieldDef = {
    ...source,
    id: crypto.randomUUID(),
    x: Math.min(source.x + 0.02, 1 - source.w),
    y: Math.min(source.y + 0.02, 1 - source.h),
    options: source.options ? [...source.options] : undefined,
  };
  template.value.fields.push(copy);
  selectedFieldId.value = copy.id;
}

// --- selected-field properties panel (DocuSign-style) -----------------------

const selectedFieldId = ref<string | null>(null);
const selectedField = computed(
  () => template.value?.fields.find((f) => f.id === selectedFieldId.value) ?? null,
);

// A selected field on another page would be edited invisibly — deselect on paging.
watch(currentPage, () => {
  selectedFieldId.value = null;
});

// --- Preview / send ---------------------------------------------------------

const previewOpen = ref(false);

function previewFieldStyle(field: FieldDef): Record<string, string> {
  return {
    left: `${field.x * 100}%`,
    top: `${field.y * 100}%`,
    width: `${field.w * 100}%`,
    height: `${field.h * 100}%`,
    borderColor: roleColor(field.role),
    color: roleColor(field.role),
  };
}

function previewFieldsForPage(page: number): FieldDef[] {
  return template.value?.fields.filter((f) => f.page === page) ?? [];
}

async function goSend(): Promise<void> {
  // The route guard would flush anyway, but doing it here surfaces a save
  // error before leaving the builder rather than mid-navigation.
  const ok = await ensureSaved();
  if (!ok) return;
  void router.push({ name: "send", params: { templateId: props.id } });
}
</script>

<template>
  <v-container fluid class="builder">
    <v-progress-linear v-if="loading" indeterminate class="mb-4" />

    <v-alert v-if="errorMessage" type="error" closable class="mb-4" @click:close="errorMessage = null">
      {{ errorMessage }}
    </v-alert>

    <template v-if="template">
      <div class="d-flex align-center mb-3 flex-wrap">
        <v-btn variant="text" prepend-icon="mdi-arrow-left" class="px-0 mr-3" :to="{ name: 'dashboard' }">Home</v-btn>
        <h1 class="text-h6 mr-3 text-truncate builder-title">{{ template.name }}</h1>
        <span class="text-caption text-medium-emphasis" aria-live="polite">
          <v-progress-circular v-if="saveState === 'saving'" indeterminate size="12" width="2" class="mr-1" />
          <v-icon v-else-if="saveState === 'saved'" icon="mdi-check" size="x-small" class="mr-1" aria-hidden="true" />
          {{ SAVE_STATE_TEXT[saveState] }}
        </span>
        <v-spacer />
        <v-btn variant="text" prepend-icon="mdi-eye-outline" class="mr-2" @click="previewOpen = true">
          Preview as signer
        </v-btn>
        <v-btn color="primary" variant="flat" prepend-icon="mdi-send" @click="goSend">Send</v-btn>
      </div>

      <v-row>
        <v-col cols="12" md="3">
          <v-card class="mb-4" variant="flat" border>
            <v-card-title class="text-subtitle-1">Signer roles</v-card-title>
            <v-card-text>
              <p v-if="roles.length === 0" class="text-caption text-medium-emphasis mb-2">
                No roles yet — add one to start placing fields.
              </p>
              <div v-for="role in roles" :key="role" class="d-flex align-center mb-2">
                <span class="role-swatch" :style="{ backgroundColor: roleColor(role) }" />
                <v-text-field
                  v-if="editingRole === role"
                  v-model="editingRoleName"
                  density="compact"
                  hide-details
                  autofocus
                  class="ml-2"
                  @keyup.enter="commitRename(role)"
                  @blur="commitRename(role)"
                />
                <template v-else>
                  <span class="ml-2 flex-grow-1">{{ role }}</span>
                  <v-tooltip
                    v-if="rolesWithoutFields.includes(role)"
                    text="This role has no fields yet — place at least one before sending."
                  >
                    <template #activator="{ props: tooltipProps }">
                      <v-chip v-bind="tooltipProps" size="x-small" color="warning" class="mr-1">no fields</v-chip>
                    </template>
                  </v-tooltip>
                  <v-btn
                    icon="mdi-pencil"
                    size="x-small"
                    variant="text"
                    :aria-label="`Rename role ${role}`"
                    @click="startRename(role)"
                  />
                  <v-btn
                    icon="mdi-close"
                    size="x-small"
                    variant="text"
                    :aria-label="`Delete role ${role}`"
                    @click="deleteRole(role)"
                  />
                </template>
              </div>
              <v-text-field
                v-model="newRoleName"
                label="New role"
                density="compact"
                hide-details
                append-inner-icon="mdi-plus"
                @click:append-inner="addRole"
                @keyup.enter="addRole"
              />

              <v-select
                v-model="selectedRole"
                :items="roles"
                label="Role for new fields"
                density="compact"
                hide-details
                class="mt-4"
              />
            </v-card-text>
          </v-card>

          <FieldPalette
            :active-type="placingType"
            :disable-signer-fields="!selectedRole"
            @select="togglePlacing"
          />

        </v-col>

        <v-col cols="12" md="9">
          <div class="d-flex builder-canvas">
            <PageThumbRail
              v-if="pdfUrl"
              :src="pdfUrl"
              :page-count="template.page_count"
              :current="currentPage"
              :field-counts="fieldCounts"
              @update:current="currentPage = $event"
            />

            <div class="flex-grow-1 min-width-0" @pointerdown="selectedFieldId = null">
              <div class="d-flex align-center mb-2">
                <span class="text-body-2 text-medium-emphasis">
                  Page {{ currentPage + 1 }} of {{ template.page_count }}
                </span>
              </div>
              <PdfPage v-if="pdfUrl" :src="pdfUrl" :page="currentPage" @rendered="onRendered" @error="onPdfError">
                <div
                  class="placement-catcher"
                  :class="{ active: placingType }"
                  @pointerdown="onPlacementPointerDown"
                  @pointermove="onPlacementPointerMove"
                  @pointerup="onPlacementPointerUp"
                  @pointercancel="onPlacementPointerUp"
                >
                  <FieldBox
                    v-for="field in fieldsOnCurrentPage"
                    :key="field.id"
                    :field="field"
                    :page-width="pageWidthPx"
                    :page-height="pageHeightPx"
                    :color="field.type === 'label' ? '#616161' : roleColor(field.role)"
                    :selected="field.id === selectedFieldId"
                    @select="selectedFieldId = $event"
                    @update:field="updateField"
                    @delete="deleteField"
                    @duplicate="duplicateField"
                  />
                </div>
              </PdfPage>
            </div>

            <div class="props-col">
              <FieldPropertiesPanel
                v-if="selectedField"
                :field="selectedField"
                :owner-label="selectedField.role"
                :color="selectedField.type === 'label' ? '#616161' : roleColor(selectedField.role)"
                @update:field="updateField"
                @delete="deleteField"
              />
              <v-card v-else variant="flat" border>
                <v-card-text class="text-caption text-medium-emphasis">
                  Select a field on the page to edit its properties — required, font size, prefill text.
                </v-card-text>
              </v-card>
            </div>
          </div>
        </v-col>
      </v-row>

      <!-- Preview as signer -->
      <v-dialog v-model="previewOpen" max-width="880">
        <v-card>
          <v-card-title class="d-flex align-center">
            <span>Signer preview — {{ template.name }}</span>
            <v-spacer />
            <v-btn icon="mdi-close" variant="text" aria-label="Close preview" @click="previewOpen = false" />
          </v-card-title>
          <v-card-text class="preview-scroll">
            <div v-for="page in pageNumbers" :key="page" class="preview-page mb-4">
              <PdfPage v-if="pdfUrl && previewOpen" :src="pdfUrl" :page="page">
                <div
                  v-for="field in previewFieldsForPage(page)"
                  :key="field.id"
                  class="preview-field"
                  :style="previewFieldStyle(field)"
                >
                  <span class="preview-field-label">
                    <template v-if="field.type === 'label'">{{ field.default_value || "Label" }}</template>
                    <template v-else>
                      {{ field.type === "signature" ? "Sign here" : field.type === "initials" ? "Initial here" : field.type }}
                      · {{ field.role }}
                    </template>
                  </span>
                </div>
              </PdfPage>
            </div>
            <p v-if="template.fields.length === 0" class="text-medium-emphasis text-center">
              No fields yet — signers would have nothing to do.
            </p>
          </v-card-text>
        </v-card>
      </v-dialog>
    </template>
  </v-container>
</template>

<style scoped>
.builder {
  max-width: 1400px;
}

.builder-title {
  max-width: 40vw;
}

.role-swatch {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 2px;
  flex: none;
}

.builder-canvas {
  gap: 12px;
  flex-wrap: wrap;
}

.props-col {
  width: 250px;
  flex: none;
}

.min-width-0 {
  min-width: 0;
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

.preview-scroll {
  max-height: 75vh;
  overflow-y: auto;
  background: rgba(0, 0, 0, 0.04);
}

.preview-page {
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
}

.preview-field {
  position: absolute;
  border: 1.5px solid;
  border-radius: 2px;
  box-sizing: border-box;
  background: rgba(255, 255, 255, 0.35);
  overflow: hidden;
}

.preview-field-label {
  font-size: 10px;
  line-height: 1.3;
  padding: 0 2px;
  white-space: nowrap;
}
</style>
