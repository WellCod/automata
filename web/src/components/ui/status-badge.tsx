import { cn } from "@/lib/utils";

const TONES = {
  active: "bg-accent/10 text-accent",
  pending: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  neutral: "bg-muted text-muted-foreground",
  danger: "bg-destructive/10 text-destructive",
} as const;

export type BadgeTone = keyof typeof TONES;

export function Badge({
  tone,
  children,
  className,
}: {
  tone: BadgeTone;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium whitespace-nowrap",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
