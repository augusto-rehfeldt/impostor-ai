# Impostor

A terminal word-association deduction game played entirely by AI agents. Every
player except the impostor knows a secret famous person. Each round, players
say one hint word, the most suspicious player defends themselves, and everyone
votes. The crew wins by voting out every impostor; the impostors win at parity or
by surviving ten rounds. You watch.

```
📂 Category: World Leaders
🔍 Secret person: Napoleon
🕵️  Impostor(s): Alice

📊 Round 1 | Active players: 5
----------------------------------------
  👤 Bob: bicorne
  👤 Casey: waterloo
  🕵️ Alice: speech
  👤 Eve: corsica
  👤 Dana: exile
----------------------------------------
🔔 Alice is being questioned!
   🗣️  Alice says: "Every great leader is remembered for a speech!"

📊 VOTE TALLY:
   Alice: 4 vote(s)
   Casey: 1 vote(s)

❌ Alice was voted out!
✅ It was Alice! An IMPOSTOR was caught!
```

*(Example session, abridged; words and votes come from the model and vary.)*

## Run

Models come from the shared [ai-suite](https://github.com/augusto-rehfeldt/ai-suite)
package, like every AI script in this workspace: clone it next to this folder (or set
`AI_SUITE_DIR`) and configure a provider there.

```powershell
python main.py   # first asks for provider and model; the pick is remembered
```

Choose 4–10 players, a category (historical figures, scientists, artists, world
leaders or random) and, with six or more players, one or two impostors.
API errors fall back to neutral moves ("hmm", a random valid vote) so a game
never crashes mid-round.

## Tests

```powershell
python -B -m unittest -q test_main
```

Offline: the ai_suite package is stubbed; no provider is called. Covers role setup,
prompts (the impostor never sees the secret), vote validation, ties/skips,
single- and double-impostor win conditions and the round limit.

## License

CC0 1.0. See [LICENSE](LICENSE).
