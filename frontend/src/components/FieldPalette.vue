<script setup lang="ts">
import type { FieldType } from "../types";
import { FIELD_TYPES } from "../types";

defineProps<{
  activeType: FieldType | null;
  disableSignerFields?: boolean;
}>();

const emit = defineEmits<{ select: [type: FieldType] }>();

const FIELD_ICONS: Record<FieldType, string> = {
  signature: "mdi-draw-pen",
  initials: "mdi-fountain-pen-tip",
  name: "mdi-account-outline",
  date: "mdi-calendar-outline",
  text: "mdi-form-textbox",
  checkbox: "mdi-checkbox-marked-outline",
  dropdown: "mdi-form-dropdown",
  radio: "mdi-radiobox-marked",
  attachment: "mdi-paperclip",
  label: "mdi-label-outline",
};
</script>

<template>
  <v-card variant="flat" border class="field-palette">
    <v-card-title class="text-subtitle-1">Add field</v-card-title>
    <v-card-text>
      <v-btn
        v-for="fieldType in FIELD_TYPES"
        :key="fieldType"
        block
        class="mb-2 text-capitalize justify-start"
        :prepend-icon="FIELD_ICONS[fieldType]"
        :variant="activeType === fieldType ? 'flat' : 'tonal'"
        :color="activeType === fieldType ? 'primary' : undefined"
        :disabled="disableSignerFields && fieldType !== 'label'"
        @click="emit('select', fieldType)"
      >
        {{ fieldType }}
      </v-btn>
      <p v-if="activeType" class="text-caption text-medium-emphasis mb-0">
        Click and drag on the page to place a {{ activeType }} field.
      </p>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.field-palette { width: 100%; }
</style>
