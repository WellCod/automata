import { Button as ButtonPrimitive } from "@base-ui/react/button";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center rounded border border-transparent bg-transparent uppercase tracking-[0.05em] text-[11px] font-medium whitespace-nowrap transition-colors outline-none select-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/20 disabled:pointer-events-none disabled:opacity-40 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-3.5",
  {
    variants: {
      variant: {
        default:
          "border-border text-muted-foreground hover:border-foreground/50 hover:text-foreground",
        primary: "border-foreground text-foreground hover:border-accent hover:text-accent",
        accent: "border-accent text-accent hover:border-accent/70 hover:text-accent/70",
        destructive:
          "border-destructive/60 text-destructive hover:border-destructive hover:text-destructive",
        ghost: "border-transparent text-muted-foreground hover:border-border hover:text-foreground",
        link: "border-transparent text-accent underline-offset-4 hover:underline",
      },
      size: {
        default: "h-7 gap-1.5 px-3 py-1.5",
        sm: "h-6 gap-1 px-2 text-[10px]",
        lg: "h-8 gap-1.5 px-3",
        icon: "size-7",
        "icon-sm": "size-6",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
}

export { Button, buttonVariants };
