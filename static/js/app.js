const $=(s,e=document)=>e.querySelector(s),$$=(s,e=document)=>[...e.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const S={user:null,csrf:'',settings:{},docs:[]},V={},charts={};
const NAV=[['dashboard','🏠','Dashboard'],['documents','📚','Documents'],['notes','📝','Notes'],['concepts','💡','Concepts'],['formulas','∑','Formulas'],['mentor','💬','AI Mentor'],['quizzes','🧪','Quizzes'],['exams','🎯','Exam Prep'],['flashcards','🃏','Flashcards'],['planner','📅','Planner'],['settings','⚙️','Settings']];

async function api(path,{method='GET',body,form}={}){
  const h={};if(method!=='GET')h['X-CSRF-Token']=S.csrf;let b;
  if(form)b=form;else if(body!==undefined){h['Content-Type']='application/json';b=JSON.stringify(body)}
  let r;try{r=await fetch('/api'+path,{method,headers:h,body:b,credentials:'same-origin'})}catch(e){throw new Error('Network error — check your connection.')}
  let d={};try{d=await r.json()}catch{}
  if(r.status===401&&S.user){S.user=null;location.hash='#/login'}
  if(!r.ok)throw new Error(d.error||'Request failed ('+r.status+')');
  return d;
}
function toast(m,t=''){const e=document.createElement('div');e.className='toast '+t;e.textContent=m;$('#toasts').append(e);setTimeout(()=>e.remove(),t==='error'?6000:3500)}
async function run(btn,fn){const o=btn&&btn.innerHTML;if(btn){btn.disabled=true;btn.innerHTML='<span class="spin"></span> Working…'}
  try{return await fn()}catch(e){toast(e.message,'error')}finally{if(btn){btn.disabled=false;btn.innerHTML=o}}}
function renderMath(el){try{renderMathInElement(el,{delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}],throwOnError:false})}catch{}}
function md(t){const m=[];t=(t||'').replace(/\$\$([\s\S]+?)\$\$|\$([^\n$]+?)\$/g,x=>{m.push(x);return `@@M${m.length-1}@@`});
  return DOMPurify.sanitize(marked.parse(t)).replace(/@@M(\d+)@@/g,(_,i)=>esc(m[i]))}
function setMd(el,t){el.innerHTML=md(t);renderMath(el)}
function skeleton(n=3){return Array.from({length:n},()=>'<div class="sk"></div>').join('')}
function modal(html){const m=document.createElement('div');m.className='modal';m.innerHTML='<div role="dialog" aria-modal="true">'+html+'</div>';
  m.onclick=e=>{if(e.target===m)m.remove()};document.addEventListener('keydown',function k(e){if(e.key==='Escape'){m.remove();document.removeEventListener('keydown',k)}});document.body.append(m);return m}
