import { BrowserRouter, Route, Routes } from "react-router-dom";
import ErrorPage from "@/pages/ErrorPage";
import QuoteFormPage from "@/pages/QuoteFormPage";

/**
 * The public form has exactly one real route.
 *
 * `/quote/:rfqId/:token` is the whole application: `rfq_id` and the token are
 * read from the path and the token *is* the credential, so there is no login,
 * no session and nothing to persist in the browser. Every other path — an email
 * client that truncated the link, a typo, a stale bookmark, a crawler — must
 * land on the "not valid" page rather than a blank screen or a 404 from the
 * static host.
 */
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/quote/:rfqId/:token" element={<QuoteFormPage />} />
        <Route
          path="*"
          element={
            <ErrorPage
              tone="warning"
              title="This link is not valid"
              message="A quote link looks like https://quote.example.com/quote/1234/abc123. Please open the original email and tap the button again, or ask the buyer to resend your invitation."
            />
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
