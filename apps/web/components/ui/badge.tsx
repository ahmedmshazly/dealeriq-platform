import type { ReactNode } from "react";

type Severity = "success" | "info" | "warning" | "critical" | "neutral";
type Shape = "chip" | "pill";

const SEVERITY_CLASSES: Record<Severity, string> = {
  success: "bg-success-bg border-success-border text-success-fg",
  info: "bg-info-bg border-info-border text-info-fg",
  warning: "bg-warning-bg border-warning-border text-warning-fg",
  critical: "bg-critical-bg border-critical-border text-critical-fg",
  neutral: "bg-surface-sunken border-border-hairline text-text-secondary",
};

interface BadgeProps {
  severity?: Severity;
  shape?: Shape;
  children: ReactNode;
  className?: string;
}

/** Two distinct badge shapes per the Brand Guidelines: `chip` (6-8px radius) for order/entity
 * status, `pill` (fully rounded) for temperature/priority tags — never interchange them. */
export function Badge({ severity = "neutral", shape = "chip", children, className = "" }: BadgeProps) {
  const shapeClass = shape === "pill" ? "rounded-full" : "rounded-sm";
  return (
    <span
      className={`inline-flex items-center gap-1.5 border px-2.5 py-1 text-xs font-medium ${shapeClass} ${SEVERITY_CLASSES[severity]} ${className}`}
    >
      {children}
    </span>
  );
}
