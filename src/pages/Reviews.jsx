import { useState } from "react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { api } from "@/lib/api"
import { FIELDS, FIELD_LABELS, REASON_LABELS } from "@/lib/format"
import { useApi } from "@/lib/useApi"

// ---------- 1. The list of cases that wait for a person ----------
export function ReviewsView({ reviews, error, onOpen }) {
  if (error) {
    return (
      <Alert variant="destructive" className="bg-white">
        <AlertTitle>Cannot load the review queue</AlertTitle>
        <AlertDescription>{error.message}</AlertDescription>
      </Alert>
    )
  }
  if (!reviews) return <Skeleton className="h-72 rounded-2xl" />

  return (
    <div className="space-y-5">
      <div className="text-white">
        <h1 className="text-2xl font-bold">Review queue</h1>
        <p className="text-sm text-white/90">{reviews.length} case(s) the system could not decide alone. A person looks at the documents and answers.</p>
      </div>
      {reviews.length === 0 && (
        <Card className="border-transparent shadow-soft"><CardContent className="py-10 text-center text-muted-foreground">Nothing is waiting. Good job!</CardContent></Card>
      )}
      <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
        {reviews.map((review) => (
          <Card key={review.id} className="border-transparent shadow-soft">
            <CardHeader>
              <CardTitle className="flex items-center justify-between text-base">
                <span>{review.email_id}</span>
                <span className="text-xs font-normal text-muted-foreground">#{review.id}</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Badge variant="secondary">{REASON_LABELS[review.reason] || review.reason}</Badge>
              <div>
                <Button size="sm" onClick={() => onOpen(review.id)}>Open</Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

export default function Reviews({ reviewId, onOpen, onBack, onDraft }) {
  const list = useApi(() => api.reviews("OPEN"), [reviewId])
  if (reviewId) return <ReviewDetail reviewId={reviewId} onBack={onBack} onDraft={onDraft} />
  return <ReviewsView reviews={list.data} error={list.error} onOpen={onOpen} />
}

// ---------- 2. One case: the evidence and the answer form ----------
function EvidenceCard({ title, doc }) {
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
              {doc.error && <Badge variant="outline" className="border-amber-200 bg-amber-50 text-amber-700">{doc.error}</Badge>}
              {doc.noisy && <Badge variant="secondary">read by OCR</Badge>}
            </div>
            <div className="max-h-64 overflow-auto rounded-md border">
              <Table>
                <TableBody>
                  {(doc.pairs || []).map((pair, index) => (
                    <TableRow key={index}>
                      <TableCell className="w-2/5 align-top text-xs font-medium">{pair[0]}</TableCell>
                      <TableCell className="whitespace-normal text-xs text-muted-foreground">{pair[1]}</TableCell>
                    </TableRow>
                  ))}
                  {(doc.pairs || []).length === 0 && (
                    <TableRow><TableCell className="text-xs text-muted-foreground">No values were extracted.</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}

const blank = () => Object.fromEntries(FIELDS.map((field) => [field, ""]))
const keepFilled = (values) => Object.fromEntries(Object.entries(values).filter(([, value]) => value.trim() !== ""))

export function ReviewForm({ review, result, onDone, onDraft }) {
  const [si, setSi] = useState(blank)
  const [bl, setBl] = useState(blank)
  const [verdict, setVerdict] = useState("")
  const [defects, setDefects] = useState([])
  const [name, setName] = useState("")
  const [note, setNote] = useState("")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const evidence = review.evidence || {}
  const toggle = (field) => setDefects((now) => (now.includes(field) ? now.filter((f) => f !== field) : [...now, field]))

  async function submit() {
    setSaving(true)
    setError(null)
    try {
      await api.resolve(review.id, {
        by: name.trim() || "reviewer",
        note,
        verdict: verdict || null,
        defect_fields: verdict === "MISMATCH" ? defects : [],
        si_values: keepFilled(si),
        bl_values: keepFilled(bl),
      })
      onDone()
    } catch (e) {
      setError(e)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="text-white">
        <h1 className="text-2xl font-bold">Review #{review.id}: {review.email_id}</h1>
        <p className="text-sm text-white/90">{result?.subject}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Badge className="bg-white/25 text-white">{REASON_LABELS[review.reason] || review.reason}</Badge>
          {result?.message && <span className="text-sm text-white/90">{result.message}</span>}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <EvidenceCard title="Shipping instruction (SI): the reference" doc={evidence.si} />
        <EvidenceCard title="Draft bill of lading (BL)" doc={evidence.bl} />
      </div>

      {review.state !== "OPEN" ? (
        <Alert className="bg-white"><AlertTitle>This case is already {review.state.toLowerCase()}</AlertTitle></Alert>
      ) : (
        <Card className="border-transparent shadow-soft">
          <CardHeader><CardTitle className="text-base">Your answer</CardTitle></CardHeader>
          <CardContent className="space-y-5">
            <p className="text-sm text-muted-foreground">
              Either type the correct value for the fields you know (an empty box keeps what the system read), or choose a verdict.
            </p>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Field</TableHead>
                  <TableHead>SI value</TableHead>
                  <TableHead>BL value</TableHead>
                  {verdict === "MISMATCH" && <TableHead>Defect?</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {FIELDS.map((field) => (
                  <TableRow key={field}>
                    <TableCell className="text-sm font-medium">{FIELD_LABELS[field]}</TableCell>
                    <TableCell><Input value={si[field]} onChange={(e) => setSi({ ...si, [field]: e.target.value })} /></TableCell>
                    <TableCell><Input value={bl[field]} onChange={(e) => setBl({ ...bl, [field]: e.target.value })} /></TableCell>
                    {verdict === "MISMATCH" && (
                      <TableCell>
                        <input type="checkbox" className="size-4 accent-[#f26b21]" checked={defects.includes(field)} onChange={() => toggle(field)} />
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            <div className="grid gap-4 md:grid-cols-3">
              <label className="space-y-1 text-sm font-medium">
                Verdict (optional)
                <select
                  value={verdict}
                  onChange={(e) => setVerdict(e.target.value)}
                  className="border-input h-9 w-full rounded-md border bg-white px-3 text-sm"
                >
                  <option value="">Use the values I typed</option>
                  <option value="OK">OK: nothing differs</option>
                  <option value="MISMATCH">MISMATCH: something differs</option>
                </select>
              </label>
              <label className="space-y-1 text-sm font-medium">
                Your name
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="reviewer" />
              </label>
              <div className="flex items-end">
                <Button variant="outline" className="border-primary text-primary" onClick={() => onDraft(review.email_id)}>
                  Draft a reply to the sender
                </Button>
              </div>
            </div>
            <label className="block space-y-1 text-sm font-medium">
              Note
              <Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} placeholder="What did you check? (optional)" />
            </label>

            {error && (
              <Alert variant="destructive" className="bg-white">
                <AlertTitle>The answer was not accepted</AlertTitle>
                <AlertDescription>{error.message}</AlertDescription>
              </Alert>
            )}
            <Button onClick={submit} disabled={saving}>{saving ? "SAVING..." : "RESOLVE"}</Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export function ReviewDetail({ reviewId, onBack, onDraft }) {
  const review = useApi(() => api.review(reviewId), [reviewId])
  const emailId = review.data?.email_id
  const result = useApi(() => (emailId ? api.result(emailId) : Promise.resolve(null)), [emailId])

  if (review.error) {
    return (
      <Alert variant="destructive" className="bg-white">
        <AlertTitle>Cannot load this review</AlertTitle>
        <AlertDescription>{review.error.message}</AlertDescription>
      </Alert>
    )
  }
  if (!review.data) return <Skeleton className="h-96 rounded-2xl" />

  return (
    <div className="space-y-4">
      <Button variant="ghost" className="text-white hover:bg-white/20 hover:text-white" onClick={onBack}>&larr; Back to the queue</Button>
      <ReviewForm review={review.data} result={result.data?.result} onDone={onBack} onDraft={onDraft} />
    </div>
  )
}
