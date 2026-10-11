const EXAMS=['GATE','GRE','GMAT','SSC','Banking (IBPS/SBI)','UPSC','State PSC','Campus placement aptitude','Coding interview','General aptitude & reasoning','Custom'];
const TYPES=[['mcq','Multiple choice'],['tf','True/False'],['fill','Fill in the blanks'],['short','Short answer'],['numeric','Numerical'],['match','Match the following'],['assertion','Assertion & reason']];

function quizSetup(v,exam){
  return `<div class="card"><div class="grid g2"><div>${exam?`<label class="f">Exam category (AI-generated practice; not official papers)</label><select id="qc">${EXAMS.map(e=>`<option>${e}</option>`).join('')}</select><label class="f">Custom exam name</label><input class="input" id="qcu" placeholder="Only if 'Custom'">`:''}
  <label class="f">Subject</label><input class="input" id="qs" value="${esc(S.settings.default_subject||'')}"><label class="f">Chapter / topic${exam?' / syllabus':''}</label><input class="input" id="qt" placeholder="e.g. Time & work"><label class="f">Source documents ${exam?'(optional)':''}</label>${picker('dp')}</div>
  <div><div class="grid g2"><div><label class="f">Questions</label><input class="input" type="number" id="qn" value="10" min="1" max="30"></div><div><label class="f">Difficulty</label><select id="qd"><option>easy</option><option selected>medium</option><option>hard</option></select></div>
  <div><label class="f">Mode</label><select id="qm"><option value="practice">Practice (instant feedback)</option><option value="timed">Timed test</option></select></div><div><label class="f">Minutes (timed)</label><input class="input" type="number" id="qx" value="15" min="1"></div></div>
  <label class="f">Question types</label>${TYPES.map(t=>`<label class="chk"><input type="checkbox" value="${t[0]}" name="qty" ${t[0]==='mcq'?'checked':''}> ${t[1]}</label>`).join('')}</div></div>
  <button class="btn pri" id="qg">✨ Generate ${exam?'mock test':'quiz'}</button></div>`}
async function genQuiz(v,exam){
  const ids=picked('dp'),cat=exam?($('#qc').value==='Custom'?$('#qcu').value:$('#qc').value):'';
  const r=await api('/quizzes/generate',{method:'POST',body:{doc_ids:ids,subject:$('#qs').value,topic:$('#qt').value,category:cat,count:+$('#qn').value,difficulty:$('#qd').value,mode:$('#qm').value,time_limit:+$('#qx').value,types:$$('[name=qty]:checked').map(c=>c.value)}});
  playQuiz(v,r.quiz)}

