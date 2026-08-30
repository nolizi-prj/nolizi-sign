/**
 * Shared signer-role helpers, used by the template builder, the send
 * wizard, and anywhere else roles are shown. Color assignment is
 * deterministic: a role's color is its index in the caller's role list.
 */
import type { TemplateOut } from "../types";

const ROLE_COLORS = [
  "#1C3A62", // navy (primary)
  "#B45309", // amber
  "#5B21B6", // violet
  "#2E7D32", // green
  "#B3261E", // red
  "#24425C", // ink blue
];

export function roleColor(role: string, roles: readonly string[]): string {
  const idx = roles.indexOf(role);
  return ROLE_COLORS[(idx < 0 ? 0 : idx) % ROLE_COLORS.length];
}

/**
 * A template's signer roles, in display order. Persisted roles win;
 * deriving from fields covers templates saved before roles became a stored
 * template attribute.
 */
export function templateRoles(template: Pick<TemplateOut, "roles" | "fields">): string[] {
  const seen: string[] = [...template.roles];
  for (const field of template.fields) {
    // Labels are role-less sender text (role "") — never a signer role; an
    // empty string here would make the builder's roles PUT fail validation.
    if (!field.role) continue;
    if (!seen.includes(field.role)) seen.push(field.role);
  }
  return seen;
}
