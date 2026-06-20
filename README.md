# Pub-Sub Log Aggregator Terdistribusi

Sistem **Pub-Sub Log Aggregator Terdistribusi** berbasis multi-service dengan fitur **idempotent consumer**, **deduplication berbasis PostgreSQL**, **transaksi database**, dan **kontrol konkurensi**. Sistem dibangun menggunakan **Python FastAPI**, **PostgreSQL**, **Redis**, dan dijalankan sepenuhnya menggunakan **Docker Compose** pada jaringan lokal.

Sistem ini dibuat untuk memenuhi tugas UAS Sistem Paralel dan Terdistribusi dengan tema:

> Pub-Sub Log Aggregator Terdistribusi dengan Idempotent Consumer, Deduplication, dan Transaksi/Kontrol Konkurensi.

---

## Link Repository, Video, dan Laporan

| Komponen          | Link                                                                                                   |
| ----------------- | ------------------------------------------------------------------------------------------------------ |
| Repository GitHub | https://github.com/junN0ir/-UAS-Pub-Sub-Log-Aggregator-Terdistribusi                                   |
| Video Demo        | https://youtu.be/tngRHaQBZIs?si=-QqtN8yVP22dbsZx                                                       |
| Laporan PDF/MD    | https://drive.google.com/drive/folders/184jXiVDNAMiccfqPjYbNhnj79GcabTuN?hl=ID                         |
| Swagger UI Lokal  | http://localhost:8080/docs                                                                             |
| Aggregator Lokal  | http://localhost:8080                                                                                  |

---

## Fitur Utama

| Fitur               | Keterangan                                                           |
| ------------------- | -------------------------------------------------------------------- |
| Multi-service       | Terdiri dari aggregator, publisher, PostgreSQL, dan Redis            |
| Docker Compose      | Semua service dijalankan dengan Docker Compose                       |
| Idempotent Consumer | Event yang sama tidak diproses dua kali                              |
| Deduplication       | Duplikasi dicegah berdasarkan kombinasi `topic` dan `event_id`       |
| Transaksi Database  | Insert event, audit log, dan update stats dilakukan secara konsisten |
| Kontrol Konkurensi  | Menggunakan unique constraint dan `ON CONFLICT DO NOTHING`           |
| Persistensi Data    | PostgreSQL memakai named volume agar data tetap aman                 |
| Observability       | Endpoint `/health`, `/stats`, `/events`, `/audit`, dan logs          |
| Stress Test         | Mendukung pengujian 20.000 event dengan duplikasi                    |

---

## Stack Teknologi

| Komponen          | Teknologi            |
| ----------------- | -------------------- |
| Bahasa            | Python               |
| API Framework     | FastAPI              |
| ASGI Server       | Uvicorn              |
| Database          | PostgreSQL 16 Alpine |
| Database Driver   | asyncpg              |
| Broker Internal   | Redis 7 Alpine       |
| HTTP Client       | HTTPX                |
| Schema Validation | Pydantic             |
| Containerization  | Docker Compose       |
| Testing           | pytest               |

---

## Arsitektur Sistem

```text
┌─────────────────────────────────────────────────────┐
│                 Docker Compose Network              │
│                                                     │
│  ┌─────────────┐      HTTP POST      ┌─────────────┐│
│  │  publisher  │ ─────────────────► │ aggregator  ││
│  │ simulator   │  /publish           │  FastAPI    ││
│  │ event       │  /publish/batch     │ port 8080   ││
│  └─────────────┘                     └──────┬──────┘│
│                                             │       │
│                                      asyncpg│       │
│                                             │       │
│                                      ┌──────▼──────┐│
│                                      │ PostgreSQL  ││
│                                      │  storage    ││
│                                      └─────────────┘│
│                                                     │
│                                      ┌─────────────┐│
│                                      │    Redis    ││
│                                      │   broker    ││
│                                      └─────────────┘│
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Alur Sistem

```text
Publisher membuat event JSON
        ↓
Publisher mengirim ke aggregator
        ↓
Aggregator menerima event melalui /publish atau /publish/batch
        ↓
