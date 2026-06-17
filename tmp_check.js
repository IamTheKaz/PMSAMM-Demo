
// ---------------------------------------------------------------
// CONFIG - paste your Lambda Function URL here
// ---------------------------------------------------------------
const BEDROCK_URL = 'https://a3rb7swog2.execute-api.us-west-2.amazonaws.com/analyze';
const SAM_URL = 'https://wtcqbp7rmnoy3pf7hty2bcyoea0dcese.lambda-url.us-west-2.on.aws/';
const SAM_PRECEDENCE_THRESHOLD = 80;

let state = {
  crit: 3,
  imgDataUrl: null,
  imgName: null,
  samJudgment: null,
  fullReport: null,
  claudeParsed: null,
  currentStage: 0,
  jobId: null
};

function generateJobId() {
  let part = (document.getElementById('t-part').value || 'UNKNOWN').replace(/[^a-zA-Z0-9]/g,'-').substring(0,12).toUpperCase();
  let crew = (document.getElementById('t-crew').value || 'CREW').replace(/[^a-zA-Z0-9]/g,'').substring(0,8).toUpperCase();
  let ts = new Date().toISOString().substring(0,10).replace(/-/g,'');
  return 'HAVEN1-'+part+'-'+crew+'-'+ts;
}

// ---------------------------------------------------------------
function renderSAMSummary() {
  if(!state.samJudgment) return '';
  return '<div class="resp-block" style="border-color:#0033a044;background:#edf3ff;">' +
         '<div class="resp-src" style="color:#0033a0">RECORDED SAM PREDICTION</div>' +
         '<div class="outcome-summary">SAM predicted <strong>' + String(state.samJudgment.e).toUpperCase() + '</strong> at <strong>' + state.samJudgment.c + '%</strong> confidence.</div>' +
         '</div><br>';
}

function samAndClaudeAgree() {
  if(!state.claudeParsed || !state.samJudgment) return false;
  let samLabel = String(state.samJudgment.e || '').trim().toLowerCase();
  let claudeLabel = String(state.claudeParsed.detected_defect || '').trim().toLowerCase();
  return samLabel && claudeLabel && samLabel === claudeLabel;
}

function renderSamClaudeComparison() {
  if(!state.claudeParsed || !state.samJudgment) return '';
  let samLabel = String(state.samJudgment.e || 'UNKNOWN').trim().toUpperCase();
  let claudeLabel = String(state.claudeParsed.detected_defect || 'UNKNOWN').trim().toUpperCase();
  let html = '<div class="resp-block" style="border-color:#0033a044;background:#edf3ff;">';
  html += '<div class="resp-src" style="color:#0033a0">SAM vs CLAUDE</div>';
  html += '<div class="outcome-summary">Recorded SAM prediction: <strong>' + samLabel + '</strong> at <strong>' + state.samJudgment.c + '%</strong> confidence.<br>';
  html += 'Claude parsed defect: <strong>' + claudeLabel + '</strong>.</div>';
  if(samLabel === claudeLabel) {
    html += '<div style="font-size:11px;color:#3fb950;margin-top:6px;">SAM and Claude agree on the defect label.</div>';
  } else {
    html += '<div style="font-size:11px;color:#f85149;margin-top:6px;">SAM and Claude do not agree on the defect label.</div>';
  }
  html += '</div><br>';
  return html;
}

function shouldPreserveSamDecision() {
  if(!state.claudeParsed || !state.samJudgment) return false;
  let samLabel = String(state.samJudgment.e || '').trim().toLowerCase();
  let claudeLabel = String(state.claudeParsed.detected_defect || '').trim().toLowerCase();
  if(!samLabel || !claudeLabel) return false;
  return state.samJudgment.c >= SAM_PRECEDENCE_THRESHOLD && samLabel !== claudeLabel;
}

function renderDecisionSource(source) {
  return '<div class="resp-block" style="border-color:#64748b44;background:#f8fafc;">' +
         '<div class="resp-src" style="color:#334155">FINAL DECISION SOURCE</div>' +
         '<div class="outcome-summary">' + source + '</div>' +
         '</div><br>';
}

// ---------------------------------------------------------------
// CRITICALITY
// ---------------------------------------------------------------
function setCrit(n) {
  state.crit = n;
  [1,2,3].forEach(i => {
    let el = document.getElementById('crit-'+i);
    el.className = 'crit-btn';
    if(i===n) el.classList.add('sel-'+n);
  });
}
setCrit(3);

