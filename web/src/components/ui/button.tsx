import { Button as ButtonPrimitive } from "@base-ui/react/button";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

// DESIGN.md: fundo transparente, borda 1px, texto uppercase; hover muda só borda e texto
const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center gap-1.5 rounded border bg-transparent font-medium tracking-[0.05em] whitespace-nowrap uppercase transition-colors outline-none select-none focus-visible:border-accent focus-visible:text-accent disabled:pointer-events-none disabled:opacity-40 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-3.5",
  {
    variants: {
      variant: {
        default: "border-border text-foreground hover:border-accent hover:text-accent",
        strong: "border-foreground text-foreground hover:border-accent hover:text-accent",
        muted:
          "border-border text-muted-foreground hover:border-foreground/50 hover:text-foreground",
        accent: "border-accent text-accent hover:border-accent/70 hover:text-accent/70",
        destructive:
          "border-destructive text-destructive hover:border-destructive/70 hover:text-destructive/70",
        subtleDestructive:
          "border-border text-muted-foreground hover:border-destructive hover:text-destructive",
        ghost:
          "border-transparent text-muted-foreground normal-case tracking-normal hover:border-border hover:text-foreground",
      },
      size: {
        default: "h-7 px-3 text-[11px]",
        sm: "h-6 px-2 text-[10px]",
        xs: "h-5 px-1.5 text-[10px]",
        icon: "size-6 [&_svg:not([class*='size-'])]:size-3.5",
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
