import { useState } from "react";

import AppShell from "./components/AppShell";
import Checks from "./pages/Checks";
import Dashboard from "./pages/Dashboard";
import Draft from "./pages/Draft";
import Reviews from "./pages/Reviews";

// Which page is showing, plus the little bit of state the pages hand to each other
// (which review is open, which email a draft reply is for). No router library needed.
function App() {
  const [page, setPage] = useState("dashboard");
  const [reviewId, setReviewId] = useState(null);
  const [draftEmailId, setDraftEmailId] = useState("");

  function navigate(next) {
    setPage(next);
    if (next !== "reviews") setReviewId(null);
  }

  function openDraft(emailId) {
    setDraftEmailId(emailId || "");
    setPage("draft");
  }

  function openReviews(emailId) {
    // Checks gives us an email id, not a review id, so open the queue and let the
    // reviewer pick. Clearing reviewId makes Reviews show its list.
    setReviewId(null);
    setDraftEmailId(emailId || draftEmailId);
    setPage("reviews");
  }

  return (
    <AppShell page={page} onNavigate={navigate}>
      {page === "dashboard" && <Dashboard onNavigate={navigate} />}
      {page === "checks" && <Checks onReview={openReviews} onDraft={openDraft} />}
      {page === "reviews" && (
        <Reviews
          reviewId={reviewId}
          onOpen={setReviewId}
          onBack={() => setReviewId(null)}
          onDraft={openDraft}
        />
      )}
      {page === "draft" && <Draft emailId={draftEmailId} />}
    </AppShell>
  );
}

export default App;
