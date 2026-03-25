"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { AnimatePresence, motion } from "framer-motion"
import ModeSwitch, { type Mode } from "@/components/ModeSwitch"
import IsometricWorld, { type WorldState } from "@/components/IsometricWorld"
import InputSurface from "@/components/InputSurface"

interface AMAResponse {
  answer: string
  sources_used: string[]
  audience: string
  routing_reasoning: string
  is_off_topic: boolean
  is_low_confidence: boolean
  latency_ms: number
}

interface Message {
  id: string
  query: string
  response: AMAResponse
}


const STARTER_PROMPTS = [
  "What are you most proud of building?",
  "How do you work with ambiguity?",
  "Tell me about your working style and values",
  "What makes you different as an engineer?",
]

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([])
  const [mode, setMode] = useState<Mode>("general")
  const [worldState, setWorldState] = useState<WorldState>("idle")
  const [activeSource, setActiveSource] = useState<string | null>(null)
  const [liveResponse, setLiveResponse] = useState<AMAResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const chatBottomRef = useRef<HTMLDivElement>(null)
  const history = messages.slice(-4).map((m): [string, string] => [m.query, m.response.answer])

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [messages, isLoading])

  const handleQuery = useCallback(async (query: string) => {
    setIsLoading(true)
    setError(null)
    setLiveResponse(null)
    setActiveSource(null)
    setWorldState("thinking")

    try {
      const res = await fetch("https://aditya-agent.onrender.com/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, audience: mode, history }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: "Unknown error" }))
        throw new Error(err.error ?? `HTTP ${res.status}`)
      }

      const data: AMAResponse = await res.json()

      const realSource = data.is_off_topic ? null : (data.sources_used[0] ?? null)
      setActiveSource(realSource)

      if (data.is_off_topic) {
        setWorldState("falling")
        setLiveResponse(data)
        await delay(4500)
        setMessages((prev) => [...prev, { id: crypto.randomUUID(), query, response: data }])
        setWorldState("idle")
        setActiveSource(null)
        setLiveResponse(null)
      } else {
        setWorldState("walking")
        await delay(2000)
        setWorldState("answering")
        setLiveResponse(data)
        setMessages(prev => [...prev, { id: crypto.randomUUID(), query, response: data }])
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong")
    } finally {
      setIsLoading(false)
    }
  }, [mode, history])

  const inputDisabled = isLoading || worldState === "thinking" || worldState === "walking"

  return (
    <div
      className="app-shell"
      style={{
        padding: "26px 28px",
        background:
          "linear-gradient(180deg, #f3efe7 0%, #eeeadf 100%)",
      }}
    >
      <div className="paper-texture" />
      <div className="bg-atmo" />

      <div className="console-shell"
        style={{
          position: "relative",
          zIndex: 5,
          width: "100%",
          maxWidth: 1480,
          margin: "0 auto",
          height: "calc(100svh - 52px)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            inset: 0,
            pointerEvents: "none",
            background:
              "radial-gradient(circle at 20% 0%, rgba(255,255,255,0.3), transparent 24%)",
          }}
        />
        <div
          style={{
            position: "absolute",
            top: 18,
            left: 18,
            width: 54,
            height: 54,
            borderRadius: "50%",
            border: "3px solid rgba(255,255,255,0.65)",
            opacity: 0.7,
          }}
        />

        <header
          style={{
            height: 80,
            padding: '0 32px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'linear-gradient(to bottom, #fdfaf6, #f8f3ea)',
            borderBottom: '2px solid #d9c7b2',
            boxShadow: '0 4px 16px rgba(0,0,0,0.08), inset 0 2px 8px rgba(255,255,255,0.4)',
            borderRadius: '0 0 24px 24px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 16 }}>
            <h1 style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 26,
              fontWeight: 700,
              color: '#2c2418',
              letterSpacing: '-0.02em',
            }}>
              Project AMA
            </h1>
            <span style={{
              color: '#8b7a5e',
              fontSize: 14,
              fontWeight: 500,
            }}>
              P.A.I.Q (Pixel Aditya answering Interview Questions)
            </span>
          </div>

          <ModeSwitch mode={mode} onChange={setMode} />
        </header>

        <main
          style={{
            display: "grid",
            gridTemplateRows: "1fr auto",
            height: "calc(100% - 106px)",
            position: "relative",
            zIndex: 10,
          }}
        >
          <section
            style={{
              display: "grid",
              gridTemplateColumns: "320px 1fr",
              gap: 22,
              padding: "20px 22px 14px",
              minHeight: 0,
            }}
          >
            <aside
              style={{
                borderRadius: 24,
                background: '#fdfaf6',
                border: '2px solid #e0d5c0',
                boxShadow: 'inset 0 3px 10px rgba(255,255,255,0.5), 0 6px 20px rgba(0,0,0,0.08)',
                overflow: 'hidden',
                padding: '24px',
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 11, color: '#a08b6f', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 6 }}>
                  CANDIDATE PROFILE
                </div>
                <h2 style={{ fontSize: 24, fontWeight: 600, color: '#2c2418', marginBottom: 4 }}>
                  Aditya Misra
                </h2>
                <p style={{ color: '#6b5a3e', fontSize: 14 }}>
                  AI Engineer · Year 4, NUS Computer Science
                </p>
              </div>

              <div
                style={{
                  padding: '20px 24px',
                  background: 'rgba(255,255,255,0.6)',
                  borderRadius: 16,
                  border: '1px solid #e0d5c0',
                  boxShadow: 'inset 0 2px 6px rgba(0,0,0,0.04)',
                  marginBottom: 20,
                }}
              >
                <p style={{
                  fontStyle: 'italic',
                  color: '#5c4a38',
                  lineHeight: 1.7,
                  fontSize: 15,
                }}>
                  I build production-grade GenAI systems that real people can trust and depend on, caring about the user more than the technology.
                </p>
              </div>

              {messages.length > 0 && (
                <div style={{
                  flex: 1,
                  overflowY: 'auto',
                  minHeight: 0,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 10,
                  borderTop: '1px solid #e0d5c0',
                  paddingTop: 14,
                  marginTop: 4,
                }}>
                  {messages.map((msg) => (
                    <div key={msg.id} style={{
                      background: 'rgba(255,255,255,0.55)',
                      border: '1px solid #e8dccf',
                      borderRadius: 12,
                      padding: '10px 12px',
                    }}>
                      <div style={{ display: 'flex', gap: 7, marginBottom: 7, alignItems: 'flex-start' }}>
                        <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9, fontWeight: 700, color: '#ff7a00', flexShrink: 0, paddingTop: 1 }}>Q</span>
                        <span style={{ fontSize: 11, color: '#3a2e1f', lineHeight: 1.45 }}>{msg.query}</span>
                      </div>
                      <div style={{ display: 'flex', gap: 7, alignItems: 'flex-start' }}>
                        <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9, fontWeight: 700, color: '#2e7d32', flexShrink: 0, paddingTop: 1 }}>A</span>
                        <span style={{ fontSize: 11, color: '#5c4a38', lineHeight: 1.55 }}>{msg.response.answer}</span>
                      </div>
                      {msg.response.is_off_topic && (
                        <span style={{ fontSize: 9, color: '#a08b6f', fontFamily: 'JetBrains Mono, monospace', marginTop: 4, display: 'block' }}>off-topic</span>
                      )}
                    </div>
                  ))}
                  <div ref={chatBottomRef} />
                </div>
              )}
            </aside>

            <div className="viewport-bezel">
              <div style={{ height: 42, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 16px', borderBottom: '1px solid rgba(84,74,59,0.10)', background: 'rgba(255,255,255,0.36)', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'rgba(60,50,35,0.55)'}}> 
                <span>World View</span>
              </div>

              <div className="viewport-frame">
                <IsometricWorld
                  state={worldState}
                  activeSource={activeSource}
                  response={liveResponse}
                />
              </div>
            </div>
          </section>

          <section
            style={{
              padding: '20px 28px',
              background: 'linear-gradient(to top, #f0e8d8, transparent)',
              borderTop: '1px solid #d9c7b2',
            }}
          >
            <div style={{ maxWidth: 1100, margin: '0 auto' }}>
              {!inputDisabled && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 16 }}>
                  {STARTER_PROMPTS.map(prompt => (
                    <button
                      key={prompt}
                      onClick={() => handleQuery(prompt)}
                      disabled={inputDisabled}
                      style={{
                        padding: '10px 18px',
                        borderRadius: 20,
                        background: '#fff8ee',
                        border: '1.5px solid #e0d5c0',
                        color: '#5c4a38',
                        fontSize: 13,
                        cursor: inputDisabled ? 'not-allowed' : 'pointer',
                        transition: 'all 0.16s ease',
                        boxShadow: '0 2px 6px rgba(0,0,0,0.05)',
                      }}
                      className="hover:bg-[#ffebcc] hover:shadow-md active:scale-95 disabled:opacity-60"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              )}

              <InputSurface onSubmit={handleQuery} disabled={inputDisabled} mode={mode} />
            </div>
          </section>
        </main>

        <AnimatePresence>
          {isLoading && (
            <motion.div
              className="loading-block"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              style={{
                position: "absolute",
                right: 22,
                bottom: 132,
                width: 220,
                zIndex: 30,
              }}
            >
              <div className="loading-dots-row">
                <div className="loading-dot" />
                <div className="loading-dot" />
                <div className="loading-dot" />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {error && (
            <motion.div
              className="error-toast"
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              onClick={() => setError(null)}
              role="alert"
            >
              <span className="error-label">Error</span>
              <span className="error-text">{error}</span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

function delay(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms))
}