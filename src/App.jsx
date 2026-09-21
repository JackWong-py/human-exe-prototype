import { useState } from "react"
import AppShell from "@/components/AppShell"
import { api } from "@/lib/api"
import Checks from "@/pages/Checks"
import Dashboard from "@/pages/Dashboard"
import Draft from "@/pages/Draft"
import Emails from "@/pages/Emails"
import MismatchReview from "@/pages/MismatchReview"
import Reviews from "@/pages/Reviews"

// The whole app. It remembers which page is open (`page`) and passes small "go there" functions to the pages.
export default function App() {
  const [page, setPage] = useState("dashboard")
  const [reviewId, setReviewId] = useState(null)
  const [draftEmail, setDraftEmail] = useState("")
  const [mismatchEmail, setMismatchEmail] = useState("")
  const [emailsCategory, setEmailsCategory] = useState("ALL")
  const [problem, setProblem] = useState(null)

  function navigate(next) {
    setPage(next)
    setProblem(null)
    if (next === "emails") setEmailsCategory("ALL")
    if (next !== "reviews") setReviewId(null)
  }

  // From a category bar on the dashboard: open the Emails page for that category.
  function openCategory(category) {
    setEmailsCategory(category)
    setPage("emails")
  }

  // From a table: find the open review of that email, then show it.
  async function openReviewFor(emailId) {
    try {
      const open = await api.reviews("OPEN")
      const found = open.find((review) => review.email_id === emailId)
      setReviewId(found ? found.id : null)
      setPage("reviews")
    } catch (error) {
      setProblem(error.message)
    }
  }

  function openMismatch(emailId) {
    setMismatchEmail(emailId)
    setPage("mismatch")
  }

  function openDraft(emailId) {
    setDraftEmail(emailId)
    setPage("draft")
  }

  // From the Emails page: a mismatch opens its comparison, a case that needs a person opens the review queue.
  function openCheck(row) {
    if (row.status === "MISMATCH") openMismatch(row.email_id)
    else if (row.status === "NEEDS_REVIEW") openReviewFor(row.email_id)
  }

  return (
    <AppShell page={page === "mismatch" ? "checks" : page} onNavigate={navigate}>
      {problem && <div className="mb-4 rounded-md bg-white p-3 text-sm text-red-700">{problem}</div>}
      {page === "dashboard" && <Dashboard onNavigate={navigate} onOpenCategory={openCategory} />}
      {page === "emails" && <Emails key={emailsCategory} initialCategory={emailsCategory} onOpenCheck={openCheck} />}
      {page === "checks" && <Checks onReview={openReviewFor} onMismatch={openMismatch} onDraft={openDraft} />}
      {page === "mismatch" && (
        <MismatchReview key={mismatchEmail} emailId={mismatchEmail} onBack={() => setPage("checks")} onDraft={openDraft} />
      )}
      {page === "reviews" && (
        <Reviews reviewId={reviewId} onOpen={setReviewId} onBack={() => setReviewId(null)} onDraft={openDraft} />
      )}
      {page === "draft" && <Draft key={draftEmail} emailId={draftEmail} />}
    </AppShell>
  )
}
