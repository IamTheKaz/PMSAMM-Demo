# SAM - PMSAMM Demo

A single-page HTML/JavaScript demo showcasing a 3D print monitoring workflow using the **Synthetic Anomaly Model (SAM)** within the **Predictive Multi-Stage Anomaly Monitoring Model (PMSAMM)**.

## Overview

This demo simulates a human-in-the-loop decision-making pipeline for 3D printer defect detection:

1. **Telemetry Parsing** — Load system metrics (nozzle temp, extrusion rate, layer height, etc.)
2. **SAM Analysis** — Classify detected print anomalies (stringing, spaghetti, under-extrusion, etc.) with confidence scores
3. **Rekognition** — Placeholder AWS Rekognition labels and bounding boxes for detected issues
4. **Claude AI Review** — Send compiled report to Claude; paste JSON responses to extract recommendations and crew notifications
5. **Outcome & Disposition** — Display final status and crew notification based on Claude's analysis

## Features

- **Haven-1 themed UI** — Clean white/tan palette with NASA blue accents
- **Mission-critical component levels** — Classify parts as Non-Critical, Semi-Critical, or Mission-Critical
- **Manual SAM error override** — Select a specific error label to override randomized SAM judgment
- **Claude JSON parsing** — Parse `recommendations`, `notify_crew`, `action_required`, and `risk_level` from Claude responses
- **Crew notification logic** — Conditionally send crew alerts based on Claude recommendations or selected SAM error
- **ASCII-only output** — Clean, plain-text rendering with no Unicode decorative characters

## How to Run

1. Open `SAM_PMSAMM_demo.html` in a modern web browser (Chrome, Firefox, Safari, Edge)
2. No external dependencies or build step required — runs completely client-side
3. Load a JPG or PNG frame capture from a 3D printer camera
4. Select component criticality level (1–3)
5. Click **Run SAM Analysis** to see telemetry and SAM judgment
6. Review AWS Rekognition response
7. Forward to Claude and paste Claude's response (JSON or plain text)
8. View final outcome and crew notifications

## Demo Workflow

### Stage 0: Telemetry Input
- Load frame capture image
- Set component criticality level
- Input part/reference number
- Optionally override SAM error label for demo purposes

### Stage 1: SAM Report
- Displays SAM judgment (confidence, error classification)
- Shows parsed telemetry metrics
- Indicates whether error label was manually overridden

### Stage 2: Rekognition
- Simulates AWS Rekognition labeling
- Shows confidence scores and bounding boxes (demo values)
- Displays moderation flags if anomalies detected

### Stage 3: Claude AI
- Displays compiled report to send to Claude
- **Accept Claude response** — Upload `.txt` or `.json` file, or paste response directly
- Parses JSON fields: `action_required`, `risk_level`, `analysis_summary`, `recommendations`, `notify_crew`
- Falls back to regex pattern matching for plain-text responses

### Stage 4: Outcome
- Shows final disposition (status label, color, action, crew notification)
- Claude's `notify_crew` flag and selected SAM error label determine crew notification
- Display clarifier notes on how outcome was derived

## Claude JSON Response Format

Example response for Claude to return (or paste):

```json
{
  "action_required": "CREW_APPROVAL",
  "risk_level": "HIGH",
  "analysis_summary": "Frame analysis indicates probable stringing artifact on print perimeter.",
  "recommendations": [
    "Inspect nozzle tip for accumulated filament residue.",
    "Verify retraction settings in slicing profile.",
    "Consider test print with optimized speed parameters."
  ],
  "notify_crew": true
}
```

## Environment

- **Standalone HTML/CSS/JavaScript** — No frameworks or external dependencies
- **Client-side only** — No server backend required for demo
- **Responsive design** — Works on desktop and tablet browsers
- **Accessibility** — ARIA labels and semantic HTML for screen readers

## Files

- `SAM_PMSAMM_demo.html` — Complete demo application
- `vast.jpg` — Haven-1 topbar logo
- `README.md` — This file

## License

Demo for Haven-1 3D printer monitoring research.

## Notes

- In production, AWS Rekognition and Claude API calls would be real; this demo uses placeholder responses
- SAM judgments are randomized unless an error label is manually selected
- Crew notifications are driven by Claude recommendations and component criticality
- All output is ASCII-safe for compatibility with terminal displays and logging systems
