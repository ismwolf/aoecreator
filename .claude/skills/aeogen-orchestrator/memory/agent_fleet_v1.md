# Agent fleet v1 (cached decision — 2026-05-14)

**Karar:** Project-scope custom agent'lar kuruldu `.claude/agents/`
altında. Hepsi **Opus** modeli kullanır.

## Üye listesi

- `aeogen-orchestrator.md` (model: opus) — dispatcher, delegated
  invocation için. Ana conversation'daki skill'in agent karşılığı.
- `aeogen-code-writer.md` (model: opus) — implementation default.
  TDD, master plan §2 lock-in, escalation on drift.
- `aeogen-code-reviewer.md` (model: opus, tools = Read/Grep/Glob/
  Bash/PowerShell — **no Edit/Write**) — verdict only.

## Activation note (kritik)

Custom agent dosyaları **session başlangıcında** yüklenir. Yeni
yaratılan agent'lar mevcut sessionda Agent tool'da görünmez. Bir
sonraki session başlangıcında otomatik aktif olur.

## Smoke test sonucu (A.T3)

- Code-writer leg: bu sessionda doğrudan main Claude yazdı (writer
  agent henüz yüklü değildi)
- Reviewer leg: `superpowers:code-reviewer` Agent tool ile çağrıldı
  → PASS, 1× P2 fix (pnpm@10.0.0 → 10.18.0)
- Bir sonraki sessionda aynı task `Agent(subagent_type="aeogen-code-writer", ...)`
  ile delege edilebilecek

## Resume yolu

Yeni session: `Skill(skill="aeogen-orchestrator", args="continue")`
→ PROGRESS.md "Mevcut task"'tan otomatik devam.
