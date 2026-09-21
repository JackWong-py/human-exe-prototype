import { useState } from "react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import CategoryBadge from "@/components/CategoryBadge"
import StatusBadge from "@/components/StatusBadge"
import { api } from "@/lib/api"
import { CATEGORY_LABELS, CATEGORY_ORDER, RULE_LABELS } from "@/lib/format"
import { useApi } from "@/lib/useApi"

const PAGE = 50

// Every email and the category the system sorted it into, with the rule that decided.
export function EmailsView({ results, error, category, onCategory, query, onQuery, limit, onMore, onOpenCheck }) {
  if (error) {
    return (
      <Alert variant="destructive" className="bg-white">
        <AlertTitle>Cannot load the emails</AlertTitle>
        <AlertDescription>{error.message}</AlertDescription>
      </Alert>
    )
  }
  if (!results) return <Skeleton className="h-96 rounded-2xl" />

  const count = (value) => (value === "ALL" ? results.length : results.filter((r) => r.category === value).length)
  const text = query.trim().toLowerCase()
  const rows = results
    .filter((r) => (category === "ALL" || r.category === category) && (!text || `${r.email_id} ${r.subject || ""} ${r.sender || ""}`.toLowerCase().includes(text)))
    .sort((a, b) => a.email_id.localeCompare(b.email_id))
  const shown = rows.slice(0, limit)

  return (
    <div className="space-y-5">
      <div className="text-white">
        <h1 className="text-2xl font-bold">Email classification</h1>
        <p className="text-sm text-white/90">Every email, the category it was sorted into, and the rule that decided.</p>
      </div>

      <Card className="border-transparent shadow-soft">
        <CardContent className="space-y-4 px-3 sm:px-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Tabs value={category} onValueChange={onCategory} className="max-w-full overflow-x-auto">
              <TabsList>
                <TabsTrigger value="ALL">All ({count("ALL")})</TabsTrigger>
                {CATEGORY_ORDER.map((value) => (
                  <TabsTrigger key={value} value={value}>
                    {CATEGORY_LABELS[value]} ({count(value)})
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
            <Input value={query} onChange={(e) => onQuery(e.target.value)} placeholder="Search number, subject or sender" className="w-full sm:max-w-xs" />
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Category</TableHead>
                <TableHead className="hidden md:table-cell">Decided by</TableHead>
                <TableHead>Result</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {shown.map((row) => (
                <TableRow key={row.email_id}>
                  <TableCell>
                    <div className="text-sm font-semibold">{row.email_id}</div>
                    <div className="max-w-56 truncate text-xs text-muted-foreground">{row.subject}</div>
                  </TableCell>
                  <TableCell><CategoryBadge category={row.category} /></TableCell>
                  <TableCell className="hidden text-xs text-muted-foreground md:table-cell">
                    {RULE_LABELS[row.rule] || row.rule}
                    <div className="font-mono text-[11px]">{row.rule} &middot; {row.confidence} confidence</div>
                  </TableCell>
                  <TableCell className="whitespace-nowrap">
                    {row.category === "BL_COMPARISON" && row.status ? (
                      <div className="flex items-center gap-2">
                        <StatusBadge status={row.status} />
                        {row.status !== "OK" && (
                          <Button size="sm" variant="outline" className="border-primary text-primary" onClick={() => onOpenCheck(row)}>
                            Open
                          </Button>
                        )}
                      </div>
                    ) : (
                      <Badge variant="secondary">no check needed</Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {shown.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="py-8 text-center text-sm text-muted-foreground">
                    Nothing matches. Try another category or clear the search.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>

          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Showing {shown.length} of {rows.length}</span>
            {rows.length > shown.length && (
              <Button size="sm" variant="outline" onClick={onMore}>Show {Math.min(PAGE, rows.length - shown.length)} more</Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default function Emails({ initialCategory = "ALL", onOpenCheck }) {
  const results = useApi(() => api.results())
  const [category, setCategory] = useState(initialCategory)
  const [query, setQuery] = useState("")
  const [limit, setLimit] = useState(PAGE)

  return (
    <EmailsView
      results={results.data}
      error={results.error}
      category={category}
      onCategory={(value) => {
        setCategory(value)
        setLimit(PAGE)
      }}
      query={query}
      onQuery={(value) => {
        setQuery(value)
        setLimit(PAGE)
      }}
      limit={limit}
      onMore={() => setLimit((now) => now + PAGE)}
      onOpenCheck={onOpenCheck}
    />
  )
}
