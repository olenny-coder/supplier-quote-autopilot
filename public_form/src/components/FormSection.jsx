/**
 * One card per group of related questions.
 *
 * Extracted purely so the form reads as a sequence of plain-language questions
 * rather than a wall of markup: the section scaffolding (card, heading, optional
 * one-line explanation) is identical for every group and is easy to drift apart
 * when it is copy-pasted eight times. `aria-labelledby` on a real `<h2>` keeps the
 * heading structure meaningful for a screen-reader user jumping between groups.
 */
export default function FormSection({
  id,
  title,
  description,
  children,
  className = "",
}) {
  const headingId = `${id}-heading`;

  return (
    <section
      aria-labelledby={headingId}
      className={`rounded-2xl border border-border-default bg-surface p-4 shadow-card sm:p-5 ${className}`.trim()}
    >
      <h2 id={headingId} className="text-base font-bold text-content">
        {title}
      </h2>
      {description ? (
        <p className="mt-1 text-sm text-muted">{description}</p>
      ) : null}
      <div className="mt-4 space-y-4">{children}</div>
    </section>
  );
}
