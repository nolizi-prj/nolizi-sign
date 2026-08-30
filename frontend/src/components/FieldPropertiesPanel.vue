<script setup lang="ts">
/**
 * DocuSign-style properties panel for the selected field box: everything
 * editable about a field (required, font size, prefill / label text,
 * delete) lives here, so the boxes on the page stay clean and legible no
 * matter how small they are. Shared by the template builder and the send
 * wizard's Place-fields step; the parent owns selection and the field list.
 */
import { computed } from "vue";
import type { FieldDef } from "../types";

const props = defineProps<{
  field: FieldDef;
  /** Display name for the field's owner (person name or role string). */
  ownerLabel: string;
  color: string;
}>();

const emit = defineEmits<{
  "update:field": [field: FieldDef];
  delete: [id: string];
}>();

/** text and label boxes carry sender-editable content (prefill / label text). */
const hasContentInput = computed(() => props.field.type === "text" || props.field.type === "label");

/** Field types that render text and so can carry a sender-chosen font size. */
const hasFontSize = computed(() => ["text", "label", "name", "date", "dropdown", "radio"].includes(props.field.type));

/** Choice fields carry a sender-defined option list. */
const hasOptions = computed(() => props.field.type === "dropdown" || props.field.type === "radio");

const VALIDATION_ITEMS = [
  { title: "Any text", value: null },
  { title: "Email address", value: "email" },
  { title: "Number", value: "number" },
];

function onContentInput(value: string): void {
  emit("update:field", { ...props.field, default_value: value || null });
}

function onOptionsInput(value: unknown): void {
  const raw = Array.isArray(value) ? value : [];
  const options = [...new Set(raw.map((option) => String(option).trim()).filter(Boolean))].slice(0, 20);
  emit("update:field", { ...props.field, options: options.length > 0 ? options : null });
}

function onValidationInput(value: "email" | "number" | null): void {
  emit("update:field", { ...props.field, validation: value });
}

function onFontSizeInput(value: string): void {
  const parsed = value === "" ? null : Math.min(72, Math.max(6, Math.round(Number(value))));
  emit("update:field", { ...props.field, font_size: Number.isNaN(parsed as number) ? null : parsed });
}

function onRequiredToggle(value: boolean | null): void {
  emit("update:field", { ...props.field, required: value === true });
}
</script>

<template>
  <v-card variant="flat" border class="field-props">
    <v-card-title class="text-subtitle-2 d-flex align-center">
      <span class="props-swatch mr-2" :style="{ backgroundColor: color }" />
      <span class="text-truncate">
        {{ field.type === "label" ? "Label" : `${ownerLabel} · ${field.type}` }}
      </span>
    </v-card-title>
    <v-card-text>
      <v-switch
        v-if="field.type !== 'label'"
        :model-value="field.required"
        label="Required field"
        color="primary"
        density="compact"
        hide-details
        class="mb-3"
        @update:model-value="onRequiredToggle"
      />
      <v-text-field
        v-if="hasContentInput"
        :model-value="field.default_value ?? ''"
        :label="field.type === 'label' ? 'Label text' : 'Prefill (optional)'"
        maxlength="500"
        density="compact"
        class="mb-3"
        hide-details
        @update:model-value="onContentInput"
      />
      <v-combobox
        v-if="hasOptions"
        :model-value="field.options ?? []"
        label="Options"
        multiple
        chips
        closable-chips
        density="compact"
        hint="Type an option and press Enter. At least one is required."
        persistent-hint
        class="mb-3"
        @update:model-value="onOptionsInput"
      />
      <v-select
        v-if="field.type === 'text'"
        :model-value="field.validation ?? null"
        :items="VALIDATION_ITEMS"
        label="Input format"
        density="compact"
        hide-details
        class="mb-3"
        @update:model-value="onValidationInput"
      />
      <v-text-field
        v-if="hasFontSize"
        :model-value="field.font_size ?? ''"
        label="Font size (pt)"
        type="number"
        min="6"
        max="72"
        density="compact"
        hint="Empty = automatic (fits the box)"
        persistent-hint
        class="mb-3"
        @update:model-value="onFontSizeInput"
      />
      <v-btn
        block
        variant="tonal"
        color="error"
        prepend-icon="mdi-delete-outline"
        @click="emit('delete', field.id)"
      >
        Delete field
      </v-btn>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.props-swatch {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 2px;
  flex: none;
}
</style>
