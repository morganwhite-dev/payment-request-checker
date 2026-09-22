'use strict';
const $ = id => document.getElementById(id);
let vendors=[], samples=[], activeSample=null, extractedPdf=null, analysisController=null;

function el(tag,text,className){const node=document.createElement(tag);node.textContent=text;if(className)node.className=className;return node;}
async function getJSON(path,options){const response=await fetch(path,options);const body=await response.json();if(!response.ok)throw new Error(body.error||'The local service could not complete this request.');return body;}

function renderVendor(){
  const container=$('vendor-record');container.replaceChildren();
  if($('vendor').value==='new'){
    const block=el('div','','new-vendor');block.append(el('strong','No trusted history available'),el('p','A new vendor requires purchase confirmation, an independent callback, and second approval before a trusted record is created.'));container.append(block);return;
  }
  const vendor=vendors.find(v=>v.id===$('vendor').value);
  if(!vendor){container.append(el('p','Choose a scenario to see the fictional reference record.','empty'));return;}
  const list=document.createElement('dl');
  for(const [label,key] of [['Vendor','name'],['Email on file','email'],['Phone on file','phone'],['Account on file','account'],['Payment terms','terms']]){
    const row=document.createElement('div'),dt=el('dt',label),dd=el('dd',vendor[key]);row.append(dt,dd);list.append(row);
  }container.append(list);
}

function updateAnalyze(){
  const ready=$('email').value.trim()&&$('vendor').value;
  $('analyze').disabled=!ready;
  $('analyze-help').textContent=ready?'The scenario email, its invoice, and the trusted vendor record will be reviewed locally.':'Choose a scenario to begin.';
}
function updateOutcomeHint(){const items=[...$('checklist').querySelectorAll('.check-status')];const open=items.filter(x=>x.value!=='done').length;const hint=$('outcome-hint');
  if(!$('outcome').value){hint.textContent='Choose how this review ends. This is a recorded label only.';return;}
  hint.textContent=$('outcome').value==='ready'?(open?`${open} action(s) are not marked done. Confirm they are complete before choosing this label.`:'Recorded as ready for the normal approval process. This tool does not approve or send payment.'):'Recorded as a hold. Escalate through your normal process. This tool does not approve or send payment.';}
function clearResult(){
  if(analysisController)analysisController.abort();
  $('result-content').hidden=true;$('comparison').replaceChildren();$('checklist').replaceChildren();
  $('result-message').textContent='Choose a scenario, then select Analyze request.';$('results').setAttribute('aria-busy','false');updateAnalyze();
}
function resetPdf(){
  extractedPdf=null;$('pdf-output').hidden=true;$('pdf-pages').replaceChildren();$('pdf-warning').textContent='';
  $('load-sample-pdf').disabled=!activeSample;$('load-sample-pdf').textContent='Load PDF';
  $('invoice-card').className='invoice-card waiting';$('invoice-name').textContent=activeSample?`${activeSample.name} PDF`:'No sample PDF selected';
  $('invoice-status').textContent=activeSample?'Not loaded':'Choose a scenario';$('invoice-description').textContent=activeSample?'Ready to load the invoice that belongs to this scenario.':'The matching fictional invoice will be read locally on this computer.';
}
function clearRequest(){
  activeSample=null;$('sample').value='';$('email').value='';$('vendor').value='';$('file-feedback').textContent='';
  $('sample-description').textContent='All examples use invented businesses and payment details.';
  resetPdf();renderVendor();clearResult();
}

