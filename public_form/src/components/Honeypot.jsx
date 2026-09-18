/**
 * Spam honeypot.
 *
 * Why the styling is exactly this and not something "simpler":
 *
 *  - **Not `type="hidden"`, not `display:none`, not `visibility:hidden`.**
 *    Cheap bots and form-fillers skip inputs they can detect as hidden by those
 *    mechanisms, so a hidden input catches nothing. An ordinary visible text
 *    input that is merely parked off-screen is filled by them.
 *  - **`aria-hidden="true"` + `tabIndex={-1}`.** Humans must never reach it:
 *    it is removed from the accessibility tree and from the tab order, so a
 *    screen-reader or keyboard user never meets a field they are told to leave
 *    blank.
 *  - **A plausible label.** If anyone ever does see it, "Company website (leave
 *    blank)" reads like a legitimate optional field. The word "honeypot" must
 *    never appear in the DOM.
 *  - **The submitted value is always `""` regardless of what is typed**, exactly
 *    as the API contract requires — the field exists to waste a bot's time, and
 *    the value is discarded at build-payload time, never read from the DOM.
 *
 * The field name comes from the server (`preview.honeypot_field`), so the buyer
 * can rotate it without a frontend deploy.
 */
export default function Honeypot({ fieldName }) {
  if (!fieldName) return null;

  const inputId = `hp-${fieldName}`;

  return (
    <div
      // Inline styles on purpose: they must not be affected by any Tailwind
      // purge/ordering question, and this exact combination is part of the
      // contract with the API's spam filter.
      style={{
        position: "absolute",
        left: "-9999px",
        top: "auto",
        opacity: 0,
        height: 0,
        width: 0,
        overflow: "hidden",
      }}
      aria-hidden="true"
    >
      <label htmlFor={inputId}>Company website (leave blank)</label>
      <input
        id={inputId}
        name={fieldName}
        type="text"
        tabIndex={-1}
        autoComplete="off"
        // Uncontrolled: React never reads this value, and `defaultValue` avoids
        // React's controlled-input warning without putting it in form state.
        defaultValue=""
      />
    </div>
  );
}
