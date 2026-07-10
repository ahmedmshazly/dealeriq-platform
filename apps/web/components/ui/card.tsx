import type { HTMLAttributes } from "react";

export function Card({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`rounded-card border border-border-hairline bg-surface-raised shadow-1 ${className}`}
      {...props}
    />
  );
}