function playQuiz(v,q){
  const st={i:0,ans:{},mark:new Set(),checked:{},t0:Date.now(),left:q.mode==='timed'?q.time_limit*60:0,done:false};let timer;
  const answered=i=>{const a=st.ans[i];return a!=null&&a!==''&&!(Array.isArray(a)&&a.every(x=>x==null))};
  function draw(){
    const x=q.questions[st.i],i=st.i,ck=st.checked[i];
    v.innerHTML=`<div class="grid" style="grid-template-columns:minmax(0,1fr) 230px"><div class="card"><div class="row between"><b>${esc(q.title)}</b><span>${q.mode==='timed'?`⏱ <b id="tm"></b>`:''}</span></div>
    <div class="bar" style="margin:.6rem 0"><i style="width:${100*Object.keys(st.ans).length/q.questions.length}%"></i></div><small>Question ${i+1} of ${q.questions.length} · ${esc(x.topic)} · <span class="pill">AI-generated</span></small>
    <h3 style="margin-top:.5rem">${esc(x.question)}</h3><div id="qa">${input(x,i)}</div><div id="fb">${ck?feedback(ck):''}</div>
    <div class="row gap wrap" style="margin-top:1rem"><button class="btn" id="pv" ${i?'':'disabled'}>‹ Prev</button><button class="btn" id="nx" ${i<q.questions.length-1?'':'disabled'}>Next ›</button><button class="btn" id="mk">${st.mark.has(i)?'🚩 Unmark':'⚑ Mark for review'}</button>
    ${q.mode==='practice'?'<button class="btn cy" id="ck">Check answer</button>':''}<button class="btn pri" id="sb" style="margin-left:auto">Submit</button></div></div>
    <div class="card pal"><b>Navigator</b><div>${q.questions.map((_,k)=>`<button data-k="${k}" class="${answered(k)?'done':''} ${st.mark.has(k)?'mk':''} ${k===i?'cur':''}">${k+1}</button>`).join('')}</div></div></div>`;
    wire(x,i);tick()}
  function input(x,i){const a=st.ans[i],lock=st.checked[i]?'disabled':'';
    if(x.options)return x.options.map((o,k)=>`<button class="btn opt ${a===k?'sel':''}" data-o="${k}" ${lock}>${String.fromCharCode(65+k)}. ${esc(o)}</button>`).join('');
    if(x.type==='match'){const cur=a||[];return x.left.map((l,k)=>`<div class="row gap" style="margin:.3rem 0"><span style="flex:1">${esc(l)}</span><select data-m="${k}" ${lock}><option value="">—</option>${x.right.map((r,j)=>`<option value="${j}" ${cur[k]===j?'selected':''}>${esc(r)}</option>`).join('')}</select></div>`).join('')}
    if(x.type==='short')return `<textarea id="ti" ${lock}>${esc(a||'')}</textarea>`;
    return `<input class="input" id="ti" ${x.type==='numeric'?'inputmode="decimal"':''} value="${esc(a||'')}" placeholder="${x.type==='numeric'?'Number'+(x.unit?' ('+esc(x.unit)+')':''):'Your answer'}" ${lock}>`}
  const feedback=c=>`<div class="card" style="margin-top:1rem;border-color:${c.correct?'var(--ok)':c.score>0?'var(--warn)':'var(--err)'}"><b>${c.correct?'✅ Correct':c.score>0?'◐ Partly correct':'❌ Incorrect'}</b><p>Answer: <b>${esc(c.correct_answer)}</b></p><p>${esc(c.explanation)}</p>${c.source?`<small>Source: ${esc(c.source)}</small>`:''}</div>`;
  function wire(x,i){
    $$('[data-o]').forEach(b=>b.onclick=()=>{st.ans[i]=+b.dataset.o;draw()});
    $$('[data-m]').forEach(s=>s.onchange=()=>{const a=st.ans[i]||x.left.map(()=>null);a[+s.dataset.m]=s.value===''?null:+s.value;st.ans[i]=a;$$('.pal button')[i].classList.add('done')});
    const ti=$('#ti');if(ti)ti.oninput=()=>{st.ans[i]=ti.value;$$('.pal button')[i].classList.toggle('done',!!ti.value)};
    $('#pv').onclick=()=>{st.i--;draw()};$('#nx').onclick=()=>{st.i++;draw()};$('#mk').onclick=()=>{st.mark.has(i)?st.mark.delete(i):st.mark.add(i);draw()};
    $$('.pal [data-k]').forEach(b=>b.onclick=()=>{st.i=+b.dataset.k;draw()});
    $('#ck')&&($('#ck').onclick=e=>run(e.target,async()=>{const r=await api(`/quizzes/${q.id}/check`,{method:'POST',body:{index:i,answer:st.ans[i]??null}});st.checked[i]=r;draw()}));
    $('#sb').onclick=()=>{const un=q.questions.length-Object.keys(st.ans).filter(k=>answered(+k)).length;if(confirm(un?`${un} question(s) unanswered. Submit anyway?`:'Submit your answers?'))submit()}}
  function tick(){clearInterval(timer);if(!q.mode||q.mode!=='timed')return;const upd=()=>{const e=$('#tm');if(e)e.textContent=Math.floor(st.left/60)+':'+String(st.left%60).padStart(2,'0')};upd();
    timer=setInterval(()=>{st.left--;upd();if(st.left<=0){clearInterval(timer);toast("Time's up — submitting","error");submit()}},1000)}
  async function submit(){if(st.done)return;st.done=true;clearInterval(timer);const a={};Object.entries(st.ans).forEach(([k,val])=>{if(answered(+k))a[k]=val});
    try{const r=await api(`/quizzes/${q.id}/submit`,{method:'POST',body:{answers:a,duration:Math.round((Date.now()-st.t0)/1000)}});results(v,r.attempt,q)}catch(e){st.done=false;toast(e.message,'error')}}
  draw();
}
function results(v,a,q){
  const pct=Math.round(100*a.score/a.total);
  v.innerHTML=`<div class="card"><h2>${pct>=70?'🎉':'📘'} Score: ${a.score}/${a.total} (${pct}%)</h2><small>Time: ${Math.round(a.duration/60)} min</small>
  <div class="grid g2"><div style="height:220px"><canvas id="rt"></canvas></div><div><h3>Topic-wise</h3>${Object.entries(a.topics).map(([k,p])=>`<div>${esc(k)}<div class="bar"><i style="width:${p}%"></i></div></div>`).join('')}</div></div>
  <div class="row gap"><button class="btn pri" id="rtk">↺ Retake</button><label class="chk"><input type="checkbox" id="wo"> Show only incorrect</label></div></div><div id="rv"></div>`;
  chart('rt',{type:'bar',data:{labels:Object.keys(a.topics),datasets:[{data:Object.values(a.topics),backgroundColor:'#6366f1',borderRadius:6}]},options:{scales:{y:{max:100,beginAtZero:true}}}});
  const show=()=>$('#rv').innerHTML=a.results.filter(r=>!$('#wo').checked||r.score<1).map(r=>`<div class="card"><b>Q${r.index+1}. ${esc(r.question)}</b><p>${r.score>=1?'✅':r.score>0?'◐':'❌'} Your answer: ${r.answered?esc(Array.isArray(r.your_answer)?r.your_answer.join(','):r.options&&typeof r.your_answer==='number'?r.options[r.your_answer]:r.your_answer):'<i>not answered</i>'}<br>Correct: <b>${esc(r.correct_answer)}</b></p><p>${esc(r.explanation)}</p>${r.source?`<small>Source: ${esc(r.source)}</small>`:''}</div>`).join('')||'<div class="card empty">Nothing to show 🎉</div>';
  $('#wo').onchange=show;show();$('#rtk').onclick=async()=>{const r=await api('/quizzes/'+q.id);playQuiz(v,r.quiz)}}

