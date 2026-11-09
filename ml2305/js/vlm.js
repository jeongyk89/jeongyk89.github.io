import {csv} from './core.js';

const $ = id => document.getElementById(id);
const STORAGE_KEY = 'ml2305-vlm-trials-v2';
const fields = ['date', 'station', 'provider', 'model', 'task', 'prompt', 'image_condition', 'expected_text', 'notes'];
const prompts = {
  object: $('object-prompt').value,
  pose: $('pose-prompt').value
};
let trials = [];
let storageAvailable = true;

try {
  const stored = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '[]');
  if (Array.isArray(stored)) {
    trials = stored.filter(row => row && typeof row === 'object' && typeof row.date === 'string')
      .map(row => Object.fromEntries(fields.map(field => [field, String(row[field] ?? '')])));
  }
} catch {
  storageAvailable = false;
}

function updateCount() {
  $('trial-count').textContent = `${trials.length} saved`;
  $('export').disabled = trials.length === 0;
  if (!storageAvailable) {
    $('storage-note').textContent = 'Session storage is unavailable. Notes stay in memory only; export before reloading or closing.';
  }
}

async function copyPrompt(task) {
  const field = $(`${task}-prompt`);
  const message = $(`${task}-copy-status`);
  try {
    if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
    await navigator.clipboard.writeText(field.value);
    message.textContent = 'Copied. Paste it beside the approved image.';
  } catch {
    field.focus();
    field.select();
    field.setSelectionRange(0, field.value.length);
    message.textContent = 'Prompt selected. Use your device’s Copy command.';
  }
}

for (const button of document.querySelectorAll('[data-copy]')) {
  button.addEventListener('click', () => copyPrompt(button.dataset.copy));
}

$('record-form').addEventListener('submit', event => {
  event.preventDefault();
  const task = $('prompt-used').value;
  const model = $('model').value.trim();
  const imageCondition = $('condition').value.trim();
  const expected = $('expected').value.trim();
  const notes = $('notes').value.trim();
  if (!model || !imageCondition || !expected || !notes) {
    $('trial-toast').textContent = 'Add the model, image condition, expected result and observation.';
    return;
  }
  trials.push({
    date: new Date().toISOString(),
    station: 'C - Vision-language comparison',
    provider: $('provider').value,
    model,
    task: task === 'pose' ? 'Visible posture' : 'Objects and counts',
    prompt: prompts[task],
    image_condition: imageCondition,
    expected_text: expected,
    notes
  });
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(trials));
    storageAvailable = true;
    $('storage-note').textContent = 'Notes stay in this tab’s session. No images are stored. Export before closing the tab.';
  } catch {
    storageAvailable = false;
  }
  updateCount();
  $('trial-toast').textContent = `Trial ${trials.length} saved. Export your evidence before closing.`;
  $('notes').value = '';
});

$('export').addEventListener('click', () => {
  if (!trials.length) return;
  // Keep text beginning with spreadsheet formula characters as literal text.
  const safeRows = trials.map(row => Object.fromEntries(fields.map(field => {
    const value = String(row[field] ?? '');
    return [field, /^[=+\-@\t\r]/.test(value) ? `'${value}` : value];
  })));
  const blob = new Blob(['\uFEFF', csv(safeRows)], {type: 'text/csv;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `ML2305_VLM_trials_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  $('trial-toast').textContent = `${trials.length} trial${trials.length === 1 ? '' : 's'} exported.`;
});

updateCount();
