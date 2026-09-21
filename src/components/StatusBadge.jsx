import { Badge } from "@/components/ui/badge"

const STYLES = {
  OK: "border-emerald-200 bg-emerald-50 text-emerald-700",
  MISMATCH: "border-red-200 bg-red-50 text-red-700",
  NEEDS_REVIEW: "border-amber-200 bg-amber-50 text-amber-700",
}
const LABELS = { OK: "OK", MISMATCH: "Mismatch", NEEDS_REVIEW: "Needs review" }

// A small coloured label for a result: green OK, red Mismatch, amber Needs review.
export default function StatusBadge({ status }) {
  return (
    <Badge variant="outline" className={STYLES[status] || ""}>
      {LABELS[status] || status || "n/a"}
    </Badge>
  )
}
