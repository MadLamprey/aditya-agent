"use client"

import { motion, useMotionValue, animate } from "framer-motion"
import { useState, useEffect } from "react"

export type WorldState = "idle" | "thinking" | "walking" | "answering" | "falling"

interface Props {
  state: WorldState
  activeSource: string | null
  response: {
    answer: string
    sources_used: string[]
    audience: string
    is_low_confidence: boolean
    latency_ms: number
    is_off_topic: boolean
  } | null
}

const C = {
  black:      "#0f0f1a",
  darkGray:   "#2a2a3a",
  darkBlue:   "#1e3a5f",
  brown:      "#5c3f2a",
  green:      "#2e7d32",
  lime:       "#66bb6a",
  cream:      "#f5f0e6",
  white:      "#ffffff",
  peach:      "#ffe0b2",
  yellow:     "#ffca28",
  blue:       "#42a5f5",
  lavender:   "#b39ddb",
  pink:       "#f06292",
  coral:      "#ff7043",
  skyStart:   "#a1d4ff",
  skyMid:     "#c3e0ff",
  skyEnd:     "#e3f2fd",
  ground1:    "#c8e6c9",
  ground2:    "#a5d6a7",
  ground3:    "#81c784",
  lightGray:  "#6b7280",
}

const SOURCES = {
  resume:   { x: 80,  y: 140, label: "RESUME RETREAT" },
  blog:     { x: 200, y: 170, label: "BLOG BUNGALOW" },
  linkedin: { x: 320, y: 130, label: "LINKEDIN LODGE" },
  github:   { x: 440, y: 170, label: "GITHUB GRANGE" },
  values:   { x: 560, y: 140, label: "VALUES VILLA" },
}

