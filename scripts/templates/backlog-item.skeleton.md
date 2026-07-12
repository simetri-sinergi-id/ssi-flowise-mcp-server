---
id: BL-0000
title: <judul>
area: <core|tools|wiki|retrieval|docs|infra|release>
type: feature
priority: medium
status: todo
created: 1970-01-01
updated: 1970-01-01
depends_on: []
skills: []
---

# BL-0000 — <judul>

## Konteks

<Kenapa pekerjaan ini ada. Rujuk keputusan/rencana/tiket bila ada.>

## Sasaran

<Satu kalimat hasil akhir yang terukur. Satu item = satu sasaran.>

## Ruang Lingkup

- File dibuat/diubah: `<path nyata>`
- Di luar lingkup: `<apa yang TIDAK dikerjakan di item ini>`

## Rencana Eksekusi

1. [<skill>] <langkah konkret>
2. [<skill>] <langkah konkret>

## Kriteria Penerimaan

- [ ] <butir yang bisa dibuktikan benar/salah>

## Skenario Uji

<Unit test yang harus ditulis: aksi, masukan, hasil yang diharapkan. Mock HTTP dengan respx.>

## Definition of Done

- [ ] Kriteria Penerimaan terpenuhi semua.
- [ ] `ruff check .`, `mypy src`, dan `pytest` hijau.
- [ ] `git status --porcelain` kosong setelah test (tanpa artefak).
- [ ] `status` item diubah ke `done` dan `scripts/backlog.sh reindex` dijalankan.

## Dependensi & Catatan

Tidak ada.
