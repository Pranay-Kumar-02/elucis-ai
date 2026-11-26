import type { Role } from "@/lib/api/types";

export const roleLabels: Record<Role, string> = {
  owner: "Owner",
  editor: "Editor",
  viewer: "Viewer",
};

export const roleDescriptions: Record<Role, string> = {
  owner: "Manages members, settings, integrations and deletion",
  editor: "Imports, analyses, prioritises and writes documents",
  viewer: "Reads everything and asks the assistant",
};

export const ROLES: Role[] = ["viewer", "editor", "owner"];
