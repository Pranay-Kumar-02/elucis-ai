/**
 * Product identity. The single place the product name appears, so a rename is one edit.
 * Internal programme details (team, batch, project code) never belong in the product UI.
 */
export const product = {
  name: "Leonis AI",
  /** What the name stands for. */
  expansion: "Learning from Evidence, Opinions & Needs to Inform Strategy",
  description: "Turn customer feedback into evidence-backed product decisions.",
} as const;
