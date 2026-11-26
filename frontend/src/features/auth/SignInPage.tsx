import { useId, useState, type SubmitEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router";

import { ErrorAlert } from "@/components/layout/ErrorAlert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { product } from "@/config/product";
import { AuthLayout } from "@/features/auth/AuthLayout";
import { retryAfterMinutes, safeNext, useMe, useSignIn } from "@/features/auth/queries";

export function SignInPage() {
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const navigate = useNavigate();
  const me = useMe();
  const signIn = useSignIn();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const id = useId();

  if (me.isSuccess) return <Navigate to={next} replace />;

  const onSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    signIn.mutate({ email, password }, { onSuccess: () => void navigate(next, { replace: true }) });
  };
  const minutes = retryAfterMinutes(signIn.error);

  return (
    <AuthLayout title="Sign in" description={`Welcome back to ${product.name}.`}>
      <form className="space-y-4" onSubmit={onSubmit} noValidate>
        {signIn.isError &&
          (minutes ? (
            <ErrorAlert
              error={signIn.error}
              title="Too many attempts"
              hint={`For your security, try again in ${minutes} minute${minutes === 1 ? "" : "s"}.`}
            />
          ) : (
            <ErrorAlert error={signIn.error} title="Sign-in failed" />
          ))}
        <div className="space-y-1.5">
          <Label htmlFor={`${id}-email`}>Email</Label>
          <Input
            id={`${id}-email`}
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
            }}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${id}-password`}>Password</Label>
          <Input
            id={`${id}-password`}
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
            }}
          />
        </div>
        <Button type="submit" className="w-full" disabled={signIn.isPending || !email || !password}>
          {signIn.isPending ? "Signing in…" : "Sign in"}
        </Button>
        <p className="text-center text-sm text-muted-foreground">
          New here?{" "}
          <Link
            to={`/register${next === "/" ? "" : `?next=${encodeURIComponent(next)}`}`}
            className="font-medium text-primary hover:underline"
          >
            Create an account
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}
