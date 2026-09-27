#!/usr/bin/env python3
"""Build script to generate the official UAAF WebForge Project Kit (.zip).

This script packages the complete, hydrated UAAF Agentic Scaffold,
PRD architecture, design system, active task contracts, starter skeleton,
and multi-agent rules into a standalone .zip file.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path
import yaml

WORKSPACE = Path(__file__).resolve().parents[1]
OUTPUT_ZIP = WORKSPACE / "uaaf-webforge-project-kit.zip"
OUTPUT_DIR = WORKSPACE / "uaaf-webforge-kit"

def generate_kit() -> Path:
    # Clean previous build
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Copy official UAAF core scaffold
    scaffold_src = WORKSPACE / "scaffold"
    ai_dst = OUTPUT_DIR / ".ai"
    shutil.copytree(scaffold_src / ".ai", ai_dst)

    # Hydrate .ai/manifest.yaml
    manifest_path = ai_dst / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    manifest["project"] = {
        "name": "UAAF WebForge",
        "type": "saas_platform",
        "description": "Public SaaS platform converting website ideas into deterministic UAAF agent-ready project kits.",
        "maturity": "greenfield",
        "status": "active"
    }
    manifest["profile"] = "standard"
    manifest["capabilities"] = {
        "product": True,
        "frontend": True,
        "backend": True,
        "api": True,
        "database": False,
        "ui": True,
        "design_system": True,
        "security": True,
        "performance": True,
        "deployment": True,
        "mobile": False,
        "data": False,
        "testing": True,
        "infrastructure": True
    }
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    # 2. Write AGENTS.md
    (OUTPUT_DIR / "AGENTS.md").write_text("""# UAAF Agent Kernel — UAAF WebForge

Read `.ai/manifest.yaml`, `.ai/core/*`, `.ai/memory/STATE.md`, and `.ai/INDEX.md` before consequential work.

## Golden Rules
- Understand before changing.
- Inspect before inventing.
- Search before creating.
- Reuse → extend → modify → create.
- Preserve user intent: Build UAAF WebForge as a high-performance, stateless SaaS web tool.
- Zero-Log Privacy: Never store user prompts/conversations in server databases.
- Strictly adhere to active task perimeter in `.ai/tasks/active/`.
- Framework lifecycle records (`.ai/memory/STATE.md`, `.ai/evidence/`, `.ai/tasks/`) are always authorized for status, blockers, and handoffs without violating task `permitted_files`.
- Out-of-scope defects or environment anomalies must be recorded in `.ai/memory/STATE.md` (or via `python tools/uaf.py blocker`), not left solely in chat.
- Verifiable quality: Execute `python tools/uaf.py check` before claiming completion.

## Active Project Roadmap
1. `TASK-0001`: Backend FastAPI server, Gemini Flash client, and guardrails.
2. `TASK-0002`: SaaS Landing Page (Hero, 3-step value prop, UAAF badges, FAQ).
3. `TASK-0003`: Split-Screen Studio UI (Chat with 8-turn counter, live blueprint canvas).
4. `TASK-0004`: Dynamic in-memory UAAF ZIP packager & scaffold hydrator.
5. `TASK-0005`: Dockerfile, render.yaml, zero-cost cloud deploy verification.
""", encoding="utf-8")

    # 3. Write CLAUDE.md
    (OUTPUT_DIR / "CLAUDE.md").write_text("""# Claude Code Directives — UAAF WebForge

This project is governed by the Universal AI Agent Framework (UAAF v3.3).
Before making any modifications:
1. Review `.ai/manifest.yaml` and `.ai/tasks/active/`.
2. Find the active task (e.g. `TASK-0001-...yaml`).
3. Only modify files listed within `scope.permitted_files` (framework records in `.ai/` are always permitted for logging status and blockers).
4. If a pre-existing out-of-scope defect is found, record it in `.ai/memory/STATE.md` (`python tools/uaf.py blocker "<message>"`); do not silently touch out-of-scope files.
5. Ensure all Python code adheres to FastAPI async best practices and PEP 8.
6. Ensure all frontend code is clean Vanilla HTML5, CSS3, and ES6 JavaScript (no heavy node_modules).
7. Run `python tools/uaf.py check` to verify deliverables before handoff.
""", encoding="utf-8")

    # 4. Write .cursorrules
    (OUTPUT_DIR / ".cursorrules").write_text("""# Cursor Composer Rules for UAAF WebForge