export default function IsometricWorld({ state, activeSource, response }: Props) {
  const isOffTopic = response?.is_off_topic || state === "falling"
  const activeSources = response?.sources_used || []

  // Calculate character position
  const charPos = activeSource && SOURCES[activeSource as keyof typeof SOURCES]
    ? { x: SOURCES[activeSource as keyof typeof SOURCES].x, y: SOURCES[activeSource as keyof typeof SOURCES].y + 40 }
    : { x: 320, y: 200 }

  return (
    <div className="relative w-full max-w-2xl mx-auto">
      {/* CRT-style frame */}
      <div 
        className="rounded-lg overflow-hidden"
        style={{
          boxShadow: `
            0 0 0 4px ${C.black},
            0 0 0 8px ${C.darkGray},
            0 8px 32px rgba(0,0,0,0.3)
          `,
        }}
      >
        {/* Scanline + vignette overlay */}
        <div 
          className="absolute inset-0 pointer-events-none z-10"
          style={{
            background: `repeating-linear-gradient(
              0deg,
              transparent,
              transparent 2px,
              rgba(0,0,0,0.04) 2px,
              rgba(0,0,0,0.04) 4px
            ),
            radial-gradient(circle at 50% 50%, transparent 40%, rgba(0,0,0,0.25) 100%)`,
          }}
        />
        
        <svg
          viewBox="0 0 640 280"
          className="w-full h-auto block"
          style={{
            imageRendering: "pixelated",
            background: `linear-gradient(180deg, 
              ${C.skyStart} 0%, 
              ${C.skyMid} 45%, 
              ${C.skyEnd} 60%, 
              ${C.ground1} 65%, 
              ${C.ground2} 80%, 
              ${C.ground3} 100%)`,
          }}
        >
          {/* Sky gradient layers */}
          <rect y="0" width="640" height="60" fill="#87CEEB" />
          <rect y="60" width="640" height="40" fill="#98D8EB" />
          <rect y="100" width="640" height="40" fill="#B8E8F0" />
          <rect y="140" width="640" height="20" fill="#E8F8EC" />
          
          {/* Ground layers */}
          <rect y="160" width="640" height="40" fill={C.lime} />
          <rect y="200" width="640" height="40" fill={C.green} />
          <rect y="240" width="640" height="40" fill="#2d9d50" />
          
          {/* Pixel clouds */}
          <PixelCloud x={60} y={20} />
          <PixelCloud x={280} y={40} />
          <PixelCloud x={500} y={16} />
          
          {/* Distant mountains */}
          <PixelMountain x={80} y={120} />
          <PixelMountain x={520} y={124} />
          
          {/* Ground path */}
          <PixelPath />
          
          {/* Trees - back layer */}
          <PixelTree x={24} y={136} variant="pine" />
          <PixelTree x={608} y={132} variant="pine" />
          
          {/* Buildings */}
          <PixelCastle 
            x={SOURCES.resume.x} 
            y={SOURCES.resume.y} 
            active={activeSources.includes("resume") || activeSource === "resume"} 
          />
          <PixelHouse 
            x={SOURCES.blog.x} 
            y={SOURCES.blog.y} 
            active={activeSources.includes("blog") || activeSource === "blog"} 
          />
          <PixelTower 
            x={SOURCES.linkedin.x} 
            y={SOURCES.linkedin.y} 
            active={activeSources.includes("linkedin") || activeSource === "linkedin"} 
          />
          <PixelMill 
            x={SOURCES.github.x} 
            y={SOURCES.github.y} 
            active={activeSources.includes("github") || activeSource === "github"} 
          />
          <PixelChurch 
            x={SOURCES.values.x} 
            y={SOURCES.values.y} 
            active={activeSources.includes("values") || activeSource === "values"} 
          />
          
          {/* Decorative elements */}
          <PixelTree x={140} y={220} variant="round" />
          <PixelTree x={480} y={224} variant="round" />
          <PixelBush x={260} y={232} />
          <PixelBush x={380} y={228} />
          <PixelFlowers x={180} y={244} />
          <PixelFlowers x={520} y={248} />
          
          {/* Building labels — rendered before boy so boy/bubble paints on top */}
          {Object.entries(SOURCES).map(([key, { x, y, label }]) => {
            const isActive = activeSources.includes(key) || activeSource === key;
            return (
              <g key={key}>
                <rect
                  x={x - 50}
                  y={y - 65}
                  width={100}
                  height={24}
                  rx={12}
                  ry={12}
                  fill={C.black}
                  opacity={isActive ? 0.85 : 0.65}
                />
                <text
                  x={x}
                  y={y - 50}
                  textAnchor="middle"
                  fontSize="10"
                  fontFamily="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Courier New', monospace"
                  fontWeight="bold"
                  fill={isActive ? C.yellow : C.cream}
                  style={{
                    letterSpacing: "0.6px",
                    filter: isActive ? "drop-shadow(0 0 4px #ffeb3b)" : "none",
                  }}
                >
                  {label}
                </text>
              </g>
            );
          })}

          <PixelBoy
            x={charPos.x}
            y={charPos.y}
            state={state}
            isOffTopic={isOffTopic}
            answer={response?.answer}
          />
        </svg>
      </div>

      {/* Status bar */}
      <div className="mt-4 flex justify-center">
        <div 
          className="px-6 py-2 flex items-center gap-3 rounded-lg"
          style={{
            background: C.black,
            border: `4px solid ${C.darkGray}`,
            fontFamily: "monospace",
          }}
        >
          <motion.div 
            className="w-3 h-3 rounded-full"
            style={{
              background: 
                state === "answering" ? C.lime :
                state === "thinking" ? C.peach :
                state === "walking" ? C.yellow :
                isOffTopic ? C.coral :
                C.lightGray,
            }}
            animate={state !== "idle" ? { scale: [1, 0.85, 1] } : {}}
            transition={{ duration: 1.4, repeat: Infinity }}
          />
          <span 
            className="text-xs uppercase tracking-widest font-bold"
            style={{ color: C.cream }}
          >
            {state === "thinking" ? "ADITYA IS THINKING..." :
             isOffTopic ? "OFF TOPIC" : state.toUpperCase()}
          </span>
        </div>
      </div>
    </div>
  )
}

// Pixel Cloud - blocky cloud shape
function PixelCloud({ x, y }: { x: number; y: number }) {
  return (
    <motion.g
      animate={{ x: [0, 20, 0] }}
      transition={{ duration: 30, repeat: Infinity, ease: "linear" }}
    >
      {/* Cloud made of pixel blocks */}
      <rect x={x} y={y + 4} width={8} height={8} fill={C.white} />
      <rect x={x + 8} y={y} width={16} height={12} fill={C.white} />
      <rect x={x + 24} y={y + 4} width={12} height={8} fill={C.white} />
      <rect x={x + 12} y={y + 8} width={8} height={8} fill={C.cream} opacity={0.5} />
    </motion.g>
  )
}

