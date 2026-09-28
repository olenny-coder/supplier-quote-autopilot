import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "@/App";
import { ThemeProvider } from "@/theme/ThemeProvider";
import "@/index.css";

const container = document.getElementById("root");

if (!container) {
  throw new Error("The #root container is missing from index.html.");
}

createRoot(container).render(
  <StrictMode>
    {/* ThemeProvider is outermost, exactly as in the buyer app, so everything
        below it — including the error pages that render without an invitation —
        is inside the theme context. */}
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </StrictMode>
);