function showPdf(data,file){
  $('pdf-pages').replaceChildren();
  data.pages.forEach(page=>{const detail=document.createElement('details');detail.append(el('summary',`Inspect extracted text · Page ${page.page}`),el('pre',page.text||'[No text extracted from this page]'));$('pdf-pages').append(detail);});
  $('pdf-warning').textContent=data.warnings.join(' ');$('pdf-output').hidden=false;$('file-feedback').textContent=`Read ${data.page_count} page(s) from ${file.name}. The text is ready for local analysis.`;
  $('invoice-card').className='invoice-card ready';$('invoice-name').textContent=file.name;$('invoice-status').textContent='Ready';$('invoice-description').textContent=`${data.page_count} page(s) extracted and ready for comparison.`;
}
function updateProgress(){const items=[...$('checklist').querySelectorAll('.check-status')];$('progress').textContent=`${items.filter(s=>s.value==='done').length} of ${items.length} checks marked done`;}
function diffCell(segs,fallback){const cell=document.createDocumentFragment();if(!segs||!segs.length){cell.append(fallback);return cell;}const addText=(parent,text)=>{text.split(/(?<=@)/).forEach((part,i)=>{if(i){parent.append(document.createElement('wbr'));const keep=el('span',part,'keep-together');parent.append(keep);}else parent.append(document.createTextNode(part));});};segs.forEach(seg=>{if(seg.differs){const mark=document.createElement('mark');mark.className='diff';addText(mark,seg.text);cell.append(mark);}else addText(cell,seg.text);});return cell;}
function evidenceRow(row,cols){const tr=document.createElement('tr');tr.className='evidence-row';tr.hidden=true;const td=document.createElement('td');td.colSpan=cols;const box=el('div','','evidence-box');box.append(el('h4',`Where "${row.field}" was found`));const list=document.createElement('dl');list.className='evidence-sources';(row.evidence?.sources||[]).forEach(src=>{const item=document.createElement('div');item.append(el('dt',src.label),el('dd',src.line));list.append(item);});box.append(list);box.append(el('p','Highlighted characters differ from the other value. The raw line is shown exactly as written in that source.','hint'));td.append(box);tr.append(td);return tr;}
function renderResult(data){
  window.lastLevel=data.fraud_risk_level;
  $('status-banner').className=`status-banner ${data.tone}`;$('status-title').textContent=data.title;$('status-description').textContent=data.description;
  $('fraud-risk-level').textContent=`Fraud risk level: ${data.fraud_risk_level}`;
  $('result-eyebrow').textContent=data.explanation_mode==='local_model'?'LIVE LOCAL REVIEW · LLAMA EXPLANATION':'LIVE LOCAL REVIEW · RULE-BASED EXPLANATION';
  $('mode-note').textContent=data.mode_note;$('result-badge').textContent='LIVE LOCAL REVIEW';$('comparison').replaceChildren();
  document.querySelector('.evidence-table').open=true;
  data.rows.forEach((row,rowIndex)=>{const tr=document.createElement('tr');const ev=row.evidence||{};
    const kind=row.review==='Match'?'match':row.review==='Mismatch'?'risk':'verify';
    const th=el('th',row.field);th.scope='row';
    const reqTd=document.createElement('td');reqTd.append(diffCell(ev.request_segments,row.request));
    const refTd=document.createElement('td');refTd.append(diffCell(ev.reference_segments,row.reference));
    [[reqTd,row.request],[refTd,row.reference]].forEach(([cell,value])=>{if(String(value).includes('@'))cell.className='email-cell';});
    const revTd=document.createElement('td');revTd.append(el('span',row.review,'field-status '+kind));
    const srcTd=document.createElement('td');srcTd.append(el('span',row.source));
    const detail=evidenceRow(row,5);detail.id=`evidence-${rowIndex}`;
    if((ev.sources||[]).length&&row.review!=='Match'){const toggle=el('button','Show evidence','evidence-toggle secondary');toggle.type='button';toggle.setAttribute('aria-expanded','false');toggle.setAttribute('aria-controls',detail.id);toggle.addEventListener('click',()=>{const open=detail.hidden;detail.hidden=!open;toggle.setAttribute('aria-expanded',String(open));toggle.textContent=open?'Hide evidence':'Show evidence';});srcTd.append(document.createElement('br'),toggle);}
    tr.append(th,reqTd,refTd,revTd,srcTd);$('comparison').append(tr,detail);});
  $('checklist').replaceChildren();
  data.checks.forEach((check,index)=>{const item=el('div','','check-item');item.append(el('h4',`${index+1}. ${check.title}`),el('p',check.why),el('p',check.how,'check-how'));const statusLabel=el('label','Status');statusLabel.htmlFor=`check-status-${index}`;const status=document.createElement('select');status.id=`check-status-${index}`;status.className='check-status';[['todo','Not started'],['done','Done'],['unconfirmed','Could not confirm']].forEach(([v,t])=>status.add(new Option(t,v)));status.addEventListener('change',()=>{updateProgress();updateOutcomeHint();});const noteLabel=el('label','Verification result');noteLabel.htmlFor=`check-note-${index}`;const note=document.createElement('textarea');note.id=`check-note-${index}`;note.rows=2;note.placeholder='Who verified it, how, and what was confirmed?';note.dataset.sample=check.sample||'This verification step was recorded for the classroom presentation.';note.dataset.status=check.sample_status||'done';item.append(statusLabel,status,noteLabel,note);$('checklist').append(item);});
  $('outcome').value='';updateOutcomeHint();
  updateProgress();$('result-content').hidden=false;$('result-message').textContent='Analysis completed locally. Review every source and complete the required verification steps.';$('status-banner').focus();
}