// Pixel Mountain
function PixelMountain({ x, y }: { x: number; y: number }) {
  return (
    <g opacity={0.4}>
      <polygon points={`${x},${y} ${x - 40},${y + 40} ${x + 40},${y + 40}`} fill="#6b8e7d" />
      <polygon points={`${x},${y} ${x},${y + 16} ${x + 24},${y + 40} ${x + 40},${y + 40}`} fill="#5a7d6c" />
      {/* Snow cap */}
      <polygon points={`${x},${y} ${x - 8},${y + 12} ${x + 8},${y + 12}`} fill={C.white} />
    </g>
  )
}

// Pixel Path
function PixelPath() {
  return (
    <g>
      {/* Main horizontal path */}
      <rect x={60} y={192} width={520} height={16} fill="#d4a574" />
      <rect x={60} y={192} width={520} height={4} fill="#e8c89c" />
      <rect x={60} y={204} width={520} height={4} fill="#b8956c" />
      
      {/* Pixel details on path */}
      {[100, 180, 280, 380, 460, 540].map((px, i) => (
        <rect key={i} x={px} y={196} width={4} height={4} fill="#c49464" />
      ))}
    </g>
  )
}

// Pixel Tree
function PixelTree({ x, y, variant }: { x: number; y: number; variant: "pine" | "round" }) {
  if (variant === "pine") {
    return (
      <g>
        {/* Trunk */}
        <rect x={x - 4} y={y + 20} width={8} height={16} fill="#6b4226" />
        <rect x={x - 4} y={y + 20} width={4} height={16} fill="#8b5a3c" />
        {/* Foliage layers */}
        <polygon points={`${x},${y - 20} ${x - 16},${y + 4} ${x + 16},${y + 4}`} fill="#2d9d50" />
        <polygon points={`${x},${y - 8} ${x - 12},${y + 12} ${x + 12},${y + 12}`} fill={C.green} />
        <polygon points={`${x},${y + 4} ${x - 8},${y + 20} ${x + 8},${y + 20}`} fill={C.lime} />
      </g>
    )
  }
  return (
    <g>
      {/* Trunk */}
      <rect x={x - 3} y={y + 8} width={6} height={12} fill="#6b4226" />
      {/* Round foliage */}
      <rect x={x - 12} y={y - 8} width={24} height={16} fill={C.green} />
      <rect x={x - 8} y={y - 12} width={16} height={4} fill={C.green} />
      <rect x={x - 8} y={y + 8} width={16} height={4} fill={C.green} />
      {/* Highlight */}
      <rect x={x - 8} y={y - 8} width={8} height={8} fill={C.lime} />
    </g>
  )
}

// Pixel Bush
function PixelBush({ x, y }: { x: number; y: number }) {
  return (
    <g>
      <rect x={x - 8} y={y} width={16} height={8} fill={C.green} />
      <rect x={x - 4} y={y - 4} width={8} height={4} fill={C.green} />
      <rect x={x - 4} y={y} width={4} height={4} fill={C.lime} />
    </g>
  )
}

// Pixel Flowers
function PixelFlowers({ x, y }: { x: number; y: number }) {
  return (
    <g>
      <rect x={x} y={y} width={4} height={4} fill={C.pink} />
      <rect x={x} y={y} width={2} height={2} fill={C.yellow} />
      <rect x={x + 10} y={y + 2} width={4} height={4} fill={C.lavender} />
      <rect x={x + 10} y={y + 2} width={2} height={2} fill={C.yellow} />
      <rect x={x + 5} y={y - 2} width={4} height={4} fill={C.coral} />
    </g>
  )
}

// BUILDINGS

