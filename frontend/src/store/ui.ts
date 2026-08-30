/**
 * UI store: a single global toast (snackbar) queue.
 *
 * Every mutation in the app confirms itself through `toast()` so the user
 * always gets feedback ("Reminder sent.", "Envelope cancelled.", ...) —
 * the host `<v-snackbar>` lives in App.vue. Only one toast shows at a
 * time; a new call replaces the current one (fine for this app's rate of
 * actions, and far simpler than a real queue).
 */
import { defineStore } from "pinia";
import { ref } from "vue";

export type ToastColor = "success" | "error" | "info";

export const useUiStore = defineStore("ui", () => {
  const toastOpen = ref(false);
  const toastMessage = ref("");
  const toastColor = ref<ToastColor>("success");

  function toast(message: string, color: ToastColor = "success"): void {
    // Close then reopen on next tick isn't needed: v-snackbar restarts its
    // timeout when model-value flips; replacing text while open is fine.
    toastMessage.value = message;
    toastColor.value = color;
    toastOpen.value = true;
  }

  return { toastOpen, toastMessage, toastColor, toast };
});
