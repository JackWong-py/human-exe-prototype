import { useState } from "react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import StatusBadge from "@/components/StatusBadge"
import { api } from "@/lib/api"
import { describe, sortForAttention } from "@/lib/format"
import { useApi } from "@/lib/useApi"

const FILTERS = [
  ["ALL", "All"],
  ["OK", "OK"],
  ["MISMATCH", "Mismatch"],
  ["NEEDS_REVIEW", "Needs review"],
]

export function ChecksView({ checks, error, filter, onFilter, query, onQuery, onReview, onMismatch, onDraft }) {
  if (error) {
    return (
      <Alert variant="destructive" className="bg-white">
        <AlertTitle>Cannot load the checks</AlertTitle>
        <AlertDescription>{error.message}</AlertDescription>
      </Alert>
    )
  }
  if (!checks) return <Skeleton className="h-96 rounded-2xl" />

  const count = (status) => (status === "ALL" ? checks.length : checks.filter((r) => r.status === status).length)
  const text = query.trim().toLowerCase()
  const rows = sortForAttention(checks).filter(
    (r) => (filter === "ALL" || r.status === filter) && (!text || `${r.email_id} ${r.subject || ""}`.toLowerCase().includes(text)),
  )

  return (
    <div className="space-y-5">
      <div className="text-white">
        <h1 className="text-2xl font-bold">Document checks</h1>
        <p className="text-sm text-white/90">Every request to compare a shipping instruction with a draft bill of lading.</p>
      </div>

      <Card className="border-transparent shadow-soft">
        <CardContent className="space-y-4 px-3 sm:px-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Tabs value={filter} onValueChange={onFilter} className="max-w-full overflow-x-auto">
              <TabsList>
                {FILTERS.map(([value, label]) => (
                  <TabsTrigger key={value} value={value}>
                    {label} ({count(value)})
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
            <Input value={query} onChange={(e) => onQuery(e.target.value)} placeholder="Search email number or subject" className="w-full sm:max-w-xs" />
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>What needs attention</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.email_id}>
                  <TableCell>
                    <div className="text-sm font-semibold">{row.email_id}</div>
                    <div className="max-w-56 truncate text-xs text-muted-foreground">{row.subject}</div>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={row.status} />
                    {row.resolved_by_human ? <div className="mt-1 text-[11px] text-muted-foreground">fixed by a person</div> : null}
                  </TableCell>
                  <TableCell className="max-w-md whitespace-normal text-xs text-muted-foreground">{describe(row)}</TableCell>
                  <TableCell className="space-x-2 whitespace-nowrap text-right">
                    {row.status === "MISMATCH" && (
                      <Button size="sm" onClick={() => onMismatch(row.email_id)}>Review</Button>
                    )}
                    {row.status === "NEEDS_REVIEW" && !row.resolved_by_human && (
                      <Button size="sm" onClick={() => onReview(row.email_id)}>Review</Button>
                    )}
                    {row.status !== "OK" && (
                      <Button size="sm" variant="outline" className="border-primary text-primary" onClick={() => onDraft(row.email_id)}>
                        Draft reply
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {rows.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="py-8 text-center text-sm text-muted-foreground">
                    Nothing matches. Try another filter or clear the search.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

export default function Checks({ onReview, onMismatch, onDraft }) {
  const checks = useApi(() => api.results({ category: "BL_COMPARISON" }))
  const [filter, setFilter] = useState("ALL")
  const [query, setQuery] = useState("")

  return (
    <ChecksView
      checks={checks.data}
      error={checks.error}
      filter={filter}
      onFilter={setFilter}
      query={query}
      onQuery={setQuery}
      onReview={onReview}
      onMismatch={onMismatch}
      onDraft={onDraft}
    />
  )
}
