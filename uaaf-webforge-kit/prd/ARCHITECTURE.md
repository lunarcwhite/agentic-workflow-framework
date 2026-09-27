# UAAF WebForge — Product Requirements Document (PRD)

## 1. Executive Summary
UAAF WebForge adalah platform SaaS publik yang menjembatani ide website mentah dari pengguna menjadi paket kerja deterministik (UAAF Project Kit) yang siap dieksekusi oleh AI coding agents (Cursor, Claude Code, Antigravity, Windsurf).

## 2. Key User Flow
1. **Landing Page**: Pengunjung mempelajari nilai tambah, 3 langkah mudah, zero-log privacy, dan mengklik "Mulai Rancang Website".
2. **Consultation Studio**:
   - Split-Screen Layout: Kiri chat konsultasi, Kanan Live Blueprint Canvas.
   - AI Consultant mewawancarai kebutuhan bisnis, target persona, rekomendasi stack adaptif, dan rekomendasi hosting gratis.
   - Batasan sesi: Maksimal 8 putaran chat.
   - Guardrail: AI menolak pertanyaan di luar perancangan website.
3. **Live Blueprint Preview**:
   - Executive summary, sitemap (Single/Multi-page), palet warna HSL interaktif, dan UAAF task contracts.
4. **1-Click Download**:
   - Menghasilkan file ZIP in-memory yang berisi template UAAF terhidrasi lengkap.

## 3. Tech Stack
- **Backend**: Python 3.11+, FastAPI, Uvicorn, httpx, PyYAML, python-dotenv.
- **Frontend**: Semantic HTML5, Modern Vanilla CSS (Glassmorphism, Dark Palette), ES6+ JavaScript.
- **AI Engine**: Google Gemini Flash via REST API dengan fallback smart simulation.
- **Deployment**: Docker, Render.com (`render.yaml`), Railway.