// ---------------------------------------------------------------
// IMAGE LOAD
// ---------------------------------------------------------------
function loadImage(e) {
  let file = e.target.files[0];
  if(!file) return;
  state.imgName = file.name;
  let reader = new FileReader();
  reader.onload = function(ev) {
    state.imgDataUrl = ev.target.result;
    let wrap = document.getElementById('img-preview-wrap');
    wrap.innerHTML = '<img src="'+ev.target.result+'" style="max-height:160px;max-width:100%;border-radius:4px;"><div class="img-drop-text" style="margin-top:6px;color:#3fb950;">Frame captured - '+file.name+'</div>';
    document.getElementById('img-drop').classList.add('has-img');
  };
  reader.readAsDataURL(file);
}

function renderImagePreview() {
  let wrap = document.getElementById('img-preview-wrap');
  if(state && state.imgDataUrl) {
    let name = state.imgName || 'capture.jpg';
    wrap.innerHTML = '<img src="'+state.imgDataUrl+'" style="max-height:160px;max-width:100%;border-radius:4px;"><div class="img-drop-text" style="margin-top:6px;color:#3fb950;">Frame captured - '+name+'</div>';
    document.getElementById('img-drop').classList.add('has-img');
  }
}

// ---------------------------------------------------------------
// CRITICALITY LABELS
// ---------------------------------------------------------------
function getCritLabel(n) {
  if(n===1) return ['NON-CRITICAL','Decorative or aesthetic component. Failure has no operational impact.','#3fb950'];
  if(n===2) return ['SEMI-CRITICAL','Minor functional part. Failure degrades but does not halt operations.','#d29922'];
  return ['MISSION-CRITICAL','Structural, life support, or safety-adjacent component. Any defect must escalate immediately.','#f85149'];
}

// ---------------------------------------------------------------
// SAM JUDGMENT
// ---------------------------------------------------------------
function getSAMJudgment() {
  let opts = [
    {j:'Spaghetti stringing detected on perimeter layers. Extrusion inconsistency noted at 23% print height.', e:'stringing', c:71},
    {j:'Print progressing nominally. Layer adhesion consistent. No anomalies detected in current frame.', e:'none', c:94},
    {j:'Possible filament spaghetti build-up detected along outer contours. Print extrusion appears unstable.', e:'spaghetti', c:62},
    {j:'Under-extrusion artifacts visible on upper layers. Potential partial clog in nozzle assembly.', e:'underextrusion', c:78},
    {j:'Model confidence is low. Prediction is uncertain and may require manual review.', e:'low confidence (unsure)', c:49}
  ];
  return opts[Math.floor(Math.random()*opts.length)];
}

function getManualSAMJudgment(label) {
  switch(String(label).trim().toLowerCase()) {
    case 'stringing':      return {j:'Spaghetti stringing detected on perimeter layers. Extrusion inconsistency noted at 23% print height.', e:'stringing', c:71};
    case 'spaghetti':     return {j:'Possible filament spaghetti build-up detected along outer contours. Print extrusion appears unstable.', e:'spaghetti', c:62};
    case 'underextrusion':return {j:'Under-extrusion artifacts visible on upper layers. Potential partial clog in nozzle assembly.', e:'underextrusion', c:78};
    case 'none':          return {j:'Print progressing nominally. Layer adhesion consistent. No anomalies detected in current frame.', e:'none', c:94};
    case 'low confidence (unsure)': return {j:'Model confidence is low. Prediction is uncertain and may require manual review.', e:'low confidence (unsure)', c:49};
    default: return getSAMJudgment();
  }
}

