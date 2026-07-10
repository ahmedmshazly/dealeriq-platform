// Ported from the brand kit Tailwind snippet (see docs/adr — frontend architecture).
// Colors/radius/shadow reference CSS custom properties from tokens.css so theme swapping
// ([data-theme="dark"]) works live. Breakpoints use Tailwind's stock scale (the brand kit
// deliberately doesn't define custom ones); the mockups' fixed content widths (1120/1180px)
// become named maxWidth tokens instead, kept separate from responsive breakpoints.
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["selector", '[data-theme="dark"]'],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        neutral: {
          50: "var(--color-neutral-50)",
          100: "var(--color-neutral-100)",
          200: "var(--color-neutral-200)",
          300: "var(--color-neutral-300)",
          400: "var(--color-neutral-400)",
          500: "var(--color-neutral-500)",
          600: "var(--color-neutral-600)",
          700: "var(--color-neutral-700)",
          800: "var(--color-neutral-800)",
          900: "var(--color-neutral-900)",
        },
        primary: {
          50: "var(--color-primary-50)",
          100: "var(--color-primary-100)",
          200: "var(--color-primary-200)",
          300: "var(--color-primary-300)",
          400: "var(--color-primary-400)",
          500: "var(--color-primary-500)",
          600: "var(--color-primary-600)",
          700: "var(--color-primary-700)",
          800: "var(--color-primary-800)",
        },
        secondary: {
          50: "var(--color-secondary-50)",
          100: "var(--color-secondary-100)",
          300: "var(--color-secondary-300)",
          500: "var(--color-secondary-500)",
          600: "var(--color-secondary-600)",
          700: "var(--color-secondary-700)",
        },
        success: {
          bg: "var(--color-success-bg)",
          border: "var(--color-success-border)",
          fg: "var(--color-success-fg)",
        },
        info: {
          bg: "var(--color-info-bg)",
          border: "var(--color-info-border)",
          fg: "var(--color-info-fg)",
        },
        warning: {
          bg: "var(--color-warning-bg)",
          border: "var(--color-warning-border)",
          fg: "var(--color-warning-fg)",
        },
        critical: {
          bg: "var(--color-critical-bg)",
          border: "var(--color-critical-border)",
          fg: "var(--color-critical-fg)",
        },
        forecast: {
          line: "var(--color-forecast-line)",
          text: "var(--color-forecast-text)",
        },
        surface: {
          canvas: "var(--surface-canvas)",
          raised: "var(--surface-raised)",
          sunken: "var(--surface-sunken)",
          overlay: "var(--surface-overlay)",
        },
        border: {
          hairline: "var(--border-hairline)",
          strong: "var(--border-strong)",
        },
        text: {
          primary: "var(--text-primary)",
          secondary: "var(--text-secondary)",
          muted: "var(--text-muted)",
          disabled: "var(--text-disabled)",
          onaccent: "var(--text-on-accent)",
        },
        "chart-cat-1": "var(--chart-cat-1)",
        "chart-cat-2": "var(--chart-cat-2)",
        "chart-cat-3": "var(--chart-cat-3)",
        "chart-cat-4": "var(--chart-cat-4)",
        "chart-cat-5": "var(--chart-cat-5)",
        "chart-cat-6": "var(--chart-cat-6)",
        "chart-cat-7": "var(--chart-cat-7)",
        "chart-cat-8": "var(--chart-cat-8)",
      },
      fontFamily: {
        ui: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      fontSize: {
        "2xs": ["12px", "16px"],
        xs: ["13px", "18px"],
        sm: ["14px", "20px"],
        md: ["16px", "24px"],
        lg: ["18px", "26px"],
        xl: ["20px", "28px"],
        "2xl": ["24px", "30px"],
        "3xl": ["28px", "34px"],
        "4xl": ["36px", "42px"],
      },
      spacing: {
        0: "0px",
        1: "4px",
        2: "8px",
        3: "12px",
        4: "16px",
        5: "20px",
        6: "24px",
        8: "32px",
        10: "40px",
        12: "48px",
        16: "64px",
        20: "80px",
        24: "96px",
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        control: "var(--radius-control)",
        card: "var(--radius-card)",
        full: "var(--radius-full)",
      },
      boxShadow: {
        1: "var(--shadow-1)",
        2: "var(--shadow-2)",
        3: "var(--shadow-3)",
      },
      transitionDuration: { fast: "120ms", base: "200ms", slow: "320ms" },
      transitionTimingFunction: {
        standard: "cubic-bezier(0.2, 0, 0, 1)",
        decelerate: "cubic-bezier(0, 0, 0.2, 1)",
        spring: "cubic-bezier(0.34, 1.56, 0.64, 1)",
      },
      maxWidth: {
        content: "1120px",
        dashboard: "1180px",
      },
    },
  },
  plugins: [],
};

export default config;