Aggregator melakukan validasi schema dengan Pydantic
        ↓
Aggregator membuka transaksi database
        ↓
INSERT event ke PostgreSQL
        ↓
Jika topic + event_id belum ada → accepted
Jika topic + event_id sudah ada → duplicate
        ↓
Audit log ditulis
        ↓
Stats diperbarui
        ↓
Response dikirim ke client
```

---

## Struktur Repository

```text
uas-pub-sub/
├── aggregator/
│   ├── Dockerfile
│   ├── main.py
│   ├── database.py
│   ├── schemas.py
│   └── requirements.txt
├── publisher/
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── init-db/
│   └── init.sql
├── tests/
│   ├── test_api.py
│   ├── test_dedup.py
│   ├── test_schema.py
│   ├── test_stats.py
│   ├── test_persistence.py
│   ├── test_concurrency.py
│   └── test_stress.py
├── docker-compose.yml
├── README.md
└── report.md / report.pdf
```

---

# Cara Menjalankan Project

## 1. Clone repository

```powershell
git clone "https://github.com/junN0ir/-UAS-Pub-Sub-Log-Aggregator-Terdistribusi.git"
```

```powershell
cd "-UAS-Pub-Sub-Log-Aggregator-Terdistribusi"
```

Jika project sudah ada di laptop, cukup masuk ke folder project:

```powershell
D:
cd "D:\belajar hebat\Sister\uas-pub-sub"
```

---

## 2. Jalankan Docker Compose

Untuk menjalankan dari kondisi bersih:

```powershell
docker compose down -v --remove-orphans
```

```powershell
docker compose up -d --build
```

Perintah tersebut akan:

* Menghapus container dan volume lama.
* Build ulang image aggregator dan publisher.
* Menjalankan PostgreSQL, Redis, aggregator, dan publisher.
* Publisher otomatis mengirim event setelah aggregator healthy.

---

## 3. Cek status container

```powershell
docker compose ps
```

Output yang diharapkan:

```text
aggregator_service    Up ... (healthy)     0.0.0.0:8080->8080/tcp
pg_storage            Up ... (healthy)     5432/tcp
redis_broker          Up ... (healthy)     6379/tcp
publisher_service     Up ...
```

---

## 4. Cek health aggregator

```powershell
curl.exe http://localhost:8080/health
```

Output yang diharapkan:

```json
{
  "status": "ok",
  "timestamp": "..."
}
```

---

## 5. Cek log publisher

```powershell
docker compose logs publisher --tail=80
```

Log publisher menunjukkan event yang dikirim ke aggregator, termasuk event duplikat.

---

## 6. Cek statistik awal

```powershell
curl.exe http://localhost:8080/stats
```

Contoh output:

```json
{
  "received": 650,
  "unique_processed": 500,
  "duplicate_dropped": 150,
  "error_count": 0,
  "topics": [
    "system.auth",
    "system.order",
    "system.payment"
  ],
  "uptime_seconds": 120.5,
  "duplicate_rate_percent": 23.08,
  "lag_seconds": 0.12
}
```

Konsistensi utama:

```text
received = unique_processed + duplicate_dropped
```

---

# Endpoint API

| Method | Endpoint            | Fungsi                                          |
| ------ | ------------------- | ----------------------------------------------- |
| GET    | `/health`           | Mengecek status aggregator dan koneksi database |
| POST   | `/publish`          | Mengirim satu event                             |
| POST   | `/publish/batch`    | Mengirim banyak event sekaligus                 |
| GET    | `/events`           | Melihat event unik yang tersimpan               |
| GET    | `/events?topic=...` | Melihat event berdasarkan topic                 |
| GET    | `/stats`            | Melihat statistik sistem                        |
| GET    | `/audit`            | Melihat audit log semua event masuk             |

---

# Format Event

```json
{
  "topic": "system.order",
  "event_id": "order-demo-001",
  "timestamp": "2025-01-01T00:00:00Z",
  "source": "demo-manual",
  "payload": {
    "item": "laptop",
    "qty": 1,
    "price": 15000000
  }
}
```

Aturan validasi:

| Field       | Aturan                                                  |
| ----------- | ------------------------------------------------------- |
| `topic`     | Wajib, tidak boleh kosong, tidak boleh mengandung spasi |
| `event_id`  | Wajib, digunakan untuk deduplication                    |
| `timestamp` | Wajib, format ISO 8601                                  |
| `source`    | Asal event                                              |
| `payload`   | Isi data event                                          |

---

# Demo Manual via PowerShell

## 1. Publish event unik

Buat body event:

```powershell
$body = @{
  topic = "system.order"
  event_id = "order-demo-101"
  timestamp = "2025-01-01T00:00:00Z"
  source = "demo-manual"
  payload = @{
    item = "laptop"
    qty = 1
    price = 15000000
  }
} | ConvertTo-Json -Depth 5
```

Kirim event:

```powershell
Invoke-RestMethod -Uri "http://localhost:8080/publish" -Method POST -ContentType "application/json" -Body $body | ConvertTo-Json
```

Output yang diharapkan:

```json
{
  "status": "ok",
  "accepted": 1,
  "duplicates": 0,
  "errors": 0
}
```

---

## 2. Kirim event yang sama lagi

```powershell
Invoke-RestMethod -Uri "http://localhost:8080/publish" -Method POST -ContentType "application/json" -Body $body | ConvertTo-Json
```

Output yang diharapkan:

```json
{
  "status": "ok",
  "accepted": 0,
  "duplicates": 1,
  "errors": 0
}
```

Ini membuktikan idempotency karena event yang sama tidak diproses dua kali.

---

## 3. Cek audit log

```powershell
curl.exe "http://localhost:8080/audit?limit=5"
```

Atau output lebih rapi:

```powershell
$audit = Invoke-RestMethod "http://localhost:8080/audit?limit=5"
$audit | ConvertTo-Json -Depth 10
```

---

## 4. Publish batch berisi event unik dan duplikat

Buat batch body:

```powershell
$batchBody = @'
{
  "events": [
    {
      "topic": "system.auth",
      "event_id": "auth-batch-101",
      "timestamp": "2025-01-01T00:02:00Z",
      "source": "batch-demo",
      "payload": {"user_id": 1001}
    },
    {
      "topic": "system.auth",
      "event_id": "auth-batch-102",
      "timestamp": "2025-01-01T00:02:01Z",
      "source": "batch-demo",
      "payload": {"user_id": 1002}
    },
    {
      "topic": "system.auth",
      "event_id": "auth-batch-101",
      "timestamp": "2025-01-01T00:02:00Z",
      "source": "batch-demo",
      "payload": {"user_id": 1001}
    }
  ]
}
'@
```

Kirim batch:

```powershell
Invoke-RestMethod -Uri "http://localhost:8080/publish/batch" -Method POST -ContentType "application/json" -Body $batchBody | ConvertTo-Json
```

Output yang diharapkan:

```json
{
  "status": "ok",
  "accepted": 2,
  "duplicates": 1,
  "errors": 0
}
```

---

## 5. Lihat event unik

```powershell
Invoke-RestMethod "http://localhost:8080/events?limit=5" | ConvertTo-Json -Depth 10
```

Filter berdasarkan topic:

```powershell
Invoke-RestMethod "http://localhost:8080/events?topic=system.order&limit=10" | ConvertTo-Json -Depth 10
```

---

## 6. Cek stats

```powershell
curl.exe http://localhost:8080/stats
```

---

# Validasi Schema

## 1. Event tanpa event_id

```powershell
$invalidBody = @'
{
  "topic": "system.order",
  "timestamp": "2025-01-01T00:00:00Z",
  "source": "demo",
  "payload": {}
}
'@
```

```powershell
try {
  Invoke-RestMethod -Uri "http://localhost:8080/publish" -Method POST -ContentType "application/json" -Body $invalidBody
} catch {
  $_.ErrorDetails.Message
}
```

---

## 2. Topic berisi spasi

```powershell
$invalidTopic = @'
{
  "topic": "topic dengan spasi",
  "event_id": "test-topic-001",
  "timestamp": "2025-01-01T00:00:00Z",
  "source": "demo",
  "payload": {}
}
'@
```

```powershell
try {
  Invoke-RestMethod -Uri "http://localhost:8080/publish" -Method POST -ContentType "application/json" -Body $invalidTopic
} catch {
  $_.ErrorDetails.Message
}
```

---

## 3. Timestamp tidak valid

```powershell
$invalidTimestamp = @'
{
  "topic": "system.test",
  "event_id": "test-ts-001",
  "timestamp": "31-12-2024",
  "source": "demo",
  "payload": {}
}
'@
```

```powershell
try {
  Invoke-RestMethod -Uri "http://localhost:8080/publish" -Method POST -ContentType "application/json" -Body $invalidTimestamp
} catch {
  $_.ErrorDetails.Message
}
```

---

# Menjalankan Test

## 1. Jalankan semua test

```powershell
python -m pytest .\tests -v
```

---

## 2. Test schema

```powershell
python -m pytest .\tests\test_schema.py -v
```

---

## 3. Test deduplication

```powershell
python -m pytest .\tests\test_dedup.py -v
```

---

## 4. Test API

```powershell
python -m pytest .\tests\test_api.py -v
```

---

## 5. Test stats

```powershell
python -m pytest .\tests\test_stats.py -v
```

---

## 6. Test persistence

```powershell
python -m pytest .\tests\test_persistence.py -v
```

---

## 7. Test concurrency

```powershell
python -m pytest .\tests\test_concurrency.py -v
```

---

## 8. Stress test 20.000 event

```powershell
python -m pytest .\tests\test_stress.py -v -s
```

Output yang diharapkan:

```text
--- Hasil Stress Test ---
Total event: 20000
Accepted: 14000
Duplicates: 6000
Errors: 0
Waktu: ...
Throughput: ... event/detik
Duplicate rate: 30.0%
PASSED
```

---

# Daftar Test

| No | File                  | Yang Diuji                         |
| -- | --------------------- | ---------------------------------- |
| 1  | `test_schema.py`      | Validasi event valid dan invalid   |
| 2  | `test_dedup.py`       | Idempotency dan deduplication      |
| 3  | `test_api.py`         | Endpoint API utama                 |
| 4  | `test_stats.py`       | Konsistensi statistik              |
| 5  | `test_persistence.py` | Persistensi deduplication          |
| 6  | `test_concurrency.py` | Race condition dan request paralel |
| 7  | `test_stress.py`      | Stress test 20.000 event           |

---

# Demonstrasi Persistensi Data

Penting: untuk membuktikan persistensi, jangan gunakan `docker compose down -v`, karena `-v` menghapus volume.

## 1. Catat stats sebelum restart

```powershell
curl.exe http://localhost:8080/stats
```

## 2. Restart aggregator

```powershell
docker compose restart aggregator
```

## 3. Cek container

```powershell
docker compose ps
```

## 4. Cek health

```powershell
curl.exe http://localhost:8080/health
```

## 5. Cek stats lagi

```powershell
curl.exe http://localhost:8080/stats
```

## 6. Kirim ulang event lama

```powershell
Invoke-RestMethod -Uri "http://localhost:8080/publish" -Method POST -ContentType "application/json" -Body $body | ConvertTo-Json
```

Output yang diharapkan:

```json
{
  "status": "ok",
  "accepted": 0,
  "duplicates": 1,
  "errors": 0
}
```

Jika output menunjukkan duplicate, berarti deduplication tetap bekerja setelah restart.

---

# Recreate Container Tanpa Hapus Volume

Untuk bukti lebih kuat bahwa data tetap ada meskipun container aplikasi dibuat ulang:

```powershell
docker compose stop aggregator
```

```powershell
docker compose rm -f aggregator
```

```powershell
docker compose up -d aggregator
```

Cek ulang:

```powershell
docker compose ps
```

```powershell
curl.exe http://localhost:8080/stats
```

Kirim ulang event lama:

```powershell
Invoke-RestMethod -Uri "http://localhost:8080/publish" -Method POST -ContentType "application/json" -Body $body | ConvertTo-Json
```

Output tetap harus:

```json
{
  "status": "ok",
  "accepted": 0,
  "duplicates": 1,
  "errors": 0
}
```

---

# Logs dan Observability

## Logs semua service

```powershell
docker compose logs --tail=100
```

## Logs aggregator

```powershell
docker compose logs aggregator --tail=100
```

## Logs publisher

```powershell
docker compose logs publisher --tail=100
```

## Logs real-time

```powershell
docker compose logs -f
```

Endpoint observability:

| Endpoint  | Fungsi                                        |
| --------- | --------------------------------------------- |
| `/health` | Mengecek kondisi service                      |
| `/stats`  | Melihat metrik sistem                         |
| `/events` | Melihat event unik yang tersimpan             |
| `/audit`  | Melihat semua event masuk, termasuk duplicate |
| `/docs`   | Swagger UI                                    |

---

# Keamanan dan Jaringan Lokal

Sistem ini tidak menggunakan layanan eksternal publik. Semua service berjalan di jaringan lokal Docker Compose.

| Service    | Akses                                         |
| ---------- | --------------------------------------------- |
| aggregator | Diekspos ke host melalui port 8080 untuk demo |
| publisher  | Internal Compose                              |
| PostgreSQL | Internal Compose                              |
| Redis      | Internal Compose                              |

Cek dengan:

```powershell
docker compose ps
```

Jika hanya aggregator yang memiliki mapping ke `0.0.0.0:8080`, maka service database dan broker tetap internal.

---

# Perintah GitHub

## 1. Cek status repository

```powershell
git status
```

## 2. Tambahkan semua file

```powershell
git add .
```

## 3. Commit

```powershell
git commit -m "Update README and project documentation"
```

## 4. Push ke GitHub

```powershell
git push -u origin main
```

Jika remote belum ada:

```powershell
git remote add origin "https://github.com/junN0ir/-UAS-Pub-Sub-Log-Aggregator-Terdistribusi.git"
```

```powershell
git push -u origin main
```

Jika remote sudah ada tapi URL salah:

```powershell
git remote set-url origin "https://github.com/junN0ir/-UAS-Pub-Sub-Log-Aggregator-Terdistribusi.git"
```

```powershell
git push -u origin main
```

---

# Troubleshooting

## Port 8080 sudah digunakan

```powershell
netstat -ano | findstr :8080
```

Matikan proses berdasarkan PID:

```powershell
taskkill /PID <PID> /F
```

---

## Container lama masih nyangkut

```powershell
docker compose down --remove-orphans
```

```powershell
docker compose up -d --build
```

---

## Reset total data

```powershell
docker compose down -v
```

```powershell
docker compose up -d --build
```

Catatan: `docker compose down -v` akan menghapus volume PostgreSQL, sehingga semua data hilang.

---

## Cek nama service Compose

```powershell
docker compose ps --services
```

---

## Cek isi folder tests

```powershell
Get-ChildItem .\tests
```

---

# Catatan Penting

* Gunakan `curl.exe`, bukan `curl`, di Windows PowerShell.
* Untuk POST JSON, gunakan `Invoke-RestMethod`.
* Untuk here-string PowerShell, pembuka `@'` harus berdiri sendiri di satu baris.
* Jangan gunakan `docker compose down -v` saat membuktikan persistensi.
* Gunakan `docker compose down -v` hanya jika ingin reset total data.
* Jika output `accepted` dan `duplicates` berbeda dari contoh, kemungkinan `event_id` sudah pernah digunakan.
* Untuk demo ulang, gunakan `event_id` baru atau reset database.

---

# Referensi

van Steen, M., & Tanenbaum, A. S. (2023). *Distributed systems* (4th ed., Version 4.01). Maarten van Steen.

---

# Penulis

Nama: Junnior Marcellino Polla
NIM: 11231034
Kelas: B
Mata Kuliah: Sistem Paralel dan Terdistribusi
