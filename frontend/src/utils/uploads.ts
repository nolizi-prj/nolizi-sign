/**
 * File types the backend can convert to PDF (see backend/app/conversion.py
 * ALLOWED_EXTENSIONS) — the single source for every upload picker's `accept`.
 */
export const UPLOAD_ACCEPT =
  ".pdf,.doc,.docx,.dot,.dotm,.dotx,.xls,.xlsm,.xlsx,.ppt,.pptx,.pps,.ppsx," +
  ".rtf,.odt,.ods,.odp,.txt,.csv,.htm,.html,.md,.markdown,.eml,.msg,.epub," +
  ".png,.jpg,.jpeg,.tif,.tiff";

export const MAX_SOURCE_FILE_BYTES = 20_000_000;
export const MAX_SOURCE_SET_BYTES = 20_000_000;

export function validateSourceFiles(files: File[]): string | null {
  const allowed = new Set(UPLOAD_ACCEPT.split(",").map((extension) => extension.slice(1)));
  const unsupported = files.find((file) => {
    const extension = file.name.toLowerCase().split(".").pop() || "";
    return !allowed.has(extension);
  });
  if (unsupported) return `“${unsupported.name}” is not a supported document format.`;
  const oversized = files.find((file) => file.size > MAX_SOURCE_FILE_BYTES);
  if (oversized) return `“${oversized.name}” is larger than 20 MB. Compress it or split it into smaller documents.`;
  const total = files.reduce((sum, file) => sum + file.size, 0);
  if (total > MAX_SOURCE_SET_BYTES) return "These documents total more than 20 MB. Compress them or upload a smaller set.";
  return null;
}
