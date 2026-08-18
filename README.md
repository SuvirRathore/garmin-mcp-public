# garmin-mcp

A small MCP server that gives Claude Desktop read-only access to Garmin Connect running, strength-training and calorie data. There are three tools and it takes roughly fifteen minutes to set up.

I built this because I wanted to track progress, amongst other things, and to analyse some data from my own training (e.g. how has my easy-run pace changed, or what did I lift on the days I also ran) without exporting CSVs by hand. It talks directly to Garmin's Connect API, so there is no third-party service in the middle and nothing is uploaded anywhere.

### The tools

- `list_runs(limit, start)`: date, run type, distance, time, average pace, average and max HR, cadence, temperature. Covers treadmill runs too.
- `list_strength(limit, start)`: date, session name, duration, sets, reps, gross and active calories, average and max HR.
- `daily_calories(days, end)`: per-day total, active and BMR calories, plus steps and resting heart rate.

`start` is a row offset and `end` is a date, so Claude can page back through years of history rather than only the last few entries.

Everything is read-only. The library underneath (`garth-ng`) does expose write endpoints, but nothing here calls them: that is the only thing making this safe, since the tokens themselves grant full account access.

### Requirements

macOS or Linux, Python 3.12+, [uv](https://docs.astral.sh/uv/), Claude Desktop, and a Garmin Connect account. This will not work in the Claude mobile app or in claude.ai, because a local stdio server has no URL for them to connect to.

### Setup

1. Change your Garmin password to something you do not use anywhere else, since you are about to type it into a script.

2. Clone and install:

```bash
git clone https://github.com/SuvirRathore/garmin-mcp.git
cd garmin-mcp
uv sync
```

3. Authenticate once. This exchanges your password for OAuth tokens saved in `~/.garth`, after which the password is never needed again:

```bash
cd garmin-mcp
uv run auth_setup.py
```

Enter your MFA code if prompted. The OAuth1 token lasts about a year and the OAuth2 one refreshes itself, so this is roughly an annual chore. Treat `~/.garth` as a credential: anyone holding it can read your entire Garmin account.

4. Test the tools directly, before involving Claude. A failure here is an auth or endpoint problem rather than an MCP problem, and it is far quicker to debug at this level than through Desktop's logs:

```bash
cd garmin-mcp
uv run python -c "import server; print(server.list_runs(3))"
uv run python -c "import server; print(server.list_strength(3))"
uv run python -c "import server; print(server.daily_calories(7)[0])"
```

5. Find the two absolute paths the config needs:

```bash
cd garmin-mcp
which uv
pwd
```

6. Create or edit `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, or `~/.config/Claude/claude_desktop_config.json` on Linux, substituting the two paths from step 5 and change both instances of "YOUR_USERNAME" to your own username:

```json
{
  "mcpServers": {
    "garmin": {
      "command": "/Users/YOUR_USERNAME/.local/bin/uv",
      "args": ["--directory", "/Users/YOUR_USERNAME/path/to/garmin-mcp",
               "run", "server.py"]
    }
  }
}
```

Both paths must be absolute. Desktop launches the server with a minimal PATH, so a bare `uv` fails even though it works in your shell. If you already have other servers configured, add the `garmin` entry alongside them rather than replacing the object. If you edit this file in TextEdit, turn smart quotes off first: curly quotes are invalid JSON.

7. Quit Claude Desktop completely (Cmd-Q, not just closing the window) and reopen it. The config is only read at launch. Then ask it something like "show me my last five runs and my calorie burn this week" and approve the tool calls.

### If it does not work

Validate the JSON first, then read the server's stderr:

```bash
cd garmin-mcp
uv run python -m json.tool ~/Library/Application\ Support/Claude/claude_desktop_config.json
tail -50 ~/Library/Logs/Claude/mcp-server-garmin.log
```

Errors on every call usually mean the tokens expired: re-run `auth_setup.py`. The "add custom connector" dialog inside Claude is not relevant here, since it expects a remote HTTPS URL.

### Notes for anyone extending this

Garmin's Connect API is undocumented and its field names drift, so when something comes back empty, inspect one real object rather than guessing:

```python
import garth

garth.resume("~/.garth")
a = garth.connectapi(
    "/activitylist-service/activities/search/activities",
    params={"start": 0, "limit": 1},
)[0]
print(sorted(a))
```

Two behaviours worth knowing before you add a tool. The `activityType` filter accepts parent categories only: `running` works and quietly includes `treadmill_running`, while `strength_training` returns HTTP 400 and has to be requested as `fitness_equipment` then filtered in Python. And each activity carries about a hundred fields, so map them down to the handful you need: returning raw Garmin JSON floods the context window on every call.

Keep the number of tools small for the same reason. Three focused tools with descriptive docstrings work better than a dozen vague ones, because the docstrings are what Claude reads when choosing which tool to call.

MIT licensed.