async function quizPage(v,exam){
  await loadDocs();const h=await api('/quizzes/history');const rows=h.attempts.filter(a=>exam?a.category:!a.category);
  v.innerHTML=quizSetup(v,exam)+(exam?`<div class="grid g2"><div class="card"><h3>📅 Study schedule suggestion</h3><div class="row gap wrap"><input class="input" type="date" id="xd" style="max-width:170px"><input class="input" type="number" id="xh" value="2" min="1" max="12" style="max-width:90px" aria-label="Hours per day"><button class="btn" id="xs">Suggest</button></div><div class="md" id="xo"></div></div>
  <div class="card"><h3>📑 Analyse uploaded previous-year papers</h3>${picker('dp2')}<button class="btn" id="xa" style="margin-top:.5rem">Analyse</button><div class="md" id="xr"></div></div></div>`:'')+
  `<div class="card"><h3>History &amp; score trend</h3>${rows.length?`<div style="height:160px"><canvas id="ht"></canvas></div><table><tr><th>Quiz</th><th>Score</th><th>Date</th><th></th></tr>${rows.map(a=>`<tr><td>${esc(a.title)}</td><td>${a.score}/${a.total}</td><td>${ago(a.at)}</td><td><button class="btn sm" data-rt="${a.quiz_id}">Retake</button> <button class="btn sm" data-rv="${a.id}">Review</button></td></tr>`).join('')}</table>`:'<p class="muted">No attempts yet.</p>'}</div>`;
  $('#qg').onclick=e=>run(e.target,()=>genQuiz(v,exam));
  if(rows.length)chart('ht',{type:'line',data:{labels:rows.map(a=>ago(a.at)).reverse(),datasets:[{data:rows.map(a=>Math.round(100*a.score/a.total)).reverse(),borderColor:'#06b6d4',tension:.3}]},options:{scales:{y:{max:100,beginAtZero:true}}}});
  $$('[data-rt]').forEach(b=>b.onclick=()=>run(b,async()=>playQuiz(v,(await api('/quizzes/'+b.dataset.rt)).quiz)));
  $$('[data-rv]').forEach(b=>b.onclick=()=>run(b,async()=>{const a=(await api('/quizzes/attempts/'+b.dataset.rv)).attempt;results(v,{...a,duration:0},{id:rows.find(r=>r.id==b.dataset.rv).quiz_id})}));
  if(exam){$('#xs').onclick=e=>run(e.target,async()=>{const r=await api('/exams/schedule',{method:'POST',body:{category:$('#qc').value,exam_date:$('#xd').value,hours:+$('#xh').value}});setMd($('#xo'),r.plan)});
    $('#xa').onclick=e=>run(e.target,async()=>{const r=await api('/exams/analyze',{method:'POST',body:{doc_ids:picked('dp2')}});setMd($('#xr'),r.analysis)})}
}
V.quizzes=v=>quizPage(v,false);V.exams=v=>quizPage(v,true);

