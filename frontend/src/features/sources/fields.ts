import type { MappingField, SourceType } from "@/lib/api/types";

export const sourceTypes: { value: SourceType; label: string; hint: string }[] = [
  { value: "review", label: "Customer reviews", hint: "App store, G2 or survey reviews" },
  { value: "ticket", label: "Support tickets", hint: "Help desk conversations" },
  { value: "feature_request", label: "Feature requests", hint: "Ideas portals, request forms" },
  { value: "transcript", label: "Meeting transcripts", hint: "Customer calls and interviews" },
  { value: "other", label: "Other feedback", hint: "Anything else customers said" },
  { value: "metrics", label: "Product metrics", hint: "Daily or weekly usage numbers" },
];

/** Standard fields in the order UI-03 shows them. Labels are what a PM recognises. */
export const fieldLabels: Record<MappingField, string> = {
  text: "Feedback text",
  occurred_at: "Date",
  customer_id: "Customer ID",
  rating: "Rating",
  product_version: "Product version",
  source_record_id: "Record ID",
  speaker: "Speaker",
  metric_name: "Metric name",
  metric_value: "Value",
  dimension: "Dimension",
};

export const feedbackFields: MappingField[] = [
  "text",
  "occurred_at",
  "customer_id",
  "rating",
  "product_version",
  "source_record_id",
  "speaker",
];
export const metricFields: MappingField[] = [
  "metric_name",
  "occurred_at",
  "metric_value",
  "dimension",
];

export const fieldsFor = (type: SourceType): MappingField[] =>
  type === "metrics" ? metricFields : feedbackFields;

/** Plain-language names for validation codes returned by the API. */
export const issueLabels: Record<string, string> = {
  text_missing: "Empty feedback text",
  extra_values: "More values than columns",
  not_an_object: "Not a record",
  metric_name_missing: "Missing metric name",
  metric_date_missing: "Missing date",
  metric_date_invalid: "Date not in YYYY-MM-DD format",
  metric_value_missing: "Missing value",
  metric_value_invalid: "Value is not a number",
  duplicate_metric_observation: "Repeated metric, date and dimension",
  occurred_at_missing: "No date",
  occurred_at_unparseable: "Date couldn't be read",
  text_truncated: "Very long text (analysed in part)",
  rating_invalid: "Rating isn't a number",
  duplicate_source_record_id: "Record ID repeated",
};