// ---------------------------------------------------------------
// REPORT BUILDER
// ---------------------------------------------------------------
function formatReport(includeRek, rekContent) {
  let nozzle  = document.getElementById('t-nozzle').value || '-';
  let crew    = document.getElementById('t-crew').value || '[unassigned]';
  let bed     = document.getElementById('t-bed').value || '-';
  let speed   = document.getElementById('t-speed').value || '-';
  let layer   = document.getElementById('t-layer').value || '-';
  let extrude = document.getElementById('t-extrude').value || '-';
  let retract = document.getElementById('t-retract').value || '-';
  let vib     = document.getElementById('t-vib').value || '-';
  let prog    = document.getElementById('t-prog').value || '-';
  let mat     = document.getElementById('t-mat').value || '-';
  let part    = document.getElementById('t-part').value || '[unspecified]';
  let [clabel] = getCritLabel(state.crit);
  let j = state.samJudgment;
  let ts = new Date().toISOString().replace('T',' ').substring(0,19)+' UTC';
  let defect = (j.e || 'UNKNOWN').toUpperCase();
  let modelConf = (j.c / 100).toFixed(2);
  let rekConf = Math.min(99, Math.max(60, Math.round(j.c * 0.92 + 5)));

  let lines = [];
  lines.push('==================================================');
  lines.push('  SAM - PMSAMM - HAVEN-1 - BAY 3');
  lines.push('  MONITORING REPORT - SN: 3DP-H1-007');
  lines.push('  '+ts);
  lines.push('==================================================');
  lines.push('');
  lines.push('-- TELEMETRY -------------------------------------');
  lines.push('  Nozzle Temp    : '+nozzle+' C');
  lines.push('  Bed Temp       : '+bed+' C');
  lines.push('  Print Speed    : '+speed+' mm/s');
  lines.push('  Layer Height   : '+layer+' mm');
  lines.push('  Extrusion Rate : '+extrude+' %');
  lines.push('  Retraction     : '+retract+' mm');
  lines.push('  Vibration      : '+vib+' m/s^2');
  lines.push('  Progress       : '+prog+' %');
  lines.push('  Material       : '+mat);
  lines.push('');
  lines.push('-- COMPONENT ------------------------------------');
  lines.push('  Description    : '+part);
  lines.push('  Crew Member    : '+crew);
  lines.push('  Criticality    : Level '+state.crit+' - '+clabel);
  lines.push('  Crit. Basis    : '+getCritLabel(state.crit)[1]);
  lines.push('');
  lines.push('-- SAM VISUAL INFERENCE -------------------------');
  lines.push('  Frame          : '+(state.imgName||'[no image loaded]'));
  lines.push('  SAM Judgment   : '+j.j);
  lines.push('  Confidence     : '+j.c+'%');
  lines.push('  TF Model       : sam-3dp-v2.1-lite');
  lines.push('  Error Label    : '+(j.e || 'UNKNOWN'));
  lines.push('');
  if(includeRek && rekContent) {
    lines.push('-- AWS REKOGNITION RESPONSE ----------------------');
    lines.push(rekContent.split('\n').map(l=>'  '+l).join('\n'));
    lines.push('');
  }
  lines.push('-- DIRECTIVE ------------------------------------');
  lines.push('  To: Claude AI - Haven-1 AI Monitoring Specialist');
  lines.push('');
  lines.push('  Current Situation - Layer '+layer+' of active print:');
  lines.push('  - SAM prediction  : '+defect+' (Confidence: '+j.c+'%)');
  lines.push('  - Rekognition     : '+defect+' (Confidence: '+rekConf+'%)');
  lines.push('  - Nozzle Temp     : '+nozzle+'C');
  lines.push('  - Bed Temp        : '+bed+'C');
  lines.push('  - Extrusion Rate  : '+extrude+'%');
  lines.push('  - Print Speed     : '+speed+' mm/s');
  lines.push('  - Retraction      : '+retract+' mm');
  lines.push('  - Layer Height    : '+layer+' mm');
  lines.push('  - Part Criticality: Level '+state.crit+' ('+clabel+')');
  lines.push('');
  lines.push('  Perform step-by-step analysis:');
  lines.push('  1. Interpret combined model predictions and telemetry.');
  lines.push('  2. Consider microgravity-specific effects (FOD risk, filament behavior, cooling).');
  lines.push('  3. Assess structural integrity and crew safety implications.');
  lines.push('  4. Provide specific, actionable corrective recommendations.');
  lines.push('  5. State clearly whether crew approval is required.');
  lines.push('');
  lines.push('  Provide your full sectioned analysis per your standing instructions.');
  lines.push('  End with the compliance log section with action_required, risk_level, notify_crew, detected_defect.');
  lines.push('');
  lines.push('==================================================');
  lines.push('  END OF SAM REPORT');
  lines.push('==================================================');
  return lines.join('\n');
}

