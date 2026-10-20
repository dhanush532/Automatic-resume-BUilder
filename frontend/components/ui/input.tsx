import { type InputHTMLAttributes, forwardRef } from "react";

import { cn } from "@/lib/cn";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...props },
  ref,
) {
  return (
    <input
      className={cn(
        "h-11 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink placeholder:text-muted/75 outline-none transition focus:border-brand focus:ring-2 focus:ring-indigo-100 disabled:cursor-not-allowed disabled:bg-surface",
        className,
      )}
      ref={ref}
      {...props}
    />
  );
});
