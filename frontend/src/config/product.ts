/**
 * Product identity. The single place the product name appears, so a rename is one edit.
 * Internal programme details (team, batch, project code) never belong in the product UI.
 */
export const product = {
  name: "PM Copilot",
  fullName: "AI Product Manager Copilot",
  description: "Turn customer feedback into evidence-backed product decisions.",
} as const;
