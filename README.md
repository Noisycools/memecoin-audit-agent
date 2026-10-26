# Memecoin Audit Agent (GMGN Scout + 9router AI Analyst)

Sistem pemindaian, audit teknis, dan penilaian kelayakan memecoin **Solana** secara otomatis dengan saringan dua tahap:
1. **Tahap 1 — Auditor Deterministik & GMGN Scout:** Memindai token terbaru/boosted dari DexScreener setiap 60 detik, menarik laporan keamanan kontrak dan top holder dari RugCheck, lalu menghitung **Skor Risiko Deterministik (0–100)** dan verdict (`AVOID`, `HIGH RISK`, `WATCH`, `PROMISING`).
2. **Tahap 2 — Analisis Prospek & Kesehatan Pasar via AI Lokal (`9router`):** Untuk koin yang lolos saringan ketat (`PROMISING` dan `WATCH`, maupun audit manual), sistem memanggil `9router` lokal (`http://localhost:20128/v1`, model `gemini-3.8-flash-high`) untuk memvonis apakah koin **Sehat (`HEALTHY`) / Meragukan (`MIXED`) / Tidak Sehat (`UNHEALTHY`)**, mendeteksi kualitas **Real Buyer (`ORGANIC`)** vs bot/insider, menguji ketahanan likuiditas terhadap porsi Top 10 holder, dan menyusun skenario keputusan (*Bull Case*, *Red Flag*, dan *Invalidation Trigger*).

---

## Cara Menjalankan Proyek

### 1. Menjalankan Langsung di Lokal (Windows / macOS / Linux)

Pastikan `9router` sudah aktif di `http://localhost:20128` dengan model `gemini-3.8-flash-high`.

**Backend (FastAPI + Scanner Worker di Port `8004`):**
```powershell
python -m pip install --no-build-isolation -e "backend[dev]"
python -m backend
# atau:
python -m uvicorn backend.api.main:create_app --factory --host 0.0.0.0 --port 8004
```

**CLI Audit Manual:**
```powershell
# Ambil data mentah DexScreener + RugCheck
python -m backend.cli fetch <SOLANA_MINT_ADDRESS>

# Jalankan audit lengkap + analisis 9router AI
python -m backend.cli audit <SOLANA_MINT_ADDRESS>
```

**Frontend (Next.js Live Dashboard di Port `3003`):**
```powershell
cd frontend
npm install
npm run dev
```
Buka dashboard di `http://localhost:3003`.

### 2. Menjalankan dengan Docker Compose (Satu Perintah)

```bash
cp .env.example .env
docker compose up --build
```

---

## Variabel Environment (`.env`)

| Variabel | Default | Fungsi |
| --- | --- | --- |
| `BACKEND_PORT` | `8004` | Port HTTP untuk server FastAPI backend |
| `FRONTEND_PORT` | `3003` | Port HTTP untuk dashboard Next.js frontend |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8004` | URL API backend yang diakses oleh frontend |
| `DATABASE_URL` | `sqlite+aiosqlite:///./memecoin_audit.db` | Lokasi database SQLite (mode WAL) atau PostgreSQL |
| `NINEROUTER_BASE_URL` | `http://localhost:20128/v1` | Endpoint OpenAI-compatible untuk `9router` lokal |
| `NINEROUTER_MODEL` | `gemini-3.8-flash-high` | Nama model AI di `9router` |
| `NINEROUTER_API_KEY` | `local-9router` | API key opsional untuk `9router` |
| `RUGCHECK_API_KEY` | *(kosong)* | API key opsional untuk header `X-API-KEY` RugCheck |
| `HELIUS_API_KEY` / `SOLANA_RPC_URL` | *(kosong)* | RPC Solana opsional untuk deteksi wash trade per wallet |
| `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID` | *(kosong)* | Notifikasi alert opsional via Bot Telegram |

---

## Cara Menambahkan Chain Baru

Seluruh pengambilan data pasar dan pemeriksaan keamanan kontrak diabstraksikan melalui class `ChainAdapter` di `backend/adapters/base.py`:
1. Buat file adapter baru di `backend/adapters/<chain>.py` (mis. `base_chain.py` atau `bsc.py`) yang mengimplementasikan `discover_tokens()` dan `enrich_token()`.
2. Daftarkan chain tersebut ke `active_chains` di `config/thresholds.yaml`.

---

## Contoh Laporan JSON Per Token

```json
{
  "token": {
    "chain": "solana",
    "address": "So11111111111111111111111111111111111111112",
    "symbol": "BONKAI",
    "name": "Bonk Agent"
  },
  "scanned_at": "2026-10-24T20:00:00+07:00",
  "market": {
    "price_usd": 0.0041,
    "liquidity_usd": 68000.0,
    "market_cap": 410000.0,
    "volume_24h": 520000.0,
    "pair_age_minutes": 42
  },
  "risk_score": 18,
  "verdict": "PROMISING",
  "confidence": "high",
  "breakdown": {
    "contract": 0,
    "holders": 8,
    "volume_integrity": 4,
    "liquidity": 4,
    "social": 2
  },
  "flags": [
    {
      "category": "holders",
      "severity": "warn",
      "code": "CREATOR_HOLDINGS_HIGH",
      "value": 0.024,
      "threshold": 0.05,
      "source": "rugcheck"
    }
  ],
  "summary_id": "Token memiliki struktur kontrak aman tanpa otoritas mint/freeze. Distribusi holder sehat dengan arus pembeli organik. Pantau pergerakan wallet creator yang masih memegang 2.4% suplai.",
  "ai_analysis": {
    "status": "completed",
    "model": "gemini-3.8-flash-high",
    "health_status": "HEALTHY",
    "buyer_quality": "ORGANIC",
    "conviction_score": 84,
    "momentum_phase": "EARLY_ACCUMULATION",
    "liquidity_stress": {
      "rating": "STRONG",
      "lp_to_top10_ratio": 0.79,
      "note_id": "Likuiditas $68K sanggup menyerap tekanan jual Top 10."
    },
    "narrative_quality": "SOLID",
    "summary_id": "Token memiliki struktur kontrak aman tanpa otoritas mint/freeze. Distribusi holder sehat dengan arus pembeli organik. Pantau pergerakan wallet creator yang masih memegang 2.4% suplai.",
    "decision_brief": {
      "bull_case_id": "Kontrak bersih dan rasio pembelian organik kuat di 62%.",
      "red_flag_id": "Umur pair baru 42 menit.",
      "invalidation_trigger_id": "Batalkan pantauan jika likuiditas turun di bawah $45.000."
    },
    "shortlist_rank_reason_id": "Kandidat paling sehat karena likuiditas tebal dan minim bot."
  },
  "disclaimer": "Analisis otomatis, bukan nasihat keuangan."
}
```

---

## Batasan dan Disclaimer Penting

- **Heuristik wash trade dari DexScreener bersifat proksi**, bukan bukti transaksi per wallet (kecuali adapter RPC Solana diaktifkan).
- **Skor risiko adalah potret pada waktu pemindaian**, bukan prediksi harga di masa depan. Token baru bergerak sangat cepat.
- **Lolos audit (`PROMISING` / `HEALTHY`) tidak berarti bebas risiko**: rug pull atau koordinasi dompet di luar on-chain graph tetap bisa terjadi.
- **Bukan nasihat keuangan**: Sistem ini bersifat *read-only* sebagai alat bantu analisis kedua (*second opinion*), dan perdagangan memecoin berisiko kehilangan seluruh modal.
