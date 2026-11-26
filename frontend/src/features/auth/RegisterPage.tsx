import { useId, useState, type SubmitEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router";

import { ErrorAlert } from "@/components/layout/ErrorAlert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { product } from "@/config/product";
import { AuthLayout } from "@/features/auth/AuthLayout";
import { useMe, useRegister } from "@/features/auth/queries";
import { ApiError } from "@/lib/api/client";

const MIN_PASSWORD = 12;

function fieldIssue(error: unknown, field: string): string | null {
  if (!(error instanceof ApiError)) return null;
  const issues = error.details.filter((d) => d.field === field).map((d) => d.issue);
  return issues.length ? issues.join("; ") : null;
}

export function RegisterPage() {
  const navigate = useNavigate();
  const me = useMe();
  const register = useRegister();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const id = useId();

  if (me.isSuccess) return <Navigate to="/" replace />;

  const tooShort = password.length > 0 && password.length < MIN_PASSWORD;
  const passwordIssue = fieldIssue(register.error, "password");
  const emailTaken = register.error instanceof ApiError && register.error.code === "email_taken";
  const onSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    register.mutate(
      { email, password, ...(displayName.trim() && { display_name: displayName.trim() }) },
      // A new account has no workspace yet: the workspaces page is the next step.
      { onSuccess: () => void navigate("/workspaces", { replace: true }) },
    );
  };

  return (
    <AuthLayout title="Create your account" description={`Start using ${product.name}.`}>
      <form className="space-y-4" onSubmit={onSubmit} noValidate>
        {register.isError && !passwordIssue && (
          <ErrorAlert
            error={register.error}
            title={emailTaken ? "Email already registered" : "Could not create the account"}
            {...(emailTaken && { hint: "Sign in instead, or use another email address." })}
          />
        )}
        <div className="space-y-1.5">
          <Label htmlFor={`${id}-email`}>Email</Label>
          <Input
            id={`${id}-email`}
            type="email"
            autoComplete="email"
            required
            aria-invalid={emailTaken || undefined}
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
            }}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${id}-name`}>
            Name <span className="font-normal text-muted-foreground">(optional)</span>
          </Label>
          <Input
            id={`${id}-name`}
            autoComplete="name"
            maxLength={80}
            value={displayName}
            onChange={(e) => {
              setDisplayName(e.target.value);
            }}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${id}-password`}>Password</Label>
          <Input
            id={`${id}-password`}
            type="password"
            autoComplete="new-password"
            required
            maxLength={128}
            aria-invalid={tooShort || Boolean(passwordIssue) || undefined}
            aria-describedby={`${id}-password-hint`}
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
            }}
          />
          <p
            id={`${id}-password-hint`}
            className={
              passwordIssue ? "text-[13px] text-destructive" : "text-[13px] text-muted-foreground"
            }
          >
            {passwordIssue
              ? `The password ${passwordIssue}.`
              : `At least ${MIN_PASSWORD} characters. A short phrase is easy to remember and hard to guess.`}
          </p>
        </div>
        <Button
          type="submit"
          className="w-full"
          disabled={register.isPending || !email || password.length < MIN_PASSWORD}
        >
          {register.isPending ? "Creating account…" : "Create account"}
        </Button>
        <p className="text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link to="/sign-in" className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}
