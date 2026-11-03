import * as SwitchPrimitive from "@radix-ui/react-switch";
import * as React from "react";

import { cn } from "@/lib/utils";

export const Switch = React.forwardRef<
  React.ElementRef<typeof SwitchPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>
>(({ className, ...props }, ref) => (
  <SwitchPrimitive.Root
    ref={ref}
    className={cn(
      "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border transition-colors",
      "data-[state=checked]:border-navy data-[state=checked]:bg-navy",
      "data-[state=unchecked]:border-line data-[state=unchecked]:bg-surface",
      "disabled:cursor-not-allowed disabled:opacity-50",
      className,
    )}
    {...props}
  >
    <SwitchPrimitive.Thumb
      className={cn(
        "block size-3.5 translate-x-0.5 rounded-full transition-transform",
        "data-[state=checked]:translate-x-[18px] data-[state=checked]:bg-surface",
        "data-[state=unchecked]:bg-muted",
      )}
    />
  </SwitchPrimitive.Root>
));
Switch.displayName = "Switch";
