<script setup lang="ts">
/**
 * One draggable/resizable field box, positioned absolutely over a PdfPage's
 * canvas. Coordinates on `field` are normalized (0..1) fractions of the
 * page; this component converts to/from pixels using `pageWidth`/`pageHeight`
 * and always emits normalized, page-clamped values back to the parent
 * (fields are a prop, not v-model, so the parent owns the source of truth).
 *
 * DocuSign-style split: the box itself is display-only (name label, drag,
 * resize, select) — full property editing (font size, prefill / label text,
 * validation) lives in FieldPropertiesPanel, which the parent shows for the
 * selected field. Controls used to render inside the box and became an
 * unreadable jumble for small fields; the selected box instead gets a
 * fixed-size floating mini-toolbar *below* it (required / duplicate /
 * delete), which never scales with the field.
 */
import { computed } from "vue";
import type { FieldDef } from "../types";

const props = defineProps<{
  field: FieldDef;
  pageWidth: number;
  pageHeight: number;
  color: string;
  /** Display name for the field's owner; defaults to the raw role string
   *  (the send wizard shows person names over internal signer-N roles). */
  roleLabel?: string;
  /** Highlighted + editable in the parent's properties panel. */
  selected?: boolean;
}>();

const emit = defineEmits<{
  "update:field": [field: FieldDef];
  select: [id: string];
  delete: [id: string];
  /** Ask the parent to place a copy of this field (new id, slight offset). */
  duplicate: [id: string];
}>();

function toggleRequired(): void {
  emit("update:field", { ...props.field, required: !props.field.required });
}

const MIN_SIZE = 0.02;

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), Math.max(min, max));
}

/** The field's owner as shown to the user — display name when given, raw role otherwise. */
const ownerLabel = computed(() => props.roleLabel ?? props.field.role);

/** Label fields read as their own text (that's what gets stamped); other
 *  fields as "owner: type". */
const headerText = computed(() => {
  if (props.field.type === "label") return props.field.default_value?.trim() || "Label";
  return `${ownerLabel.value}: ${props.field.type}`;
});

const style = computed(() => ({
  left: `${props.field.x * props.pageWidth}px`,
  top: `${props.field.y * props.pageHeight}px`,
  width: `${props.field.w * props.pageWidth}px`,
  height: `${props.field.h * props.pageHeight}px`,
  color: props.color,
  borderColor: props.color,
  backgroundColor: `${props.color}26`,
}));

// Drag/resize gestures both track pointer deltas in px, converted to
// normalized units against the *current* page pixel size. Plain closure
// variables (not reactive state) are enough here — they only drive the
// emitted values, nothing reads them in the template.
let dragState: { startX: number; startY: number; origX: number; origY: number } | null = null;
let resizeState: { startX: number; startY: number; origW: number; origH: number } | null = null;

function onDragPointerDown(event: PointerEvent): void {
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  dragState = { startX: event.clientX, startY: event.clientY, origX: props.field.x, origY: props.field.y };
  emit("select", props.field.id);
  event.stopPropagation();
}

function onDragPointerMove(event: PointerEvent): void {
  if (!dragState || props.pageWidth <= 0 || props.pageHeight <= 0) return;
  const dx = (event.clientX - dragState.startX) / props.pageWidth;
  const dy = (event.clientY - dragState.startY) / props.pageHeight;
  const x = clamp(dragState.origX + dx, 0, 1 - props.field.w);
  const y = clamp(dragState.origY + dy, 0, 1 - props.field.h);
  emit("update:field", { ...props.field, x, y });
}

function onDragPointerUp(event: PointerEvent): void {
  if (!dragState) return;
  dragState = null;
  (event.currentTarget as HTMLElement).releasePointerCapture(event.pointerId);
}

function onResizePointerDown(event: PointerEvent): void {
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  resizeState = { startX: event.clientX, startY: event.clientY, origW: props.field.w, origH: props.field.h };
  emit("select", props.field.id);
  event.stopPropagation();
}

function onResizePointerMove(event: PointerEvent): void {
  if (!resizeState || props.pageWidth <= 0 || props.pageHeight <= 0) return;
  const dw = (event.clientX - resizeState.startX) / props.pageWidth;
  const dh = (event.clientY - resizeState.startY) / props.pageHeight;
  const w = clamp(resizeState.origW + dw, MIN_SIZE, 1 - props.field.x);
  const h = clamp(resizeState.origH + dh, MIN_SIZE, 1 - props.field.y);
  emit("update:field", { ...props.field, w, h });
}

