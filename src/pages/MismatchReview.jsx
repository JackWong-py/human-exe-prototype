import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import StatusBadge from "@/components/StatusBadge"
import { api } from "@/lib/api"
import { FIELDS, FIELD_LABELS } from "@/lib/format"
import { useApi } from "@/lib/useApi"

// The values the system read from one document, exactly as found (label and value).
function DocCard({ title, doc }) {
  return (
    <Card className="border-transparent shadow-soft">
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {!doc ? (
          <div className="text-sm text-muted-foreground">Not provided</div>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span className="break-all">{doc.path}</span>
              <Badge variant="secondary">{doc.doc_type}</Badge>
              {doc.noisy && <Badge variant="secondary">read by OCR</Badge>}
            </div>
            <div className="max-h-72 overflow-auto rounded-md border">
              <Table>
                <TableBody>
                  {(doc.pairs || []).map((pair, index) => (
                    <TableRow key={index}>
                      <TableCell className="w-2/5 align-top text-xs font-medium">{pair[0]}</TableCell>
                      <TableCell className="whitespace-normal break-words text-xs text-muted-foreground">{pair[1]}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}

// A place to look at one MISMATCH: what differs, what matched, and the two documents side by side.
export function MismatchView({ result, error, onBack, onDraft }) {
  if (error) {
    return (
      <Alert variant="destructive" className="bg-white">
        <AlertTitle>Cannot load this case</AlertTitle>
        <AlertDescription>{error.message}</AlertDescription>
      </Alert>
    )
  }
  if (!result) return <Skeleton className="h-96 rounded-2xl" />

  const diffs = result.diffs || []
  const flagged = result.defect_fields || []
  const matched = FIELDS.filter((field) => !flagged.includes(field))
  const evidence = result.evidence || {}

  return (
    <div className="space-y-6">
      <Button variant="ghost" className="text-white hover:bg-white/20 hover:text-white" onClick={onBack}>
        &larr; Back to document checks
      </Button>

      <div className="text-white">
        <h1 className="text-2xl font-bold">Mismatch: {result.email_id}</h1>
        <p className="text-sm text-white/90">{result.subject}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <StatusBadge status={result.status} />
          <span className="text-sm text-white/90">
            {diffs.length} field{diffs.length === 1 ? "" : "s"} differ
          </span>
        </div>
      </div>

      <Card className="border-transparent shadow-soft">
        <CardHeader>
          <CardTitle className="text-base">What differs</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Field</TableHead>
                <TableHead>Shipping instruction (SI)</TableHead>
                <TableHead>Draft bill of lading (BL)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {diffs.map((diff) => (
                <TableRow key={diff.field} className="bg-red-50/60">
                  <TableCell className="text-sm font-semibold">{FIELD_LABELS[diff.field] || diff.field}</TableCell>
                  <TableCell className="whitespace-normal break-words text-sm">{diff.si}</TableCell>
                  <TableCell className="whitespace-normal break-words text-sm font-semibold text-red-700">{diff.bl}</TableCell>
                </TableRow>
              ))}
              {diffs.length === 0 && (
                <TableRow>
                  <TableCell colSpan={3} className="py-6 text-center text-sm text-muted-foreground">No differing fields were recorded.</TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-muted-foreground">Matched:</span>
            {matched.map((field) => (
              <Badge key={field} variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-700">
                {FIELD_LABELS[field]}
              </Badge>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            The system ignores capital letters, commas in numbers and port codes when it compares. A field is listed as different only if the values still
            differ after that. The two documents below show everything that was read, so you can check it yourself.
          </p>
          <div>
            <Button variant="outline" className="border-primary text-primary" onClick={() => onDraft(result.email_id)}>
              Draft a reply to the sender
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2 [&>*]:min-w-0">
        <DocCard title="Shipping instruction (SI): the reference" doc={evidence.si} />
        <DocCard title="Draft bill of lading (BL)" doc={evidence.bl} />
      </div>
    </div>
  )
}

export default function MismatchReview({ emailId, onBack, onDraft }) {
  const detail = useApi(() => api.result(emailId), [emailId])
  return <MismatchView result={detail.data?.result} error={detail.error} onBack={onBack} onDraft={onDraft} />
}
