# Channel Strategy — "The Ledger" (working title)

> Faceless, static-AI-imagery documentary channel covering **financial history &
> wealth case studies** — "the rise, fall, and psychology of money."

## 1. Niche Decision

### The winning niche: Financial & Economic History Case Studies

Long-form (12–22 min) narrative documentaries on the rise/fall of companies,
fortunes, currencies, empires, and economic eras — e.g. *"The Collapse of the
South Sea Bubble,"* *"How the Medici Invented Banking,"* *"The $2 Trillion
Mistake: Nokia's Fall,"* *"The Weimar Hyperinflation, Explained."*

This sits at the intersection of three signals from the research below, and no
single one of them alone is the right call:

| Signal | Data | Source |
|---|---|---|
| Finance-adjacent niches carry the highest faceless RPM | Personal finance $15–25, luxury/wealth $12–18, B2B/finance $14–38 | Fliki, OutlierKit, EasyViral 2026 niche reports |
| Pure history/documentary alone under-monetizes | $5–12 RPM, diluted by international audience mix | OutlierKit RPM data |
| The static-image + Ken Burns + AI-narration format is *proven at scale in this exact genre* | "Boring History" — 6-hour AI-narrated documentaries, scripts from Claude, narration from ElevenLabs, ~$40–60K/month | Faceless.my / OutlierKit channel case studies |
| 8+ minute run time unlocks mid-roll ads | Mid-rolls lift RPM 40–100% vs. pre-roll only | FluxNote 2026 mid-roll data |

**Why the hybrid beats each pure play:**
- Pure "personal finance tips" ($15–25 RPM) is the single highest-earning
  faceless category, but it's also the most saturated and policy-scrutinized
  (YouTube explicitly flags "synthetic AI personas covering sensitive topics
  like health and finance" as a monetization risk when there's no real
  original analysis behind it).
- Pure "history" ($5–12 RPM) has proven audience retention (documentary
  structure = problem → conflict → resolution, built for long watch time) but
  leaves money on the table with a lower-value ad demographic.
- **Financial history** inherits history's retention mechanics and its
  strong fit with the static-image/Ken Burns format, while pulling in
  finance/investing/business advertisers (fintech apps, brokerages, business
  software, MBA programs, business books) that bid at the higher end of the
  RPM range. It also reads unambiguously as *original, researched,
  editorial content* rather than a "synthetic persona giving financial
  advice" — sidestepping the exact category YouTube is cracking down on.

### Target sub-formats (rotating within one channel identity)
1. **Company case studies** — "The Rise and Fall of ___" (Enron, Nokia, Lehman Brothers, Blockbuster, Toys R Us)
2. **Currency & crisis deep dives** — hyperinflation events, bank runs, bubbles, crashes
3. **Wealth biographies** — how historical fortunes were built and lost (Medici, Rockefeller, Vanderbilt, Fugger)
4. **Economic-era explainers** — gold standard, Bretton Woods, the eurodollar system

Rotating sub-formats under one identity is itself a defense against the
"repetitive/formulaic" monetization flag — each video has a different
narrative arc, sourcing, and visual world rather than one templated pattern
repeated verbatim.

## 2. Visual & Artistic Direction

- **Style:** consistent painterly-cinematic realism — muted, desaturated
  period-accurate palettes per era (sepia/oil-painting tones for 1800s
  content, cool fluorescent/CRT tones for 1980s–2000s corporate stories).
  A single locked art style (defined in `config/style_guides/*.yaml`) is the
  channel's visual signature — the same reason "Fascinating Horror" and
  "Business Casual" are instantly recognizable by thumbnail alone.
- **Motion:** slow Ken Burns pan/zoom (2–5% scale drift over 6–10s per
  image), never more than one image per ~8–12s of narration, easing curves
  instead of linear zoom to avoid the "AI slideshow" feel called out in
  YouTube's inauthentic-content guidance.
- **Composition rule:** every generated image is composed for a 16:9 safe
  crop with headroom for burned-in lower-third subtitles — no text baked
  into the AI image itself (avoids garbled AI-text artifacts).
- **Continuity:** recurring visual motifs (a signature ledger/chart wipe
  transition, consistent title card, consistent narrator "voice mark") build
  brand recognition without a human face.

## 3. Target Audience

- **Primary:** 25–54, English-speaking, desktop/TV-app viewers interested in
  business, investing, self-improvement, and history — the demographic
  advertisers pay the most to reach (fintech, brokerages, business SaaS,
  online courses, business books/audiobooks).
