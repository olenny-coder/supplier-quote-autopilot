import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

/**
 * Theme ownership for the public form.
 *
 * This is the buyer app's provider (`../../frontend/src/shared/theme/
 * ThemeProvider.jsx`) moved over unchanged, so both apps agree on the storage
 * key, the `.dark` class on <html> and the resolution order. Do not fork it:
 * a second mechanism here would mean the two halves of the product could
 * disagree about what "dark" means.
 *
 * Resolution order, once per load:
 *
 *  1. An explicit choice the supplier made with the header toggle, read from
 *     localStorage. That always wins — a supplier who asked for light on a dark
 *     phone must not be flipped back on their next visit.
 *  2. Otherwise the phone's own setting (`prefers-color-scheme`). A supplier
 *     opening this link from an email should get the page their device is
 *     already set up for, not a white rectangle in a dark room.
 *
 * `index.html` runs the same resolution in an inline script before the first
 * paint; this provider takes over from there — hence the duplicated logic. It is
 * duplicated on purpose: doing it here would be a frame too late and a dark phone
 * would get a white flash on every load.
 */

const STORAGE_KEY = "theme";

const ThemeContext = createContext({
  theme: "light",
  isDark: false,
  toggleTheme: () => {},
  setTheme: () => {},
});

function getInitialTheme() {
  // Server-side render (and the test harness): no stored choice, no media query,
  // so light is the only honest answer until the browser is there to ask.
  if (typeof window === "undefined") return "light";

  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;

  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function applyTheme(theme) {
  const root = document.documentElement;
  root.classList.toggle("dark", theme === "dark");
}

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(getInitialTheme);

  // Keep <html> class and persisted preference in sync with state.
  useEffect(() => {
    applyTheme(theme);
    window.localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  // Follow the OS preference until the user makes an explicit choice.
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");

    const handleChange = (event) => {
      if (window.localStorage.getItem(STORAGE_KEY)) return;
      setThemeState(event.matches ? "dark" : "light");
    };

    media.addEventListener("change", handleChange);
    return () => media.removeEventListener("change", handleChange);
  }, []);

  const setTheme = useCallback((next) => {
    setThemeState((prev) => (next === "dark" || next === "light" ? next : prev));
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => (prev === "dark" ? "light" : "dark"));
  }, []);

  const value = useMemo(
    () => ({
      theme,
      isDark: theme === "dark",
      toggleTheme,
      setTheme,
    }),
    [theme, toggleTheme, setTheme]
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTheme() {
  return useContext(ThemeContext);
}
