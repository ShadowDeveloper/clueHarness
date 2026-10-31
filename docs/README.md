# Documentation index

| Document | Audience | Contents |
|---|---|---|
| [../README.md](../README.md) | everyone | Overview, 5-minute quickstart, acceptance checklist |
| [../RULES_SPEC.md](../RULES_SPEC.md) | everyone | The exact rules implemented, with Hasbro source and every edge case |
| [playing.md](playing.md) | players | The TUI (keys, panels, notebook symbols), the plain CLI, spectating AI games |
| [configuration.md](configuration.md) | users | `game.yaml` reference, `--players` shorthand, `.env` / providers, all CLI flags |
| [architecture.md](architecture.md) | developers | The four layers, data flow, key types, invariants, package map |
| [observation_schema.md](observation_schema.md) | agent authors | Every field an agent receives, with an example |
| [replay_format.md](replay_format.md) | analysts | JSONL replay records, redaction rules, determinism hash, save/load |
| [tools.md](tools.md) | agent authors | Symbolic deduction tools: signatures, algorithms, guarantees |
| [analyst.md](analyst.md) | players | Standalone analyst for real-table games: `clue analyze` TUI/CLI, web Analyst page, GitHub Pages build |
| [strategies.md](strategies.md) | prompt authors | How strategy prompts are composed, writing your own, evaluating them |
| [extending.md](extending.md) | developers | Add an LLM provider, a new agent, a rule variant, a metric |
| [pondering.md](pondering.md) | developers / researchers | Parallel thinking between turns: lifecycle, interrupts, isolation, audit |
| [evaluation.md](evaluation.md) | researchers | Tournament metrics, ELO, ablations, reproducing the report |
| [tui_screenshot.txt](tui_screenshot.txt) / [.svg](tui_screenshot.svg) | — | Illustrative headless TUI capture snapshot; regenerate with `python eval/make_tui_screenshot.py` |

- [web.md](web.md) — web UI: `clue web`, pages, secret links & redaction, hot-seat, API, development
- [web_ui_plan.md](web_ui_plan.md) — historical web UI plan (all milestones implemented; see `web.md` for current behavior)
