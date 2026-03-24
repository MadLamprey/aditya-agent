"use client"

export type Mode = "general" | "technical" | "behavioral"

interface Props {
  mode: Mode
  onChange: (mode: Mode) => void
}

const MODES: { value: Mode; label: string }[] = [
  { value: "general", label: "GENERAL" },
  { value: "technical", label: "TECHNICAL" },
  { value: "behavioral", label: "BEHAVIORAL" },
]

export default function ModeSwitch({ mode, onChange }: Props) {
  return (
    <div
      style={{
        display: "flex",
        gap: 8,
        padding: "6px",
        background: "rgba(248,244,238,0.85)",
        borderRadius: 16,
        border: "1px solid #e0d5c0",
        boxShadow: "inset 0 1px 4px rgba(0,0,0,0.04), 0 2px 8px rgba(0,0,0,0.06)",
      }}
    >
      {MODES.map(({ value, label }) => {
        const isActive = mode === value

        return (
          <button
            key={value}
            type="button"
            onClick={() => onChange(value)}
            style={{
              padding: "8px 16px",
              borderRadius: 12,
              fontFamily: "JetBrains Mono, monospace",
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              color: isActive ? "#ffffff" : "#6b5a3e",
              background: isActive ? "#ff7a00" : "transparent",
              border: "none",
              cursor: "pointer",
              transition: "all 0.18s ease",
              boxShadow: isActive ? "0 2px 8px rgba(255,122,0,0.35)" : "none",
              transform: isActive ? "translateY(-1px)" : "none",
            }}
            className="hover:bg-[#ff8c1a] hover:text-white hover:shadow-md active:scale-95"
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}