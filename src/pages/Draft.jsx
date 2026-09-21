import { useState } from "react"
import { Copy, Sparkles } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { api } from "@/lib/api"

const DISCLAIMER = "AI-assisted draft. Read it, edit it and send it yourself. Nothing is sent automatically."

// The screen. `note` explains where the text came from (AI or the safe template).
export function DraftView({ emailId, onEmailId, to, subject, onSubject, body, onBody, note, loading, error, notice, onMake, onCopy }) {
  return (
    <div className="space-y-5">
      <div className="text-white">
        <h1 className="text-2xl font-bold">Draft reply</h1>
        <p className="text-sm text-white/90">A ready-to-edit message to the sender, built from the facts the system found.</p>
      </div>

      <Alert className="bg-white">
        <Sparkles className="size-4" />
        <AlertTitle>{DISCLAIMER}</AlertTitle>
        <AlertDescription>The facts (file names, field names, values) always come from the checks. The AI may only reword them.</AlertDescription>
      </Alert>

      <Card className="border-transparent shadow-soft">
        <CardContent className="space-y-4 px-6">
          <div className="flex flex-wrap items-end gap-3">
            <label className="space-y-1 text-sm font-medium">
              Email number
              <Input value={emailId} onChange={(e) => onEmailId(e.target.value)} placeholder="email_507" className="w-48" />
            </label>
            <Button disabled={loading || !emailId.trim()} onClick={() => onMake(true)}>DRAFT WITH AI</Button>
            <Button variant="outline" className="border-primary text-primary" disabled={loading || !emailId.trim()} onClick={() => onMake(false)}>
              TEMPLATE ONLY
            </Button>
          </div>

          {error && (
            <Alert variant="destructive" className="bg-white">
              <AlertTitle>No draft</AlertTitle>
              <AlertDescription>{error.message}</AlertDescription>
            </Alert>
          )}
          {note && <p className="text-sm text-muted-foreground">{note}</p>}

          <label className="block space-y-1 text-sm font-medium">
            To
            <Input value={to} readOnly />
          </label>
          <label className="block space-y-1 text-sm font-medium">
            Subject
            <Input value={subject} onChange={(e) => onSubject(e.target.value)} />
          </label>
          <label className="block space-y-1 text-sm font-medium">
            Message (you can edit it)
            <Textarea value={body} onChange={(e) => onBody(e.target.value)} rows={14} />
          </label>
          <div className="flex items-center gap-3">
            <Button variant="outline" className="border-primary text-primary" disabled={!body} onClick={onCopy}>
              <Copy className="size-4" /> COPY
            </Button>
            {notice && <span className="text-sm text-muted-foreground">{notice}</span>}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default function Draft({ emailId: startId = "" }) {
  const [emailId, setEmailId] = useState(startId)
  const [to, setTo] = useState("")
  const [subject, setSubject] = useState("")
  const [body, setBody] = useState("")
  const [note, setNote] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState("")

  async function make(useAi) {
    setLoading(true)
    setError(null)
    setNotice("")
    try {
      const draft = await api.draft(emailId.trim(), useAi)
      if (!draft.needed) {
        setError(new Error(draft.message || "No reply is needed for this email."))
        return
      }
      setTo(draft.to)
      setSubject(draft.subject)
      setBody(draft.body)
      setNote(`Source: ${draft.source}. ${draft.note}`)
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }

  async function copy() {
    await navigator.clipboard.writeText(`To: ${to}\nSubject: ${subject}\n\n${body}`)
    setNotice("Copied. Paste it into your email program.")
  }

  return (
    <DraftView
      emailId={emailId}
      onEmailId={setEmailId}
      to={to}
      subject={subject}
      onSubject={setSubject}
      body={body}
      onBody={setBody}
      note={note}
      loading={loading}
      error={error}
      notice={notice}
      onMake={make}
      onCopy={copy}
    />
  )
}
