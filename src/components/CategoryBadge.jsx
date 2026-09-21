import { Badge } from "@/components/ui/badge"
import { CATEGORY_LABELS, CATEGORY_STYLES } from "@/lib/format"

// A small coloured label for the category an email was sorted into.
export default function CategoryBadge({ category }) {
  return (
    <Badge variant="outline" className={CATEGORY_STYLES[category] || ""}>
      {CATEGORY_LABELS[category] || category || "n/a"}
    </Badge>
  )
}
