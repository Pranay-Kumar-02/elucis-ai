import { useMutation, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/endpoints";

export function useSourceAdapters() {
  return useQuery({
    queryKey: ["sources", "adapters"],
    queryFn: ({ signal }) => api.sourceAdapters(signal),
    staleTime: Infinity,
  });
}

export function useFilePreview() {
  return useMutation({ mutationFn: (file: File) => api.previewFile(file) });
}
