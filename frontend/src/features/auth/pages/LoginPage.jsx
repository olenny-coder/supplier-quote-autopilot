import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { toast } from "sonner";

import { Button, FormField, inputClass } from "@/shared/components/ui";
import { buttonClass } from "@/shared/lib/button";

import AuthLayout from "../components/AuthLayout";
import { resolveRedirectTarget, withNext } from "../navigation";
import { useAuth } from "../useAuth";

const errorClass = "border-danger/60 bg-danger-soft/40";

function LoginPage() {
  const { login, token, loading: sessionLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const redirectTo = resolveRedirectTarget(location.search, location.state);

  const [formData, setFormData] = useState({ email: "", password: "" });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (event) => {
    const { name, value } = event.target;

    setFormData((prev) => ({ ...prev, [name]: value }));

    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: null }));
    if (formError) setFormError(null);
  };

  const validate = () => {
    const errs = {};

    if (!formData.email.trim()) {
      errs.email = "Email is required";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email.trim())) {
      errs.email = "Enter a valid email address";
    }

    if (!formData.password) {
      errs.password = "Password is required";
    }

    return errs;
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    const errs = validate();

    if (Object.keys(errs).length) {
      setErrors(errs);
      return;
    }

    try {
      setSubmitting(true);
      setFormError(null);

      await login({
        email: formData.email.trim(),
        password: formData.password,
      });

      toast.success("Signed in.");

      navigate(redirectTo, { replace: true });
    } catch (error) {
      // Surfaced inline as well as in a toast: the buyer is looking at this
      // form, so the reason ("Invalid credentials") must be readable next to it.
      setFormError(error.message);
      toast.error(error.message);
    } finally {
      setSubmitting(false);
    }
  };

  // Already authenticated (bookmark, back button): skip the form entirely.
  if (!sessionLoading && token) {
    return <Navigate replace to={redirectTo} />;
  }

  return (
    <AuthLayout
      title="Sign in"
      subtitle="Access your RFQs, supplier responses and award decisions."
      footer={
        <>
          New here?{" "}
          <Link
            to={withNext("/register", redirectTo)}
            className="font-medium text-primary transition hover:underline"
          >
            Create a buyer account
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-5" noValidate>
        {formError && (
          <div className="flex items-start gap-2.5 rounded-xl border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger-soft-fg">
            <svg
              className="mt-0.5 h-4 w-4 shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m0 3.75h.008M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span>{formError}</span>
          </div>
        )}

        <FormField label="Work email" required error={errors.email}>
          <input
            name="email"
            type="email"
            autoComplete="email"
            value={formData.email}
            onChange={handleChange}
            placeholder="buyer@company.com"
            className={`${inputClass} ${errors.email ? errorClass : ""}`}
          />
        </FormField>

        <FormField label="Password" required error={errors.password}>
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            value={formData.password}
            onChange={handleChange}
            placeholder="••••••••"
            className={`${inputClass} ${errors.password ? errorClass : ""}`}
          />
        </FormField>

        <Button
          type="submit"
          className="w-full"
          loading={submitting}
          loadingText="Signing in…"
        >
          Sign in
        </Button>

        {/* The demo sits beside the form rather than only in the footer: a
            visitor who is not ready to sign in should not have to scroll past the
            login they cannot complete to find out what the product does. */}
        <div className="flex items-center gap-3 pt-1">
          <span className="h-px flex-1 bg-border-default" />
          <span className="text-xs font-medium uppercase tracking-wider text-subtle">
            or
          </span>
          <span className="h-px flex-1 bg-border-default" />
        </div>

        <Link to="/demo" className={`${buttonClass("outline", "lg")} w-full`}>
          Explore the demo — no account needed
        </Link>
      </form>
    </AuthLayout>
  );
}

export default LoginPage;