/* ---------- flashcards ---------- */
V.flashcards=async v=>{
  await loadDocs();const notes=(await api('/study/notes')).notes;const r=await api('/flashcards?due=1');
  v.innerHTML=`<div class="grid g4"><div class="card stat"><b>${r.due_count}</b><span>Due today</span></div><div class="card stat"><b>${r.reviewed_today}/${r.daily_goal}</b><span>Daily goal</span></div><div class="card stat"><b>${r.total}</b><span>Total cards</span></div></div>
  <div class="card"><div class="bar"><i style="width:${Math.min(100,100*r.reviewed_today/r.daily_goal)}%"></i></div></div><div id="st"></div>
  <details class="card"><summary><b>Generate cards</b></summary><div class="grid g2"><div><label class="f">From documents</label>${picker('dp')}</div><div><label class="f">Or from a saved note</label><select id="fn"><option value="">—</option>${notes.map(n=>`<option value="${n.id}">${esc(n.title)}</option>`).join('')}</select><label class="f">Topic (optional)</label><input class="input" id="ft"><label class="f">How many</label><input class="input" type="number" id="fc" value="15" min="3" max="40"></div></div><button class="btn pri" id="fg" style="margin-top:.6rem">✨ Generate</button></details>
  <div class="card"><div class="row between"><h3>Browse all</h3><label class="chk"><input type="checkbox" id="fb"> Bookmarked only</label></div><div id="fl"></div></div>`;
  let queue=[...r.cards],shown=false,done=0;
  const study=()=>{const s=$('#st');if(!queue.length){s.innerHTML='<div class="card empty">🎉 No cards due. Generate more or come back tomorrow.</div>';return}const c=queue[0];
    s.innerHTML=`<div class="card"><small>${queue.length} left · ${esc(c.topic)}</small><div class="flip ${shown?'on':''}" id="fp" tabindex="0" role="button" aria-label="Flip card"><div><div class="face"><h3>${esc(c.front)}</h3></div><div class="face back"><div class="md">${esc(c.back)}</div></div></div></div>
    <div class="row gap wrap" style="margin-top:.8rem;justify-content:center">${shown?'<button class="btn danger" data-r="hard">😓 Hard</button><button class="btn" data-r="medium">🙂 Medium</button><button class="btn cy" data-r="easy">😎 Easy</button>':'<button class="btn pri" id="sh">Show answer</button>'}<button class="btn sm" id="bk">${c.bookmarked?'★':'☆'} Bookmark</button></div></div>`;
    const flip=()=>{shown=!shown;study()};$('#fp').onclick=flip;$('#fp').onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();flip()}};$('#sh')&&($('#sh').onclick=flip);
    $('#bk').onclick=async()=>{c.bookmarked=!c.bookmarked;await api('/flashcards/'+c.id,{method:'PATCH',body:{bookmarked:c.bookmarked}});study()};
    $$('[data-r]',s).forEach(b=>b.onclick=()=>run(b,async()=>{await api(`/flashcards/${c.id}/review`,{method:'POST',body:{rating:b.dataset.r}});queue.shift();if(b.dataset.r==='hard')queue.push(c);shown=false;done++;study()}))};
  study();
  const browse=async()=>{const x=await api('/flashcards'+($('#fb').checked?'?bookmarked=1':''));$('#fl').innerHTML=x.cards.map(c=>`<div class="row between"><span><b>${esc(c.front)}</b> <small>${esc(c.topic)} · due ${c.due}</small></span><button class="btn sm danger" data-x="${c.id}">✕</button></div>`).join('')||'<p class="muted">No cards.</p>';
    $$('[data-x]').forEach(b=>b.onclick=async()=>{await api('/flashcards/'+b.dataset.x,{method:'DELETE'});browse()})};browse();$('#fb').onchange=browse;
  $('#fg').onclick=e=>run(e.target,async()=>{const body={count:+$('#fc').value,topic:$('#ft').value};if($('#fn').value)body.note_id=+$('#fn').value;else body.doc_ids=picked('dp');
    const g=await api('/flashcards/generate',{method:'POST',body});toast(`Created ${g.cards.length} cards`,'ok');V.flashcards(v)});
};
