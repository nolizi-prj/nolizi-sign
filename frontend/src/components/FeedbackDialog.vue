<script setup lang="ts">
/**
 * Pumasi Sign Feedback Widget + Modal.
 * Captures diagnostics and page preview, supports paste/upload, and submits to GitHub issues.
 * Features both floating screen trigger and optional navbar button.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import html2canvas from "html2canvas";
import { useAuthStore } from "../store/auth";
import { useUiStore } from "../store/ui";
import http, { extractError } from "../utils/http";

interface ErrorItem {
  message: string;
  source?: string;
  lineno?: number;
  colno?: number;
  timestamp: string;
}

const props = withDefaults(
  defineProps<{
    showFloating?: boolean;
    showNavbarBtn?: boolean;
  }>(),
  {
    showFloating: true,
    showNavbarBtn: true,
  }
);

const ui = useUiStore();
const auth = useAuthStore();
const route = useRoute();

const open = ref(false);
const opening = ref(false);
const message = ref("");
const userEmail = ref("");
const feedbackType = ref<"bug" | "enhancement" | "question">("bug");
const screenshot = ref<File | File[] | null>(null);
const submitting = ref(false);
const error = ref("");
const successIssueUrl = ref<string | null>(null);
const previewUrl = ref<string | null>(null);
const screenshotIsAuto = ref(false);
const contextSnapshot = ref<Record<string, string | number | boolean | null | undefined> | null>(null);
const errLog = ref<ErrorItem[]>([]);

const MAX_SCREENSHOT_BYTES = 4 * 1024 * 1024;

// Global Client-Side Error Tracking
function errorHandler(e: ErrorEvent) {
  errLog.value.push({
    message: e.message || String(e),
    source: e.filename,
    lineno: e.lineno,
    colno: e.colno,
    timestamp: new Date().toISOString(),
  });
  if (errLog.value.length > 10) errLog.value.shift();
}

function rejectionHandler(e: PromiseRejectionEvent) {
  errLog.value.push({
    message: "Unhandled Promise Rejection: " + (e.reason?.message || String(e.reason)),
    timestamp: new Date().toISOString(),
  });
  if (errLog.value.length > 10) errLog.value.shift();
}

onMounted(() => {
  window.addEventListener("error", errorHandler);
  window.addEventListener("unhandledrejection", rejectionHandler);
});

onBeforeUnmount(() => {
  window.removeEventListener("error", errorHandler);
  window.removeEventListener("unhandledrejection", rejectionHandler);
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value);
  }
});

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

function buildContext(): Record<string, string | number | boolean | null | undefined> {
  const nav = navigator as any;
  return {
    Page: route.fullPath,
    URL: window.location.href,
    User: auth.me ? `${auth.me.name} <${auth.me.email}>` : (userEmail.value.trim() || "Anonymous"),
    Browser: navigator.userAgent,
    Platform: nav.userAgentData?.platform || navigator.platform || "Unknown",
    Language: navigator.language,
    Timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
    Viewport: `${window.innerWidth}x${window.innerHeight}`,
    Screen: `${window.screen.width}x${window.screen.height} @${window.devicePixelRatio || 1}x`,
    Network: navigator.onLine ? "Online" : "Offline",
    Hardware: `${navigator.hardwareConcurrency || "unknown"} cores`,
    DeviceMemory: nav.deviceMemory ? `${nav.deviceMemory} GB` : "unknown",
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
    ctx.fillText("Tip: Press Ctrl+V anytime to paste your screenshot!", 24, 150);
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
  if (auth.me?.email && !userEmail.value) {
    userEmail.value = auth.me.email;
  }
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
    error.value = "Screenshot must be 4 MB or smaller.";
    return;
  }
  submitting.value = true;
  error.value = "";
  successIssueUrl.value = null;

  try {
    const form = new FormData();
    form.append("message", message.value);
    form.append("type", feedbackType.value);
    if (userEmail.value.trim()) {
      form.append("userEmail", userEmail.value.trim());
    }
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
    if (errLog.value.length > 0) {
      form.append("errors", JSON.stringify(errLog.value));
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
  <!-- Optional Top Navbar Trigger Button -->
  <v-btn
    v-if="showNavbarBtn"
    variant="text"
    prepend-icon="mdi-message-alert-outline"
    :loading="opening"
    class="mr-1"
    @click="openFeedback"
  >
    Feedback
  </v-btn>

  <!-- Persistent Floating Screen Action Button (Bottom Right) -->
  <div v-if="showFloating" class="pf-floating-wrap">
    <button
      type="button"
      class="pf-floating-btn"
      aria-label="Send Feedback"
      title="Send Feedback or Report an Issue"
      @click="openFeedback"
    >
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="pf-btn-icon">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
      </svg>
      <span class="pf-btn-text">Feedback</span>
    </button>
  </div>

  <!-- Interactive Feedback & Diagnostic Dialog -->
  <v-dialog v-model="open" max-width="560">
    <v-card title="💬 Send Feedback & Report Issues" @paste="onPaste">
      <v-card-text>
        <v-alert v-if="error" type="error" density="compact" class="mb-3">{{ error }}</v-alert>

        <div v-if="successIssueUrl" class="mb-4 pa-3 rounded bg-green-lighten-5 border border-green">
          <p class="text-body-2 font-weight-medium text-green-darken-3 mb-2">
            ✔ Feedback posted directly to GitHub issue tracker!
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

        <!-- Feedback Type Selector -->
        <div class="mb-3">
          <v-btn-toggle v-model="feedbackType" mandatory density="compact" color="primary">
            <v-btn value="bug" prepend-icon="mdi-bug">🐛 Bug</v-btn>
            <v-btn value="enhancement" prepend-icon="mdi-lightbulb-on">✨ Idea</v-btn>
            <v-btn value="question" prepend-icon="mdi-help-circle">💬 Question</v-btn>
          </v-btn-toggle>
        </div>

        <!-- Description Area -->
        <v-textarea
          v-model="message"
          label="What happened or what would you like to see?"
          placeholder="Describe the issue or suggestion in detail..."
          rows="4"
          counter="5000"
          maxlength="5000"
          autofocus
          class="mb-1"
        />

        <!-- Optional User Email -->
        <v-text-field
          v-model="userEmail"
          label="Your email (optional, for notifications)"
          placeholder="you@company.com"
          density="comfortable"
          type="email"
          prepend-inner-icon="mdi-email-outline"
          class="mb-2"
        />

        <!-- Screenshot Attachment & Preview -->
        <v-file-input
          v-model="screenshot"
          label="Screenshot & Attachment (optional)"
          accept="image/png,image/jpeg,image/webp"
          prepend-icon="mdi-camera"
          density="comfortable"
          hint="Press Ctrl+V anywhere in this dialog to paste a screenshot"
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

        <!-- Collapsible Diagnostic Environment Section -->
        <v-expansion-panels variant="accordion" class="mt-4">
          <v-expansion-panel title="🔍 Included Diagnostics (Full Transparency)">
            <v-expansion-panel-text>
              <div class="text-caption">
                <table class="pf-diag-tbl">
                  <tbody>
                    <tr v-for="(val, key) in (contextSnapshot || {})" :key="key">
                      <td class="font-weight-bold pr-2 py-1">{{ key }}</td>
                      <td class="text-medium-emphasis py-1 font-mono text-truncate" style="max-width: 280px;">{{ val }}</td>
                    </tr>
                    <tr v-if="errLog.length > 0">
                      <td class="font-weight-bold pr-2 py-1 text-error">Errors ({{ errLog.length }})</td>
                      <td class="text-error py-1 text-truncate" style="max-width: 280px;">
                        {{ errLog[errLog.length - 1].message }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-card-text>

      <v-card-actions class="pa-4">
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

<style scoped>
/* Persistent Floating Action Button on Bottom-Right */
.pf-floating-wrap {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 999;
}

.pf-floating-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #1A56DB;
  color: #ffffff;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 9999px;
  padding: 8px 16px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(26, 86, 219, 0.35), 0 2px 6px rgba(0, 0, 0, 0.15);
  transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
  user-select: none;
}

.pf-floating-btn:hover {
  background: #1E40AF;
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(26, 86, 219, 0.45), 0 3px 8px rgba(0, 0, 0, 0.2);
}

.pf-floating-btn:active {
  transform: translateY(0);
}

.pf-btn-icon {
  flex-shrink: 0;
}

.pf-diag-tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.78rem;
}

.pf-diag-tbl tr {
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.font-mono {
  font-family: monospace;
}
</style>
