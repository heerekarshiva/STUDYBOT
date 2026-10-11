/* Shared output panel: edit / save / copy / export / search / bookmark / regenerate sections / explain selection */
function panel(host,o){
  let md0=o.md,editing=false,bm=o.bookmarks||[],noteId=o.noteId||null;
  host.innerHTML=`<div class="card"><div class="row between wrap gap"><h3 style="margin:0">${esc(o.title)}</h3><div class="row gap wrap tools">
  <button class="btn sm" data-p="edit">✏️ Edit</button><button class="btn sm" data-p="save">💾 Save</button><button class="btn sm" data-p="copy">📋 Copy</button><button class="btn sm" data-p="pdf">PDF</button><button class="btn sm" data-p="md">.md</button><button class="btn sm" data-p="txt">.txt</button><button class="btn sm" data-p="exp">💡 Explain selection</button></div></div>
  ${o.warn?`<p style="color:var(--warn)">⚠ ${esc(o.warn)}</p>`:''}${o.sources?.length?`<div>${o.sources.map(s=>`<span class="chip">${esc(s.doc)} · p.${s.page}</span>`).join('')}</div>`:''}
  <input class="input" id="pf" placeholder="Search in this output…" style="margin:.6rem 0"><div class="md" id="pb"></div></div>`;
  const body=$('#pb',host);
  const secs=()=>md0.split(/\n(?=## )/);
  function draw(){
    if(editing){body.innerHTML='<textarea id="pe" style="min-height:420px;font-family:monospace"></textarea>';$('#pe').value=md0;return}
    setMd(body,md0);
    $$('h2',body).forEach((h,i)=>{const t=h.textContent;const w=document.createElement('span');w.className='sec-tools';
      w.innerHTML=`<button title="Bookmark" aria-label="Bookmark section">${bm.includes(t)?'★':'☆'}</button>${o.regen?'<button title="Regenerate section" aria-label="Regenerate section">↻</button>':''}`;
      w.children[0].onclick=()=>{bm=bm.includes(t)?bm.filter(x=>x!==t):[...bm,t];draw();if(noteId)api('/study/notes/'+noteId,{method:'PATCH',body:{bookmarks:bm}}).catch(()=>{})};
      if(w.children[1])w.children[1].onclick=async e=>{const ins=prompt('Optional instruction (e.g. "simpler", "add an example")','');if(ins===null)return;
        await run(e.target,async()=>{const parts=secs(),idx=parts.findIndex(p=>p.startsWith('## '+t));if(idx<0)return;
          const r=await api('/study/notes/regenerate',{method:'POST',body:{section:parts[idx],instruction:ins,doc_ids:o.docIds||[]}});parts[idx]=r.section.trim();md0=parts.join('\n');draw()})};
      h.prepend(w)});
  }
  draw();
  $('#pf',host).oninput=e=>{$$('mark',body).forEach(m=>m.replaceWith(document.createTextNode(m.textContent)));body.normalize();const q=e.target.value.trim();if(q.length<2)return;
    const re=new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi'),w=document.createTreeWalker(body,NodeFilter.SHOW_TEXT),hit=[];
    while(w.nextNode()){const n=w.currentNode;if(n.parentElement.closest('.katex')||!re.test(n.textContent))continue;re.lastIndex=0;hit.push(n)}
    hit.forEach(n=>{const f=document.createDocumentFragment();let last=0,m;re.lastIndex=0;const t=n.textContent;while((m=re.exec(t))){f.append(t.slice(last,m.index));const k=document.createElement('mark');k.textContent=m[0];f.append(k);last=m.index+m[0].length}f.append(t.slice(last));n.replaceWith(f)});
    $('mark',body)?.scrollIntoView({block:'center'})};
  const act={
    edit(b){if(editing){md0=$('#pe').value;editing=false;b.textContent='✏️ Edit'}else{editing=true;b.textContent='✅ Done'}draw()},
    async save(){if(editing)md0=$('#pe').value;const r=noteId?await api('/study/notes/'+noteId,{method:'PATCH',body:{content:md0,bookmarks:bm}}):await api('/study/notes/save',{method:'POST',body:{title:o.title,kind:o.kind||'notes',content:md0,sources:o.sources||[]}});noteId=r.note.id;toast('Saved','ok')},
    async copy(){await navigator.clipboard.writeText(md0);toast('Copied','ok')},
    md(){dl((o.title||'notes').replace(/\W+/g,'_')+'.md',md0,'text/markdown')},
    txt(){dl((o.title||'notes').replace(/\W+/g,'_')+'.txt',body.innerText)},
    pdf(){const w=open('','_blank');if(!w)return toast('Allow pop-ups to export PDF','error');w.document.write(`<!doctype html><title>${esc(o.title)}</title><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css"><style>body{font:14px/1.5 system-ui;max-width:800px;margin:2rem auto}table{border-collapse:collapse}td,th{border:1px solid #999;padding:4px 8px}.sec-tools{display:none}</style><h1>${esc(o.title)}</h1>${body.innerHTML}`);w.document.close();setTimeout(()=>w.print(),700)},
    async exp(b){const sel=getSelection().toString().trim();if(!sel)return toast('Select some text in the output first','error');
      await run(b,async()=>{const r=await api('/study/concepts',{method:'POST',body:{concept:sel.slice(0,400),mode:'standard',doc_ids:o.docIds||[]}});const m=modal(`<h3>${esc(sel.slice(0,80))}</h3><div class="md"></div>`);setMd($('.md',m),r.content)})}};
  $$('[data-p]',host).forEach(b=>b.onclick=()=>run(['edit','copy','md','txt','pdf'].includes(b.dataset.p)?null:b,()=>act[b.dataset.p](b)));
}

const GEN_FORM=(withKind)=>`<div class="card"><div class="grid g2"><div><label class="f">Source documents</label>${picker('dp')}</div><div>
${withKind?`<label class="f">Notes type</label><select id="kind"><option value="chapter">Comprehensive chapter notes</option><option value="revision">Short revision notes</option><option value="beginner">Beginner-friendly</option><option value="topic">Topic-wise</option><option value="exam">Exam-oriented</option><option value="definitions">Definitions &amp; key concepts</option><option value="facts">Facts &amp; dates</option><option value="derivations">Step-by-step derivations</option><option value="examples">Examples &amp; applications</option><option value="mistakes">Common mistakes</option><option value="lastminute">Last-minute summary</option><option value="qa">Important Q&amp;A</option></select>`:''}
<label class="f">Chapter / topic (focus)</label><input class="input" id="topic" placeholder="e.g. Laws of motion"><label class="f">Subject</label><input class="input" id="subj" value="${esc(S.settings.default_subject||'')}"></div></div>`;

V.notes=async v=>{
  await loadDocs();const saved=(await api('/study/notes?kind=notes')).notes.concat((await api('/study/notes?kind=formula')).notes).sort((a,b)=>b.updated_at.localeCompare(a.updated_at));
  v.innerHTML=GEN_FORM(true)+`<div class="grid g4"><div><label class="f">Level</label><select id="lvl"><option>school</option><option selected>undergraduate</option><option>postgraduate</option><option>competitive exam</option></select></div>
  <div><label class="f">Complexity</label><select id="cx"><option>simple</option><option selected>medium</option><option>advanced</option></select></div><div><label class="f">Length</label><select id="ln"><option>short</option><option selected>medium</option><option>long</option></select></div>
  <div><label class="f">Exam type</label><input class="input" id="ex" value="${esc(S.settings.exam_pref||'')}" placeholder="General"></div><div><label class="f">Language</label><input class="input" id="lg" value="${esc(S.settings.language)}"></div></div>
  <button class="btn pri" id="go" style="margin-top:.8rem">✨ Generate notes</button></div>`+'<div id="out"></div><div class="card"><h3>Saved notes &amp; formula sheets</h3><input class="input" id="sq" placeholder="Search saved…"><div id="sl"></div></div>';
  const drawSaved=l=>$('#sl').innerHTML=l.map(n=>`<div class="row between"><a href="#" data-n="${n.id}">${n.kind==='formula'?'∑':'📝'} ${esc(n.title)}</a><span><small>${ago(n.updated_at)}</small> <button class="btn sm danger" data-x="${n.id}">✕</button></span></div>`).join('')||'<p class="muted">Nothing saved yet.</p>';
  const bind=()=>{$$('[data-n]').forEach(a=>a.onclick=async e=>{e.preventDefault();const n=(await api('/study/notes/'+a.dataset.n)).note;panel($('#out'),{title:n.title,md:n.content,noteId:n.id,sources:n.sources,bookmarks:n.bookmarks,kind:n.kind,regen:true,docIds:[]});$('#out').scrollIntoView()});
    $$('[data-x]').forEach(b=>b.onclick=async()=>{if(!confirm('Delete this note?'))return;await api('/study/notes/'+b.dataset.x,{method:'DELETE'});V.notes(v)})};
  drawSaved(saved);bind();
  $('#sq').oninput=async e=>{const r=await api('/study/notes?q='+encodeURIComponent(e.target.value));drawSaved(r.notes);bind()};
  $('#go').onclick=e=>run(e.target,async()=>{const ids=picked('dp');if(!ids.length)throw new Error('Select at least one document.');
    const r=await api('/study/notes',{method:'POST',body:{doc_ids:ids,kind:$('#kind').value,topic:$('#topic').value,subject:$('#subj').value,level:$('#lvl').value,complexity:$('#cx').value,length:$('#ln').value,exam:$('#ex').value,language:$('#lg').value}});
    panel($('#out'),{title:r.note.title,md:r.note.content,noteId:r.note.id,sources:r.note.sources,kind:'notes',regen:true,docIds:ids});$('#out').scrollIntoView({behavior:'smooth'})});
};

V.concepts=async v=>{
  await loadDocs();
  v.innerHTML=`<div class="card"><div class="grid g2"><div><label class="f">Concept or question</label><textarea id="cc" placeholder="e.g. Explain Bernoulli's principle — or paste a paragraph"></textarea>
  <label class="f">Mode</label><select id="md"><option value="beginner">Explain like I'm a beginner</option><option value="standard" selected>Standard academic</option><option value="advanced">Advanced technical</option><option value="exam">Exam-oriented</option><option value="examples">With examples</option><option value="steps">Step by step</option></select></div>
  <div><label class="f">Reference documents (optional)</label>${picker('dp')}</div></div><button class="btn pri" id="go" style="margin-top:.8rem">💡 Explain</button></div><div id="out"></div>`;
  $('#go').onclick=e=>run(e.target,async()=>{const ids=picked('dp');const r=await api('/study/concepts',{method:'POST',body:{concept:$('#cc').value,mode:$('#md').value,doc_ids:ids}});
    panel($('#out'),{title:r.title,md:r.content,sources:r.sources,kind:'concept',docIds:ids})});
};

V.formulas=async v=>{
  await loadDocs();
  v.innerHTML=GEN_FORM(false)+'<button class="btn pri" id="go" style="margin-top:.8rem">∑ Build formula sheet</button></div>'+'<div id="out"></div>';
  $('#go').onclick=e=>run(e.target,async()=>{const ids=picked('dp');if(!ids.length)throw new Error('Select at least one document.');
    const r=await api('/study/formulas',{method:'POST',body:{doc_ids:ids,topic:$('#topic').value}});
    const ocr=S.docs.some(d=>ids.includes(d.id)&&(d.mime!=='application/pdf'||d.warnings.length));
    panel($('#out'),{title:r.note.title+' — Formula sheet',md:r.note.content,noteId:r.note.id,sources:r.note.sources,kind:'formula',regen:true,docIds:ids,warn:ocr?'Some source text came from OCR. Verify highlighted formulas against the original pages.':''})});
};
