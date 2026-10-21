import { type EvalSuiteStatus, SUITE_STATE_LABEL } from "@/lib/eval-checks";
import { Badge, type BadgeTone } from "@/components/ui/status-badge";

const TONE: Record<EvalSuiteStatus["state"], BadgeTone> = {
  running: "neutral",
  passing: "active",
  failing: "danger",
  regressed: "danger",
};

export function SuiteBadge({ status }: { status: EvalSuiteStatus | undefined }) {
  if (!status) return null;
  const regressions =
    status.state === "regressed" ? ` (${status.regressions} desde o último agendado)` : "";
  return (
    <Badge tone={TONE[status.state]}>
      {SUITE_STATE_LABEL[status.state]}
      {regressions}
    </Badge>
  );
}
