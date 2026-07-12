#!/usr/bin/env bash
# backlog.sh — utilitas store backlog ssi-flowise-mcp-server.
#
#   scripts/backlog.sh new <area> "<judul>"   Buat berkas item baru bernomor urut.
#   scripts/backlog.sh reindex                 Bangun ulang BACKLOG.md dari frontmatter.
#
# Store = repo ini sendiri (akar repo). Berbeda dari backlog Odoo SSI yang memakai
# store git terpisah (${ODOO_BACKLOG_PATH}) demi menjaga PR upstream OCA tetap bersih —
# di sini repo adalah milik sendiri, jadi backlog ikut ter-commit bersama kode.
# Override akar dengan --root DIR bila perlu.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ "${1:-}" == "--root" ]]; then
  ROOT="$(cd "${2:?--root butuh DIR}" && pwd)"; shift 2
fi

CMD="${1:-}"; shift || true

AREAS="core|tools|wiki|retrieval|docs|infra|release"

slugify() {
  echo "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' \
    | cut -c1-60
}

# Hanya berkas item (backlog/<area>/*.md) yang dihitung. Berkas di akar backlog/
# — mis. FORMAT.md yang memuat contoh frontmatter — bukan item dan harus diabaikan.
next_id_num() {
  local max=0 n
  while IFS= read -r n; do
    n=$((10#$n))
    (( n > max )) && max=$n
  done < <(find "${ROOT}/backlog" -mindepth 2 -maxdepth 2 -name '*.md' -print0 2>/dev/null \
           | xargs -0 -r grep -hoE '^id:[[:space:]]*BL-[0-9]+' 2>/dev/null \
           | grep -oE '[0-9]+$' || true)
  printf '%04d' $((max + 1))
}

cmd_new() {
  local area="${1:-}" title="${2:-}"
  if [[ -z "${area}" || -z "${title}" ]]; then
    echo "Pemakaian: scripts/backlog.sh new <area> \"<judul>\"" >&2
    echo "Area yang dipakai: ${AREAS//|/ | }" >&2
    exit 2
  fi
  if [[ ! "${area}" =~ ^(${AREAS})$ ]]; then
    echo "ERROR: area tidak dikenal: ${area}" >&2
    echo "Area yang dipakai: ${AREAS//|/ | }" >&2
    exit 2
  fi

  local num id slug dir file today
  num="$(next_id_num)"
  id="BL-${num}"
  slug="$(slugify "${title}")"
  dir="${ROOT}/backlog/${area}"
  file="${dir}/${num}-${slug}.md"
  today="$(date +%F)"
  mkdir -p "${dir}"

  [[ -e "${file}" ]] && { echo "ERROR: ${file} sudah ada." >&2; exit 1; }

  sed -E \
    -e "s|^id: .*|id: ${id}|" \
    -e "s|^title: .*|title: ${title}|" \
    -e "s|^area: .*|area: ${area}|" \
    -e "s|^created: .*|created: ${today}|" \
    -e "s|^updated: .*|updated: ${today}|" \
    "${SCRIPT_DIR}/templates/backlog-item.skeleton.md" > "${file}"
  sed -i -E "0,/^# BL-.*/s|^# BL-.*|# ${id} — ${title}|" "${file}"

  echo "Dibuat: ${file}"
  echo "-> Lengkapi SEMUA section wajib hingga siap-eksekusi, lalu: scripts/backlog.sh reindex"
}

cmd_reindex() {
  ROOT="${ROOT}" python3 - <<'PYEOF'
import glob
import os
import re

root = os.environ["ROOT"]
bdir = os.path.join(root, "backlog")
items = []

fm_re = re.compile(r"^---\s*$(.*?)^---\s*$", re.S | re.M)


def field(fm, key):
    m = re.search(rf"^{key}:\s*(.*?)\s*$", fm, re.M)
    return m.group(1).strip() if m else ""


# Hanya backlog/<area>/*.md — berkas di akar backlog/ (mis. FORMAT.md) bukan item.
for path in sorted(glob.glob(os.path.join(bdir, "*", "*.md"))):
    with open(path, encoding="utf-8") as f:
        txt = f.read()
    m = fm_re.search(txt)
    if not m:
        continue
    fm = m.group(1)
    item_id = field(fm, "id")
    if not re.fullmatch(r"BL-\d+", item_id):
        continue
    rel = os.path.relpath(path, root)
    items.append({
        "id": item_id,
        "title": field(fm, "title"),
        "area": field(fm, "area"),
        "type": field(fm, "type"),
        "priority": field(fm, "priority"),
        "status": field(fm, "status") or "todo",
        "depends_on": field(fm, "depends_on"),
        "path": rel.replace(os.sep, "/"),
    })

order = ["in-progress", "todo", "blocked", "done", "cancelled"]
labels = {
    "in-progress": "In Progress", "todo": "Todo", "blocked": "Blocked",
    "done": "Done", "cancelled": "Cancelled",
}
prio_rank = {"high": 0, "medium": 1, "low": 2}

lines = [
    "<!-- BERKAS INI DIBANGUN ULANG OLEH scripts/backlog.sh reindex — JANGAN EDIT MANUAL. -->",
    "# BACKLOG — ssi-flowise-mcp-server",
    "",
    f"Total item: **{len(items)}**. Sumber kebenaran ada di berkas per item di `backlog/`.",
    "Perbarui indeks ini dengan `scripts/backlog.sh reindex`, bukan mengedit tangan.",
    "Format item: lihat `backlog/FORMAT.md`.",
    "",
]

for st in order:
    group = [it for it in items if it["status"] == st]
    lines.append(f"## {labels[st]} ({len(group)})")
    lines.append("")
    if not group:
        lines.append("_(kosong)_")
        lines.append("")
        continue
    lines.append("| Id | Judul | Area | Tipe | Prioritas | Depends | Berkas |")
    lines.append("|----|-------|------|------|-----------|---------|--------|")
    group.sort(key=lambda it: (prio_rank.get(it["priority"], 9), it["id"]))
    for it in group:
        dep = it["depends_on"] or "[]"
        dep = "—" if dep in ("[]", "") else dep.strip("[]")
        lines.append(
            f"| {it['id']} | {it['title']} | {it['area']} | {it['type']} "
            f"| {it['priority']} | {dep} | [{it['path']}]({it['path']}) |"
        )
    lines.append("")

out = os.path.join(root, "BACKLOG.md")
with open(out, "w", encoding="utf-8") as f:
    f.write("\n".join(lines).rstrip() + "\n")
print(f"BACKLOG.md diperbarui: {out} ({len(items)} item)")
PYEOF
}

case "${CMD}" in
  new)     cmd_new "$@" ;;
  reindex) cmd_reindex ;;
  *)
    echo "Pemakaian:" >&2
    echo "  scripts/backlog.sh new <area> \"<judul>\"   (area: ${AREAS//|/ | })" >&2
    echo "  scripts/backlog.sh reindex" >&2
    exit 2 ;;
esac
