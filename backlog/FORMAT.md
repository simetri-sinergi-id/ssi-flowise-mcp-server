# Format & Mekanisme Backlog — ssi-flowise-mcp-server

Backlog ini merekam pekerjaan pengembangan sebagai berkas Markdown yang **deterministik
dan siap dieksekusi tanpa interpretasi ulang**. Polanya mengikuti konvensi backlog Odoo SSI
(`odoo-development-backlog`), tetapi **store-nya di dalam repo ini sendiri** — bukan store
git terpisah — karena repo ini milik sendiri, bukan fork upstream yang PR-nya harus bersih.

## Prinsip

1. **Satu indeks + banyak item.** Tepat satu `BACKLOG.md` (indeks) + direktori `backlog/`
   berisi satu berkas per item, dikelompokkan per area: `backlog/<area>/<id>-<slug>.md`.
2. **Siap-eksekusi.** Setiap item memuat konteks, sasaran, file yang disentuh, langkah
   eksplisit + skill per langkah, kriteria penerimaan terverifikasi, skenario uji, dan DoD.
   Bila setelah membaca item masih muncul pertanyaan *"maksudnya apa?"*, item itu **belum layak**.
3. **Indeks tidak diedit tangan.** `BACKLOG.md` dibangun ulang dari frontmatter seluruh item
   dengan `scripts/backlog.sh reindex`. Dilarang mengklaim indeks sudah diperbarui tanpa
   menjalankan skrip.

## Perintah

```bash
scripts/backlog.sh new <area> "<judul>"   # buat item baru bernomor urut (BL-NNNN)
scripts/backlog.sh reindex                # bangun ulang BACKLOG.md dari frontmatter
```

## Area

| Area | Cakupan |
|------|---------|
| `core` | `settings.py`, `server.py`, siklus hidup & transport MCP |
| `tools` | Registrasi & kontrak tool MCP (chatflow Flowise, deskripsi tool) |
| `wiki` | Klien Wiki.js GraphQL (`wikijs.py`), `fetch_wiki_page` |
| `retrieval` | Mode pgvector + Ollama (embedding, pencarian langsung) |
| `docs` | README, CHANGELOG, `.env.example`, dokumentasi |
| `infra` | Dockerfile, GitHub Actions, pre-commit, tooling |
| `release` | Tagging, GitHub Release, image GHCR |

## Frontmatter (wajib)

```yaml
---
id: BL-0001                  # unik, immutable
title: <judul>
area: wiki                   # core | tools | wiki | retrieval | docs | infra | release
type: bugfix                 # feature | bugfix | refactor | config | docs | test | chore
priority: high               # high | medium | low
status: todo                 # todo | in-progress | blocked | done | cancelled
created: 2026-07-13          # YYYY-MM-DD
updated: 2026-07-13          # diperbarui tiap perubahan status
depends_on: []               # id yang harus selesai lebih dulu
skills: [mcp-development]    # skill yang dipanggil saat eksekusi
---
```

`status: blocked` **wajib** disertai alasan + id pemblokir di section *Dependensi & Catatan*.

## Section wajib

`## Konteks` · `## Sasaran` · `## Ruang Lingkup` · `## Rencana Eksekusi` ·
`## Kriteria Penerimaan` · `## Skenario Uji` · `## Definition of Done` · `## Dependensi & Catatan`

Template siap-salin: `scripts/templates/backlog-item.skeleton.md`.

## Alur

1. Rencana (plan mode) **wajib** dimaterialisasi jadi item backlog — rencana yang tidak
   tercatat = pekerjaan hilang.
2. Mulai kerja → ubah `status` ke `in-progress`, perbarui `updated`, reindex.
3. Selesai → penuhi DoD, ubah `status` ke `done`, reindex.
