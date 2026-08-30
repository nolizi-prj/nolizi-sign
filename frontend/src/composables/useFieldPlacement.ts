/**
 * Shared "click-and-drag to place a field" pointer-gesture logic, used by
 * both TemplateBuilderView (fields keyed by a free-text role name) and
 * SendView's one-off path (fields keyed by a recipient's internal
 * signer-N role name).
 *
 * Callers own the field list (a reactive array, pushed/spliced by this
 * composable's handlers) and the "role for new fields" selection; this
 * composable only owns the placing-in-progress UI state (`placingType`,
 * which field id is currently being dragged into position) and the pointer
 * math that turns a pointerdown/move/up sequence on the placement-catcher
 * element into a normalized (0..1), page-clamped FieldDef.
 */
import { ref, type Ref } from "vue";
import type { FieldDef, FieldType } from "../types";

export const DEFAULT_SIZES: Record<FieldType, { w: number; h: number }> = {
  // ~1.7in x 0.6in on a US-letter page — close to DocuSign's stamp, which
  // is wide but short; the old 0.28 x 0.09 default dwarfed the documents it
  // was dropped on (user feedback 2026-08-11). Signatures are trimmed to
  // their ink at stamp time, so a shorter box no longer shrinks the drawing.
  signature: { w: 0.2, h: 0.055 },
  // Small stamp for per-page initialing, DocuSign-style.
  initials: { w: 0.09, h: 0.05 },
  text: { w: 0.2, h: 0.04 },
  date: { w: 0.12, h: 0.04 },
  name: { w: 0.15, h: 0.04 },
  checkbox: { w: 0.03, h: 0.03 },
  dropdown: { w: 0.2, h: 0.04 },
  radio: { w: 0.2, h: 0.04 },
  attachment: { w: 0.2, h: 0.05 },
  label: { w: 0.25, h: 0.04 },
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), Math.max(min, max));
}

export interface UseFieldPlacementOptions {
  /** 0-indexed page a newly-placed field should land on. */
  currentPage: Ref<number>;
  /** Current rendered page size in px (from PdfPage's `rendered` emit). */
  pageWidthPx: Ref<number>;
  pageHeightPx: Ref<number>;
  /** The role new fields are placed under; placement is disabled while null. */
  selectedRole: Ref<string | null>;
  /** The reactive field list to push new fields onto / adjust during drag. Anything with a settable `.value` array works (a plain ref or a computed forwarding into a parent object). */
  fields: { value: FieldDef[] };
  /**
   * Whether the document is actually loaded (TemplateBuilderView:
   * `template.value !== null`; EnvelopeComposeView: `pdfUrl.value !== null`).
   * Guards against a stray/late pointer event creating or moving a field
   * before there's a document to place it on — inline `!template.value`
   * checks in TemplateBuilderView before this logic was extracted here.
   */
  docLoaded: Ref<boolean>;
}

export function useFieldPlacement(options: UseFieldPlacementOptions) {
  const { currentPage, pageWidthPx, pageHeightPx, selectedRole, fields, docLoaded } = options;

  const placingType = ref<FieldType | null>(null);
  const placingFieldId = ref<string | null>(null);

  function togglePlacing(type: FieldType): void {
    // Labels are sender text — no owning role, placeable regardless of the
    // role selection. Every other type needs a role to belong to.
    if (type !== "label" && !selectedRole.value) return;
    placingType.value = placingType.value === type ? null : type;
  }

  function normalizedPointFromEvent(event: PointerEvent, el: HTMLElement): { x: number; y: number } {
    const rect = el.getBoundingClientRect();
    const x = pageWidthPx.value > 0 ? (event.clientX - rect.left) / pageWidthPx.value : 0;
    const y = pageHeightPx.value > 0 ? (event.clientY - rect.top) / pageHeightPx.value : 0;
    return { x, y };
  }

  function onPlacementPointerDown(event: PointerEvent): void {
    if (!placingType.value || !docLoaded.value) return;
    if (placingType.value !== "label" && !selectedRole.value) return;
    const target = event.currentTarget as HTMLElement;
    target.setPointerCapture(event.pointerId);

    const size = DEFAULT_SIZES[placingType.value];
    const { x: cx, y: cy } = normalizedPointFromEvent(event, target);
    const x = clamp(cx - size.w / 2, 0, 1 - size.w);
    const y = clamp(cy - size.h / 2, 0, 1 - size.h);

    const field: FieldDef = {
      id: crypto.randomUUID(),
      type: placingType.value,
      role: placingType.value === "label" ? "" : (selectedRole.value ?? ""),
      page: currentPage.value,
      x,
      y,
      w: size.w,
      h: size.h,
      // Signature/initials fields default to required — the field types a
      // signer virtually never leaves blank; the per-field toggle in
      // FieldBox.vue still lets the caller turn it off for an edge case.
      required: placingType.value === "signature" || placingType.value === "initials",
    };
    if (placingType.value === "dropdown" || placingType.value === "radio") {
      // The backend rejects a choice field with no options — seed one so a
      // just-placed field is saveable; the properties panel is where the
      // sender writes the real list.
      field.options = ["Option 1"];
    }
    fields.value.push(field);
    placingFieldId.value = field.id;
  }

  function onPlacementPointerMove(event: PointerEvent): void {
    if (!placingFieldId.value || !placingType.value || !docLoaded.value) return;
    const target = event.currentTarget as HTMLElement;
    const size = DEFAULT_SIZES[placingType.value];
    const { x: cx, y: cy } = normalizedPointFromEvent(event, target);
    const x = clamp(cx - size.w / 2, 0, 1 - size.w);
    const y = clamp(cy - size.h / 2, 0, 1 - size.h);

    const idx = fields.value.findIndex((f) => f.id === placingFieldId.value);
    if (idx === -1) return;
    fields.value[idx] = { ...fields.value[idx], x, y };
  }

  function onPlacementPointerUp(event: PointerEvent): void {
    if (!placingFieldId.value) return;
    const target = event.currentTarget as HTMLElement;
    if (target.hasPointerCapture(event.pointerId)) target.releasePointerCapture(event.pointerId);
    placingFieldId.value = null;
    placingType.value = null;
  }

  return {
    placingType,
    togglePlacing,
    onPlacementPointerDown,
    onPlacementPointerMove,
    onPlacementPointerUp,
  };
}
