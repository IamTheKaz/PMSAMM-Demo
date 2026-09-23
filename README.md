# PMSAMM — Preventative Maintenance System for Additive Manufacturing Monitoring

Capstone demo for **Haven-1 Bay 3**: a three-tier AI monitor for 3D-print defects in microgravity. Edge TFLite classifies the frame, cloud vision can add labels, and an LLM (Claude on Bedrock) is the final decision authority — unless comms are down, in which case SAM governs locally.

**Repo:** [IamTheKaz/PMSAMM-Demo](https://github.com/IamTheKaz/PMSAMM-Demo)
**GitHub Pages:** [iamthekaz.github.io/PMSAMM-Demo](https://iamthekaz.github.io/PMSAMM-Demo/)
**Primary UI:** `SAM_PMSAMM_demo.html` (also `SAM_PMSAMM_demo-2.html`, `SAM_PMSAMM_demo-16.html`)

Basis for a 2026 IEEE conference paper submission. Several external users have run the demo.

---

## What it is

SAM (Structural Anomaly Monitor) watches a printer camera frame plus telemetry (nozzle, bed, speed, layer, extrusion, retraction, vibration, progress). It classifies **none / underextrusion / stringing / spaghetti**, then asks whether the print can continue autonomously, needs a crew look, or must abort — with FOD (floating debris) rules for microgravity.

Human-in-the-loop is the point. Criticality of the part (decorative vs mission-critical) changes who is allowed to decide.

---

## Three-tier architecture

```
Camera frame + telemetry
        |
        v
+---------------------------+
|  Tier 1 — Edge SAM        |  TFLite model (sam_model.tflite)
|  AWS Lambda Function URL  |  classes: none, underextrusion,
|  (or local Python server) |  stringing, spaghetti
+------------+--------------+
             | label, confidence, raw_scores
             v
+---------------------------+
|  Tier 2 — Cloud vision    |  AWS Rekognition labels / boxes
|  (simulated in demo)      |  folded into the Claude report
+------------+--------------+
             v
+---------------------------+
|  Tier 3 — LLM authority   |  Claude Sonnet on Amazon Bedrock
|  API Gateway + DynamoDB   |  action, risk, crew message,
|                           |  telemetry adjustments, abort rules
+---------------------------+
```

If **comms blackout** is on, tier 3 is skipped. SAM's own prediction governs; crew still gets a local go/no-go when confidence is low or the part is Level 2/3.

---

## Pipeline (what the UI actually does)

| Stage | Behavior |
| --- | --- |
| **0 Telemetry** | Load a JPG/PNG frame. Set nozzle/bed/speed/layer/extrusion, part, crew name, criticality 1–3, optional comms blackout and SAM override. |
| **1 SAM** | POST the image to the TFLite Lambda (or local server). Confidence under 55% becomes `low confidence (unsure)`. |
| **2 Rekognition** | Demo-mode labels/boxes; production would call Rekognition. |
| **3 Claude** | Structured report + image to Bedrock. Returns markdown analysis plus a compliance log: `action_required`, `risk_level`, `notify_crew`, `detected_defect`, `crew_message`, `autonomous_corrections`, `telemetry_adjustments`. |
| **4 Outcome** | Disposition, SAM-vs-Claude agreement, crew modal if required. |

**Crew modal** depends on action:

- `CREW_APPROVAL` — Approve autonomous changes / Override
- `PAUSE_AND_INSPECT` — Inspected, resume / Confirm abort
- `ABORT` — Acknowledge + FOD sweep / Hold for review
- Blackout — local Continue / Pause

**History / abort (DynamoDB):** same defect twice after corrections → persistent-error abort. Two different defect types in one job → unstable-print abort. Both skip Claude.

---

## Criticality

| Level | Meaning | Typical policy |
| --- | --- | --- |
| 1 Non-critical | Decorative | Fixable defects can auto-correct; spaghetti still alerts crew |
| 2 Semi-critical | Minor functional | High continuation risk pauses for crew |
| 3 Mission-critical | Structural / life support | Any defect needs crew approval |

---

## How it was built (agentic coding)

Capstone work, directed with **Claude, Grok, and VS Code** — same loop as [AOBook2](https://github.com/IamTheKaz/AOBook2) and [Read2Me](https://github.com/IamTheKaz/Read2Me):

1. Specify the operational rules (criticality, blackout, FOD, abort history).
2. Let agents draft the HTML console, Lambda handlers, and Bedrock prompt.
3. Review and override: TFLite on Lambda, not a random demo label; LLM as *final* authority, not a paste box; DynamoDB history that can abort without calling Claude.
4. Iterate with real frames, local TFLite, then Function URL + API Gateway.

Earlier README text described a paste-Claude placeholder. The code in this repo is the live three-tier system (`SYSTEM_OVERVIEW.txt`, `lambda_function.py`, `claude_print_analyzer.py`).

---

## Repo map

| File | Role |
| --- | --- |
| `SAM_PMSAMM_demo.html` | Full browser console (GitHub Pages) |
| `SAM_PMSAMM_demo-2.html`, `SAM_PMSAMM_demo-16.html` | Alternate / later UI revisions |
| `sam_model.tflite` | Edge classifier (224×224, 4 classes) |
| `lambda_function.py` | SAM inference Lambda (TFLite / tflite_runtime) |
| `sam_inference_lambda.py`, `sam_defect_inference.py` | Related inference helpers |
| `claude_print_analyzer.py` | Bedrock + DynamoDB analysis Lambda |
| `local_sam_server.py`, `local_proxy.py`, `local_sam_test.py` | Run SAM on a laptop |
| `simple_local_sam.html`, `simple_local_server_sam.html`, `simple_sam_inference.html` | Minimal inference UIs |
| `SYSTEM_OVERVIEW.txt` | Full operational spec |
| `README_LOCAL_*.md`, `README_PROXY.md` | Local / proxy notes |
| `samiam.mp4` | Demo clip |

---

## Run the UI

**GitHub Pages (no install):** open [iamthekaz.github.io/PMSAMM-Demo](https://iamthekaz.github.io/PMSAMM-Demo/) or `SAM_PMSAMM_demo.html` on Pages.

**From disk:**

```bash
python -m http.server 8000
```

Open `http://localhost:8000/SAM_PMSAMM_demo.html`.

Live SAM inference needs the Lambda Function URL (see `SYSTEM_OVERVIEW.txt`) or the local server below. Without it, the UI still walks the workflow; SAM may fall back depending on the HTML revision.

---

## Run SAM locally (TFLite)

```bash
python local_sam_server.py
```

Details: `README_LOCAL_SERVER.md`, `README_LOCAL_BROWSER.md`, `README_LOCAL_TEST.md`, `README_PROXY.md`.

`lambda_function.py` expects:

- Image as a data URL or raw base64
- Optional `{ "action": "ping" }` / `{ "action": "diag" }`
- Response: `{ "label", "confidence", "raw_scores" }`

---

## Claude / Bedrock contract

Analysis Lambda accepts `{ report, image, job_id, sam_result, meta }` and returns sectioned markdown plus a compliance block, for example:

```
action_required: CREW_APPROVAL
risk_level: HIGH
notify_crew: true
detected_defect: SPAGHETTI
crew_message: Commander Harris - Bay 3 print terminated.
autonomous_corrections: NONE - catastrophic failure
telemetry_adjustments: {}
```

`action_required` is one of `NONE | PAUSE_AND_INSPECT | CREW_APPROVAL | ABORT`.

---

## SAM labels

| Label | Meaning |
| --- | --- |
| `none` | Nominal print |
| `underextrusion` | Gaps / weak bonding — often temp or flow |
| `stringing` | Wisps between features — retraction / temp |
| `spaghetti` | Catastrophic nest; stop print; FOD sweep |
| `low confidence (unsure)` | Model under 55%; Claude uses the image, not the label |

---

## Stack

- Frontend: standalone HTML/CSS/JS (Haven-1 console)
- Edge model: TensorFlow Lite (`sam_model.tflite`)
- Inference: AWS Lambda (tflite_runtime or TensorFlow) or local Python
- LLM: Amazon Bedrock, Claude Sonnet
- Logs: DynamoDB (`SAM_PMSAMM_Logs`)
- Hosting: GitHub Pages + Lambda Function URL / API Gateway

---

## Related

- [Read2Me](https://github.com/IamTheKaz/Read2Me) — classroom karaoke reader (Grok Build)
- [AOBook2](https://github.com/IamTheKaz/AOBook2) — novel companion site and chapter reader

---

## Author

**Kassandra (Kaz) Wolff** — [@IamTheKaz](https://github.com/IamTheKaz)
B.S. AI Applications, University of Maryland Global Campus (capstone).

Demo for Haven-1 additive-manufacturing monitoring research. Not an official Vast / Haven-1 product.
