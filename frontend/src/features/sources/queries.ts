import { useMutation, useQuery } from "@tanstack/react-query";

import { api, type SourceInput } from "@/lib/api/endpoints";
import type { ColumnMapping, SourceType } from "@/lib/api/types";

export function useSourceAdapters() {
  return useQuery({
    queryKey: ["sources", "adapters"],
    queryFn: ({ signal }) => api.sourceAdapters(signal),
    staleTime: Infinity,
  });
}

export function useSourcePreview() {
  return useMutation({
    mutationFn: ({ input, sourceType }: { input: SourceInput; sourceType: SourceType }) =>
      api.previewSource(input, sourceType),
  });
}

export function useSourceValidation() {
  return useMutation({
    mutationFn: ({
      input,
      sourceType,
      mapping,
    }: {
      input: SourceInput;
      sourceType: SourceType;
      mapping: ColumnMapping;
    }) => api.validateSource(input, sourceType, mapping),
  });
}