function PixelCastle({ x, y, active }: { x: number; y: number; active: boolean }) {
  return (
    <motion.g
      animate={active ? { y: -4 } : { y: 0 }}
      transition={{ type: "spring", stiffness: 300 }}
    >
      {/* Shadow */}
      <rect x={x - 28} y={y + 44} width={56} height={4} fill={C.black} opacity={0.2} />
            {active && (
        <motion.g
          animate={{ opacity: [0.4, 0.7, 0.4] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        >
          <rect 
            x={x - 34} y={y + 38} 
            width={68} height={16} 
            rx={8} ry={8}
            fill={C.yellow}
            opacity={0.15}
            filter="url(#glow)"
          />
        </motion.g>
      )}
      
      {/* Base walls */}
      <rect x={x - 24} y={y + 8} width={48} height={36} fill="#a0a0a8" />
      <rect x={x - 24} y={y + 8} width={8} height={36} fill="#b8b8c0" />
      <rect x={x + 16} y={y + 8} width={8} height={36} fill="#888890" />
      
      {/* Left tower */}
      <rect x={x - 28} y={y - 12} width={16} height={56} fill="#a0a0a8" />
      <rect x={x - 28} y={y - 12} width={4} height={56} fill="#b8b8c0" />
      {/* Battlements */}
      <rect x={x - 28} y={y - 16} width={4} height={6} fill="#888890" />
      <rect x={x - 20} y={y - 16} width={4} height={6} fill="#888890" />
      
      {/* Right tower */}
      <rect x={x + 12} y={y - 12} width={16} height={56} fill="#909098" />
      <rect x={x + 12} y={y - 16} width={4} height={6} fill="#888890" />
      <rect x={x + 20} y={y - 16} width={4} height={6} fill="#888890" />
      
      {/* Center tower */}
      <rect x={x - 8} y={y - 24} width={16} height={40} fill="#b8b8c0" />
      <rect x={x - 8} y={y - 28} width={4} height={6} fill="#a0a0a8" />
      <rect x={x + 4} y={y - 28} width={4} height={6} fill="#a0a0a8" />
      
      {/* Flag */}
      <rect x={x} y={y - 44} width={2} height={18} fill="#6b4226" />
      <motion.g
        animate={active ? { x: [0, 2, 0] } : {}}
        transition={{ duration: 0.3, repeat: Infinity }}
      >
        <rect x={x + 2} y={y - 44} width={12} height={8} fill={C.coral} />
        <rect x={x + 2} y={y - 44} width={12} height={4} fill="#ff8888" />
      </motion.g>
      
      {/* Windows */}
      <rect x={x - 4} y={y - 16} width={8} height={12} fill={active ? C.yellow : C.darkGray} />
      <rect x={x - 22} y={y + 16} width={6} height={8} fill={active ? C.yellow : C.darkGray} />
      <rect x={x + 18} y={y + 16} width={6} height={8} fill={active ? C.yellow : C.darkGray} />
      
      {/* Door */}
      <rect x={x - 6} y={y + 28} width={12} height={16} fill="#4a3828" />
      <rect x={x - 6} y={y + 28} width={12} height={4} fill="#5a4838" />
      
      {/* Active glow */}
      {active && (
        <motion.rect
          x={x - 30} y={y + 44}
          width={60} height={8}
          fill={C.yellow}
          opacity={0.4}
          animate={{ opacity: [0.3, 0.5, 0.3] }}
          transition={{ duration: 1, repeat: Infinity }}
        />
      )}
    </motion.g>
  )
}

function PixelHouse({ x, y, active }: { x: number; y: number; active: boolean }) {
  return (
    <motion.g
      animate={active ? { y: -4 } : { y: 0 }}
      transition={{ type: "spring", stiffness: 300 }}
    >
      {/* Shadow */}
      <rect x={x - 24} y={y + 36} width={48} height={4} fill={C.black} opacity={0.2} />
            {active && (
        <motion.g
          animate={{ opacity: [0.4, 0.7, 0.4] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        >
          <rect 
            x={x - 34} y={y + 38} 
            width={68} height={16} 
            rx={8} ry={8}
            fill={C.yellow}
            opacity={0.15}
            filter="url(#glow)"
          />
        </motion.g>
      )}
      
      {/* Walls */}
      <rect x={x - 20} y={y + 4} width={40} height={32} fill="#e8d8c8" />
      <rect x={x - 20} y={y + 4} width={8} height={32} fill="#f4e8dc" />
      <rect x={x + 12} y={y + 4} width={8} height={32} fill="#d4c4b4" />
      
      {/* Roof */}
      <polygon points={`${x - 24},${y + 4} ${x},${y - 20} ${x + 24},${y + 4}`} fill={C.coral} />
      <polygon points={`${x},${y - 20} ${x + 24},${y + 4} ${x + 24},${y + 8} ${x},${y - 16}`} fill="#cc5555" />
      
      {/* Chimney */}
      <rect x={x + 8} y={y - 20} width={8} height={16} fill="#888890" />
      <rect x={x + 8} y={y - 20} width={8} height={4} fill="#a0a0a8" />
      {/* Smoke */}
      {active && (
        <>
          <motion.rect
            x={x + 10} y={y - 28} width={4} height={4}
            fill="#d0d0d0"
            animate={{ y: [0, -16], opacity: [0.8, 0] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
          <motion.rect
            x={x + 12} y={y - 24} width={4} height={4}
            fill="#e0e0e0"
            animate={{ y: [0, -20], opacity: [0.6, 0] }}
            transition={{ duration: 2, repeat: Infinity, delay: 0.5 }}
          />
        </>
      )}
      
      {/* Door */}
      <rect x={x - 6} y={y + 20} width={12} height={16} fill="#6b4226" />
      <rect x={x - 6} y={y + 20} width={12} height={4} fill="#8b5a3c" />
      <rect x={x + 2} y={y + 28} width={2} height={2} fill={C.yellow} />
      
      {/* Windows */}
      <rect x={x - 16} y={y + 12} width={8} height={8} fill={active ? C.yellow : C.blue} />
      <rect x={x - 16} y={y + 12} width={8} height={2} fill={C.white} opacity={0.5} />
      <rect x={x + 8} y={y + 12} width={8} height={8} fill={active ? C.yellow : C.blue} />
      <rect x={x + 8} y={y + 12} width={8} height={2} fill={C.white} opacity={0.5} />
      
      {active && (
        <motion.rect
          x={x - 26} y={y + 36}
          width={52} height={8}
          fill={C.peach}
          opacity={0.4}
          animate={{ opacity: [0.3, 0.5, 0.3] }}
          transition={{ duration: 1, repeat: Infinity }}
        />
      )}
    </motion.g>
  )
}

function PixelTower({ x, y, active }: { x: number; y: number; active: boolean }) {
  return (
    <motion.g
      animate={active ? { y: -4 } : { y: 0 }}
      transition={{ type: "spring", stiffness: 300 }}
    >
      <rect x={x - 20} y={y + 40} width={40} height={4} fill={C.black} opacity={0.2} />
            {active && (
        <motion.g
          animate={{ opacity: [0.4, 0.7, 0.4] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        >
          <rect 
            x={x - 34} y={y + 38} 
            width={68} height={16} 
            rx={8} ry={8}
            fill={C.yellow}
            opacity={0.15}
            filter="url(#glow)"
          />
        </motion.g>
      )}
      
      {/* Tower body */}
      <rect x={x - 14} y={y} width={28} height={40} fill={C.blue} />
      <rect x={x - 14} y={y} width={6} height={40} fill="#4dc4ff" />
      <rect x={x + 8} y={y} width={6} height={40} fill="#1a8dcc" />
      
      {/* Pointed roof */}
      <polygon points={`${x},${y - 28} ${x - 18},${y} ${x + 18},${y}`} fill="#1a8dcc" />
      <polygon points={`${x},${y - 28} ${x},${y} ${x + 18},${y}`} fill={C.blue} />
      
      {/* Flag */}
      <rect x={x - 1} y={y - 40} width={2} height={14} fill="#6b4226" />
      <motion.g
        animate={active ? { x: [0, 2, 0] } : {}}
        transition={{ duration: 0.3, repeat: Infinity }}
      >
        <rect x={x + 1} y={y - 40} width={10} height={6} fill="#0077b5" />
      </motion.g>
      
      {/* Windows */}
      <rect x={x - 4} y={y + 8} width={8} height={12} fill={active ? C.yellow : C.black} />
      <rect x={x - 4} y={y + 8} width={8} height={4} fill={active ? "#ffee99" : C.darkGray} />
      <rect x={x - 4} y={y + 26} width={8} height={8} fill={active ? C.yellow : C.black} />
      
      {active && (
        <motion.rect
          x={x - 22} y={y + 40}
          width={44} height={8}
          fill={C.blue}
          opacity={0.5}
          animate={{ opacity: [0.3, 0.6, 0.3] }}
          transition={{ duration: 1, repeat: Infinity }}
        />
      )}
    </motion.g>
  )
}

function PixelMill({ x, y, active }: { x: number; y: number; active: boolean }) {
  return (
    <motion.g
      animate={active ? { y: -4 } : { y: 0 }}
      transition={{ type: "spring", stiffness: 300 }}
    >
      <rect x={x - 18} y={y + 36} width={36} height={4} fill={C.black} opacity={0.2} />
      
      {/* Mill body - tapered */}
      <polygon points={`${x - 16},${y + 36} ${x - 10},${y - 4} ${x + 10},${y - 4} ${x + 16},${y + 36}`} fill="#e8e0d8" />
      <polygon points={`${x - 16},${y + 36} ${x - 10},${y - 4} ${x - 4},${y - 4} ${x - 8},${y + 36}`} fill="#f4ece4" />
      
      {/* Roof cap */}
      <polygon points={`${x},${y - 16} ${x - 12},${y - 4} ${x + 12},${y - 4}`} fill={C.coral} />
      
      {/* Door */}
      <rect x={x - 5} y={y + 22} width={10} height={14} fill="#6b4226" />
      
      {/* Window */}
      <rect x={x - 4} y={y + 6} width={8} height={8} fill={active ? C.yellow : C.blue} />
      
      {/* Windmill blades */}
      <motion.g
        style={{ transformOrigin: `${x}px ${y}px` }}
        animate={active ? { rotate: 360 } : {}}
        transition={active ? { duration: 4, repeat: Infinity, ease: "linear" } : {}}
      >
        {/* Vertical blade */}
        <rect x={x - 3} y={y - 36} width={6} height={36} fill="#c4a574" />
        <rect x={x - 3} y={y} width={6} height={32} fill="#c4a574" />
        {/* Horizontal blade */}
        <rect x={x - 36} y={y - 3} width={72} height={6} fill="#c4a574" />
        {/* Blade accents */}
        <rect x={x - 2} y={y - 32} width={4} height={12} fill="#d4b584" />
        <rect x={x - 2} y={y + 16} width={4} height={12} fill="#d4b584" />
        <rect x={x - 32} y={y - 2} width={12} height={4} fill="#d4b584" />
        <rect x={x + 16} y={y - 2} width={12} height={4} fill="#d4b584" />
      </motion.g>
      
      {/* Center hub */}
      <rect x={x - 4} y={y - 4} width={8} height={8} fill="#8b5a3c" />
      <rect x={x - 2} y={y - 2} width={4} height={4} fill="#6b4226" />
      
      {active && (
        <motion.rect
          x={x - 20} y={y + 36}
          width={40} height={8}
          fill={C.lime}
          opacity={0.5}
          animate={{ opacity: [0.3, 0.6, 0.3] }}
          transition={{ duration: 1, repeat: Infinity }}
        />
      )}
    </motion.g>
  )
}

function PixelChurch({ x, y, active }: { x: number; y: number; active: boolean }) {
  return (
    <motion.g
      animate={active ? { y: -4 } : { y: 0 }}
      transition={{ type: "spring", stiffness: 300 }}
    >
      <rect x={x - 22} y={y + 40} width={44} height={4} fill={C.black} opacity={0.2} />
      
      {/* Main building */}
      <rect x={x - 18} y={y + 4} width={36} height={36} fill={C.cream} />
      <rect x={x - 18} y={y + 4} width={6} height={36} fill={C.white} />
      <rect x={x + 12} y={y + 4} width={6} height={36} fill="#e4e4e4" />
      
      {/* Roof */}
      <polygon points={`${x - 22},${y + 4} ${x},${y - 12} ${x + 22},${y + 4}`} fill={C.lavender} />
      <polygon points={`${x},${y - 12} ${x + 22},${y + 4} ${x + 22},${y + 8} ${x},${y - 8}`} fill="#a0a0c8" />
      
      {/* Steeple */}
      <rect x={x - 6} y={y - 28} width={12} height={20} fill={C.cream} />
      <polygon points={`${x},${y - 44} ${x - 8},${y - 28} ${x + 8},${y - 28}`} fill="#a0a0c8" />
      
      {/* Cross */}
      <rect x={x - 2} y={y - 56} width={4} height={14} fill={C.yellow} />
      <rect x={x - 6} y={y - 52} width={12} height={4} fill={C.yellow} />
      
      {/* Bell */}
      {active && (
        <motion.rect
          x={x - 3} y={y - 22} width={6} height={8}
          fill={C.yellow}
          animate={{ rotate: [-8, 8, -8] }}
          transition={{ duration: 0.3, repeat: Infinity }}
          style={{ transformOrigin: `${x}px ${y - 28}px` }}
        />
      )}
      
      {/* Rose window */}
      <rect x={x - 6} y={y - 4} width={12} height={12} fill={active ? C.yellow : C.lavender} />
      <rect x={x - 4} y={y - 2} width={8} height={8} fill={active ? C.peach : "#d8d8f0"} />
      
      {/* Door */}
      <rect x={x - 5} y={y + 24} width={10} height={16} fill="#6b4226" />
      <rect x={x - 5} y={y + 24} width={10} height={4} fill="#8b5a3c" />
      
      {/* Side windows */}
      <rect x={x - 14} y={y + 14} width={4} height={10} fill={active ? C.yellow : C.lavender} />
      <rect x={x + 10} y={y + 14} width={4} height={10} fill={active ? C.yellow : C.lavender} />
      
      {active && (
        <motion.rect
          x={x - 24} y={y + 40}
          width={48} height={8}
          fill={C.lavender}
          opacity={0.5}
          animate={{ opacity: [0.3, 0.6, 0.3] }}
          transition={{ duration: 1, repeat: Infinity }}
        />
      )}
    </motion.g>
  )
}

function PixelBoy({
  x, y, state, isOffTopic, answer
}: {
  x: number; y: number; state: WorldState; isOffTopic: boolean; answer?: string
}) {
  const isThinking = state === "thinking"
  const isWalking = state === "walking"
  const isAnswering = state === "answering"

  // Animate position in SVG user units (avoids CSS px vs viewBox mismatch)
  const motX = useMotionValue(x)
  const motY = useMotionValue(y)
  const [svgX, setSvgX] = useState(x)
  const [svgY, setSvgY] = useState(y)

  useEffect(() => {
    const unsubX = motX.on("change", setSvgX)
    const unsubY = motY.on("change", setSvgY)
    return () => { unsubX(); unsubY() }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const dur = isWalking ? 2.0 : 0
    const cx = animate(motX, x, { duration: dur, ease: "easeInOut" })
    const cy = animate(motY, y, { duration: dur, ease: "easeInOut" })
    return () => { cx.stop(); cy.stop() }
  }, [x, y, isWalking]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <g transform={`translate(${svgX} ${svgY})`}>
      {/* Shadow */}
      <rect x={-8} y={20} width={16} height={4} fill={C.black} opacity={0.2} />

      {/* Bounce when walking */}
      <motion.g
        animate={isWalking ? { y: [0, -6, 0] } : { y: 0 }}
        transition={{ duration: 0.45, repeat: isWalking ? Infinity : 0 }}
      >
        {/* Legs */}
        <motion.g
          animate={isWalking ? { x: [-3.5, 3.5, -3.5] } : {}}
          transition={{ duration: 0.45, repeat: Infinity }}
        >
          <rect x={-6} y={12} width={4} height={8} fill="#4a5568" />
        </motion.g>
        <motion.g
          animate={isWalking ? { x: [3.5, -3.5, 3.5] } : {}}
          transition={{ duration: 0.45, repeat: Infinity }}
        >
          <rect x={2} y={12} width={4} height={8} fill="#374151" />
        </motion.g>

        {/* Body */}
        <rect x={-6} y={0} width={12} height={14} fill={C.blue} />
        <rect x={-6} y={0} width={4} height={14} fill="#4dc4ff" />
        <rect x={2} y={0} width={4} height={14} fill="#1a8dcc" />

        {/* Arms */}
        <motion.g
          animate={isWalking ? { rotate: [25, -25, 25] } : isAnswering ? { rotate: [-45, -35, -45] } : {}}
          transition={{ duration: 0.4, repeat: Infinity }}
          style={{ transformOrigin: "-8px 2px" }}
        >
          <rect x={-10} y={2} width={4} height={10} fill={C.peach} />
        </motion.g>
        <motion.g
          animate={isWalking ? { rotate: [-25, 25, -25] } : isAnswering ? { rotate: [45, 35, 45] } : {}}
          transition={{ duration: 0.4, repeat: Infinity }}
          style={{ transformOrigin: "8px 2px" }}
        >
          <rect x={6} y={2} width={4} height={10} fill="#e8b860" />
        </motion.g>

        {/* Head – tilt when thinking */}
        <motion.g
          animate={isThinking ? { rotate: [-6, 6, -6] } : { rotate: 0 }}
          transition={{ duration: 1.8, repeat: isThinking ? Infinity : 0 }}
          style={{ transformOrigin: "0px -8px" }}
        >
          <rect x={-8} y={-16} width={16} height={16} fill={C.peach} />
          <rect x={-8} y={-16} width={4} height={16} fill="#ffe090" />

          {/* Hair */}
          <rect x={-8} y={-20} width={16} height={8} fill="#5c3c24" />
          <rect x={-10} y={-16} width={4} height={4} fill="#5c3c24" />
          <rect x={6} y={-16} width={4} height={4} fill="#5c3c24" />
          <rect x={-6} y={-18} width={4} height={4} fill="#7a5434" />

          {/* Eyes – blink slower when thinking */}
          <motion.g
            animate={{ scaleY: [1, 0.1, 1] }}
            transition={{ duration: 0.12, repeat: Infinity, repeatDelay: isThinking ? 4 : 3.5 }}
          >
            <rect x={-6} y={-10} width={4} height={4} fill={C.black} />
            <rect x={2} y={-10} width={4} height={4} fill={C.black} />
            <rect x={-6} y={-10} width={2} height={2} fill={C.white} />
            <rect x={2} y={-10} width={2} height={2} fill={C.white} />
          </motion.g>

          {/* Blush */}
          <rect x={-10} y={-6} width={4} height={2} fill={C.pink} opacity={0.6} />
          <rect x={6} y={-6} width={4} height={2} fill={C.pink} opacity={0.6} />
        </motion.g>
      </motion.g>

      {/* Thinking bubble with ... */}
      {isThinking && (
        <motion.g
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
        >
          <rect x={-24} y={-48} width={48} height={28} rx={14} fill={C.black} opacity={0.8} />
          <rect x={-21} y={-45} width={42} height={22} rx={11} fill="#fffef0" />
          <text
            x={0}
            y={-28}
            textAnchor="middle"
            fontSize={16}
            fontFamily="monospace"
            fontWeight="bold"
            fill="#666"
          >
            ...
          </text>
        </motion.g>
      )}

      {/* Confusion when off-topic */}
      {isOffTopic && (
        <motion.g
          animate={{ y: [0, -4, 0] }}
          transition={{ duration: 0.4, repeat: Infinity }}
        >
          <text x={-6} y={-28} fontSize="14" fontWeight="bold" fontFamily="monospace" fill={C.coral}>?</text>
          <text x={4} y={-32} fontSize="10" fontWeight="bold" fontFamily="monospace" fill={C.pink}>?</text>
        </motion.g>
      )}

      {/* Speech bubble — pixel art style, above head */}
      {isAnswering && answer && (() => {
        const BW = 210, BH = 108
        const margin = 6
        // Clamp so bubble stays within viewBox [0..640] regardless of boy position
        const bx = Math.max(margin - svgX, Math.min(640 - margin - svgX - BW, -BW / 2))
        const by = -BH - 52  // bottom of bubble sits 52px above feet (above hair)
        return (
          <motion.g
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: "spring", stiffness: 280, damping: 22 }}
            style={{ transformOrigin: "0px -52px" }}
          >
            {/* Pixel border — outer black */}
            <rect x={bx - 3} y={by - 3} width={BW + 6} height={BH + 6} fill={C.black} />
            {/* Inner cream fill */}
            <rect x={bx} y={by} width={BW} height={BH} fill="#fffef0" />
            {/* Top highlight stripe */}
            <rect x={bx} y={by} width={BW} height={3} fill="rgba(255,255,255,0.75)" />
            {/* Tail — black outer */}
            <polygon points={`-5,${by + BH} 5,${by + BH} 0,${by + BH + 11}`} fill={C.black} />
            {/* Tail — cream inner */}
            <polygon points={`-2.5,${by + BH} 2.5,${by + BH} 0,${by + BH + 7}`} fill="#fffef0" />
            {/* Text content */}
            <foreignObject x={bx + 7} y={by + 7} width={BW - 14} height={BH - 14}>
              <div
                style={{
                  fontFamily: "JetBrains Mono, monospace",
                  fontSize: "9px",
                  lineHeight: "1.55",
                  color: "#1a1000",
                  wordBreak: "break-word",
                  overflow: "auto",
                  height: "100%",
                }}
              >
                {answer}
              </div>
            </foreignObject>
          </motion.g>
        )
      })()}
    </g>
  )
}
