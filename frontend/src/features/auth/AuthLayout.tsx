import { useEffect, type ReactNode } from "react";

import { Logo } from "@/components/brand/Logo";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { product } from "@/config/product";

/** Public pages (sign-in, registration): the brand, one card, nothing else. */
export function AuthLayout({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  useEffect(() => {
    document.title = `${title} · ${product.name}`;
  }, [title]);

  return (
    <div className="flex min-h-svh flex-col bg-muted/30">
      <header className="flex h-14 items-center justify-between px-6">
        <Logo />
        <ThemeToggle />
      </header>
      <main className="flex flex-1 items-start justify-center px-4 pt-[8vh] pb-16">
        <div className="w-full max-w-sm">
          <Card>
            <CardHeader>
              <CardTitle>
                <h1 className="text-xl">{title}</h1>
              </CardTitle>
              <CardDescription>{description}</CardDescription>
            </CardHeader>
            <CardContent>{children}</CardContent>
          </Card>
          <p className="mt-6 text-center text-[13px] text-muted-foreground">{product.tagline}</p>
        </div>
      </main>
    </div>
  );
}
