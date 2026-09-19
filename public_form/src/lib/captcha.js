/**
 * CAPTCHA loading/rendering.
 *
 * The provider is chosen by the *server* (`/public/config` and the invitation
 * preview), never by the client, and `"none"` is a first-class configuration:
 * when spam protection is off this module is never called and the form works
 * exactly the same. That keeps the public form usable on networks that block
 * Cloudflare/hCaptcha (common in some supplier regions) as long as the buyer
 * leaves the provider off.
 *
 * Both supported providers expose the same explicit-render API shape
 * (`render(container, {sitekey, callback})` / `remove(id)`), which is why one
 * implementation can cover them.
 */

const PROVIDERS = {
  turnstile: {
    scriptUrl: "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit",
    globalName: "turnstile",
  },
  hcaptcha: {
    scriptUrl: "https://js.hcaptcha.com/1/api.js?render=explicit",
    globalName: "hcaptcha",
  },
};

/** Only these two providers are supported; anything else is treated as "none". */
export function isSupportedProvider(provider) {
  return provider === "turnstile" || provider === "hcaptcha";
}

/**
 * True when a captcha should actually be shown: a supported provider *and* a
 * site key. Both conditions are required because a provider without a key would
 * render an empty, permanently failing widget.
 */
export function isCaptchaEnabled(captcha) {
  if (!captcha) return false;
  return (
    isSupportedProvider(captcha.provider) &&
    typeof captcha.site_key === "string" &&
    captcha.site_key.trim().length > 0
  );
}

/** In-flight/loaded script promises, keyed by provider, so the <script> tag and
 *  the provider's global are created once even across re-renders (React 19
 *  StrictMode mounts effects twice in development). */
const scriptPromises = new Map();

/**
 * Injects the provider script once and resolves with its global API object.
 * The promise is cached including on failure-free paths; a failed load clears
 * the cache so a retry actually retries.
 */
export function loadCaptchaScript(provider) {
  const config = PROVIDERS[provider];
  if (!config) {
    return Promise.reject(
      new Error(`Unsupported captcha provider: ${String(provider)}`)
    );
  }

  if (window[config.globalName]) {
    return Promise.resolve(window[config.globalName]);
  }

  const cached = scriptPromises.get(provider);
  if (cached) return cached;

  const promise = new Promise((resolve, reject) => {
    const selector = `script[data-captcha-script="${provider}"]`;
    let script = document.querySelector(selector);

    const onLoad = () => {
      const api = window[config.globalName];
      if (api) resolve(api);
      else reject(new Error("The spam check did not start correctly."));
    };
    const onError = () => {
      scriptPromises.delete(provider);
      reject(new Error("The spam check could not be loaded."));
    };

    if (!script) {
      script = document.createElement("script");
      script.src = config.scriptUrl;
      script.async = true;
      script.defer = true;
      script.dataset.captchaScript = provider;
      document.head.appendChild(script);
    }

    script.addEventListener("load", onLoad);
    script.addEventListener("error", onError);
  });

  scriptPromises.set(provider, promise);
  return promise;
}

/**
 * The widget size each provider should render at.
 *
 * Both providers default to a fixed-width "normal" widget — Turnstile 300x65,
 * hCaptcha about 303x78 — and this form's card is only about 296px wide at 360px,
 * where the site also sets `overflow-x: hidden`, so the widget was clipped
 * mid-sentence on the page that asks for a price. The checkbox sits on the left in
 * both widgets, so submission still worked; it just looked broken.
 *
 * Each provider spells "fit the container" differently, and passing one provider's
 * value to the other is an unknown option rather than an error, so they are mapped
 * explicitly rather than guessed at.
 */
const CAPTCHA_WIDGET_SIZE = {
  turnstile: "flexible",
  hcaptcha: "compact",
};

/**
 * Loads the script (if needed) and renders a widget into `container`.
 *
 * @returns {Promise<{remove: () => void}>} handle used for cleanup on unmount.
 */
export async function renderCaptchaWidget(provider, container, options) {
  const { siteKey, onToken, onError } = options;
  const api = await loadCaptchaScript(provider);

  if (!container || typeof api?.render !== "function") {
    throw new Error("The spam check is unavailable in this browser.");
  }

  let widgetId = null;
  let settled = false;

  widgetId = api.render(container, {
    sitekey: siteKey,
    size: CAPTCHA_WIDGET_SIZE[provider] || undefined,
    callback: (token) => {
      settled = true;
      onToken?.(token);
    },
    "error-callback": () => {
      settled = true;
      onError?.("The spam check failed to verify. Please try again.");
      return true; // stop the provider from retrying on its own; we re-render.
    },
    "expired-callback": () => {
      // Tokens are single-use and short-lived; tell the parent so it can clear
      // the stale value and warn before submission.
      if (settled) onToken?.(null);
    },
    theme: "light",
  });

  return {
    remove() {
      try {
        if (widgetId !== null && typeof api.remove === "function") {
          api.remove(widgetId);
        }
      } catch {
        // The provider may already have torn the widget down (e.g. after a
        // failed challenge). Cleanup must never throw during unmount.
      }
    },
  };
}
