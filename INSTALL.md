# Using OpenTama with Claude Code

OpenTama ships a `SKILL.md` at the repo root, so Claude Code can read it
directly. Two install modes:

## A. Personal skill (available in every project)

```bash
mkdir -p ~/.claude/skills
git clone <your-fork-url> ~/.claude/skills/opentama
```

Or, if you already cloned somewhere else:

```bash
ln -s "$(pwd)/OpenTama" ~/.claude/skills/opentama
```

Start a new Claude Code session. In the session, type `/skills` (or ask
"what skills do you have?") and confirm `opentama` shows up.

> **Path rule:** `SKILL.md` must sit at `~/.claude/skills/opentama/SKILL.md`
> exactly — *not* nested any deeper. The directory name (`opentama`) is
> arbitrary; only the depth matters.

## B. Project-scoped skill (committed with a repo)

When you want everyone working on a project to share the same pet:

```bash
mkdir -p .claude/skills
git submodule add <your-fork-url> .claude/skills/opentama
# or just: cp -r path/to/OpenTama .claude/skills/opentama
git commit -m "Add OpenTama as a project skill"
```

Project skills override personal skills of the same name.

## Install the Python package too

The skill describes the CLI commands, but Claude Code still needs the
`opentama` command available. From the skill directory:

```bash
pip install -e .          # editable so you can hack on it
# or
pipx install .            # isolated; recommended for daily use
```

Verify:

```bash
python -m opentama --help
```

## Make it your Claude Code "character"

The `SKILL.md` already includes proactive triggers ("OpenTama", "出社",
"my pet"), so Claude will check on the pet whenever those come up.

To make Claude greet you with the pet at the start of every session, add
this to your `~/.claude/CLAUDE.md` (user-level instructions) or your
project's `./CLAUDE.md`:

```markdown
## Session greeting

At the very start of every new session, run `python -m opentama status
--display iro` and show the result. If the command reports "No OpenTama
found", ask the user for a name and their office SSID and run `init`.
```

That makes OpenTama your daily companion: every time you open Claude
Code, your pet says hi from inside a flip-phone frame.

### Other character hooks

A few more ideas to wire OpenTama into your daily flow:

- **Pre-commit nudge.** In your project's `CLAUDE.md`, add: "Before
  finalizing any git commit, run `python -m opentama play` so the pet
  joins in." Your pet's happiness now reflects how active your repo is.
- **Bedtime.** Add: "When the user says good night / 'おつかれ' /
  'shutting down', run `python -m opentama sleep`."
- **Office mood.** Pair the WiFi detection with a slack-status hook —
  Claude can `status` and decide whether to set you as 🏢 office or 🏠
  remote.

## Sharing the pet with a teammate

Two ways:

1. **Same git remote.** Both of you `git clone` the skill repo into
   `~/.claude/skills/opentama`. Each gets their own pet (state lives in
   `~/.opentama/state.json`, not in the repo).

2. **IR visit.** Once you each have a USB IR adapter, point your tamas
   at each other and:

   ```bash
   # your machine
   python -m opentama ir greet  --port serial:///dev/ttyUSB0
   # their machine, at the same time
   python -m opentama ir listen --port serial:///dev/ttyUSB0
   ```

   Both pets pick up a `met:<peer>` achievement and a happiness boost.

## Updating

Personal:

```bash
cd ~/.claude/skills/opentama
git pull
pip install -e .          # only if pyproject.toml changed
```

Project-scoped (submodule):

```bash
git submodule update --remote .claude/skills/opentama
```
