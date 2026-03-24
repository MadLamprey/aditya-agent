"use client"

import { useState, useRef, type FormEvent, type KeyboardEvent } from "react"
import type { Mode } from "./ModeSwitch"

interface Props {
  onSubmit: (query: string) => void
  disabled: boolean
  mode: Mode
}

export default function InputSurface({ onSubmit, disabled, mode }: Props) {
  const [value, setValue] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSubmit(trimmed)
    setValue("")
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const placeholders: Record<Mode, string> = {
    general: "Ask me anything about my background...",
    technical: "Ask about my technical skills and projects...",
    behavioral: "Ask about my work style and values...",
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        display: "flex",
        borderRadius: 9999,
        overflow: "hidden",
        border: "2px solid #e0d5c0",
        background: "#ffffff",
        boxShadow: "inset 0 2px 6px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.08)",
      }}
    >
      <input
        ref={inputRef}
        type="text"
        placeholder={placeholders[mode]}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        autoComplete="off"
        spellCheck={false}
        style={{
          flex: 1,
          padding: "14px 20px",
          border: "none",
          outline: "none",
          background: "transparent",
          fontSize: 15,
          color: "#3a2e1f",
          fontFamily: "system-ui, -apple-system, sans-serif",
        }}
      />

      <button
        type="submit"
        disabled={disabled || !value.trim()}
        style={{
          padding: "0 28px",
          background: disabled || !value.trim() ? "#d9c7b2" : "#ff7a00",
          color: "white",
          border: "none",
          fontFamily: "JetBrains Mono, monospace",
          fontSize: 13,
          fontWeight: 700,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          cursor: disabled || !value.trim() ? "not-allowed" : "pointer",
          transition: "all 0.18s ease",
          display: "flex",
          alignItems: "center",
          gap: 8,
          boxShadow: disabled || !value.trim() ? "none" : "0 2px 10px rgba(255,122,0,0.3)",
        }}
        className="hover:bg-[#ff8c1a] active:scale-95 disabled:hover:bg-[#d9c7b2]"
      >
        <span>SEND</span>
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <line x1="22" y1="2" x2="11" y2="13" />
          <polygon points="22 2 15 22 11 13 2 9 22 2" />
        </svg>
      </button>
    </form>
  )
}