// ---------------------------------------------------------------
// REKOGNITION SIMULATOR
// ---------------------------------------------------------------
function buildRekResponse() {
  let j = state.samJudgment;
  let lines = [];
  if(j.c < 80) {
    lines.push('[0.'+Math.floor(80+Math.random()*15)+'] Plastic - 3D Print');
    lines.push('[0.'+Math.floor(60+Math.random()*20)+'] Defect - Stringing');
    lines.push('[0.'+Math.floor(55+Math.random()*25)+'] Print Anomaly');
    lines.push('[0.'+Math.floor(40+Math.random()*30)+'] Layer Inconsistency');
    lines.push('Moderation: Possible manufacturing defect detected.');
    lines.push('Bounding box: [x:124, y:88, w:210, h:195] - anomaly region');
  } else {
    lines.push('[0.'+Math.floor(88+Math.random()*10)+'] Plastic - 3D Print');
    lines.push('[0.'+Math.floor(70+Math.random()*20)+'] Manufacturing Process');
    lines.push('[0.'+Math.floor(60+Math.random()*25)+'] Layer Deposition');
    lines.push('Moderation: None.');
    lines.push('Bounding box: No anomaly regions flagged.');
  }
  lines.push('Image quality: ACCEPTABLE - Resolution: 1280x960');
  lines.push('[DEMO - Rekognition API placeholder]');
  return lines.join('\n');
}

// ---------------------------------------------------------------
// MAIN PIPELINE - runs automatically after SAM
// ---------------------------------------------------------------
async function runSAM() {
  let part = document.getElementById('t-part').value.trim();
  if(!part) {
    document.getElementById('t-part').focus();
    document.getElementById('t-part').style.borderColor='#f85149';
    return;
  }

  // Generate job_id once per print job
  if(!state.jobId) state.jobId = generateJobId();

  let selectedError = document.getElementById('t-error').value;

  // If image is loaded and no manual override, use real SAM inference
  if(state.imgDataUrl && !selectedError) {
    goStage(1);
    try {
      let samResp = await fetch(SAM_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: state.imgDataUrl })
      });
      let samData = await samResp.json();
      let body = typeof samData.body === 'string' ? JSON.parse(samData.body) : samData;
      if(body.label) {
        // Real SAM result
        state.samJudgment = {
          j: 'SAM inference: ' + body.label.toUpperCase() + ' detected. Confidence: ' + body.confidence + '%. Raw scores: ' + JSON.stringify(body.raw_scores),
          e: body.label,
          c: Math.round(body.confidence)
        };
        // Show raw scores in SAM stage
        document.getElementById('sam-processing').innerHTML =
          '<strong>SAM REAL INFERENCE RESULT</strong><br>' +
          'Label: <strong>' + body.label.toUpperCase() + '</strong> | Confidence: <strong>' + body.confidence + '%</strong><br>' +
          'Raw scores: ' + Object.entries(body.raw_scores).map(([k,v]) => k+': '+v+'%').join(' | ');
      } else {
        state.samJudgment = getSAMJudgment();
      }
    } catch(err) {
      console.log('SAM inference failed, using simulation:', err);
      state.samJudgment = getSAMJudgment();
    }
    setTimeout(() => {
      goToOutcome(false);
    }, 1500);
  } else {
    // Manual override or no image - use simulator
    state.samJudgment = selectedError ? getManualSAMJudgment(selectedError) : getSAMJudgment();
    goToOutcome(false);
  }
}

// ---------------------------------------------------------------
// FULL PIPELINE (SAM > Rekognition > Claude > Outcome)
// ---------------------------------------------------------------
function runFullPipeline() {
  goStage(1);
  setTimeout(() => {
    goStage(2);
    setTimeout(() => {
      let rekContent = buildRekResponse();
      state.rekContent = rekContent;
      let fullReport = formatReport(true, rekContent);
      state.fullReport = fullReport;
      goStage(3);
      callBedrock(fullReport);
    }, 1800);
  }, 900);
}

// Used when SAM real inference already ran and we're on stage 1
function runFullPipelineFromStage2() {
  goStage(2);
  setTimeout(() => {
    let rekContent = buildRekResponse();
    state.rekContent = rekContent;
    let fullReport = formatReport(true, rekContent);
    state.fullReport = fullReport;
    goStage(3);
    callBedrock(fullReport);
  }, 1800);
}

