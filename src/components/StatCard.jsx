import { Bookmark } from "lucide-react"
import { Card } from "@/components/ui/card"

// One of the three number cards: a round icon, a big number and a small explanation.
// `highlight` gives the orange frame and the little bookmark (the middle card in the design).
export default function StatCard({ icon: Icon, value, label, hint, highlight = false, onClick }) {
  return (
    <Card
      onClick={onClick}
      className={
        "relative flex-row items-center gap-5 px-6 py-6 shadow-soft " +
        (highlight ? "border-2 border-primary " : "border-transparent ") +
        (onClick ? "cursor-pointer transition hover:-translate-y-0.5" : "")
      }
    >
      {highlight && <Bookmark className="absolute -top-1 right-5 size-7 fill-primary text-primary" />}
      <div className="grid size-16 shrink-0 place-items-center rounded-full border-2 border-primary/50 bg-secondary text-primary">
        <Icon className="size-7" />
      </div>
      <div className="h-12 w-px bg-border" />
      <div>
        <div className="text-3xl font-bold text-foreground">{value}</div>
        <div className="text-sm font-medium text-foreground">{label}</div>
        {hint && <div className="mt-0.5 text-xs text-muted-foreground">{hint}</div>}
      </div>
    </Card>
  )
}
