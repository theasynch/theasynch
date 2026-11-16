# Setup (5 minutes)

1. **Repo name must equal your username**: create/use `theasynch/theasynch` (public). GitHub shows its README.md on your profile.
2. Copy everything in this folder into the repo root (keep the `.github/` folder) and push.
3. Repo **Settings > Actions > General > Workflow permissions > Read and write**.
4. **Actions tab > refresh-cards > Run workflow** once. After that it refreshes every day on its own.

## Edit your content
Everything lives in `data/profile.json`: name, tagline, flow-stage statuses
(`solid` / `building` / `progress` / `queued`), projects. Push, and the Action rebuilds the cards.

## What moves on the chip (assets/hero.svg)
Each block animates like the hardware it represents. It is pure CSS inside the SVG, so there is no JavaScript.

| Block | Animation | Colour |
|---|---|---|
| Pad ring | clock pulse circulating the die, with a fading tail | gold |
| Neuron array | neurons spike at random (two firing rates) | LED green |
| SRAM macros | word-line scan down each macro, alternating | white |
| CPU | an instruction rippling through 5 pipeline stages | LED green |
| Analog / PLL | lock ripple through the concentric rings | gold |
| Power block | diagonal rail shimmer | mint |
| Whole die | scan-chain beam sweeping top to bottom | white glow |
| Board traces | signal pulses into and out of the die | LED green |
| Status LED | slow breathing next to the eyebrow text | LED green |

Timings and colours are plain data at the top of `scripts/chip_anim.py` (`ANIMS`). Change a period or colour, push, done.
Visitors who have "reduce motion" enabled in their OS see a still image automatically.

## Use a portrait instead of the chip die
Put a photo at `source-photo.png` and set `"ascii": { "mode": "photo", ... }` in `data/profile.json`
(`"invert": true` if it looks like a negative). A photo has no blocks, so it gets a random twinkle plus the scan beam.

## Run locally
```
pip install pillow fonttools
python scripts/build.py
```
Cards land in `assets/`. Open the .svg files in a browser to see the animation.

## Notes
- GitHub caches README images for a few minutes, so a fresh build can take a moment to appear.
- Some mobile apps and email previews render SVGs as still images. The static state still looks complete.
- If GitHub's calendar markup ever changes and the live fetch fails, the build reuses `data/contribs-cache.json` instead of breaking.
- Fonts: Instrument Serif (SIL OFL). Headlines are converted to outlines, so no font loading is needed in the SVGs.
