// =====================================================
// Google Apps Script for the slide-refinement goal-evaluation study.
// Paste into a fresh Google Sheet's Apps Script editor.
// =====================================================
//
// Setup:
// 1. Create a new Google Sheet.
// 2. In row 1, add these headers (in order):
//    A1: timestamp | B1: evaluator | C1: topic | D1: paper |
//    E1: system_slot | F1: baseline | G1: goal_index |
//    H1: category | I1: requirement | J1: verdict
// 3. Extensions > Apps Script. Replace the default code with this file.
// 4. Deploy > New deployment
//    - Type: Web app
//    - Execute as: Me
//    - Who has access: Anyone
// 5. Copy the deployment URL into APPS_SCRIPT_URL in index.html
//
// verdict values: "true" | "false"
// =====================================================

function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var data = JSON.parse(e.postData.contents);
  var rows = data.rows || [];

  rows.forEach(function(row) {
    sheet.appendRow([
      row.timestamp,
      row.evaluator,
      row.topic,
      row.paper,
      row.system_slot,
      row.baseline,
      row.goal_index,
      row.category,
      row.requirement,
      row.verdict
    ]);
  });

  return ContentService
    .createTextOutput(JSON.stringify({ status: 'ok', n: rows.length }))
    .setMimeType(ContentService.MimeType.JSON);
}
