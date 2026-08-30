<script setup lang="ts">
/**
 * "New template" dialog: name + document upload, POST /templates, then
 * straight into the field builder for the created template. Shared by the
 * Templates page and the send wizard's "Use a template" card (redundant
 * entry points by design — creating a template shouldn't require leaving
 * the flow you're in).
 */
import { ref, watch } from "vue";
import { useRouter } from "vue-router";
import http, { extractError } from "../utils/http";
import { UPLOAD_ACCEPT } from "../utils/uploads";
import type { TemplateOut } from "../types";

const open = defineModel<boolean>({ required: true });

const router = useRouter();

const name = ref("");
// A non-multiple <v-file-input>'s v-model is a single File | null at runtime
// (Vuetify's useProxiedModel unwraps the array — see VFileInput's own type
// declarations), never a File[].
const file = ref<File | null>(null);
const saving = ref(false);
const errorMessage = ref<string | null>(null);

watch(open, (isOpen) => {
  if (isOpen) {
    name.value = "";
    file.value = null;
    errorMessage.value = null;
  }
});

async function create(): Promise<void> {
  if (!file.value || !name.value.trim()) {
    errorMessage.value = "Name and file are required.";
    return;
  }
  saving.value = true;
  errorMessage.value = null;
  try {
    const formData = new FormData();
    formData.append("name", name.value.trim());
    formData.append("file", file.value);
    const { data } = await http.post<TemplateOut>("/templates", formData);
    open.value = false;
    await router.push({ name: "template-builder", params: { id: String(data.id) } });
  } catch (err) {
    errorMessage.value = extractError(err);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <v-dialog v-model="open" max-width="480">
    <v-card>
      <v-card-title>New template</v-card-title>
      <v-card-text>
        <v-alert v-if="errorMessage" type="error" class="mb-4" density="compact">
          {{ errorMessage }}
        </v-alert>
        <v-text-field v-model="name" label="Name" autofocus />
        <v-file-input
          v-model="file"
          label="Document"
          :accept="UPLOAD_ACCEPT"
          prepend-icon="mdi-file-upload"
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="open = false">Cancel</v-btn>
        <v-btn color="primary" :loading="saving" @click="create">Create</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