// ---------------------------------------------------------------
// BEDROCK CALL
// ---------------------------------------------------------------
async function callBedrock(reportText) {
  try {
    // Ensure job_id persists across runs in same session
    if(!state.jobId) state.jobId = generateJobId();

    let payload = {
      report:  reportText,
      job_id:  state.jobId,
      meta: {
        crew_member:      document.getElementById('t-crew').value || '',
        part_description: document.getElementById('t-part').value || '',
        criticality:      state.crit,
        print_progress:   document.getElementById('t-prog').value || '0',
        sam_confidence:   state.samJudgment ? state.samJudgment.c : 0,
        sam_label:        state.samJudgment ? state.samJudgment.e : ''
      }
    };
    if(state.imgDataUrl) {
      payload.image = state.imgDataUrl;
      payload.imageType = state.imgDataUrl.startsWith('data:image/png') ? 'image/png' : 'image/jpeg';
    }

    let response = await fetch(BEDROCK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    let data = await response.json();
    let body = typeof data.body === 'string' ? JSON.parse(data.body) : data;
    if(body.error) throw new Error(body.error);

    let rawText = body.response || '';

    // Extract compliance fields
    let action = 'MANUAL_REVIEW';
    let risk = 'UNKNOWN';
    let notify = true;
    let defect = 'UNKNOWN';
    let crewMsg = '';
    let autoCorrections = '';

    let am = rawText.match(/action.required[^a-zA-Z]+(NONE|PAUSE_AND_INSPECT|CREW_APPROVAL|ABORT)/i);
    if(am) action = am[1].toUpperCase();

    let rm = rawText.match(/risk.level[^a-zA-Z]+(LOW|MEDIUM|HIGH)/i);
    if(rm) risk = rm[1].toUpperCase();

    let nm = rawText.match(/notify.crew[^a-zA-Z]+(true|false)/i);
    if(nm) notify = nm[1].toLowerCase() === 'true';
    else notify = (action !== 'NONE');

    let dm = rawText.match(/detected.defect[^\n:]+[:]\s*([^\n]+)/i);
    if(!dm) dm = rawText.match(/detected.defect\s*[:\-]\s*([^\n]+)/i);
    if(dm) defect = dm[1].trim();

    let cm = rawText.match(/crew.message[^\n:]+[:]\s*([^\n]+)/i);
    if(cm && cm[1].trim().toLowerCase() !== 'none') crewMsg = cm[1].trim();

    let ac = rawText.match(/autonomous.corrections[^\n:]+[:]\s*([^\n]+)/i);
    if(ac && ac[1].trim().toLowerCase() !== 'none') autoCorrections = ac[1].trim();

    if(action === 'MANUAL_REVIEW' || action === 'CREW_APPROVAL' || action === 'ABORT') notify = true;

    // Extract telemetry adjustments from Lambda response
    let telemetryAdj = {};
    try {
      let respBody = typeof data.body === 'string' ? JSON.parse(data.body) : data;
      if(respBody.telemetry_adjustments) telemetryAdj = respBody.telemetry_adjustments;
    } catch(e) {}

    state.claudeParsed = {
      raw_response:            rawText,
      action_required:         action,
      risk_level:              risk,
      notify_crew:             notify,
      detected_defect:         defect,
      crew_message:            crewMsg,
      autonomous_corrections:  autoCorrections,
      telemetry_adjustments:   telemetryAdj
    };

    goToOutcome(false);

  } catch(err) {
    state.claudeParsed = null;
    state.claudeError = err.message;
    goToOutcome(false, err.message);
  }
}

// ---------------------------------------------------------------
// END OF PRINT
// ---------------------------------------------------------------
function runEndOfPrint() {
  let part = document.getElementById('t-part').value.trim();
  if(!part) {
    document.getElementById('t-part').focus();
    document.getElementById('t-part').style.borderColor='#f85149';
    return;
  }
  // Set progress to 100 for end of print report
  let origProg = document.getElementById('t-prog').value;
  document.getElementById('t-prog').value = '100';
  state.samJudgment = {j:'Print complete. Final layer reached.', e:'none', c:99};
  let rekContent = 'END OF PRINT - Final frame analysis requested.';
  let fullReport = formatReport(true, rekContent);
  document.getElementById('t-prog').value = origProg;
  state.fullReport = fullReport;
  // Keep same job_id for end of print, then clear after
  goStage(3);
  callBedrock(fullReport).then(() => { state.jobId = null; });
}

// ---------------------------------------------------------------
// OUTCOME
// ---------------------------------------------------------------
function goToOutcome(commsLost, errorMsg) {
  goStage(4);

  // Build flow row
  let flowEl = document.getElementById('flow-outcome');
  if(commsLost) {
    flowEl.innerHTML = `
      <div class="flow-node done">Telemetry</div><span class="flow-arrow">></span>
      <div class="flow-node done">SAM</div><span class="flow-arrow">></span>
      <div class="flow-node skipped">Rekognition</div><span class="flow-arrow">></span>
      <div class="flow-node skipped">Claude</div><span class="flow-arrow">></span>
      <div class="flow-node active">Outcome</div>`;
  } else {
    flowEl.innerHTML = `
      <div class="flow-node done">Telemetry</div><span class="flow-arrow">></span>
      <div class="flow-node done">SAM</div><span class="flow-arrow">></span>
      <div class="flow-node done">Rekognition</div><span class="flow-arrow">></span>
      <div class="flow-node done">Claude</div><span class="flow-arrow">></span>
      <div class="flow-node active">Outcome</div>`;
  }

  let el = document.getElementById('outcome-content');
  let j = state.samJudgment;
  let [clabel,,ccolor] = getCritLabel(state.crit);
  let html = '';

  if(commsLost) {
    // COMMS LOST - SAM autonomous decision
    let aboveThreshold = j.c >= 80;
    let statusColor = aboveThreshold ? '#f85149' : '#d29922';
    let statusLabel = aboveThreshold ? 'COMMS LOST - SAM AUTONOMOUS DECISION' : 'COMMS LOST - CONFIDENCE BELOW THRESHOLD';
    let action = aboveThreshold
      ? 'Communication with ground systems lost. SAM confidence is '+j.c+'% (above 80% threshold). Autonomous decision issued. Crew notification sent.'
      : 'Communication with ground systems lost. SAM confidence is '+j.c+'% (below 80% threshold). Insufficient confidence for autonomous action. Crew notified to inspect manually.';

    html += '<div class="comms-banner"><span>[ ! ] COMMS LOST - AUTONOMOUS MODE ACTIVE</span></div>';
    html += '<div class="resp-block" style="border-color:'+statusColor+'44;background:'+statusColor+'08;">';
    html += '<div class="resp-src" style="color:'+statusColor+'">'+statusLabel+'</div>';
    html += '<div class="outcome-header" style="color:'+statusColor+';">'+( aboveThreshold ? (j.e === 'none' ? 'CONTINUE PRINT' : 'PAUSE AND INSPECT') : 'MANUAL REVIEW REQUIRED' )+'</div>';
    html += '<div class="outcome-summary">'+action+'</div>';
    html += '<div style="font-size:11px;color:#7c705a;margin-top:8px;">SAM Error Label: <strong>'+j.e.toUpperCase()+'</strong> &nbsp;|&nbsp; Confidence: <strong>'+j.c+'%</strong> &nbsp;|&nbsp; Criticality: <strong>'+clabel+'</strong></div>';
    html += '<div style="font-size:11px;color:'+statusColor+';margin-top:8px;">Crew notification: <strong>SENT</strong></div>';
    html += '</div>';
    html += renderDecisionSource('SAM - no Claude decision available (fallback)');

  } else if(errorMsg) {
    // BEDROCK ERROR - fall back to SAM disposition
    html += '<div class="err-block">Bedrock connection error: '+errorMsg+'<br><span style="font-size:10px;opacity:0.7;">Falling back to SAM disposition.</span></div>';
    html += renderSAMDisposition(j, clabel, ccolor);

  } else if(state.claudeParsed) {
    html += renderSAMSummary();
    html += renderSamClaudeComparison();
    if(samAndClaudeAgree()) {
      html += '<div class="resp-block" style="border-color:#3fb95044;background:#def4e0;">';
      html += '<div class="resp-src" style="color:#3fb950">SAM + Claude agree</div>';
      html += '<div class="outcome-summary">Claude confirms the same defect as SAM. Final disposition follows the shared prediction.</div>';
      html += '</div><br>';
    }
    if(shouldPreserveSamDecision()) {
      html += '<div class="err-block">Claude disagreed with a high-confidence SAM prediction, but the recorded SAM result is preserved because SAM confidence is '+state.samJudgment.c+'%.</div>';
      html += renderDecisionSource('SAM - preserved over Claude due to high confidence and disagreement');
      html += renderSAMDisposition(j, clabel, ccolor);
    } else {
      html += renderDecisionSource('Claude - final structured defect used');
      // FULL PIPELINE - show Claude raw markdown response + decision fields
      let p = state.claudeParsed;
      let riskColor   = p.risk_level === 'HIGH' ? '#f85149' : p.risk_level === 'MEDIUM' ? '#d29922' : '#3fb950';
      let actionColor = (p.action_required === 'NONE') ? '#3fb950' : '#f85149';

    // Convert markdown to basic HTML for display
    let displayText = p.raw_response
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
      .replace(/^## (.+)$/gm,'<div style="font-size:10px;letter-spacing:2px;color:#0033a0;text-transform:uppercase;margin:8px 0 3px 0;border-bottom:1px solid #d4c8b688;padding-bottom:2px;">$1</div>')
      .replace(/^# (.+)$/gm,'<div style="font-size:11px;font-weight:600;letter-spacing:1px;color:#1f1b17;margin:6px 0 3px 0;">$1</div>')
      .replace(/^\| (.+)$/gm,'<div style="font-size:10px;font-family:monospace;padding:1px 0;border-bottom:1px solid #d4c8b633;">| $1</div>')
      .replace(/^(\d+)\. (.+)$/gm,'<div style="padding:2px 0 2px 12px;border-left:2px solid #0033a022;margin-bottom:2px;font-size:11px;"><strong>$1.</strong> $2</div>')
      .replace(/---/g,'<hr style="border:none;border-top:1px solid #d4c8b644;margin:4px 0;">')
      .replace(/\n\n/g,'<br>')
      .replace(/\n/g,' ');

    html += '<div class="resp-block" style="border-color:'+riskColor+'44;background:'+riskColor+'08;max-height:420px;overflow-y:auto;">';
    html += '<div class="resp-src" style="color:#0033a0;margin-bottom:10px;">CLAUDE AI - BEDROCK ANALYSIS - HAVEN-1 AI MONITORING SPECIALIST</div>';
    html += displayText;
    html += '</div>';

    // Decision summary bar
    html += '<div style="margin-top:10px;padding:10px 14px;border:1px solid '+riskColor+'44;border-radius:6px;background:'+riskColor+'08;">';
    html += '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:6px;">';
    html += '<div style="font-size:11px;">Risk Level: <strong style="color:'+riskColor+';">'+(p.risk_level||'UNKNOWN')+'</strong></div>';
    html += '<div style="font-size:11px;">Action Required: <strong style="color:'+actionColor+';">'+(p.action_required||'N/A')+'</strong></div>';
    html += '<div style="font-size:11px;">Notify Crew: <strong style="color:'+(p.notify_crew ? '#f85149' : '#3fb950')+';">'+(p.notify_crew ? 'YES' : 'NO')+'</strong></div>';
    html += '<div style="font-size:11px;">SAM Confidence: <strong>'+j.c+'%</strong></div>';
    html += '<div style="font-size:11px;">Criticality: <strong style="color:'+ccolor+';">'+clabel+'</strong></div>';
    html += '</div>';
    if(p.crew_message) {
      html += '<div style="margin-top:8px;padding:8px 10px;background:#f8514911;border:1px solid #f8514944;border-radius:4px;font-size:11px;color:#f85149;">';
      html += '<strong>CREW NOTIFICATION:</strong> '+p.crew_message;
      html += '</div>';
    }
    if(p.autonomous_corrections) {
      html += '<div style="margin-top:8px;padding:8px 10px;background:#0033a011;border:1px solid #0033a044;border-radius:4px;font-size:11px;color:#0033a0;">';
      html += '<strong>AUTONOMOUS CORRECTIONS APPLIED:</strong> '+p.autonomous_corrections;
      html += '</div>';
    }
    html += '</div>';

  } else {
    html += renderSAMDisposition(j, clabel, ccolor);
  }

  el.innerHTML = html;
}

function renderSAMDisposition(j, clabel, ccolor) {
  let disp = getDemoDisposition(j.e);
  let html = '';
  html += '<div class="resp-block" style="border-color:'+disp.statusColor+'44;background:'+disp.statusColor+'08;">';
  html += '<div class="resp-src" style="color:'+disp.statusColor+'">SAM DISPOSITION - '+disp.statusLabel+'</div>';
  html += '<div class="outcome-summary">'+disp.action+'</div>';
  html += disp.crewNote+'<br><br>';
  html += '<div style="font-size:11px;color:#7c705a;">Criticality: <strong style="color:'+ccolor+';">'+clabel+'</strong> &nbsp;|&nbsp; SAM Confidence: <strong>'+j.c+'%</strong></div>';
  html += '</div>';
  return html;
}

// ---------------------------------------------------------------
// SAM DEMO DISPOSITIONS (fallback)
// ---------------------------------------------------------------
function getDemoDisposition(errorLabel) {
  switch(String(errorLabel || '').trim().toLowerCase()) {
    case 'none':
      return { statusLabel:'NO ERROR DETECTED', statusColor:'#3fb950', action:'SAM detected no print anomalies. Continue monitoring. No crew notification required.', crewNote:'Crew notification: <span style="color:#3fb950">NONE</span>' };
    case 'stringing':
      return { statusLabel:'STRINGING DETECTED', statusColor:'#d29922', action:'SAM flagged stringing on perimeter layers. Pause print and inspect nozzle and retraction settings.', crewNote:'Crew notification: <span style="color:#d29922">SENT</span> - "Stringing detected. Inspect nozzle and retraction settings before continuing."' };
    case 'spaghetti':
      return { statusLabel:'SPAGHETTI BUILD-UP', statusColor:'#f85149', action:'SAM flagged spaghetti formation. Immediate intervention required to clear extruded material.', crewNote:'Crew notification: <span style="color:#f85149">SENT</span> - "Spaghetti formation detected. Manual cleanup and review required."' };
    case 'underextrusion':
      return { statusLabel:'UNDER-EXTRUSION', statusColor:'#d29922', action:'SAM flagged under-extrusion. Inspect nozzle flow and filament feed path.', crewNote:'Crew notification: <span style="color:#d29922">SENT</span> - "Under-extrusion detected. Verify filament feed and nozzle condition."' };
    case 'low confidence (unsure)':
      return { statusLabel:'LOW CONFIDENCE', statusColor:'#d29922', action:'SAM confidence is below acceptable threshold. Manual visual review required before continuing.', crewNote:'Crew notification: <span style="color:#d29922">SENT</span> - "SAM confidence is low. Manual review advised before continuing."' };
    default:
      return { statusLabel:'UNKNOWN STATUS', statusColor:'#d29922', action:'No valid error label. Defaulting to caution. Manual crew review requested.', crewNote:'Crew notification: <span style="color:#d29922">SENT</span> - "Error label missing. Manual inspection required."' };
  }
}

// ---------------------------------------------------------------
// STAGE NAVIGATION
// ---------------------------------------------------------------
function goStage(n) {
  const labels = ['01 - Telemetry','02 - SAM','03 - Rekognition','04 - Claude AI','05 - Outcome'];
  for(let i=0;i<5;i++) {
    document.getElementById('stage-'+i).classList.add('hidden');
    let tab = document.querySelector('[data-stage="'+i+'"]');
    tab.className = 'stage-tab';
    if(i < n) { tab.classList.add('done'); tab.textContent = labels[i]; }
    else if(i === n) { tab.classList.add('active'); tab.textContent = labels[i]; }
    else { tab.classList.add('disabled'); tab.textContent = labels[i]; }
  }
  document.getElementById('stage-'+n).classList.remove('hidden');
  state.currentStage = n;
  if(n === 0) renderImagePreview();
}

// ---------------------------------------------------------------
// CONTINUE SAME PRINT JOB
// ---------------------------------------------------------------
function continuePrint() {
  // Apply autonomous telemetry adjustments before returning to stage 0
  if(state.claudeParsed && state.claudeParsed.telemetry_adjustments) {
    let adj = state.claudeParsed.telemetry_adjustments;
    if(adj.nozzle     !== undefined) document.getElementById('t-nozzle').value  = adj.nozzle;
    if(adj.bed        !== undefined) document.getElementById('t-bed').value      = adj.bed;
    if(adj.speed      !== undefined) document.getElementById('t-speed').value    = adj.speed;
    if(adj.retraction !== undefined) document.getElementById('t-retract').value  = adj.retraction;
    if(adj.extrude    !== undefined) document.getElementById('t-extrude').value  = adj.extrude;
    if(adj.layer      !== undefined) document.getElementById('t-layer').value    = adj.layer;
  }
  let keepImg   = state.imgDataUrl;
  let keepName  = state.imgName;
  let keepJobId = state.jobId;
  let keepCrit  = state.crit;
  state = {
    crit:         keepCrit,
    imgDataUrl:   keepImg,
    imgName:      keepName,
    samJudgment:  null,
    fullReport:   null,
    claudeParsed: null,
    currentStage: 0,
    jobId:        keepJobId
  };
  document.getElementById('t-part').style.borderColor = '';
  document.getElementById('t-error').value = '';  // always clear override on continue
  setCrit(keepCrit);
  goStage(0);
}

// ---------------------------------------------------------------
// RESET
// ---------------------------------------------------------------
function resetAll() {
  // Keep image across sessions so user doesn't need to re-upload
  let keepImg = state.imgDataUrl;
  let keepName = state.imgName;
  state = { crit: 3, imgDataUrl: keepImg, imgName: keepName, samJudgment: null, fullReport: null, claudeParsed: null, currentStage: 0, jobId: null };
  document.getElementById('t-part').value = '';
  document.getElementById('t-part').style.borderColor = '';
  // Reset file input so same file can be selected again
  document.getElementById('file-input').value = '';
  setCrit(3);
  goStage(0);
}
