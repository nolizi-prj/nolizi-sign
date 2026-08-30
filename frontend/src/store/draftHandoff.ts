import { defineStore } from "pinia";
import { ref } from "vue";

/**
 * In-memory handoff store for passing dropped/selected files from
 * the Dashboard hero dropzone directly into SendView.
 */
export const useDraftHandoffStore = defineStore("draftHandoff", () => {
  const pendingFile = ref<File | null>(null);

  function setFile(file: File | null) {
    pendingFile.value = file;
  }

  function consumeFile(): File | null {
    const f = pendingFile.value;
    pendingFile.value = null;
    return f;
  }

  return { pendingFile, setFile, consumeFile };
});
