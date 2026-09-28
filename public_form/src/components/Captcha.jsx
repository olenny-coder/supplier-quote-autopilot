import { useEffect, useRef, useState } from "react";
import { isCaptchaEnabled, renderCaptchaWidget } from "@/lib/captcha";
import { useTheme } from "@/theme/ThemeProvider";

/**
 * Renders the buyer's chosen CAPTCHA widget, if any.
 *
 * The widget is a progressive enhancement: with `provider: "none"` (or a
 * provider without a site key) this component renders nothing at all and the
 * form behaves identically — a supplier must never be locked out of submitting a
 * price because a third-party script is blocked on their network.
 *
 * The widget is a third-party iframe that paints its own background, so it is
 * drawn in the app's resolved theme: a light widget on a dark form is a white box
 * in the middle of the page. The theme is already resolved before React mounts
 * (see index.html), so the first draw is always right.
 *
 * `resetKey` forces a fresh widget, which matters because provider tokens are
 * single-use: after a failed submit the old token is dead and reusing the widget
 * would fail forever.
 */
export default function Captcha({ captcha, onToken, onError, resetKey = 0 }) {
  const { isDark } = useTheme();
  const containerRef = useRef(null);
  const handlersRef = useRef({ onToken, onError });
  const [failed, setFailed] = useState(null);

  const theme = isDark ? "dark" : "light";
  // The token belongs to the widget instance that produced it, so a theme change
  // may only re-draw the widget while it is still unsolved. Throwing away a
  // challenge the supplier has already passed would make them prove they are
  // human a second time, which is exactly the kind of thing that loses a quote.
  const themeRef = useRef(theme);
  const solvedRef = useRef(false);
  const [themeKey, setThemeKey] = useState(0);

  useEffect(() => {
    if (themeRef.current === theme) return;
    themeRef.current = theme;
    if (!solvedRef.current) setThemeKey((previous) => previous + 1);
  }, [theme]);

  // Keep the latest callbacks in a ref so the render effect depends only on the
  // provider/site key. Depending on the callbacks directly would tear down and
  // re-render the widget on every parent render, which providers rate-limit.
  useEffect(() => {
    handlersRef.current = { onToken, onError };
  });

  const enabled = isCaptchaEnabled(captcha);
  const provider = enabled ? captcha.provider : null;
  const siteKey = enabled ? captcha.site_key : null;

  useEffect(() => {
    if (!provider || !siteKey) return undefined;

    let cancelled = false;
    let handle = null;
    solvedRef.current = false;
    setFailed(null);

    renderCaptchaWidget(provider, containerRef.current, {
      siteKey,
      theme: themeRef.current,
      onToken: (token) => {
        solvedRef.current = true;
        handlersRef.current.onToken?.(token);
      },
      onError: (message) => {
        setFailed(message);
        handlersRef.current.onError?.(message);
      },
    })
      .then((created) => {
        if (cancelled) {
          created.remove();
          return;
        }
        handle = created;
      })
      .catch((error) => {
        if (cancelled) return;
        const message =
          error?.message || "The spam check could not be loaded.";
        setFailed(message);
        handlersRef.current.onError?.(message);
      });

    return () => {
      cancelled = true;
      handle?.remove();
    };
  }, [provider, siteKey, resetKey, themeKey]);

  if (!enabled) return null;

  return (
    <div className="space-y-1.5">
      {/* The provider injects its iframe here. Minimum height reserves the space
          so the sticky submit bar does not jump when the widget appears. */}
      <div ref={containerRef} className="min-h-[78px]" />
      {failed ? (
        <p className="text-sm font-medium text-danger-soft-fg">
          {failed} You can still send your quote — the buyer reviews every
          submission by hand.
        </p>
      ) : null}
      <noscript>
        <p className="text-sm text-muted">
          Please enable JavaScript to complete the spam check, or reply to the
          buyer&rsquo;s email with your price.
        </p>
      </noscript>
    </div>
  );
}
