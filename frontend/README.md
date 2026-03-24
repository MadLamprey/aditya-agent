# Project AMA — Frontend

A Next.js 14 web interface for the AMA interview assistant. Renders an isometric pixel-art world where a pixel character walks to the relevant knowledge source and displays the answer in a speech bubble.

## Prerequisites

- Node.js 18+
- The FastAPI backend running (see root `README.md`)

## Setup

```bash
cd frontend
npm install
```

## Environment

Create a `.env.local` file in this directory:

```
BACKEND_URL=http://localhost:8000
```

`BACKEND_URL` is the address of the FastAPI backend. The default (`http://localhost:8000`) is correct if you are running the backend locally. You only need to change this if the backend is on a different host or port.

> The `.env.local` file is already present in the repository with the default value.

## Running

**Development** (hot reload):
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

**Production build:**
```bash
npm run build
npm run start
```

## How it works

The frontend does not call the backend directly. All requests go through a Next.js API proxy route at `/api/ask` (`app/api/ask/route.ts`), which forwards to `BACKEND_URL/ask`. This keeps the backend URL server-side and avoids CORS issues.

## Project structure

```
frontend/
  app/
    page.tsx            Main page — layout, state machine, query handler
    layout.tsx          Root layout — font loading, metadata
    globals.css         Global styles and CSS classes
    api/ask/route.ts    API proxy to FastAPI backend
  components/
    IsometricWorld.tsx  SVG pixel-art world + PixelBoy character
    InputSurface.tsx    Question input form
    ModeSwitch.tsx      Audience mode toggle (General / Technical / Behavioral)
```

## Audience modes

The mode toggle in the top-right corner sets the `audience` field sent to the backend:

| Mode | Effect |
|------|--------|
| General | Balanced answer, no assumed technical background |
| Technical | Emphasises depth, trade-offs, implementation details |
| Behavioral | Emphasises values, working style, soft-skills framing |
