# Strategy prompts

A strategy is a Markdown file appended to `clue/agents/base_prompt.md` under a `# STRATEGY` heading. It
changes *how the model chooses among legal actions* — never what is legal. The manager validates every
action regardless of what the prompt says, and a strategy cannot switch tools on or off (that is the
`tools:` seat setting).

## Prompt composition
```
[base_prompt.md]        rules summary, observation format, hard constraints, JSON output contract
# STRATEGY
[strategies/<file>.md]  style guidance
```
Test: `test_strategy_prompt_is_appended_not_replacing_base`.

The thresholds in strategy files are prompt guidance, not engine rules. For Classic tables within solver bounds,
posterior values are exact; Large edition uses deterministic sampling and exposes `analysis.posterior.exact: false`.
A strategy should treat sampled probabilities as estimates and Large-edition candidate lists as potential triples not ruled out by propagation, not as verified feasible assignments.

## Shipped strategies
| File | Alias | Accusation threshold | Signature behaviour |
|---|---|---|---|
| `conservative_notebook.md` | `conservative` | ≥ 0.90 and ≤ 2 combos | novelty-first suggestions, repeat-show discipline |
| `aggressive_accuser.md` | `aggressive` | ≥ 0.60 or ≤ 3 combos | races; accuses on unrefuted suggestions |
| `bayesian_probabilist.md` | `bayesian` | ≥ 0.80 | picks suggestions that split the posterior |
| `info_value_hunter.md` | `info` | ≥ 0.85 | follows `top_suggestions`, targets specific disprovers |
| `deceptive_misdirector.md` | `deceptive` | ≥ 0.85 | minimises leakage when showing cards; salts suggestions with own cards |
| `room_rusher.md` | `rusher` | ≥ 0.85 | tempo: new room every turn, passages, central hubs |

## Writing your own
Required sections (the loader does not enforce them, but the model relies on the structure):
```markdown
# Strategy: <Name>
**Description:** one paragraph.
**When to use:** table size / opponent type / scoring.

## DO
- concrete, testable rules that reference observation fields (`analysis.posterior.best_prob`,
  `notebook.has_one_of`, `top_suggestions[0]`, …)

## DON'T
- the failure modes you want to prevent

## Example reasoning
> a 2–4 sentence worked example in the model's voice
```
Tips
* Refer to `analysis` numbers rather than asking the model to compute probabilities.
* State the accusation threshold explicitly; it is the single biggest behavioural lever.
* Say what to do when disproving (`choose_card_to_show`) — many strategies forget this decision.
* Keep it under ~400 words; it is sent with every decision.

Use it: `--players llm:path/to/my_style.md`, `--strategy my_style.md` (default for unassigned LLM seats),
or `strategy: path/to/my_style.md` in YAML.

## Measuring a strategy
```
python -m clue tournament --games 50 --seed 1 \
  --players llm:my_style:openai/gpt-4o-mini,llm:bayesian:openai/gpt-4o-mini,baseline,baseline --provider openrouter
```
Seats are shuffled per game (seeded), so seat order does not bias the result. Compare `win_rate`,
`avg_turns_to_win` (earlier = more aggressive), `false_accusation_rate` and `avg_suggestions_per_game`.
`eval/report.md` bracket B runs four strategies head-to-head; offline (mock model) it is noise by design
because the mock does not read prompts — use `--live`.
