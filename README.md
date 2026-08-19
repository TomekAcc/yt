# yt — "The Ledger" AI channel automation engine

An end-to-end pipeline that turns a topic idea into an uploaded YouTube
video: research → script → compliance review → AI images (Ken Burns
pan/zoom) → AI narration → synced subtitles → assembled video → SEO
metadata → upload.

Read [STRATEGY.md](STRATEGY.md) first — it explains *why* this channel
(niche, visual direction, audience, monetization compliance) before this
document explains *how* the code implements it.

## Architecture

```
yt_engine/
  models.py            # ProjectState + every stage's data model (pydantic)
  config.py             # Settings: secrets from .env, run config from config/settings.yaml
  pipeline.py            # Orchestrator: resumable stage state machine
  cli.py                  # `python -m yt_engine ...`
  content/                 # Stages 1-4: ideation, research, script, compliance
    ideation.py
    research.py
    script_writer.py
    compliance.py
    llm_client.py           # Anthropic wrapper shared by the above
    search.py                # optional Tavily web search for research grounding
  media/                    # Stages 5-7: images, narration, subtitles, assembly
    image_providers/          # OpenAI / Stability, pluggable
    tts_providers/              # ElevenLabs / OpenAI, pluggable
    subtitles.py                  # word-timing -> paced SRT
    video_assembler.py              # Ken Burns + ffmpeg subtitle burn
    thumbnail.py
  publish/                   # Stages 8-9: metadata + YouTube upload
    metadata.py
    youtube_auth.py
    youtube_uploader.py
  storage/
    project_store.py            # JSON state snapshot after every stage
```

Every stage reads/writes a single `ProjectState` (see `yt_engine/models.py`)
that's saved to `workspace/<project_id>/state.json` after each step. A
crash, an API outage, or a manual stop costs at most the stage in progress
— rerunning `python -m yt_engine run <project_id>` picks up exactly where
it left off instead of regenerating already-finished images/audio/script.

## Pipeline stages

| # | Stage | What happens | Costs money? |
|---|---|---|---|
| 1 | Ideation | LLM pitches topics rotating across the 4 sub-formats | LLM call |
| 2 | Research | LLM (+ optional Tavily search) builds a cited research brief | LLM call |
| 3 | Scripting | LLM writes scene-by-scene narration + image prompts | LLM call |
| 4 | **Compliance review** | Automated checks + **human approval gate** (default on) | free |
| 5 | Image generation | One AI image per scene, in the locked style guide | image API call per scene |
| 6 | Narration | TTS per scene (ElevenLabs returns word timings natively) | TTS API call per scene |
| 7 | Subtitles | Forced alignment (faster-whisper) only if the TTS provider didn't return timings | free (local) or GPU/CPU time |
| 8 | Assembly | Ken Burns pan/zoom per scene, concatenated, subtitles burned in via ffmpeg | free (local) |
| 9 | Metadata | LLM writes SEO title/description/tags, sets the synthetic-media disclosure | LLM call |
| 10 | Upload | Resumable upload via YouTube Data API v3, private by default | free |

