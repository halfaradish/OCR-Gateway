import * as React from "react";

import { cn } from "@/lib/utils";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement> & {
  inputSize?: "md" | "sm";
};

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type = "text", inputSize = "md", ...props }, ref) => (
    <input
      ref={ref}
      type={type}
      className={cn(
        "w-full rounded-sm border border-line bg-surface px-3 text-body text-ink",
        inputSize === "sm" ? "h-8 text-meta" : "h-9",
        "placeholder:text-muted/70 disabled:cursor-not-allowed disabled:opacity-60",
        "focus-visible:border-blue focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-blue",
        "aria-[invalid=true]:border-danger",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export type SelectProps = React.SelectHTMLAttributes<HTMLSelectElement> & {
  selectSize?: "md" | "sm";
};

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, children, selectSize = "md", ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        "rounded-sm border border-line bg-surface px-2 text-body text-ink",
        selectSize === "sm" ? "h-8 text-meta" : "h-9",
        "focus-visible:border-blue focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-blue",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  ),
);
Select.displayName = "Select";
