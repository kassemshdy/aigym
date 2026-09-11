# Investor pitch

`docs/AIGym-Investor-Pitch.pptx` — editable deck
`docs/AIGym-Investor-Pitch.pdf` — what you send

## Regenerating

```bash
cd docs/pitch
npm install pptxgenjs
node build.mjs                      # writes AIGym-Investor-Pitch.pptx

soffice --headless --norestore -env:UserInstallation=file:///tmp/loprof \
  --convert-to pdf --outdir . AIGym-Investor-Pitch.pptx
```

The PDF export needs **`libreoffice-impress`** — `libreoffice-core` alone has no Impress
import filter and fails on every `.pptx` with "source file could not be loaded", which looks
like a corrupt file but is not. It also wants **`fonts-liberation`** and
**`fonts-crosextra-carlito`**: they are metric-compatible stand-ins for Arial and Calibri, and
without them the substituted fonts have different character widths, so text that fits in
PowerPoint overflows its box in the PDF.

## Before sending it

Every number the deck does not know is marked `[FILL: …]` rather than invented. Find them all:

```bash
pdftotext AIGym-Investor-Pitch.pdf - | tr '\n' ' ' | grep -o "\[FILL:[^]]*\]"
```

The traction slide is deliberately close to empty. That is the honest state until Triple A has
run on the app for 30 days — see `../GTM.md` for the plan that fills it.
