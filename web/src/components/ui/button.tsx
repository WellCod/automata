import { Button as ButtonPrimitive } from "@base-ui/react/button";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

// DESIGN.md: texto em caixa normal; uma ação principal (azul) por tela, o resto neutro
const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center gap-1.5 rounded-md border font-medium whitespace-nowrap transition-colors outline-none select-none focus-visible:ring-2 focus-visible:ring-ring/40 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-3.5",
  {
    variants: {
      variant: {
        // secundário: contorno neutro
        default: "border-border bg-background text-foreground hover:bg-muted",
        // ação principal da tela
        strong: "border-transparent bg-accent text-accent-foreground hover:bg-accent/90",
        // criar, publicar: destaque sem competir com a principal
        accent: "border-accent/40 bg-accent/10 text-accent hover:bg-accent/15",
        // cancelar, editar, opções de seletor
        muted:
          "border-border bg-transparent text-muted-foreground hover:bg-muted hover:text-foreground",
        destructive: "border-transparent bg-destructive text-white hover:bg-destructive/90",
        // excluir antes da confirmação
        subtleDestructive:
          "border-border bg-transparent text-muted-foreground hover:border-destructive/40 hover:bg-destructive/5 hover:text-destructive",
        ghost:
          "border-transparent bg-transparent text-muted-foreground hover:bg-muted hover:text-foreground",
      },
      size: {
        default: "h-8 px-3 text-[13px]",
        sm: "h-7 px-2.5 text-[12px]",
        xs: "h-6 px-2 text-[12px]",
        icon: "size-7 [&_svg:not([class*='size-'])]:size-4",
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