function dl(name,text,type='text/plain'){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),999)}
const fmtSize=b=>b>1048576?(b/1048576).toFixed(1)+' MB':Math.round(b/1024)+' KB';
const ago=iso=>{const d=new Date(iso);return d.toLocaleDateString(undefined,{month:'short',day:'numeric'})};
async function loadDocs(){S.docs=(await api('/documents')).documents}
function picker(id){const ds=S.docs.filter(d=>d.status==='ready');return ds.length?`<div class="picker" id="${id}">`+ds.map(d=>`<label class="chk"><input type="checkbox" value="${d.id}"> ${esc(d.name)} <small>${d.pages}p</small></label>`).join('')+'</div>':'<p class="muted">No processed documents yet. <a href="#/documents">Upload one</a>.</p>'}
const picked=id=>$$('#'+id+' input:checked').map(i=>+i.value);
function chart(id,cfg){charts[id]?.destroy();const c=$('#'+id);if(c)charts[id]=new Chart(c,{...cfg,options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:cfg.legend||false}},...(cfg.options||{})}})}
function applyTheme(t){localStorage.setItem('theme',t);document.documentElement.dataset.theme=t==='system'?(matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light'):t}

/* ---------- boot / router ---------- */
async function boot(){
  try{const r=await api('/auth/me');S.csrf=r.csrf;S.user=r.user;if(S.user){S.settings=(await api('/settings')).settings;applyTheme(S.settings.theme)}}catch(e){toast(e.message,'error')}
  addEventListener('hashchange',route);route();
}
function route(){
  const name=(location.hash.replace('#/','')||'dashboard').split('?')[0];
  if(!S.user){return authView(name==='register'?'register':'login')}
  if(!V[name]){location.hash='#/dashboard';return}
  if(!$('#shell'))shell();
  $$('#side a').forEach(a=>a.classList.toggle('on',a.dataset.r===name));
  $('#title').textContent=(NAV.find(n=>n[0]===name)||[])[2]||'';
  $('#shell').classList.remove('open');Object.values(charts).forEach(c=>c.destroy());
  const v=$('#view');v.innerHTML=skeleton();V[name](v).catch(e=>{v.innerHTML=`<div class="card empty">⚠️ ${esc(e.message)}</div>`});
}
function shell(){
  $('#root').innerHTML=`<div id="shell" class="${localStorage.getItem('collapsed')?'collapsed':''}"><aside id="side" aria-label="Main navigation"><div class="brand">🎓 Study <span>Mentor</span></div>
  ${NAV.map(n=>`<a href="#/${n[0]}" data-r="${n[0]}"><span>${n[1]}</span><span class="lbl">${n[2]}</span></a>`).join('')}</aside>
  <div id="main"><div class="top"><button class="btn sm" id="tg" aria-label="Toggle sidebar">☰</button><h2 id="title"></h2>
  <button class="btn sm" id="th" aria-label="Toggle theme">🌓</button><span class="muted">${esc(S.user.name)}</span><button class="btn sm" id="lo">Log out</button></div><main id="view"></main></div></div>`;
  $('#tg').onclick=()=>{const s=$('#shell');if(innerWidth<820)s.classList.toggle('open');else{s.classList.toggle('collapsed');localStorage.setItem('collapsed',s.classList.contains('collapsed')?'1':'')}};
  $('#th').onclick=async()=>{const t=document.documentElement.dataset.theme==='dark'?'light':'dark';applyTheme(t);S.settings.theme=t;api('/settings',{method:'PATCH',body:{theme:t}}).catch(()=>{})};
  $('#lo').onclick=async()=>{await api('/auth/logout',{method:'POST'});S.user=null;VS?.active&&VS.end();location.hash='#/login';route()};
}
function authView(mode){
  const reg=mode==='register';
  $('#root').innerHTML=`<div class="auth card"><h2>🎓 ${reg?'Create your account':'Welcome back'}</h2><form id="af" class="col">
  ${reg?'<label class="f">Name<input class="input" name="name" required autocomplete="name"></label>':''}
  <label class="f">Email<input class="input" type="email" name="email" required autocomplete="email"></label>
  <label class="f">Password<input class="input" type="password" name="password" required minlength="8" autocomplete="${reg?'new':'current'}-password"></label>
  <button class="btn pri" type="submit">${reg?'Register':'Sign in'}</button></form>
  <p class="muted">${reg?'Have an account? <a href="#/login">Sign in</a>':'New here? <a href="#/register">Create account</a>'} · <a href="/">Home</a></p></div>`;
  $('#af').onsubmit=e=>{e.preventDefault();run($('#af button'),async()=>{const b=Object.fromEntries(new FormData(e.target));
    const r=await api('/auth/'+(reg?'register':'login'),{method:'POST',body:b});S.user=r.user;S.csrf=r.csrf;S.settings=(await api('/settings')).settings;applyTheme(S.settings.theme);
    $('#root').innerHTML='';location.hash='#/dashboard';route()})}
}

/* ---------- dashboard ---------- */
V.dashboard=async v=>{
  const d=await api('/dashboard'),s=d.stats;
  const st=[['Documents',s.documents],['Notes',s.notes],['Quizzes',s.quizzes],['Avg score',s.avg_score==null?'—':s.avg_score+'%'],['Cards reviewed',s.cards_reviewed],['Sessions',s.sessions]];
  v.innerHTML=`<h1>Hello, ${esc(S.user.name.split(' ')[0])} 👋</h1><div class="grid g4">${st.map(x=>`<div class="card stat"><b>${x[1]}</b><span>${x[0]}</span></div>`).join('')}</div>
  <div class="row gap wrap" style="margin-bottom:1rem"><a class="btn pri" href="#/documents">⬆ Upload material</a><a class="btn" href="#/mentor">💬 Ask mentor</a><a class="btn" href="#/quizzes">🧪 Take quiz</a><a class="btn" href="#/flashcards">🃏 Review ${s.cards_due} due</a></div>
  <div class="grid g2"><div class="card"><h3>Weekly study (minutes)</h3><div style="height:200px"><canvas id="wk"></canvas></div></div>
  <div class="card"><h3>Recommended</h3><ul>${s.documents===0?'<li>Upload your first document</li>':''}${s.cards_due?`<li>${s.cards_due} flashcards are due</li>`:''}
  ${d.weak_topics.map(w=>`<li>Revise <b>${esc(w.topic)}</b> (${w.accuracy}% accuracy)</li>`).join('')}${d.exams.map(e=>`<li>${esc(e.name)} exam on ${e.exam_date.slice(0,10)}</li>`).join('')}${s.quizzes===0&&s.documents?'<li>Generate a quiz from your material</li>':''}</ul></div>
  <div class="card"><h3>Recent files</h3>${d.recent_documents.map(x=>`<div class="row between"><span>${esc(x.name)}</span><span class="pill ${x.status}">${x.status}</span></div>`).join('')||'<p class="muted">Nothing yet.</p>'}</div>
  <div class="card"><h3>Recent mentor sessions</h3>${d.recent_conversations.map(x=>`<div><a href="#/mentor?c=${x.id}">${esc(x.title)}</a></div>`).join('')||'<p class="muted">No conversations yet.</p>'}</div>
  <div class="card"><h3>Upcoming tasks</h3>${d.upcoming_tasks.map(t=>`<div>• ${esc(t.title)} <small>${t.minutes} min${t.due?' · '+t.due.slice(0,10):''}</small></div>`).join('')||'<p class="muted">No open tasks. <a href="#/planner">Plan your week</a>.</p>'}</div></div>`;
  chart('wk',{type:'bar',data:{labels:d.weekly.labels,datasets:[{data:d.weekly.minutes,backgroundColor:'#6366f1',borderRadius:6}]}});
};

/* ---------- documents ---------- */
let pollT;
V.documents=async v=>{
  v.innerHTML=`<div class="card"><div class="drop" id="dz" tabindex="0" role="button" aria-label="Upload files"><div style="font-size:34px">⬆️</div><b>Drag &amp; drop files here</b> or <u>browse</u><br><small>PDF, PNG, JPG, JPEG · up to the server limit per file</small></div>
  <input type="file" id="fi" multiple accept=".pdf,.png,.jpg,.jpeg" hidden>
  <div class="grid g2"><label class="f">Subject<input class="input" id="us" placeholder="e.g. Physics"></label><label class="f">Topic<input class="input" id="ut" placeholder="e.g. Mechanics"></label></div><div id="up"></div></div>
  <div class="row gap wrap"><input class="input" id="dq" placeholder="Search documents…" style="max-width:300px"><select id="ds" style="max-width:200px"><option value="">All subjects</option></select></div><div id="dl" style="margin-top:1rem"></div>`;
  const dz=$('#dz'),fi=$('#fi');dz.onclick=()=>fi.click();dz.onkeydown=e=>{if(e.key==='Enter'||e.key===' ')fi.click()};
  dz.ondragover=e=>{e.preventDefault();dz.classList.add('over')};dz.ondragleave=()=>dz.classList.remove('over');
  dz.ondrop=e=>{e.preventDefault();dz.classList.remove('over');upload(e.dataTransfer.files)};fi.onchange=()=>upload(fi.files);
  $('#dq').oninput=drawDocs;$('#ds').onchange=drawDocs;
  async function upload(files){if(!files.length)return;const fd=new FormData();[...files].forEach(f=>fd.append('files',f));fd.append('subject',$('#us').value);fd.append('topic',$('#ut').value);
    const box=$('#up');box.innerHTML='<div class="bar"><i style="width:0"></i></div><small id="upt">Uploading…</small>';
    const x=new XMLHttpRequest();x.open('POST','/api/documents/upload');x.setRequestHeader('X-CSRF-Token',S.csrf);
    x.upload.onprogress=e=>{if(e.lengthComputable)$('#up i').style.width=(e.loaded/e.total*100)+'%'};
    x.onload=async()=>{let d={};try{d=JSON.parse(x.responseText)}catch{}box.innerHTML='';
      if(x.status>=400)toast(d.error||'Upload failed','error');else{toast(`Uploaded ${d.documents.length} file(s) — processing…`,'ok');(d.errors||[]).forEach(e=>toast(e,'error'));if(d.ocr_available===false)toast('OCR is not installed on this server: scanned pages cannot be read.','error')}
      await refresh()};x.onerror=()=>{box.innerHTML='';toast('Network error during upload','error')};x.send(fd);fi.value=''}
  async function refresh(){await loadDocs();drawDocs();clearTimeout(pollT);if(S.docs.some(d=>d.status==='processing')&&location.hash.startsWith('#/documents'))pollT=setTimeout(refresh,2000)}
  function drawDocs(){const q=($('#dq')?.value||'').toLowerCase(),sub=$('#ds')?.value||'';const subs=[...new Set(S.docs.map(d=>d.subject).filter(Boolean))];
    const sel=$('#ds');if(sel&&sel.options.length-1!==subs.length)sel.innerHTML='<option value="">All subjects</option>'+subs.map(s=>`<option ${s===sub?'selected':''}>${esc(s)}</option>`).join('');
    const list=S.docs.filter(d=>d.name.toLowerCase().includes(q)&&(!sub||d.subject===sub));
    $('#dl').innerHTML=list.length?list.map(d=>`<div class="card"><div class="row between wrap gap"><div><b>${esc(d.name)}</b> <span class="pill ${d.status}">${d.status}</span><br><small>${fmtSize(d.size)} · ${d.pages} page(s)${d.subject?' · '+esc(d.subject):''}${d.topic?' / '+esc(d.topic):''} · ${ago(d.created_at)}</small></div>
    <div class="row gap wrap"><button class="btn sm" data-a="view" data-id="${d.id}">Preview</button><button class="btn sm" data-a="text" data-id="${d.id}">Text</button><button class="btn sm" data-a="ren" data-id="${d.id}">Rename/Tag</button><button class="btn sm" data-a="re" data-id="${d.id}">Reprocess</button><button class="btn sm danger" data-a="del" data-id="${d.id}">Delete</button></div></div>
    ${d.status==='processing'?`<div class="bar" style="margin-top:.6rem"><i style="width:${d.progress}%"></i></div>`:''}${d.error?`<p style="color:var(--err)">⚠ ${esc(d.error)}</p>`:''}
    ${d.warnings.length?`<details><summary>${d.warnings.length} page warning(s)</summary>${d.warnings.map(w=>`<small>${esc(w)}</small><br>`).join('')}</details>`:''}</div>`).join(''):'<div class="card empty">No documents yet — upload your first file above.</div>';
    $$('#dl [data-a]').forEach(b=>b.onclick=()=>docAction(b.dataset.a,+b.dataset.id,b))}
  async function docAction(a,id,b){const d=S.docs.find(x=>x.id===id);
    if(a==='del'){if(!confirm('Delete this document and its extracted text?'))return;await run(b,()=>api('/documents/'+id,{method:'DELETE'}));refresh()}
    if(a==='re')await run(b,async()=>{await api(`/documents/${id}/process`,{method:'POST'});refresh()});
    if(a==='ren'){const n=prompt('Name',d.name);if(n===null)return;const s=prompt('Subject',d.subject||'');const t=prompt('Topic',d.topic||'');await run(b,()=>api('/documents/'+id,{method:'PATCH',body:{name:n,subject:s||'',topic:t||''}}));refresh()}
    if(a==='text')await run(b,async()=>{const r=await api(`/documents/${id}?text=1`);modal(`<h3>${esc(d.name)}</h3>`+(r.document.chunks.map(c=>`<p><small>Page ${c.page}${c.heading?' · '+esc(c.heading):''}${c.ocr?' · OCR':''}</small><br>${esc(c.text)}</p>`).join('')||'<p>No text.</p>'))});
    if(a==='view')preview(d)}
  async function preview(d){const m=modal(`<h3>${esc(d.name)}</h3><div id="pv"></div>`);const url=`/api/documents/${d.id}/file`;
    if(d.mime!=='application/pdf'){$('#pv',m).innerHTML=`<img src="${url}" alt="" style="max-width:100%">`;return}
    try{pdfjsLib.GlobalWorkerOptions.workerSrc='https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';const pdf=await pdfjsLib.getDocument(url).promise;let n=1;
      $('#pv',m).innerHTML='<div class="row gap"><button class="btn sm" id="pp">‹</button><span id="pn"></span><button class="btn sm" id="pn2">›</button></div><canvas id="pc" style="max-width:100%"></canvas>';
      const draw=async()=>{const p=await pdf.getPage(n),vp=p.getViewport({scale:1.3}),c=$('#pc',m);c.width=vp.width;c.height=vp.height;await p.render({canvasContext:c.getContext('2d'),viewport:vp}).promise;$('#pn',m).textContent=`Page ${n} / ${pdf.numPages}`};
      $('#pp',m).onclick=()=>{if(n>1){n--;draw()}};$('#pn2',m).onclick=()=>{if(n<pdf.numPages){n++;draw()}};draw()}catch(e){$('#pv',m).textContent='Preview failed: '+e.message}}
  await refresh();
};

/* ---------- planner ---------- */
V.planner=async v=>{
  const [t,sb,pg]=await Promise.all([api('/planner/tasks'),api('/planner/subjects'),api('/progress')]);
  const pct=Math.min(100,Math.round(100*pg.today_min/pg.daily_goal_min));
  v.innerHTML=`<div class="card"><h3>Today's goal: ${pg.today_min} / ${pg.daily_goal_min} min</h3><div class="bar"><i style="width:${pct}%"></i></div></div>
  <div class="grid g2"><div class="card"><h3>Subjects &amp; exams</h3><form id="sf" class="grid g2"><input class="input" name="name" placeholder="Subject" required><input class="input" type="date" name="exam_date" aria-label="Exam date"><input class="input" type="number" name="daily_goal_min" value="60" min="5" aria-label="Daily minutes"><button class="btn pri">Add</button></form>
  ${sb.subjects.map(x=>`<div class="row between"><span>${esc(x.name)} <small>${x.exam_date?'exam '+x.exam_date.slice(0,10)+' · ':''}${x.daily_goal_min} min/day</small></span><button class="btn sm danger" data-s="${x.id}">✕</button></div>`).join('')}</div>
  <div class="card"><h3>Tasks</h3><form id="tf" class="grid g2"><input class="input" name="title" placeholder="Task" required><input class="input" name="subject" placeholder="Subject"><input class="input" type="number" name="minutes" value="30" min="5" aria-label="Minutes"><input class="input" type="date" name="due" aria-label="Due"><button class="btn pri">Add task</button></form>
  ${t.tasks.map(x=>`<div class="row between"><label class="chk"><input type="checkbox" data-t="${x.id}" ${x.done?'checked':''}><span style="${x.done?'text-decoration:line-through':''}">${esc(x.title)}</span> <small>${x.minutes}m${x.due?' · '+x.due.slice(0,10):''}</small></label><button class="btn sm danger" data-d="${x.id}">✕</button></div>`).join('')||'<p class="muted">No tasks yet.</p>'}</div>
  <div class="card"><h3>Subject performance</h3><div style="height:220px"><canvas id="sp"></canvas></div></div><div class="card"><h3>Quiz score trend</h3><div style="height:220px"><canvas id="tr"></canvas></div></div>
  <div class="card"><h3>Weak topics</h3>${pg.weak_topics.map(w=>`<div>${esc(w.topic)}: <b>${w.accuracy}%</b></div>`).join('')||'<p class="muted">Take quizzes to detect weak topics.</p>'}</div></div>`;
  $('#sf').onsubmit=e=>{e.preventDefault();run($('#sf button'),async()=>{await api('/planner/subjects',{method:'POST',body:Object.fromEntries(new FormData(e.target))});V.planner(v)})};
  $('#tf').onsubmit=e=>{e.preventDefault();run($('#tf button'),async()=>{await api('/planner/tasks',{method:'POST',body:Object.fromEntries(new FormData(e.target))});V.planner(v)})};
  $$('[data-s]',v).forEach(b=>b.onclick=()=>run(b,async()=>{await api('/planner/subjects/'+b.dataset.s,{method:'DELETE'});V.planner(v)}));
  $$('[data-d]',v).forEach(b=>b.onclick=()=>run(b,async()=>{await api('/planner/tasks/'+b.dataset.d,{method:'DELETE'});V.planner(v)}));
  $$('[data-t]',v).forEach(c=>c.onchange=()=>run(null,async()=>{await api('/planner/tasks/'+c.dataset.t,{method:'PATCH',body:{done:c.checked}});V.planner(v)}));
  chart('sp',{type:'bar',data:{labels:Object.keys(pg.subject_performance),datasets:[{data:Object.values(pg.subject_performance),backgroundColor:'#06b6d4',borderRadius:6}]},options:{scales:{y:{max:100,beginAtZero:true}}}});
  chart('tr',{type:'line',data:{labels:pg.score_trend.map((_,i)=>i+1),datasets:[{data:pg.score_trend,borderColor:'#7c3aed',tension:.3}]},options:{scales:{y:{max:100,beginAtZero:true}}}});
};

/* ---------- settings ---------- */
V.settings=async v=>{
  const s=(S.settings=(await api('/settings')).settings);
  const sel=(k,opts)=>`<select data-k="${k}">${opts.map(o=>`<option ${s[k]===o?'selected':''}>${o}</option>`).join('')}</select>`;
  const chk=(k,l)=>`<label class="chk"><input type="checkbox" data-k="${k}" ${s[k]?'checked':''}> ${l}</label>`;
  v.innerHTML=`<div class="grid g2"><div class="card"><h3>Account</h3><label class="f">Name<input class="input" id="pn" value="${esc(S.user.name)}"></label><label class="f">Email<input class="input" id="pe" value="${esc(S.user.email)}"></label><button class="btn pri" id="ps" style="margin-top:.6rem">Save profile</button>
  <h4>Change password</h4><input class="input" type="password" id="cp" placeholder="Current password" autocomplete="current-password"><input class="input" type="password" id="np" placeholder="New password (8+ chars)" style="margin-top:.4rem" autocomplete="new-password"><button class="btn" id="pw" style="margin-top:.4rem">Update password</button></div>
  <div class="card"><h3>Appearance</h3>${sel('theme',['light','dark','system'])}<h3 style="margin-top:1rem">AI preferences</h3><label class="f">Explanation style</label>${sel('explanation_style',['beginner','standard','advanced','exam'])}<label class="f">Answer length</label>${sel('answer_length',['short','medium','detailed'])}
  <label class="f">Language</label><input class="input" data-k="language" value="${esc(s.language)}"><label class="f">Default subject</label><input class="input" data-k="default_subject" value="${esc(s.default_subject)}"><label class="f">Exam preparation preference</label><input class="input" data-k="exam_pref" value="${esc(s.exam_pref)}" placeholder="e.g. GATE CS"></div>
  <div class="card"><h3>Voice &amp; accessibility</h3>${chk('voice_enabled','Voice mentor enabled')}${chk('continuous','Continuous conversation (auto-listen after answers)')}${chk('spoken','Spoken answers')}${chk('push_to_talk','Push-to-talk mode')}
  <label class="f">Speech speed: <span id="rv">${s.speech_rate}</span>×</label><input type="range" data-k="speech_rate" min="0.5" max="2" step="0.1" value="${s.speech_rate}"><label class="f">Voice</label><select data-k="voice_name" id="vn"><option value="">Default</option></select>
  <label class="f">Daily flashcard goal</label><input class="input" type="number" data-k="daily_card_goal" min="1" value="${s.daily_card_goal}"><p class="muted">Voice recognition depends on your browser (Chrome/Edge work best). The microphone is only requested when you start a voice session.</p></div>
  <div class="card"><h3>Privacy &amp; data</h3><p class="muted">Manage documents on the Documents page, conversations in AI Mentor.</p><button class="btn" id="ex">Export my data (JSON)</button> <button class="btn danger" id="da">Delete account…</button></div></div>`;
  const fillVoices=()=>{const sv=$('#vn');if(!sv)return;sv.innerHTML='<option value="">Default</option>'+speechSynthesis.getVoices().map(x=>`<option ${x.name===s.voice_name?'selected':''} value="${esc(x.name)}">${esc(x.name)} (${x.lang})</option>`).join('')};
  if('speechSynthesis' in window){fillVoices();speechSynthesis.onvoiceschanged=fillVoices}
  $$('[data-k]',v).forEach(el=>el.onchange=async()=>{const k=el.dataset.k;let val=el.type==='checkbox'?el.checked:el.type==='range'||el.type==='number'?+el.value:el.value;
    try{S.settings=(await api('/settings',{method:'PATCH',body:{[k]:val}})).settings;if(k==='theme')applyTheme(val);if(k==='speech_rate')$('#rv').textContent=val;toast('Saved','ok')}catch(e){toast(e.message,'error')}});
  $('#ps').onclick=e=>run(e.target,async()=>{S.user=(await api('/auth/profile',{method:'PATCH',body:{name:$('#pn').value,email:$('#pe').value}})).user;toast('Profile saved','ok')});
  $('#pw').onclick=e=>run(e.target,async()=>{await api('/auth/password',{method:'POST',body:{current:$('#cp').value,new:$('#np').value}});toast('Password updated','ok');$('#cp').value=$('#np').value=''});
  $('#ex').onclick=e=>run(e.target,async()=>dl('study-mentor-export.json',JSON.stringify(await api('/settings/export'),null,2),'application/json'));
  $('#da').onclick=async()=>{const p=prompt('This permanently deletes your account, files and history. Enter your password to confirm:');if(!p)return;
    try{await api('/auth/account',{method:'DELETE',body:{password:p}});S.user=null;location.hash='#/login';route()}catch(e){toast(e.message,'error')}};
};
