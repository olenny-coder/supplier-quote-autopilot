/**
 * Banners / inline notices.
 *
 * Tone is limited to the four semantic tokens so contrast is guaranteed:
 * every `*-soft-fg` on its `*-soft` background clears 4.5:1. The tones are also
 * paired with an icon and a heading, never colour alone, so the message still
 * reads correctly for colour-blind users and in print.
 */

const TONES = {
  info: {
    wrapper: "bg-primary-soft text-primary-soft-fg",
    icon: "i",
  },
  success: {
    wrapper: "bg-success-soft text-success-soft-fg",
    icon: "\u2713",
  },
  warning: {
    wrapper: "bg-warning-soft text-warning-soft-fg",
    icon: "!",
  },
  danger: {
    wrapper: "bg-danger-soft text-danger-soft-fg",
    icon: "!",
  },
};

export default function Notice({
  tone = "info",
  title,
  children,
  live = false,
  className = "",
}) {
  const style = TONES[tone] || TONES.info;

  return (
    <div
      // `role="status"` + aria-live means the message is announced when it
      // appears after an async action, without stealing focus.
      role={live ? "status" : undefined}
      aria-live={live ? "polite" : undefined}
      className={`rounded-2xl p-4 ${style.wrapper} ${className}`.trim()}
    >
      <div className="flex items-start gap-3">
        <span
          aria-hidden="true"
          className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-current text-sm font-bold"
        >
          {style.icon}
        </span>
        <div className="min-w-0 space-y-1">
          {title ? (
            <p className="text-sm font-semibold leading-5">{title}</p>
          ) : null}
          {children ? (
            <div className="text-sm leading-5 [&_a]:font-semibold [&_a]:underline">
              {children}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
