// Words and small helpers shared by all pages.

export const FIELD_LABELS = {
  shipper: "Shipper",
  consignee: "Consignee",
  notify_party: "Notify party",
  port_of_loading: "Port of loading",
  port_of_discharge: "Port of discharge",
  container_count: "Container count",
  gross_weight_kg: "Gross weight (kg)",
}

// Short names for the chart's bottom axis
export const SHORT_LABELS = {
  shipper: "Shipper",
  consignee: "Consignee",
  notify_party: "Notify",
  port_of_loading: "Load port",
  port_of_discharge: "Disch. port",
  container_count: "Containers",
  gross_weight_kg: "Weight",
}

export const FIELDS = Object.keys(FIELD_LABELS)

export const REASON_LABELS = {
  wrong_doc_type: "Wrong document type",
  missing_attachment: "Missing attachment",
  unreadable: "Unreadable file",
  missing_value: "Missing value",
}

const ORDER = { NEEDS_REVIEW: 0, MISMATCH: 1, OK: 2 }

// Needs review first, then mismatches, then OK. Same status: by email number.
export function sortForAttention(rows) {
  return [...rows].sort((a, b) => (ORDER[a.status] ?? 3) - (ORDER[b.status] ?? 3) || a.email_id.localeCompare(b.email_id))
}

// One line that says what needs attention for a result
export function describe(result) {
  if (result.status === "OK") return "No mismatch detected"
  if (result.status === "MISMATCH") {
    const parts = (result.diffs || []).map((d) => `${FIELD_LABELS[d.field] || d.field}: SI ${d.si} / BL ${d.bl}`)
    return parts.join("; ") || (result.defect_fields || []).join(", ")
  }
  const reason = REASON_LABELS[result.review_reason] || result.review_reason || "Needs review"
  return result.message ? `${reason}. ${result.message}` : reason
}

// The seven fields the system can count, for the chart
export function defectsByField(rows) {
  return FIELDS.map((field) => ({
    field,
    name: SHORT_LABELS[field],
    count: rows.filter((r) => r.status === "MISMATCH" && (r.defect_fields || []).includes(field)).length,
  }))
}