- **Secondary:** general history/documentary audience via YouTube search and
  suggested-video traffic (long shelf life, evergreen search terms like
  "[Company] collapse explained").
- **Viewing context:** long-form, sit-back/background-documentary viewing —
  which is exactly what unlocks multiple mid-roll ad breaks per video.

## 4. Competitive Advantage

Existing leaders — *Business Casual*, *Practical Wisdom*, *Modern MBA*,
*Economics Explained*, *Fascinating Horror* — validate the format and the
audience, but each has a gap this channel is built to exploit:

1. **Original-value defense by construction, not afterthought.** The
   pipeline (Part 2) enforces a mandatory research/outline stage with cited
   sources and a human-approval gate before narration — the exact
   "originality and added value" signal YouTube's 2026 inauthentic-content
   policy rewards, and most low-effort AI channels skip.
2. **Locked, era-aware art direction** vs. competitors' generic
   stock-photo/stock-AI-image libraries — instantly recognizable thumbnails,
   a real brand.
3. **Automation cost advantage.** Static image + Ken Burns + TTS is
   dramatically cheaper per minute than the AI-video-clip pipelines
   (Runway/Kling/Luma) competitors are drifting toward — this channel can
   sustain 2–3x the upload cadence at the same budget, compounding
   watch-time and search coverage.
4. **Compliance moat.** As YouTube's 2026 enforcement (three-strike
   inauthentic-content system) removes the lowest-effort "verbatim
   TTS-over-slideshow" channels from the space, a channel that already
   treats disclosure (`altered_or_synthetic` toggle), sourcing, and
   non-templated structure as first-class pipeline requirements keeps its
   monetization while competitors get demonetized.

## 5. Monetization & Compliance Checklist (enforced by the pipeline, see Part 2)

- [ ] Every script passes through a **research + outline** stage with
      source citations before narration (originality signal).
- [ ] Every upload sets the **"Altered or synthetic content" disclosure**
      via the YouTube Data API `containsSyntheticMedia` field.
- [ ] No verbatim reuse of a single source text — scripts are synthesized
      from multiple sources with original framing/thesis.
- [ ] Human-in-the-loop approval gate between script generation and
      production (configurable, on by default) — keeps a person accountable
      for "original insight," which is what the policy actually tests for.
- [ ] Visual style, structure, and thesis rotate across the 4 sub-formats
      to avoid the "mass-produced/repetitive" pattern match.
- [ ] Avoid the explicitly named risk category: no synthetic persona
      presented as giving personalized financial/health advice — this is a
      documentary/historical-analysis channel, not an advice channel.

## Sources

- [18 Best Faceless YouTube Niches in 2026 — Fliki](https://fliki.ai/blog/best-faceless-youtube-niches)
- [15 Faceless YouTube Channel Ideas Ranked by RPM (2026 Data) — EasyViral.ai](https://easyviral.ai/blog/15-faceless-youtube-channel-ideas-ranked-by-rpm-2026)
- [19 Most Profitable YouTube Niches 2026 — OutlierKit](https://outlierkit.com/blog/most-profitable-youtube-niches)
- [Best Faceless YouTube Niches & Channel Ideas 2026 — OutlierKit Resources](https://outlierkit.com/resources/faceless-youtube-channels/)
- [YouTube AI Monetization Policy 2026 — Vexub](https://vexub.com/blog/ai-generated-video-monetization-policies)
- [YouTube Targets AI Slop: New Monetization Rules — AndroidHeadlines](https://www.androidheadlines.com/2026/07/youtube-monetization-rules-ai-slop-inauthentic-content.html)
- [YouTube clarifies policies around AI slop and upsetting videos — TechCrunch](https://techcrunch.com/2026/07/20/youtube-clarifies-policies-around-ai-slop-and-upsetting-videos/)
- [YouTube Inauthentic Content Policy 2026 — AuditSocials](https://www.auditsocials.com/blog/youtube-inauthentic-content-policy-2026-mass-produced-ai-generated-monetization-creators-brands)
- [Faceless Finance Channels: Complete Guide 2026 — Flarecut](https://flarecut.com/blog/faceless-finance-channels/)
- [Top Faceless YouTube Channels 2026 — Faceless.my](https://faceless.my/youtube/top-faceless-youtube-channels/)
- [YouTube Mid-Roll Ads 2026: The 8-Minute Rule — FluxNote](https://fluxnote.io/guides/youtube-mid-roll-ads-eligibility-2026)
- [Ken Burns and visual sourcing for faceless video — Thothium](https://thothium.com/blog/ken-burns-visual-sourcing-faceless-video)
