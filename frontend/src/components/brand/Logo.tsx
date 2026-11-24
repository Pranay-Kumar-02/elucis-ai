import { product } from "@/config/product";
import { cn } from "@/lib/utils";

/** Brand mark: a feedback bubble whose lines rise into a signal. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden className={cn("size-8 shrink-0", className)}>
      <rect width="32" height="32" rx="8" className="fill-primary" />
      <path
        d="M9 9.5h14a2.5 2.5 0 0 1 2.5 2.5v7a2.5 2.5 0 0 1-2.5 2.5h-7.2L11 25v-3.5H9A2.5 2.5 0 0 1 6.5 19v-7A2.5 2.5 0 0 1 9 9.5Z"
        className="fill-none stroke-primary-foreground"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path
        d="M11 18.5v-1.5M14.5 18.5V15M18 18.5v-5M21.5 18.5V13"
        className="stroke-primary-foreground"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <LogoMark />
      <span className="text-[15px] font-semibold tracking-[-0.01em]">{product.name}</span>
    </div>
  );
}