function onResizePointerUp(event: PointerEvent): void {
  if (!resizeState) return;
  resizeState = null;
  (event.currentTarget as HTMLElement).releasePointerCapture(event.pointerId);
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Delete" || event.key === "Backspace") {
    emit("delete", props.field.id);
    event.preventDefault();
  }
}
</script>

<template>
  <div
    class="field-box"
    :class="{ selected }"
    :style="style"
    role="button"
    tabindex="0"
    :aria-label="`${headerText} field — click to edit its properties`"
    :aria-pressed="selected"
    @pointerdown="onDragPointerDown"
    @pointermove="onDragPointerMove"
    @pointerup="onDragPointerUp"
    @pointercancel="onDragPointerUp"
    @keydown="onKeydown"
  >
    <span class="field-label">{{ headerText }}</span>
    <span v-if="field.required && field.type !== 'label'" class="field-required-mark" aria-hidden="true">*</span>
    <div
      class="field-resize-handle"
      @pointerdown.stop="onResizePointerDown"
      @pointermove.stop="onResizePointerMove"
      @pointerup.stop="onResizePointerUp"
      @pointercancel.stop="onResizePointerUp"
    />
    <!-- Floating mini-toolbar (DocuSign-style): fixed size below the box, so
         it stays usable however small the field is. pointerdown must not
         bubble into the drag handler above. -->
    <div v-if="selected" class="field-toolbar" @pointerdown.stop>
      <button
        v-if="field.type !== 'label'"
        type="button"
        class="field-toolbar-btn"
        :class="{ active: field.required }"
        :aria-label="field.required ? 'Make optional' : 'Make required'"
        :title="field.required ? 'Required — click to make optional' : 'Optional — click to make required'"
        @click.stop="toggleRequired"
      >
        <v-icon :icon="field.required ? 'mdi-asterisk' : 'mdi-asterisk-circle-outline'" size="14" />
      </button>
      <button
        type="button"
        class="field-toolbar-btn"
        aria-label="Duplicate field"
        title="Duplicate"
        @click.stop="emit('duplicate', field.id)"
      >
        <v-icon icon="mdi-content-copy" size="14" />
      </button>
      <button
        type="button"
        class="field-toolbar-btn"
        aria-label="Delete field"
        title="Delete"
        @click.stop="emit('delete', field.id)"
      >
        <v-icon icon="mdi-delete-outline" size="14" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.field-box {
  position: absolute;
  /* The parent placement-catcher toggles pointer-events off when no field
     type is armed for placing; boxes must stay interactive regardless. */
  pointer-events: auto;
  border: 2px solid;
  border-radius: 2px;
  box-sizing: border-box;
  cursor: move;
  touch-action: none;
}

.field-box.selected {
  outline: 2px solid currentColor;
  outline-offset: 1px;
  z-index: 5;
}

.field-box:focus-visible {
  outline: 2px solid currentColor;
  outline-offset: 1px;
}

/* Identification only — never captures the pointer, never clips siblings. */
.field-label {
  position: absolute;
  inset: 0 2px auto 2px;
  font-size: 10px;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  pointer-events: none;
}

.field-required-mark {
  position: absolute;
  top: 0;
  right: 2px;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.2;
  pointer-events: none;
}

.field-toolbar {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  display: flex;
  gap: 2px;
  padding: 2px;
  background: rgb(var(--v-theme-surface));
  color: rgba(var(--v-theme-on-surface), 0.8);
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
  z-index: 7;
  cursor: default;
}

.field-toolbar-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 3px;
  background: transparent;
  color: inherit;
  cursor: pointer;
}

.field-toolbar-btn:hover {
  background: rgba(var(--v-theme-on-surface), 0.08);
}

.field-toolbar-btn.active {
  color: rgb(var(--v-theme-primary));
}

.field-resize-handle {
  position: absolute;
  right: -4px;
  bottom: -4px;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  background: currentColor;
  cursor: nwse-resize;
  touch-action: none;
}

/* Fingers need a bigger target than a mouse pointer does. */
@media (pointer: coarse) {
  .field-resize-handle {
    width: 22px;
    height: 22px;
    right: -8px;
    bottom: -8px;
  }
}
</style>
