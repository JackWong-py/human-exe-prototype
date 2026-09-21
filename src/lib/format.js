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

// ---------- email classification ----------
export const CATEGORY_ORDER = ["BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM"]

export const CATEGORY_LABELS = {
  BL_COMPARISON: "BL comparison",
  SI_REQUEST: "SI request",
  INVOICE_QUERY: "Invoice query",
  GENERAL: "General",
  SPAM: "Spam",
}

// One short line per category, shown under the bars on the dashboard
export const CATEGORY_HINTS = {
  BL_COMPARISON: "check a draft BL against the shipping instruction",
  SI_REQUEST: "about a shipping instruction (SI)",
  INVOICE_QUERY: "questions about an invoice",
  GENERAL: "other business messages",
  SPAM: "unwanted or irrelevant",
}

export const CATEGORY_STYLES = {
  BL_COMPARISON: "border-orange-200 bg-orange-50 text-orange-700",
  SI_REQUEST: "border-amber-200 bg-amber-50 text-amber-700",
  INVOICE_QUERY: "border-sky-200 bg-sky-50 text-sky-700",
  GENERAL: "border-slate-200 bg-slate-50 text-slate-600",
  SPAM: "border-rose-200 bg-rose-50 text-rose-700",
}

// Bar colours on the dashboard
export const CATEGORY_BAR = {
  BL_COMPARISON: "#f26b21",
  SI_REQUEST: "#f9b233",
  INVOICE_QUERY: "#38bdf8",
  GENERAL: "#94a3b8",
  SPAM: "#fb7185",
}

// Which rule of the classifier decided (the raw rule name is shown next to it)
export const RULE_LABELS = {
  bl_compare: "asks to compare documents",
  gen_chase_draft_bl: "asks us to send a draft BL",
  general: "no other rule matched",
  invoice: "mentions an invoice",
  si_chase: "reminds to submit the SI",
  si_find: "asks about a shipping instruction",
  spam_body: "spam wording in the text",
  spam_domain: "spam sender address",
}
