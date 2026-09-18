import { Toaster } from "sonner";

import { useTheme } from "@/shared/theme/ThemeProvider";

// Bridges the app theme to Sonner so toasts match light/dark automatically.
function ThemedToaster() {
  const { theme } = useTheme();

  return (
    <Toaster
      theme={theme}
      position="top-right"
      richColors
      closeButton
      expand={false}
      toastOptions={{
        style: {
          borderRadius: "0.875rem",
        },
      }}
    />
  );
}

export default ThemedToaster;
