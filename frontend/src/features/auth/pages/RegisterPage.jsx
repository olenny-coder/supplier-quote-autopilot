import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { toast } from "sonner";

import { Button, FormField, inputClass } from "@/shared/components/ui";

import AuthLayout from "../components/AuthLayout";
import { resolveRedirectTarget, withNext } from "../navigation";
import { useAuth } from "../useAuth";

const initialFormState = {
  full_name: "",
  company_name: "",
  email: "",
  password: "",
  contact_email: "",
  contact_phone: "",
};

const errorClass = "border-danger/60 bg-danger-soft/40";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function RegisterPage() {
  const { register, token, loading: sessionLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const redirectTo = resolveRedirectTarget(location.search, location.state);

  const [formData, setFormData] = useState(initialFormState);
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

    if (!formData.full_name.trim()) {
      errs.full_name = "Your name is required";
    }

    if (!formData.company_name.trim()) {
      errs.company_name = "Company name is required";
    }

    if (!formData.email.trim()) {
      errs.email = "Login email is required";
    } else if (!EMAIL_PATTERN.test(formData.email.trim())) {
      errs.email = "Enter a valid email address";
    }

    if (!formData.password) {
      errs.password = "Choose a password";
    } else if (formData.password.length < 8) {
      errs.password = "Use at least 8 characters";
    }

    // The contact email is what suppliers see on invitations and reminders, so
    // it is required — but it defaults to the login email for convenience.
    if (!formData.contact_email.trim()) {
      errs.contact_email = "Suppliers need an address to reply to";
    } else if (!EMAIL_PATTERN.test(formData.contact_email.trim())) {
      errs.contact_email = "Enter a valid email address";
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

      await register({
        full_name: formData.full_name.trim(),
        company_name: formData.company_name.trim(),
        email: formData.email.trim(),
        password: formData.password,
        contact_email: formData.contact_email.trim(),
        contact_phone: formData.contact_phone.trim() || null,
      });

      toast.success("Account created — welcome aboard.");

      navigate(redirectTo, { replace: true });
    } catch (error) {
      setFormError(error.message);
      toast.error(error.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (!sessionLoading && token) {
    return <Navigate replace to={redirectTo} />;
  }

  return (
    <AuthLayout
      title="Create your buyer account"
      subtitle="Set up your company once, then invite suppliers to any RFQ."
      footer={
        <>
          Already have an account?{" "}
          <Link
            to={withNext("/login", redirectTo)}
            className="font-medium text-primary transition hover:underline"
          >
            Sign in
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

        <div className="grid gap-5 sm:grid-cols-2">
          <FormField label="Your name" required error={errors.full_name}>
            <input
              name="full_name"
              type="text"
              autoComplete="name"
              value={formData.full_name}
              onChange={handleChange}
              placeholder="Alex Mehta"
              className={`${inputClass} ${errors.full_name ? errorClass : ""}`}
            />
          </FormField>

          <FormField label="Company" required error={errors.company_name}>
            <input
              name="company_name"
              type="text"
              autoComplete="organization"
              value={formData.company_name}
              onChange={handleChange}
              placeholder="Northwind Industrial"
              className={`${inputClass} ${errors.company_name ? errorClass : ""}`}
            />
          </FormField>
        </div>

        <FormField label="Login email" required error={errors.email}>
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

        <FormField
          label="Password"
          hint="at least 8 characters"
          required
          error={errors.password}
        >
          <input
            name="password"
            type="password"
            autoComplete="new-password"
            value={formData.password}
            onChange={handleChange}
            placeholder="••••••••"
            className={`${inputClass} ${errors.password ? errorClass : ""}`}
          />
        </FormField>

        <div className="grid gap-5 sm:grid-cols-2">
          <FormField
            label="Supplier-facing email"
            hint="shown on invitations"
            required
            error={errors.contact_email}
          >
            <input
              name="contact_email"
              type="email"
              autoComplete="email"
              value={formData.contact_email}
              onChange={handleChange}
              placeholder="sourcing@company.com"
              className={`${inputClass} ${
                errors.contact_email ? errorClass : ""
              }`}
            />
          </FormField>

          <FormField label="Phone" hint="optional">
            <input
              name="contact_phone"
              type="tel"
              autoComplete="tel"
              value={formData.contact_phone}
              onChange={handleChange}
              placeholder="+1 555 0100"
              className={inputClass}
            />
          </FormField>
        </div>

        <Button
          type="submit"
          className="w-full"
          loading={submitting}
          loadingText="Creating account…"
        >
          Create account
        </Button>
      </form>
    </AuthLayout>
  );
}

export default RegisterPage;
