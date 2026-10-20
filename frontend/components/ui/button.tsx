import { type ButtonHTMLAttributes, type ReactElement, cloneElement, forwardRef } from "react";

import { cn } from "@/lib/cn";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
  asChild?: boolean;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { asChild = false, className, children, variant = "primary", type = "button", ...props },
  ref,
) {
  const variants = {
    primary: "bg-brand text-white hover:bg-[#24523f] focus-visible:outline-brand",
    secondary: "border border-line bg-white text-ink hover:bg-slate-50 focus-visible:outline-brand",
    ghost: "text-muted hover:bg-slate-100 hover:text-ink focus-visible:outline-brand",
  };

  const classes = cn(
    "inline-flex h-10 items-center justify-center gap-2 rounded-lg px-4 text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:pointer-events-none disabled:opacity-50",
    variants[variant],
    className,
  );

  if (asChild) {
    const child = children as ReactElement<{ className?: string }>;
    return cloneElement(child, { className: cn(classes, child.props.className) });
  }

  return (
    <button
      className={classes}
      ref={ref}
      type={type}
      {...props}
    >{children}</button>
  );
});