Stage 4 is the pipeline's answer to YouTube's 2026 "inauthentic content"
policy (see STRATEGY.md §5): a script can't reach image/voice generation —
where money actually gets spent — without passing automated originality
checks (multi-sourced, real thesis, sufficient research depth, non-templated
scene structure, sub-format rotation) and, by default, a human's explicit
approval.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in the keys for the providers you're using
```

Provider choice lives in `config/settings.yaml` (`providers.llm`,
`providers.image`, `providers.tts`). By default all three are set to
`gemini`, so **one `GEMINI_API_KEY` is all you need** to run the whole
pipeline (scripting, images, and narration) end to end:

1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
   and sign in with a Google account (no separate Cloud project or billing
   setup needed to start).
2. Click **Create API key** (it provisions a backing project for you
   automatically).
3. Copy the key into `.env` as `GEMINI_API_KEY=...`.

The free tier is rate-limited (whitepaper numbers move around, currently
on the order of 10 requests/minute, ~250/day) — plenty for iterating on one
video at a time; add billing on the Google Cloud project AI Studio created
if you need higher throughput.

Each stage can independently be switched to a different provider if you
want to (e.g. Anthropic for scripting, ElevenLabs for narration — see the
comments in `config/settings.yaml`), by setting that provider's option and
adding its matching key to `.env`. Nothing else needs to change.

### Narration provider and commercial-use licensing

`providers.tts` supports three options, and their licensing terms differ in
a way that matters once you plan to monetize:

| Provider | Voice quality | Native subtitle timestamps | Free tier usable for a monetized channel? |
|---|---|---|---|
| `gemini` (default) | Very good, expressive, 30+ voices | No (falls back to local whisper alignment) | **Yes.** Same `GEMINI_API_KEY` as everything else -- no separate signup. Google's Gemini API free tier does not prohibit commercial use of output; the only catch is Google may use free-tier prompts/output to improve their models, and the free tier isn't available to API clients serving users in the EEA/UK/Switzerland. |
| `elevenlabs` | Best -- most natural documentary read | Yes (`with-timestamps` endpoint) | **No.** ElevenLabs' free plan ToS explicitly forbids commercial use and requires "elevenlabs.io" attribution if you publish anything made with it. Needs at least the Starter paid plan before a monetized upload. |
| `openai` | Good | No (falls back to local whisper alignment) | **Yes, immediately.** The `/v1/audio/speech` API (what this provider calls) is pay-as-you-go from the first request with standard commercial output-ownership terms -- no separate "free vs. paid license" tier to worry about. (This is different from ChatGPT's conversational Voice Mode, which *is* non-commercial -- the API endpoint isn't that.) |

Practical read: the default (`gemini`) needs no second subscription and is
safe to monetize on the free tier. If you want the single highest voice
quality and don't mind a second signup, switch to `elevenlabs` -- but
budget for its paid plan before publishing anything monetized (testing
with a `private` upload on its free plan is fine).

For YouTube upload: create an OAuth client ID (Desktop app) in Google Cloud
Console with the YouTube Data API v3 enabled, download the client secret
JSON, and point `YOUTUBE_CLIENT_SECRETS_FILE` at it. The first upload opens
a browser for a one-time login; the refresh token is then cached at
`YOUTUBE_TOKEN_FILE`.

## Usage

```bash
# 1. Generate candidate topics (rotates across the 4 sub-formats)
python -m yt_engine ideate --count 5

# 2. Build one of them. This walks research -> script -> compliance review
#    (prints the script + checks, asks for your y/n) -> images -> narration
#    -> subtitles -> assembly -> metadata -> upload.
python -m yt_engine produce --pick 0

# Render only, skip upload:
python -m yt_engine produce --pick 0 --no-upload

# Resume a project that stopped or failed partway through:
python -m yt_engine run <project_id>

python -m yt_engine status <project_id>
python -m yt_engine list
```

Uploaded videos are set to `private` by default
(`channel.default_privacy_status` in `config/settings.yaml`) — a human does
a final look in YouTube Studio and publishes.

## Testing

```bash
pip install -r requirements.txt   # includes pytest
pytest
```

The test suite runs the full Ken Burns + ffmpeg subtitle-burn render and
the entire pipeline state machine (including the compliance gate and
resume-from-crash behavior) against small synthetic images/audio — no API
keys or network access required. LLM and third-party API calls are
replaced with fakes in `tests/fakes.py`.

## Extending

- **New image/TTS provider:** implement `ImageProvider`/`TTSProvider`
  (`yt_engine/media/*_providers/base.py`) and register it in that
  package's `build_*_provider()` factory.
- **New sub-format or niche:** add a value to `SubFormat` in `models.py`,
  update the ideation/script prompts, and add a style guide YAML under
  `config/style_guides/`.
- **Different visual identity:** edit
  `config/style_guides/financial_history.yaml` — every image prompt is
  generated with that file's content injected verbatim.
