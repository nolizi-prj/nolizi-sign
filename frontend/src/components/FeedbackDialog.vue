<script setup lang="ts">
/**
 * Feedback button + dialog, rendered on every page (see App.vue).
 *
 * Clicking Feedback snapshots context before the dialog opens — what page
 * the user is on, who they are (if signed in), browser/viewport info, and
 * an auto-captured screenshot of the visible page (html2canvas: DOM render,
 * no browser permission prompt) — then shows all of it in the dialog so the
 * user can remove the screenshot (or replace it via file pick / Ctrl+V
 * paste) before sending. POSTs to /api/feedback as multipart form data.
 */
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRoute } from "vue-router";
import html2canvas from "html2canvas";
import { useAuthStore } from "../store/auth";
import { useUiStore } from "../store/ui";
import http, { extractError } from "../utils/http";

const ui = useUiStore();
const auth = useAuthStore();
const route = useRoute();

const open = ref(false);
const opening = ref(false);
const message = ref("");
// Vuetify 3's v-file-input may model a single File or an array depending on
// version/props, so accept both and normalize in `screenshotFile`.
const screenshot = ref<File | File[] | null>(null);
const submitting = ref(false);
const error = ref("");
const previewUrl = ref<string | null>(null);
/** Whether the current screenshot is the auto-captured one (vs user-picked). */
const screenshotIsAuto = ref(false);
/** Context snapshot taken when the button was clicked (not at send time). */
const contextSnapshot = ref<Record<string, string> | null>(null);

const MAX_SCREENSHOT_BYTES = 3 * 1024 * 1024;

const screenshotFile = computed<File | null>(() => {
  const value = screenshot.value;
  if (Array.isArray(value)) return value[0] ?? null;
  return value;
});

watch(screenshotFile, (file, previous) => {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value);
    previewUrl.value = null;
  }
  if (file) {
    previewUrl.value = URL.createObjectURL(file);
  }
  // Any change away from the captured file means the user picked their own.
  if (previous !== undefined && file?.name !== "page-screenshot.jpg") {
    screenshotIsAuto.value = false;
  }
});

onBeforeUnmount(() => {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value);
  }
});

function buildContext(): Record<string, string> {
  return {
    Page: route.fullPath,
    URL: window.location.href,
    User: auth.me ? `${auth.me.name} <${auth.me.email}>` : "not signed in",
    Browser: navigator.userAgent,
    Viewport: `${window.innerWidth}x${window.innerHeight}`,
    Screen: `${window.screen.width}x${window.screen.height} @${window.devicePixelRatio || 1}x`,
  };
}

/**
 * Render the currently visible part of the page to a JPEG file. html2canvas
 * re-renders the DOM onto a canvas — including the pdf.js page canvases —
 * without any browser screen-capture permission prompt. Returns null (and
 * the dialog simply opens without a screenshot) if rendering fails or the
 * result can't be compressed under the 3 MB attachment cap.
 */
async function capturePage(): Promise<File | null> {
  try {
    const canvas = await html2canvas(document.body, {
      logging: false,
      useCORS: true,
      // Cap the pixel density: feedback needs legibility, not print quality.
      scale: Math.min(window.devicePixelRatio || 1, 1.5),
      x: window.scrollX,
      y: window.scrollY,
      width: document.documentElement.clientWidth,
      height: document.documentElement.clientHeight,
    });
    for (const quality of [0.85, 0.6, 0.4]) {
      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
      if (blob && blob.size <= MAX_SCREENSHOT_BYTES) {
        return new File([blob], "page-screenshot.jpg", { type: "image/jpeg" });
      }
    }
    return null;
  } catch {
    return null;
  }
}

async function openFeedback(): Promise<void> {
  if (opening.value) return;
  opening.value = true;
  try {
    contextSnapshot.value = buildContext();
    const captured = await capturePage();
    if (captured) {
      screenshot.value = captured;
      screenshotIsAuto.value = true;
    }
  } finally {
    opening.value = false;
    open.value = true;
  }
}

function removeScreenshot(): void {
  screenshot.value = null;
  screenshotIsAuto.value = false;
}

function onPaste(event: ClipboardEvent): void {
  const items = event.clipboardData?.items;
  if (!items) return;
  for (const item of items) {
    if (item.type !== "image/png" && item.type !== "image/jpeg") continue;
    const pasted = item.getAsFile();
    if (!pasted) continue;
    event.preventDefault();
    const name = pasted.name && pasted.name !== "image.png" ? pasted.name : "pasted-screenshot.png";
    screenshot.value = new File([pasted], name, { type: pasted.type });
    screenshotIsAuto.value = false;
    return;
  }
}

function cancel(): void {
  open.value = false;
  message.value = "";
  screenshot.value = null;
  screenshotIsAuto.value = false;
  contextSnapshot.value = null;
  error.value = "";
}

async function submit(): Promise<void> {
  const file = screenshotFile.value;
  if (file && file.size > MAX_SCREENSHOT_BYTES) {
    error.value = "Screenshot must be 3 MB or smaller.";
    return;
  }
  submitting.value = true;
  error.value = "";
  try {
    const form = new FormData();
    form.append("message", message.value);
    if (file) form.append("screenshot", file);
    if (contextSnapshot.value) form.append("context", JSON.stringify(contextSnapshot.value));
    await http.post("/feedback", form);
    cancel();
    ui.toast("Thanks for the feedback!");
  } catch (err) {
    error.value = extractError(err);
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <v-btn variant="text" prepend-icon="mdi-message-alert-outline" :loading="opening" @click="openFeedback">
    Feedback
  </v-btn>
  <v-dialog v-model="open" max-width="480">
    <v-card title="Feedback for the app" @paste="onPaste">
      <v-card-text>
        <v-alert v-if="error" type="error" density="compact" class="mb-3">{{ error }}</v-alert>
        <v-textarea
          v-model="message"
          label="What's working? What isn't?"
          rows="5"
          counter="5000"
          maxlength="5000"
          autofocus
        />
        <v-file-input
          v-model="screenshot"
          label="Screenshot (optional)"
          accept="image/png,image/jpeg"
          prepend-icon="mdi-image"
          density="comfortable"
          hint="or paste a screenshot (Ctrl+V)"
          persistent-hint
        />
        <div v-if="previewUrl" class="d-flex align-center mt-2">
          <v-img :src="previewUrl" max-width="120" max-height="120" class="rounded border" />
          <div class="ml-2">
            <p v-if="screenshotIsAuto" class="text-caption text-medium-emphasis mb-0">
              Screenshot of this page, attached automatically.
            </p>
            <v-btn size="small" variant="text" prepend-icon="mdi-close" @click="removeScreenshot">
              Remove
            </v-btn>
          </div>
        </div>
        <p v-if="contextSnapshot" class="text-caption text-medium-emphasis mt-3 mb-0">
          Sent along with your message: current page ({{ contextSnapshot.Page }}),
          {{ auth.me ? `your account (${auth.me.email})` : "no account (not signed in)" }},
          and browser info.
        </p>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" :disabled="submitting" @click="cancel">Cancel</v-btn>
        <v-btn color="primary" :disabled="!message.trim()" :loading="submitting" @click="submit">
          Send
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
