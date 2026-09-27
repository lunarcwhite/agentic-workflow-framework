# 🚀 UAAF WebForge — Project Kit

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