You are an expert fullstack software engineer building UAAF WebForge.
Core principles:
- Follow UAAF Golden Rules defined in AGENTS.md.
- Check active task contracts in .ai/tasks/active/ before writing code.
- Backend: FastAPI, Uvicorn, Python 3.11+, stateless async handlers.
- Frontend: Vanilla HTML5/CSS3/ES6+, glassmorphism dark theme (hsl(225, 25%, 7%) base), zero node_modules.
- Security: Never expose GEMINI_API_KEY to frontend. Strictly enforce topic guardrails in AI consultant.
- Quality: All HTML must be semantically valid with proper accessibility attributes.
""", encoding="utf-8")

    # 5. Write README.md
    (OUTPUT_DIR / "README.md").write_text("""# 🚀 UAAF WebForge — Project Kit

> **Scaffolded by [Universal AI Agent Framework (UAAF)](https://github.com/lunarcwhite/agentic-workflow-framework)**  
> *Ubah Ide Websitemu Menjadi Paket Kerja Agentic AI Siap Eksekusi.*

---

## ⚡ Cara Menjalankan Agen AI (Aktivasi 1-Baris)

Buka folder proyek ini di AI tool pilihan Anda, lalu kirimkan instruksi pertama berikut:

### Jika Menggunakan Cursor:
> `Analisa folder ini, pelajari AGENTS.md dan prd/ARCHITECTURE.md, lalu mulai kerjakan TASK-0001.`

### Jika Menggunakan Claude Code (Terminal):
```bash
claude
> Read AGENTS.md and start implementing TASK-0001 according to its task contract.
```

### Jika Menggunakan Google Antigravity:
> `Baca file AGENTS.md dan kontrak tugas .ai/tasks/active/TASK-0001-*.yaml, lalu mulai implementasikan.`

---

## 🏛️ Arsitektur Proyek
- `app/`: Backend FastAPI, service Gemini AI dengan guardrail ketat, dan in-memory ZIP packager.
- `static/`: Frontend Vanilla HTML/CSS/JS (SaaS Landing Page + Split-Screen Studio).
- `prd/`: Dokumen PRD Arsitektur (`ARCHITECTURE.md`) dan Sistem Desain (`DESIGN-SYSTEM.md`).
- `.ai/`: Tata kelola agen UAAF, memory state, dan kontrak tugas deterministik (`TASK-0001` s/d `TASK-0005`).
- `tools/`: Runtime & validator UAAF (`uaf.py`, `uaf_check.py`, `uaf_seo.py`, `uaf_blocker.py`) untuk verifikasi mandiri dan pencatatan blocker.

---

## 🚀 Cara Menjalankan Lokal
1. Salin `.env.example` ke `.env` dan masukkan `GEMINI_API_KEY`:
   ```bash
   cp .env.example .env
   ```
2. Install dependensi:
   ```bash
   pip install -r requirements.txt
   ```
3. Jalankan server:
   ```bash
   python app/main.py
   ```
4. Buka di browser: `http://localhost:8000`

---

## 🌐 Deploy Gratis ke Cloud (Render.com)
1. Push folder ini ke repositori GitHub Anda.
2. Buka [Render.com](https://render.com), pilih **New Web Service**, dan hubungkan repo ini.
3. Masukkan Environment Variable: `GEMINI_API_KEY`.
4. Render otomatis menggunakan `render.yaml` / `Dockerfile` bawaan proyek ini!
""", encoding="utf-8")

    # 6. Create prd/ directory
    prd_dir = OUTPUT_DIR / "prd"
    prd_dir.mkdir(parents=True, exist_ok=True)

    (prd_dir / "ARCHITECTURE.md").write_text("""# UAAF WebForge — Product Requirements Document (PRD)

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
""", encoding="utf-8")

    (prd_dir / "DESIGN-SYSTEM.md").write_text("""# UAAF WebForge — Visual Design System

## 1. Aesthetic Direction
- **Theme**: Ultra-sleek Dark Glassmorphism.
- **Background**: Deep Midnight (`hsl(225, 25%, 7%)`).
- **Surface Cards**: Translucent Glass (`hsla(225, 20%, 12%, 0.75)` with `backdrop-filter: blur(16px)`).
- **Primary Accent**: Electric Indigo / Vibrant Purple (`hsl(250, 84%, 65%)`).
- **Success / CTA Accent**: Emerald Green (`hsl(160, 84%, 45%)`).
- **Border**: Subtle Glass Border (`hsla(225, 15%, 25%, 0.5)`).

## 2. Typography
- **Heading Font**: `Plus Jakarta Sans`, sans-serif (Weights: 600, 700, 800).
- **Body Font**: `Inter`, sans-serif (Weights: 400, 500).
- **Code / Tokens Font**: `JetBrains Mono`, monospace.

## 3. Image Guidelines for Generated Websites
- Dilarang keras menggunakan placeholder abu-abu generik (`via.placeholder.com`).
- Wajib menggunakan curated Unsplash links dengan keyword industri spesifik (misal: `https://images.unsplash.com/photo-...?auto=format&fit=crop&w=1200&q=80`).
""", encoding="utf-8")

    # 7. Write task contracts in .ai/tasks/active/
    tasks_dir = ai_dst / "tasks" / "active"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    def write_task_contract(filename: str, task_dict: dict) -> None:
        integrity = {
            "intent_hash": hashlib.sha256(json.dumps(task_dict["intent"], sort_keys=True).encode()).hexdigest(),
            "requirements_hash": hashlib.sha256(json.dumps(task_dict["requirements"], sort_keys=True).encode()).hexdigest(),
            "constraints_hash": hashlib.sha256(json.dumps(task_dict["constraints"], sort_keys=True).encode()).hexdigest(),
            "non_goals_hash": hashlib.sha256(json.dumps(task_dict["non_goals"], sort_keys=True).encode()).hexdigest(),
        }
        task_dict["integrity"] = integrity
        (tasks_dir / filename).write_text(yaml.safe_dump(task_dict, sort_keys=False), encoding="utf-8")

    # TASK-0001
    write_task_contract("TASK-0001-backend-fastapi-server.yaml", {
        "id": "TASK-0001",
        "type": "FEATURE",
        "status": "PLANNED",
        "assigned_role": "backend_specialist",
        "assigned_agent": "AGENT-BACKEND",
        "role_title": "Backend & AI Engine Specialist",
        "scope": {
            "level": "FEATURE",
            "domains": ["backend", "api", "ai"],
            "risk": "LOW",
            "permitted_files": [
                "app/main.py",
                "app/config.py",
                "app/services/consultant.py",
                "requirements.txt",
                ".env.example",
            ],
        },
        "intent": {
            "statement": "Bangun server FastAPI dengan endpoint /api/chat yang terintegrasi ke Gemini Flash dan memiliki guardrail ketat.",
            "source": "user_webforge_spec",
            "confidence": "HIGH",
        },
        "requirements": [
            "Buat server FastAPI asinkron dengan CORS middleware.",
            "Implementasikan client Gemini Flash dengan system prompt konsultan produk UAAF.",
            "Terapkan guardrail ketat: tolak pertanyaan di luar perancangan website secara santun.",
            "Terapkan batasan 8 putaran chat per sesi.",
            "Sediakan fallback simulator cerdas jika GEMINI_API_KEY belum dipasang di .env.",
        ],
        "constraints": [
            "Zero-Log Privacy: Dilarang menyimpan atau mencatat prompt/konten chat user di database server.",
            "Maksimal 8 turn obrolan per sesi.",
            "Hanya boleh memodifikasi file dalam permitted_files.",
        ],
        "non_goals": [
            "Tidak membuat UI landing page atau frontend studio (cakupan TASK-0002 & TASK-0003).",
            "Tidak membuat packaging file ZIP (cakupan TASK-0004).",
        ],
        "acceptance_criteria": [
            "Endpoint GET /api/health mengembalikan status OK.",
            "Endpoint POST /api/chat merespons dalam format JSON (message, blueprint delta, turn_count).",
            "Server berjalan mulus tanpa crash.",
        ],
        "verification": [
            "python -m pytest tests/test_backend.py || python app/main.py --check",
        ],
    })

    # TASK-0002
    write_task_contract("TASK-0002-frontend-saas-landing-page.yaml", {
        "id": "TASK-0002",
        "type": "FEATURE",
        "status": "PLANNED",
        "assigned_role": "landing_page_pro",
        "assigned_agent": "AGENT-LANDING-PAGE",
        "role_title": "SaaS Landing Page Specialist",
        "scope": {
            "level": "FEATURE",
            "domains": ["frontend", "copywriting", "ui"],
            "risk": "LOW",
            "permitted_files": [
                "static/index.html",
                "static/css/landing.css",
            ],
        },
        "intent": {
            "statement": "Buat halaman depan SaaS Landing Page yang memukau untuk UAAF WebForge.",
            "source": "user_webforge_spec",
            "confidence": "HIGH",
        },
        "requirements": [
            "Hero section dengan H1 kuat, subhead persuasif, dan badge 'Powered by UAAF v3.3'.",
            "3-Step How It Works visual guide.",
            "Preview isi paket UAAF Project Kit yang akan didownload pengguna.",
            "Lencana 'Zero-Log Privacy: Ide bisnis Anda 100% aman'.",
            "FAQ interaktif dengan Schema.org FAQPage JSON-LD.",
            "Tombol CTA utama 'Mulai Rancang Websitemu' yang membuka Studio.",
        ],
        "constraints": [
            "Gunakan Vanilla HTML5, CSS3, dan ES6 tanpa framework JavaScript eksternal (zero node_modules).",
            "Patuhi sistem desain pada prd/DESIGN-SYSTEM.md.",
            "Hanya boleh memodifikasi file dalam permitted_files.",
        ],
        "non_goals": [
            "Tidak mengimplementasikan interaktivitas live chat studio (cakupan TASK-0003).",
            "Tidak mengimplementasikan endpoint backend (cakupan TASK-0001).",
        ],
        "acceptance_criteria": [
            "Tampilan responsif di mobile dan desktop.",
            "Semua heading dan elemen visual selaras dengan prd/DESIGN-SYSTEM.md.",
        ],
        "verification": [
            "python tools/uaf_seo.py audit static/ --threshold 90",
        ],
    })

    # TASK-0003
    write_task_contract("TASK-0003-frontend-split-screen-studio.yaml", {
        "id": "TASK-0003",
        "type": "FEATURE",
        "status": "PLANNED",
        "assigned_role": "frontend_specialist",
        "assigned_agent": "AGENT-FRONTEND",
        "role_title": "Split-Screen Studio Specialist",
        "scope": {
            "level": "FEATURE",
            "domains": ["frontend", "javascript", "interactivity"],
            "risk": "LOW",
            "permitted_files": [
                "static/css/studio.css",
                "static/js/app.js",
                "static/index.html",
            ],
        },
        "intent": {
            "statement": "Implementasikan antarmuka Split-Screen Studio (chat di kiri, live blueprint di kanan).",
            "source": "user_webforge_spec",
            "confidence": "HIGH",
        },
        "requirements": [
            "Panel Kiri: Chat stream interaktif, preset chips, suggestion pills, dan indikator kuota sesi (x/8).",
            "Panel Kanan: Live Blueprint Canvas (Executive summary, HSL palette swatches dengan shuffle, checklist 12-section, sitemap Single/Multi-Page, UAAF task roster).",
            "Dukungan interaktivitas dua arah: user bisa toggle section dan shuffle warna di panel kanan.",
            "Penyimpanan riwayat obrolan dan blueprint di localStorage.",
            "Tombol glowing 'Download Agent-Ready Project Kit (.zip)'.",
        ],
        "constraints": [
            "Gunakan Vanilla JavaScript murni dan localStorage untuk persistensi state client.",
            "Patuhi batasan 8 putaran chat per sesi.",
            "Hanya boleh memodifikasi file dalam permitted_files.",
        ],
        "non_goals": [
            "Tidak membangun endpoint AI backend baru (menggunakan API dari TASK-0001).",
            "Tidak membuat packaging ZIP di server (cakupan TASK-0004).",
        ],
        "acceptance_criteria": [
            "Chatbot merespons interaktif dan blueprint di kanan ter-update real-time.",
            "Refresh browser mempertahankan state sesi.",
        ],
        "verification": [
            "Buka di browser dan uji obrolan dari Turn 1 hingga Turn 8.",
        ],
    })

    # TASK-0004
    write_task_contract("TASK-0004-zip-packaging-and-scaffold-hydration.yaml", {
        "id": "TASK-0004",
        "type": "FEATURE",
        "status": "PLANNED",
        "assigned_role": "engineer",
        "assigned_agent": "AGENT-ENGINEER",
        "role_title": "Packaging & Hydration Engineer",
        "scope": {
            "level": "FEATURE",
            "domains": ["backend", "packaging", "uaaf"],
            "risk": "MEDIUM",
            "permitted_files": [
                "app/services/packager.py",
                "app/main.py",
            ],
        },
        "intent": {
            "statement": "Bangun service pembuat file ZIP in-memory yang meng-hydrate template UAAF sesuai hasil konsultasi.",
            "source": "user_webforge_spec",
            "confidence": "HIGH",
        },
        "requirements": [
            "Gunakan io.BytesIO dan zipfile bawaan Python (stateless, zero-log di disk).",
            "Salin dan hydrate .ai/manifest.yaml dengan data proyek website user.",
            "Generate prd/ARCHITECTURE.md dan prd/DESIGN-SYSTEM.md sesuai pilihan warna/section user.",
            "Generate task contracts TASK-0001 s/d TASK-0005 untuk website user.",
            "Sertakan src/index.html (dan halaman multi-page jika diminta) + src/styles/tokens.css.",
            "Sertakan validator tools/uaf.py, tools/uaf_check.py, tools/uaf_seo.py, dan tools/uaf_blocker.py serta vercel.json.",
            "Beri nama file ZIP dinamis: [project-slug]-uaaf-kit.zip.",
        ],
        "constraints": [
            "Packaging ZIP harus diproses sepenuhnya in-memory menggunakan io.BytesIO dan zipfile tanpa menyimpan file sementara ke disk.",
            "Paket ZIP wajib menyertakan uaf.py, uaf_check.py, uaf_seo.py, dan uaf_blocker.py di folder tools/ agar verifikasi mandiri dan pencatatan blocker berfungsi.",
            "Hanya boleh memodifikasi file dalam permitted_files.",
        ],
        "non_goals": [
            "Tidak membuat antarmuka UI baru.",
            "Tidak membuat database persisten.",
        ],
        "acceptance_criteria": [
            "Endpoint POST /api/export-zip menghasilkan file ZIP valid dengan status 200.",
            "File ZIP yang diekstrak lolos validasi uaf check.",
        ],
        "verification": [
            "python -c 'from app.services.packager import test_packager; test_packager()'",
        ],
    })

    # TASK-0005
    write_task_contract("TASK-0005-docker-cloud-deploy-and-verification.yaml", {
        "id": "TASK-0005",
        "type": "FEATURE",
        "status": "PLANNED",
        "assigned_role": "verifier",
        "assigned_agent": "AGENT-VERIFIER",
        "role_title": "DevOps & Quality Assurance Specialist",
        "scope": {
            "level": "FEATURE",
            "domains": ["devops", "cloud", "qa"],
            "risk": "LOW",
            "permitted_files": [
                "Dockerfile",
                "render.yaml",
                "tests/*",
            ],
        },
        "intent": {
            "statement": "Sediakan konfigurasi cloud deployment dan verifikasi kualitas akhir.",
            "source": "user_webforge_spec",
            "confidence": "HIGH",
        },
        "requirements": [
            "Buat Dockerfile multi-stage ringan berbasis python:3.11-slim.",
            "Buat render.yaml untuk 1-klik deploy di Render.com.",
            "Pastikan uaf seo audit static/ menghasilkan skor 100/100.",
        ],
        "constraints": [
            "Docker image harus seringan mungkin menggunakan base python:3.11-slim.",
            "Semua audit verifikasi UAAF dan SEO wajib lulus 100%.",
            "Hanya boleh memodifikasi file dalam permitted_files.",
        ],
        "non_goals": [
            "Tidak menambah fitur fungsional baru ke aplikasi.",
        ],
        "acceptance_criteria": [
            "Docker build sukses tanpa error.",
            "UAAF audit menghasilkan status PASS.",
        ],
        "verification": [
            "python tools/uaf.py check",
        ],
    })

    # 8. Copy tools (UAAF runtime & validator)
    tools_dst = OUTPUT_DIR / "tools"
    tools_dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(WORKSPACE / "tools" / "uaf_check.py", tools_dst / "uaf_check.py")
    shutil.copy2(WORKSPACE / "tools" / "uaf_blocker.py", tools_dst / "uaf_blocker.py")
    shutil.copy2(WORKSPACE / "tools" / "uaf_seo.py", tools_dst / "uaf_seo.py")
    shutil.copy2(WORKSPACE / "tools" / "uaf.py", tools_dst / "uaf.py")

    # 9. Create starter skeleton files
    app_dir = OUTPUT_DIR / "app"
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "__init__.py").write_text('"""UAAF WebForge Backend Application."""\\n', encoding="utf-8")
    
    # app/config.py
    (app_dir / "config.py").write_text("""import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
IS_DEMO_MODE = not bool(GEMINI_API_KEY)
""", encoding="utf-8")

    # app/main.py skeleton
    (app_dir / "main.py").write_text("""import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.config import HOST, PORT, IS_DEMO_MODE

app = FastAPI(title="UAAF WebForge API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "UAAF WebForge", "demo_mode": IS_DEMO_MODE}

# Mount static files
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    print(f"🚀 Starting UAAF WebForge on http://{HOST}:{PORT}")
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
""", encoding="utf-8")

    # static starter
    static_dir = OUTPUT_DIR / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    (static_dir / "index.html").write_text("""<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>UAAF WebForge — Ubah Ide Jadi Alur Kerja Agentic AI Siap Eksekusi</title>
  <meta name="description" content="Konsultan AI interaktif yang mengubah ide website Anda menjadi UAAF Project Kit lengkap dengan kontrak tugas deterministik untuk Cursor, Claude Code, dan Antigravity.">
  <link rel="stylesheet" href="css/style.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Plus+Jakarta+Sans:wght@600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
</head>
<body>
  <!-- UAAF WebForge Starter Scaffold -->
  <header>
    <h1>UAAF WebForge</h1>
  </header>
  <main>
    <p>Selamat datang di UAAF WebForge.</p>
  </main>
  <script src="js/app.js"></script>
</body>
</html>
""", encoding="utf-8")

    # Cloud deployment configs
    (OUTPUT_DIR / "requirements.txt").write_text("""fastapi>=0.110.0
uvicorn>=0.28.0
httpx>=0.27.0
pyyaml>=6.0.1
python-dotenv>=1.0.0
pydantic>=2.6.0
""", encoding="utf-8")

    (OUTPUT_DIR / ".env.example").write_text("""# UAAF WebForge Environment Variables
GEMINI_API_KEY=your_gemini_api_key_here
PORT=8000
HOST=0.0.0.0
""", encoding="utf-8")

    (OUTPUT_DIR / ".gitignore").write_text(""".env
__pycache__/
*.pyc
.pytest_cache/
*.zip
.venv/
""", encoding="utf-8")

    (OUTPUT_DIR / "Dockerfile").write_text("""FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "app/main.py"]
""", encoding="utf-8")

    (OUTPUT_DIR / "render.yaml").write_text("""services:
  - type: web
    name: uaaf-webforge
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python app/main.py
    envVars:
      - key: GEMINI_API_KEY
        sync: false
      - key: PORT
        value: 10000
""", encoding="utf-8")

    (OUTPUT_DIR / "vercel.json").write_text("""{
  "version": 2,
  "builds": [
    { "src": "app/main.py", "use": "@vercel/python" }
  ],
  "routes": [
    { "src": "/(.*)", "dest": "app/main.py" }
  ]
}
""", encoding="utf-8")

    # 10. Self-validation: Ensure generated kit satisfies UAAF conformance validation
    if str(WORKSPACE / "tools") not in sys.path:
        sys.path.insert(0, str(WORKSPACE / "tools"))
    import uaf_check
    check_errors, check_warnings, _ = uaf_check.check(OUTPUT_DIR, level="standard")
    if check_errors:
        raise RuntimeError(f"Generated kit failed UAAF conformance validation: {check_errors}")
    print(f"UAAF conformance check passed (0 errors, {len(check_warnings)} warnings)")

    # 11. Compress into ZIP file
    print(f"Compressing into {OUTPUT_ZIP}...")
    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(OUTPUT_DIR):
            for file in files:
                file_path = Path(root) / file
                archive_name = file_path.relative_to(OUTPUT_DIR)
                zf.write(file_path, archive_name)

    print(f"Successfully generated {OUTPUT_ZIP} ({OUTPUT_ZIP.stat().st_size} bytes)")
    return OUTPUT_ZIP

if __name__ == "__main__":
    generate_kit()
