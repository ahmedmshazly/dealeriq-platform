import type { InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: string;
}

export function Input({ error, className = "", ...props }: InputProps) {
  return (
    <div className="flex flex-col gap-1">
      <input
        className={`rounded-control border px-3 py-2 text-sm text-text-primary outline-none transition-colors duration-fast placeholder:text-text-disabled focus:border-[1.5px] focus:border-primary-500 focus:ring-4 focus:ring-primary-50 ${
          error
            ? "border-[1.5px] border-critical-fg bg-critical-bg text-critical-fg"
            : "border-border-strong bg-surface-raised"
        } ${className}`}
        {...props}
      />
      {error && <span className="text-xs text-critical-fg">{error}</span>}
    </div>
  );
}
