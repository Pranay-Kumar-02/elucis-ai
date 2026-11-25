/**
 * Product identity. The single place the product name appears, so a rename is one edit.
 * Internal programme details (team, batch, project code) never belong in the product UI.
 */
export const product = {
  name: "Elucis AI",
  /** What the name stands for. */
  expansion: "Evidence-Led Unified Customer Intelligence System",
  tagline: "Illuminate insights. Engineer better products.",
  description: "Turn customer feedback into evidence-backed product decisions.",
} as const;