$('vendor').addEventListener('change',()=>{renderVendor();clearResult();});
$('email').addEventListener('input',clearResult);
$('reset').addEventListener('click',clearRequest);
$('outcome').addEventListener('change',updateOutcomeHint);
$('sample').addEventListener('change',()=>{
  const chosen=samples.find(s=>s.id===$('sample').value);if(!chosen){clearRequest();return;}
  activeSample=chosen;$('email').value=chosen.email;$('vendor').value=chosen.vendor_id;$('sample-description').textContent=chosen.description;$('file-feedback').textContent='';resetPdf();renderVendor();clearResult();
  $('load-sample-pdf').click();
});
$('load-sample-pdf').addEventListener('click',async()=>{
  if(!activeSample)return;resetPdf();clearResult();$('load-sample-pdf').disabled=true;$('load-sample-pdf').textContent='Loading…';$('invoice-card').className='invoice-card loading';$('invoice-status').textContent='Loading';$('invoice-description').textContent='Reading the matching fictional invoice locally…';$('file-feedback').textContent='Loading and reading the matching fictional PDF locally…';
  try{
    const pdfResponse=await fetch(`/samples/${activeSample.id}-invoice.pdf`);if(!pdfResponse.ok)throw new Error('The matching sample PDF is unavailable.');
    const blob=await pdfResponse.blob(),name=`${activeSample.id}-invoice.pdf`;
    const data=await getJSON('/api/extract-pdf',{method:'POST',headers:{'Content-Type':'application/pdf'},body:blob});
    const text=data.pages.map(p=>`PAGE ${p.page}\n${p.text}`).join('\n\n');extractedPdf={name,size:blob.size,text,source:'sample'};showPdf(data,{name});
    $('file-feedback').textContent=`Loaded and read ${name}. It will be included when you analyze the request.`;
  }catch(error){$('invoice-card').className='invoice-card error';$('invoice-status').textContent='Could not load';$('invoice-description').textContent='Try loading the matching PDF again.';$('file-feedback').textContent=error instanceof TypeError?'Cannot reach the local PDF reader. Start the server and try again.':error.message;
  }finally{$('load-sample-pdf').disabled=false;$('load-sample-pdf').textContent=extractedPdf?'Reload PDF':'Load PDF';}
});
$('fill-sample').addEventListener('click',()=>{
  $('checklist').querySelectorAll('.check-item').forEach(item=>{const note=item.querySelector('textarea');item.querySelector('.check-status').value=note.dataset.status||'done';note.value=note.dataset.sample;});
  $('outcome').value=window.lastLevel==='High'?'hold':'ready';updateOutcomeHint();
  updateProgress();$('result-message').textContent='Fictional sample checklist loaded. No real verification or payment occurred.';
});
$('analyze').addEventListener('click',async()=>{
  if($('analyze').disabled)return;clearResult();$('results').setAttribute('aria-busy','true');$('analyze').disabled=true;$('analyze').textContent='Analyzing…';$('result-message').textContent='Reading the evidence and applying exact comparison rules…';
  try{
    const invoiceText=extractedPdf?.text||activeSample?.invoice||'';
    analysisController=new AbortController();const data=await getJSON('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:$('email').value,invoice_text:invoiceText||'',vendor_id:$('vendor').value}),signal:analysisController.signal});renderResult(data);
  }catch(error){if(error.name!=='AbortError')$('result-message').textContent=error instanceof TypeError?'Cannot reach the local analyzer. Start the server and try again.':error.message;
  }finally{$('results').setAttribute('aria-busy','false');$('analyze').textContent='Analyze request';updateAnalyze();}
});

Promise.all([getJSON('/api/vendors'),getJSON('/api/samples'),getJSON('/api/health')]).then(([v,s,health])=>{vendors=v;samples=s;vendors.forEach(vendor=>$('vendor').add(new Option(vendor.name,vendor.id)));samples.forEach(sample=>$(sample.difficulty==='challenge'?'challenge-options':'standard-options').append(new Option(sample.name,sample.id)));$('app-status').textContent=`Local server connected. Findings are calculated locally; payment approval remains separate.`;updateAnalyze();}).catch(()=>{$('app-status').textContent='Could not load the workspace. Start the local server and reload this page.';});
