import { useState } from "react"
import { Check, Flag, Play, Users } from "lucide-react"
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import StatCard from "@/components/StatCard"
import StatusBadge from "@/components/StatusBadge"
import { api } from "@/lib/api"
import { defectsByField, describe, sortForAttention } from "@/lib/format"
import { useApi } from "@/lib/useApi"

// The screen itself. It only DRAWS what it is given, which makes it easy to read and to test.
export function DashboardView({ summary, checks, error, running, message, onRun, onRefresh, onNavigate }) {
  if (error) {
    return (
      <Alert variant="destructive" className="bg-white">
        <AlertTitle>Cannot reach the backend</AlertTitle>
        <AlertDescription>{error.message}. Is the Python server running? Start it with: uvicorn app.api:app --port 8000</AlertDescription>
      </Alert>
    )
  }
  if (!summary || !checks) {
    return (
      <div className="grid gap-6 lg:grid-cols-[1.35fr_1fr]">
        <Skeleton className="h-72 rounded-2xl" />
        <Skeleton className="h-72 rounded-2xl" />
      </div>
    )
  }

  const status = summary.by_status || {}
  const ok = status.OK || 0
  const defects = status.MISMATCH || 0
  const review = status.NEEDS_REVIEW || 0
  const latest = sortForAttention(checks).slice(0, 6)

  return (
    <div className="space-y-8">
      <div className="grid gap-6 lg:grid-cols-[1.35fr_1fr]">
        {/* Big number + chart (the "TURNOVER" card in the design) */}
        <Card className="border-transparent shadow-soft">
          <CardContent className="px-7">
            <div className="flex items-start justify-between">
              <div className="text-xs font-semibold tracking-widest text-muted-foreground">DOCUMENT CHECKS</div>
              <button onClick={() => onNavigate("checks")} className="text-xs text-muted-foreground hover:text-primary">
                See all &rsaquo;
              </button>
            </div>
            <div className="mt-2 text-5xl font-bold text-primary">{ok + defects + review}</div>
            <div className="text-xs text-muted-foreground">Shipping instructions compared with draft bills of lading</div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge variant="secondary">{summary.total} emails read</Badge>
              <Badge variant="secondary">{summary.human_resolved || 0} fixed by a person</Badge>
            </div>
            <div className="mt-4 text-xs font-medium text-muted-foreground">Defects found, by field</div>
            <div className="h-36">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={defectsByField(checks)} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="defectFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#f26b21" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#f26b21" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid vertical={false} stroke="#eceff0" strokeDasharray="3 3" />
                  <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#8a919a" }} axisLine={false} tickLine={false} />
                  <YAxis hide allowDecimals={false} />
                  <Tooltip />
                  <Area type="monotone" dataKey="count" name="Defects" stroke="#f26b21" strokeWidth={2.5} fill="url(#defectFill)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-2 flex gap-2">
              <Button size="sm" onClick={onRefresh}>REFRESH</Button>
              <Button size="sm" variant="outline" className="border-primary text-primary" onClick={() => onNavigate("checks")}>
                SEE ALL
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Latest results (the table card in the design) */}
        <Card className="border-transparent shadow-soft">
          <CardContent className="px-2">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>What needs attention</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {latest.map((row, index) => (
                  <TableRow key={row.email_id} className={index === 0 ? "border-l-4 border-l-primary bg-white shadow-md" : ""}>
                    <TableCell className="text-xs font-semibold">{row.email_id}</TableCell>
                    <TableCell><StatusBadge status={row.status} /></TableCell>
                    <TableCell className="max-w-44 truncate text-xs text-muted-foreground">{describe(row)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      {/* Three number cards */}
      <div className="grid gap-6 md:grid-cols-3">
        <StatCard icon={Check} value={ok} label="Checked and matching" hint="No difference in the 7 fields" />
        <StatCard icon={Flag} value={defects} label="Defects found" hint="At least one field differs" highlight onClick={() => onNavigate("checks")} />
        <StatCard icon={Users} value={review} label="Need a person" hint="We could not decide alone" onClick={() => onNavigate("reviews")} />
      </div>

      {/* Bottom banner (the "Create your CRM profile" banner in the design) */}
      <div className="bg-brand-gradient flex flex-wrap items-center gap-5 rounded-2xl px-8 py-7 text-white shadow-soft">
        <div className="grid size-16 shrink-0 place-items-center rounded-full bg-white text-primary">
          <Play className="size-7" />
        </div>
        <div className="min-w-60 flex-1">
          <div className="text-lg font-semibold">Process the inbox again</div>
          <div className="text-sm text-white/90">
            Reads all {summary.total} emails, sorts them and compares the documents. Results a person has already fixed are kept.
          </div>
          {message && <div className="mt-2 text-sm font-medium">{message.text}</div>}
        </div>
        <Button onClick={onRun} disabled={running} className="bg-white/30 text-white hover:bg-white/40">
          {running ? "WORKING..." : "RUN NOW"}
        </Button>
      </div>
    </div>
  )
}

// The page: it fetches the data, then hands it to the screen above.
export default function Dashboard({ onNavigate }) {
  const summary = useApi(() => api.summary())
  const checks = useApi(() => api.results({ category: "BL_COMPARISON" }))
  const [running, setRunning] = useState(false)
  const [message, setMessage] = useState(null)

  async function run() {
    setRunning(true)
    setMessage(null)
    try {
      await api.run()
      setMessage({ text: "Done. All emails were processed again." })
      summary.reload()
      checks.reload()
    } catch (error) {
      setMessage({ text: `Something went wrong: ${error.message}` })
    } finally {
      setRunning(false)
    }
  }

  return (
    <DashboardView
      summary={summary.data}
      checks={checks.data}
      error={summary.error || checks.error}
      running={running}
      message={message}
      onRun={run}
      onRefresh={() => {
        summary.reload()
        checks.reload()
      }}
      onNavigate={onNavigate}
    />
  )
}
