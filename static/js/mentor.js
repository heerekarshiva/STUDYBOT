const M={conv:null,msgs:[]};
V.mentor=async v=>{
  await loadDocs();const cid=+(new URLSearchParams(location.hash.split('?')[1]||'').get('c')||0);M.conv=null;M.msgs=[];
  v.innerHTML=`<div class="chat"><div class="card col"><button class="btn pri" id="nc">＋ New conversation</button><input class="input" id="cs" placeholder="Search conversations…"><div id="cl"></div></div>
  <div class="card col" style="min-height:0"><div class="row gap wrap"><details><summary class="btn sm">📚 Documents (<span id="dc">0</span>)</summary>${picker('dp')}</details>
  <select id="mm" style="width:auto" aria-label="Mode"><option value="normal">Normal answer</option><option value="hint">Hint only</option><option value="steps">Step by step</option><option value="example">Example &amp; analogy</option></select>
  <button class="btn sm" id="vb">🎙️ Voice session</button><button class="btn sm" id="sm">📝 Summarize</button></div>
  <div id="vp" hidden></div><div class="msgs" id="ms" aria-live="polite"><div class="empty">Ask a question about your uploaded material.</div></div>
  <div class="row gap"><textarea id="mi" rows="2" style="min-height:48px" placeholder="Ask your mentor… (Enter to send, Shift+Enter for newline)"></textarea><button class="btn pri" id="sd">Send</button></div></div></div>`;
  const pk=()=>$$('#dp input:checked').map(i=>+i.value);
  $$('#dp input').forEach(i=>i.onchange=()=>$('#dc').textContent=pk().length);
  const drawConvs=async q=>{const r=await api('/mentor/conversations'+(q?'?q='+encodeURIComponent(q):''));
    $('#cl').innerHTML=r.conversations.map(c=>`<div class="conv ${M.conv===c.id?'on':''}" data-c="${c.id}"><span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(c.title)}</span><span><button class="btn sm" data-r="${c.id}" aria-label="Rename">✏️</button><button class="btn sm" data-d="${c.id}" aria-label="Delete">🗑</button></span></div>`).join('')||'<small>No conversations.</small>';
    $$('[data-c]').forEach(e=>e.onclick=ev=>{if(!ev.target.closest('button'))openConv(+e.dataset.c)});
    $$('[data-r]').forEach(b=>b.onclick=async()=>{const t=prompt('Rename conversation');if(t){await api('/mentor/conversations/'+b.dataset.r,{method:'PATCH',body:{title:t}});drawConvs()}});
    $$('[data-d]').forEach(b=>b.onclick=async()=>{if(!confirm('Delete conversation?'))return;await api('/mentor/conversations/'+b.dataset.d,{method:'DELETE'});if(M.conv===+b.dataset.d)newConv();drawConvs()})};
  const bubble=m=>{const d=document.createElement('div');d.className='bub '+(m.role==='user'?'user':'');
    if(m.role==='user')d.textContent=m.content;else{const b=document.createElement('div');b.className='md';setMd(b,m.content);d.append(b);
      (m.sources||[]).forEach(s=>{const c=document.createElement('span');c.className='chip';c.textContent=`${s.doc} · p.${s.page}`;d.append(c)});
      const t=document.createElement('div');t.innerHTML=`<button class="btn sm">📋 Copy</button> <button class="btn sm">${m.saved?'★ Saved':'☆ Save'}</button>`;
      t.children[0].onclick=()=>navigator.clipboard.writeText(m.content).then(()=>toast('Copied','ok'));
      t.children[1].onclick=async e=>{if(!m.id)return;const r=await api(`/mentor/messages/${m.id}/save`,{method:'POST'});m.saved=r.saved;e.target.textContent=r.saved?'★ Saved':'☆ Save'};d.append(t)}
    const box=$('#ms');box.querySelector('.empty')?.remove();box.append(d);box.scrollTop=box.scrollHeight;return d};
  const newConv=()=>{M.conv=null;$('#ms').innerHTML='<div class="empty">New conversation. Ask anything.</div>'};
  async function openConv(id){const r=await api('/mentor/conversations/'+id);M.conv=id;$('#ms').innerHTML='';r.messages.forEach(bubble);
    $$('#dp input').forEach(i=>i.checked=r.conversation.doc_ids.includes(+i.value));$('#dc').textContent=pk().length;drawConvs()}
  /* returns assistant text; used by both the text box and the voice session */
  M.send=async(text,voice=false,signal)=>{
    bubble({role:'user',content:text});const wait=bubble({role:'assistant',content:'…'});
    try{const r=await api('/mentor/chat',{method:'POST',body:{message:text,conversation_id:M.conv,doc_ids:pk(),mode:$('#mm')?.value,voice}});
      wait.remove();M.conv=r.conversation.id;bubble(r.message);drawConvs();return r.message.content}
    catch(e){wait.remove();bubble({role:'assistant',content:'⚠️ '+e.message});throw e}};
  const send=async()=>{const t=$('#mi').value.trim();if(!t)return;$('#mi').value='';$('#sd').disabled=true;try{await M.send(t)}catch{}finally{$('#sd').disabled=false}};
  $('#sd').onclick=send;$('#mi').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}};
  $('#nc').onclick=newConv;$('#cs').oninput=e=>drawConvs(e.target.value);
  $('#sm').onclick=e=>run(e.target,async()=>{if(!M.conv)throw new Error('Open a conversation first.');const r=await api(`/mentor/conversations/${M.conv}/summary`,{method:'POST'});modal('<h3>Conversation summary</h3><div class="md" id="sx"></div>');setMd($('#sx'),r.summary)});
  $('#vb').onclick=()=>voicePanel();
  await drawConvs();if(cid)openConv(cid);
};
