import { useEffect, useRef, useState } from "react";
import { isCaptchaEnabled, renderCaptchaWidget } from "@/lib/captcha";

/**
 * Renders the buyer's chosen CAPTCHA widget, if any.
 *
 * The widget is a progressive enhancement: with `provider: "none"` (or a
 * provider without a site key) this component renders nothing at all and the
 * form behaves identically — a supplier must never be locked out of submitting a
 * price because a third-party script is blocked on their network.
 *
 * `resetKey` forces a fresh widget, which matters because provider tokens are
 * single-use: after a failed submit the old token is dead and reusing the widget
 * would fail forever.
 */
export default function Captcha({ captcha, onToken, onError, resetKey = 0 }) {
  const containerRef = useRef(null);
  const handlersRef = useRef({ onToken, onError });
  const [failed, setFailed] = useState(null);

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
    setFailed(null);

    renderCaptchaWidget(provider, containerRef.current, {
      siteKey,
      onToken: (token) => handlersRef.current.onToken?.(token),
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
  }, [provider, siteKey, resetKey]);

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
