---
id: BL-0001
title: Perbaiki fetch_wiki_page yang selalu gagal saat path mengandung prefix locale
area: wiki
type: bugfix
priority: high
status: done
created: 2026-07-13
updated: 2026-07-13
depends_on: []
skills: [mcp-development, automated-test, git-workflow]
---

# BL-0001 — Perbaiki fetch_wiki_page yang selalu gagal saat path mengandung prefix locale

## Konteks

Tool MCP `fetch_wiki_page` (dirilis di v0.3.0) **selalu** gagal — hasilnya `Page not found: /...`
atau pesan GraphQL error, tidak pernah mengembalikan konten halaman.

Akar masalahnya ada di `src/flowise_mcp_server/wikijs.py`:

- Wiki.js `pages.singleByPath(path, locale)` mengharapkan **path tanpa prefix bahasa** —
  locale adalah argumen terpisah, bukan bagian dari path.
- Namun URL yang tampil di browser dan yang muncul di hasil `search_wiki` selalu berbentuk
  `https://wiki…/en/master-data/lokasi/01-membuat`, sehingga yang sampai ke tool adalah
  `/en/master-data/lokasi/01-membuat`.
- `fetch_page()` hanya melakukan `path.lstrip("/")` (wikijs.py:47), jadi segmen `en` **ikut
  terbawa sebagai bagian path**, sementara `locale` yang dikirim tetap nilai default
  `settings.wikijs_locale` = `"id"` (settings.py:103-106).
- Query akhirnya mencari path literal `"en/master-data/lokasi/01-membuat"` pada locale `"id"` —
  kombinasi yang tidak pernah ada di database Wiki.js.

Dua cacat sekaligus: (a) segmen bahasa tidak dilepas dari path, dan (b) locale tidak diturunkan
dari path yang diberikan. Ditambah `WIKIJS_LOCALE` sama sekali tidak terdokumentasi di
`.env.example`, sehingga default `"id"` diam-diam dipakai pada wiki yang ber-locale `en`.

## Sasaran

`fetch_wiki_page` mengembalikan konten halaman yang benar untuk path apa adanya dari hasil
pencarian atau URL browser — dengan prefix locale (`/en/…`), tanpa prefix, maupun berupa URL absolut.

## Ruang Lingkup

- File diubah:
  - `src/flowise_mcp_server/wikijs.py` — normalisasi path + penurunan locale + fallback.
  - `src/flowise_mcp_server/server.py` — deskripsi tool `fetch_wiki_page` (baris 68-83).
  - `src/flowise_mcp_server/settings.py` — dokumentasi field `wikijs_locale` (baris 103-106).
  - `.env.example` — tambahkan `WIKIJS_LOCALE`.
  - `README.md` — dokumentasikan `WIKIJS_LOCALE` di bagian konfigurasi Wiki.js.
  - `CHANGELOG.md` — entri `0.3.1`.
  - `pyproject.toml` — `version = "0.3.1"`.
- File dibuat:
  - `tests/test_wikijs.py` — belum ada tes apa pun untuk `wikijs.py`.
- Di luar lingkup: mode retrieval pgvector/Ollama, tool chatflow Flowise, dan penambahan
  tool Wiki.js baru (search/list). Tidak mengganti pustaka HTTP.

## Rencana Eksekusi

1. [mcp-development] Di `wikijs.py`, tambahkan helper murni
   `_normalise(path: str, default_locale: str) -> tuple[str, str]` yang mengembalikan
   `(path_bersih, locale)`:
   - Bila input URL absolut (`http://`/`https://`), ambil komponen path-nya saja dengan
     `urllib.parse.urlsplit` (buang query & fragment).
   - `strip("/")` di kedua sisi lalu `unquote()` agar path ber-escape/ber-spasi tetap cocok.
   - Bila segmen pertama cocok pola kode locale `^[a-z]{2}(-[A-Za-z]{2,4})?$` (mis. `en`, `id`,
     `en-US`), lepas segmen itu dan pakai sebagai `locale`; selain itu pakai `default_locale`.
2. [mcp-development] Di `fetch_page()`, jalankan query dengan `(path, locale)` hasil normalisasi.
   Bila hasilnya `null` **dan** prefix locale tadi memang dilepas, **retry sekali** dengan
   path asli (tanpa pelepasan prefix) + `default_locale`. Ini menutup false-positive helper
   (halaman top-level yang kebetulan bernama dua huruf) tanpa perlu daftar locale hard-code.
3. [mcp-development] Perbaiki pesan not-found/error agar menyebut path **dan** locale yang dipakai —
   pesan sekarang (`Page not found: /x`) tidak memberi petunjuk diagnosis apa pun.
