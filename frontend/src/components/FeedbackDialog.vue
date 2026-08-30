<script setup lang="ts">
/**
 * Pumasi Sign Feedback Widget + Modal.
 * Captures diagnostics and page preview, supports paste/upload, and submits to GitHub issues.
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
const feedbackType = ref<"bug" | "enhancement" | "question">("bug");
const screenshot = ref<File | File[] | null>(null);
const submitting = ref(false);
const error = ref("");
const successIssueUrl = ref<string | null>(null);
const previewUrl = ref<string | null>(null);
const screenshotIsAuto = ref(false);
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
    Time: new Date().toISOString(),
  };
}

function drawFallbackCanvas(): File | null {
  try {
    const canvas = document.createElement("canvas");
    canvas.width = Math.min(window.innerWidth, 1280);
    canvas.height = Math.min(window.innerHeight, 800);
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#101828";
    ctx.font = "bold 16px sans-serif";
    ctx.fillText("Pumasi Sign Session Snapshot", 24, 45);
    ctx.font = "14px sans-serif";
    ctx.fillText("URL: " + location.href, 24, 80);
    ctx.fillText("Time: " + new Date().toLocaleString(), 24, 110);
    ctx.fillText("Tip: Press Ctrl+V to paste your screenshot!", 24, 150);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.8);
    const byteString = atob(dataUrl.split(",")[1]);
    const ab = new ArrayBuffer(byteString.length);
    const ia = new Uint8Array(ab);
    for (let i = 0; i < byteString.length; i++) ia[i] = byteString.charCodeAt(i);
    return new File([ab], "page-screenshot.jpg", { type: "image/jpeg" });
  } catch {
    return null;
  }
}

async function capturePage(): Promise<File | null> {
  try {
    const canvas = await html2canvas(document.body, {
      logging: false,
      useCORS: true,
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
    return drawFallbackCanvas();
  } catch {
    return drawFallbackCanvas();
  }
}

async function openFeedback(): Promise<void> {
  if (opening.value) return;
  opening.value = true;
  successIssueUrl.value = null;
  error.value = "";
  contextSnapshot.value = buildContext();
  
  // Set fallback snapshot immediately for zero delay
  const fallback = drawFallbackCanvas();
  if (fallback) {
    screenshot.value = fallback;
    screenshotIsAuto.value = true;
  }
  open.value = true;
  opening.value = false;

  // Enhance with real html2canvas asynchronously in background
  capturePage().then((captured) => {
    if (captured && screenshotIsAuto.value) {
      screenshot.value = captured;
    }
  });
}

function removeScreenshot(): void {
  screenshot.value = null;
  screenshotIsAuto.value = false;
}

function onPaste(event: ClipboardEvent): void {
  const items = event.clipboardData?.items;
  if (!items) return;
  for (const item of items) {
    if (item.type.includes("image")) {
      const pasted = item.getAsFile();
      if (!pasted) continue;
      event.preventDefault();
      screenshot.value = new File([pasted], "pasted-screenshot.png", { type: pasted.type });
      screenshotIsAuto.value = false;
      return;
    }
  }
}

function cancel(): void {
  open.value = false;
  message.value = "";
  screenshot.value = null;
  screenshotIsAuto.value = false;
  contextSnapshot.value = null;
  error.value = "";
  successIssueUrl.value = null;
}

async function submit(): Promise<void> {
  const file = screenshotFile.value;
  if (file && file.size > MAX_SCREENSHOT_BYTES) {
    error.value = "Screenshot must be 3 MB or smaller.";
    return;
  }
  submitting.value = true;
  error.value = "";
  successIssueUrl.value = null;

  try {
    const form = new FormData();
    form.append("message", message.value);
    form.append("type", feedbackType.value);
    if (file) {
      const reader = new FileReader();
      const base64Promise = new Promise<string>((resolve) => {
        reader.onload = () => resolve(reader.result as string);
        reader.readAsDataURL(file);
      });
      const base64Data = await base64Promise;
      form.append("screenshot", base64Data);
    }
    if (contextSnapshot.value) {
      form.append("context", JSON.stringify(contextSnapshot.value));
    }

    const res: any = await http.post("/feedback", form);
    if (res.data?.issueUrl) {
      successIssueUrl.value = res.data.issueUrl;
      ui.toast("Feedback posted to GitHub!");
    } else {
      cancel();
      ui.toast("Thanks for the feedback!");
    }
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
  <v-dialog v-model="open" max-width="520">
    <v-card title="Send Feedback to Pumasi" @paste="onPaste">
      <v-card-text>
        <v-alert v-if="error" type="error" density="compact" class="mb-3">{{ error }}</v-alert>

        <div v-if="successIssueUrl" class="mb-4 pa-3 rounded bg-green-lighten-5 border border-green">
          <p class="text-body-2 font-weight-medium text-green-darken-3 mb-2">
            ✔ Feedback posted to GitHub issue tracker!
          </p>
          <v-btn
            :href="successIssueUrl"
            target="_blank"
            color="success"
            variant="tonal"
            size="small"
            append-icon="mdi-open-in-new"
          >
            View Issue on GitHub
          </v-btn>
        </div>

        <div class="mb-3">
          <v-btn-toggle v-model="feedbackType" mandatory density="compact" color="primary">
            <v-btn value="bug" prepend-icon="mdi-bug">Bug</v-btn>
            <v-btn value="enhancement" prepend-icon="mdi-lightbulb-on">Feature</v-btn>
            <v-btn value="question" prepend-icon="mdi-help-circle">Question</v-btn>
          </v-btn-toggle>
        </div>

        <v-textarea
          v-model="message"
          label="What happened? What would you like to see?"
          rows="4"
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
          hint="or press Ctrl+V to paste"
          persistent-hint
        />

        <div v-if="previewUrl" class="d-flex align-center mt-2 pa-2 border rounded bg-grey-lighten-4">
          <v-img :src="previewUrl" max-width="140" max-height="90" class="rounded border" />
          <div class="ml-3">
            <p v-if="screenshotIsAuto" class="text-caption text-medium-emphasis mb-1">
              Live page preview attached automatically.
            </p>
            <v-btn size="small" variant="text" color="error" prepend-icon="mdi-close" @click="removeScreenshot">
              Remove Screenshot
            </v-btn>
          </div>
        </div>

        <p v-if="contextSnapshot" class="text-caption text-medium-emphasis mt-3 mb-0">
          Diagnostics: {{ contextSnapshot.Page }} &middot; {{ auth.me ? auth.me.email : "guest" }} &middot; {{ contextSnapshot.Screen }}
        </p>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" :disabled="submitting" @click="cancel">
          {{ successIssueUrl ? "Close" : "Cancel" }}
        </v-btn>
        <v-btn
          v-if="!successIssueUrl"
          color="primary"
          :disabled="!message.trim()"
          :loading="submitting"
          @click="submit"
        >
          Submit Feedback &rarr;
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
