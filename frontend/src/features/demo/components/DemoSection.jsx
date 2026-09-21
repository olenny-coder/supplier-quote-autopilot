/**
 * One step of the guided tour.
 *
 * Numbered on purpose: the page is making an argument in a fixed order — here is
 * the request, here is what came back, here is the ranking, here is how the
 * system chased the stragglers — and the numbers are what tell a visitor how much
 * of it is left.
 */
function DemoSection({ step, title, description, aside = null, children }) {
  return (
    <section className="scroll-mt-24">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="max-w-3xl">
          <div className="flex items-center gap-2.5">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-soft text-xs font-semibold text-primary-soft-fg">
              {step}
            </span>
            <h2 className="text-lg font-semibold tracking-tight text-content sm:text-xl">
              {title}
            </h2>
          </div>

          {description && (
            <p className="mt-2 text-sm leading-relaxed text-muted">
              {description}
            </p>
          )}
        </div>

        {aside}
      </div>

      <div className="mt-4">{children}</div>
    </section>
  );
}

export default DemoSection;