4. [mcp-development] Perbarui deskripsi tool `fetch_wiki_page` di `server.py`: nyatakan bahwa
   prefix bahasa (`/en/…`) dan URL penuh **boleh** diberikan dan ditangani otomatis — supaya
   model pemanggil tidak "membersihkan" path sendiri dengan cara yang salah.
5. [automated-test] Tulis `tests/test_wikijs.py` (pytest + `respx`, sesuai dev-dependency di
   `pyproject.toml` dan gaya `tests/test_server.py`).
6. [mcp-development] Tambahkan `WIKIJS_LOCALE=en` + komentar penjelas di `.env.example`, catat di
   `README.md`, bump versi ke `0.3.1`, dan tulis entri `CHANGELOG.md`.
7. [git-workflow] Commit (Bahasa Indonesia) — **hanya bila user meminta secara eksplisit**.

## Kriteria Penerimaan

- [x] `_normalise("/en/a/b", "id")` → `("a/b", "en")`.
- [x] `_normalise("/a/b", "id")` → `("a/b", "id")`.
- [x] `_normalise("https://wiki.x/en/a/b?x=1", "id")` → `("a/b", "en")`.
- [x] `_normalise("a/b%20c", "id")` → `("a/b c", "id")` (URL-decode berjalan).
- [x] `fetch_page` mengirim variabel GraphQL `path` **tanpa** segmen locale dan `locale` yang
      diturunkan dari path.
- [x] Saat query pertama mengembalikan `null` untuk path ber-prefix, dilakukan **tepat satu**
      query ulang memakai path ber-prefix + locale default.
- [x] Halaman yang benar-benar tidak ada → string `Page not found` yang menyebut path & locale,
      bukan exception.
- [x] GraphQL `errors` → string pesan error, bukan exception.
- [x] `WIKIJS_LOCALE` terdokumentasi di `.env.example` dan `README.md`.

## Skenario Uji

`tests/test_wikijs.py`, HTTP di-mock dengan `respx`:

1. **Unit `_normalise`** — parametrized atas keempat kasus di Kriteria Penerimaan (prefix locale,
   tanpa prefix, URL absolut, URL-encoded).
2. **`fetch_page` sukses dengan prefix locale** — input `/en/master-data/lokasi`; assert body
   request GraphQL memuat `variables == {"path": "master-data/lokasi", "locale": "en"}`; assert
   keluaran memuat judul, `Path:`, dan isi markdown halaman.
3. **`fetch_page` fallback** — respons pertama `data.pages.singleByPath = null`, respons kedua
   berisi halaman; assert ada 2 request dan request kedua memakai
   `{"path": "en/master-data/lokasi", "locale": <default>}`; assert konten halaman dikembalikan.
4. **`fetch_page` not-found** — kedua respons `null`; assert string mengandung `Page not found`
   beserta path dan locale.
5. **`fetch_page` GraphQL error** — respons memuat `errors`; assert string mengandung pesan error
   dan tidak melempar exception.

## Definition of Done

- [x] Kriteria Penerimaan terpenuhi semua.
- [x] `ruff check .` dan `mypy src` bersih untuk seluruh berkas yang diubah (`wikijs.py`,
      `server.py`, `settings.py`, `tests/test_wikijs.py`). `pytest` hijau untuk
      `tests/test_wikijs.py` (9/9 lulus). **Catatan:** `tests/test_server.py` punya 2
      kegagalan pre-existing (`AttributeError: 'FastMCP' object has no attribute
      '_tool_manager'`) — tidak terkait perubahan ini, disebabkan API internal `fastmcp`
      yang berubah di versi terpasang; di luar lingkup BL-0001.
- [ ] Uji manual terhadap wiki nyata: **belum dilakukan** — perlu kredensial
      `WIKIJS_GRAPHQL_URL`/`WIKIJS_API_KEY`/`WIKIJS_LOCALE` instance Wiki.js SSI yang
      sebenarnya, tidak tersedia di sesi ini.
- [x] `git status --porcelain` kosong dari artefak test (cache/coverage) setelah menjalankan
      test suite; hanya berkas kerja (source, docs, backlog) yang termodifikasi.
- [x] `status` item diubah ke `done` dan `scripts/backlog.sh reindex` dijalankan.

## Dependensi & Catatan

- Belum terkonfirmasi locale sebenarnya di instance Wiki.js SSI. Bila terkonfirmasi `en`,
  pertimbangkan mengubah **default** `settings.wikijs_locale` dari `"id"` → `"en"`; bila ragu,
  biarkan default apa adanya dan andalkan env `WIKIJS_LOCALE` + mekanisme fallback (langkah 2).
