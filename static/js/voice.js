/* Turn-based voice mentor: listen → think → speak → (optionally) listen again.
   Honest limitation: this is NOT full-duplex. The mic is stopped while the mentor speaks so it can't hear itself. */
const VS={active:false,state:'idle',rec:null,micMuted:false,spkMuted:false,busy:false,speaking:false,last:'',lastAt:0,lastAnswer:'',t0:0,tick:null,stream:null,ctx:null,an:null,raf:0,abort:null,noSpeech:0,restart:null,ptt:false,
  supported(){return !!(window.SpeechRecognition||window.webkitSpeechRecognition)},
  set(st,msg){this.state=st;const e=$('#vst');if(e){e.className='vstate '+st;e.textContent={idle:'Idle',listening:'🎧 Listening…',thinking:'🤔 Thinking…',speaking:'🔊 Speaking…',error:'⚠ '+(msg||'Error'),muted:'🔇 Mic muted'}[st]||st}},
  async start(){
    const s=S.settings;if(this.active)return;
    if(!s.voice_enabled)return toast('Voice mentor is disabled in Settings.','error');
    if(!this.supported()){this.set('error','Speech recognition unsupported');return toast('This browser does not support speech recognition (try Chrome or Edge). The text mentor still works.','error')}
    try{this.stream=await navigator.mediaDevices.getUserMedia({audio:true});$('#vperm').textContent='Microphone: allowed ✅'}
    catch(e){$('#vperm').textContent='Microphone: blocked ❌';this.set('error','Microphone permission denied');return toast('Microphone permission denied. Allow it in your browser settings.','error')}
    this.active=true;this.ptt=!!s.push_to_talk;this.noSpeech=0;this.t0=Date.now();
    this.tick=setInterval(()=>{const e=$('#vtm');if(e){const t=Math.floor((Date.now()-this.t0)/1000);e.textContent=String(Math.floor(t/60)).padStart(2,'0')+':'+String(t%60).padStart(2,'0')}},1000);
    this.meter();$('#vstart').hidden=true;$('#vend').hidden=false;$('#vptt').hidden=!this.ptt;
    if(this.ptt)this.set('idle');else this.listen()},
  meter(){try{this.ctx=new (window.AudioContext||window.webkitAudioContext)();this.an=this.ctx.createAnalyser();this.an.fftSize=64;this.ctx.createMediaStreamSource(this.stream).connect(this.an)}catch{return}
    const data=new Uint8Array(this.an.frequencyBinCount),draw=()=>{const c=$('#vwave');if(!c||!this.active)return;const g=c.getContext('2d');c.width=c.clientWidth;c.height=60;g.clearRect(0,0,c.width,60);
      this.an.getByteFrequencyData(data);const on=this.state==='listening'&&!this.micMuted,w=c.width/data.length;g.fillStyle='#06b6d4';
      data.forEach((v,i)=>{const h=on?Math.max(3,v/255*56):3;g.fillRect(i*w+1,30-h/2,w-3,h)});this.raf=requestAnimationFrame(draw)};draw()},
  listen(){
    if(!this.active||this.micMuted||this.busy||this.speaking||this.rec)return;
    const R=window.SpeechRecognition||window.webkitSpeechRecognition,r=new R();this.rec=r;
    r.lang=({English:'en-US',Hindi:'hi-IN',Spanish:'es-ES',French:'fr-FR',German:'de-DE',Telugu:'te-IN'})[S.settings.language]||'en-US';r.interimResults=true;r.continuous=false;
    let finalText='';this.set('listening');
    r.onresult=e=>{let interim='';for(const x of e.results){if(x.isFinal)finalText+=x[0].transcript;else interim+=x[0].transcript}const t=$('#vtr');if(t)t.textContent=(finalText||interim);this.noSpeech=0};
    r.onerror=e=>{this.rec=null;if(['not-allowed','service-not-allowed'].includes(e.error)){this.set('error','Microphone/speech permission denied');toast('Speech recognition permission denied — voice session stopped.','error');this.end(true)}
      else if(e.error==='no-speech'){this.noSpeech++}else if(e.error==='network'){toast('Speech service network error','error');this.noSpeech+=2}else if(e.error!=='aborted'){this.noSpeech++}};
    r.onend=()=>{this.rec=null;if(!this.active)return;
      const t=finalText.trim();if(t){this.handle(t);return}
      if(this.noSpeech>=4){this.set('idle');toast('No speech detected — listening paused. Click “Mute mic” once to resume listening.');this.pause=true;return}
      if(!this.ptt&&S.settings.continuous&&!this.busy&&!this.speaking&&!this.micMuted){clearTimeout(this.restart);this.restart=setTimeout(()=>this.listen(),350)}else if(this.state==='listening')this.set('idle')};
    try{r.start()}catch(e){this.rec=null}},
  norm:t=>t.toLowerCase().replace(/[^a-z0-9\u0900-\u0fff ]/g,'').replace(/\s+/g,' ').trim(),
  async handle(text){
    const n=this.norm(text),now=Date.now();
    if(n.length<2)return this.after();
    if(n===this.last&&now-this.lastAt<6000)return this.after();                 // duplicate submission
    if(n.length>8&&this.norm(this.lastAnswer).includes(n))return this.after();  // mentor heard itself
    if(this.busy)return;this.last=n;this.lastAt=now;this.busy=true;this.set('thinking');
    $('#vq').textContent=text;this.abort=new AbortController();
    try{const ans=await M.send(text,true,this.abort.signal);if(!this.active)return;this.lastAnswer=ans;$('#va').textContent=ans.slice(0,1200);await this.speak(ans)}
    catch(e){if(this.active)this.set('error',e.message)}
    finally{this.busy=false;if(this.active&&this.state!=='error')this.after()}},
  after(){if(!this.active||this.speaking)return;if(this.micMuted)return this.set('muted');if(this.ptt||!S.settings.continuous)return this.set('idle');
    if(this.state==='error')return;setTimeout(()=>this.listen(),600)},
  speak(text){return new Promise(res=>{
    if(!S.settings.spoken||this.spkMuted||!('speechSynthesis' in window))return res();
    const clean=text.replace(/```[\s\S]*?```/g,' code omitted. ').replace(/\$\$?[^$]+\$\$?/g,' formula ').replace(/[*_#>`|~]/g,'').replace(/\[[^\]]*\]\([^)]*\)/g,'').replace(/\(([^()]*,\s*p\.\s*\d+[^()]*)\)/g,'').replace(/\s+/g,' ').trim();
    const parts=clean.match(/[^.!?\n]+[.!?]*/g)||[clean];const q=[];let cur='';parts.forEach(p=>{if((cur+p).length>180){q.push(cur);cur=p}else cur+=p});if(cur)q.push(cur);
    this.rec?.abort();this.rec=null;speechSynthesis.cancel();this.speaking=true;this.set('speaking');const voice=speechSynthesis.getVoices().find(v=>v.name===S.settings.voice_name);
    q.forEach((t,i)=>{const u=new SpeechSynthesisUtterance(t);u.rate=S.settings.speech_rate||1;if(voice)u.voice=voice;
      if(i===q.length-1){u.onend=u.onerror=()=>{this.speaking=false;res()}}speechSynthesis.speak(u)});
    if(!q.length){this.speaking=false;res()}})},
  skip(){speechSynthesis.cancel();this.speaking=false},
  toggleMic(){if(this.pause&&!this.micMuted){this.pause=false;this.noSpeech=0;this.listen();return}this.micMuted=!this.micMuted;this.stream?.getAudioTracks().forEach(t=>t.enabled=!this.micMuted);
    if(this.micMuted){this.rec?.abort();this.rec=null;this.set('muted')}else{this.noSpeech=0;this.set('idle');if(!this.ptt)this.listen()}$('#vmic').textContent=this.micMuted?'🔇 Unmute mic':'🎤 Mute mic'},
  toggleSpk(){this.spkMuted=!this.spkMuted;if(this.spkMuted)this.skip();$('#vspk').textContent=this.spkMuted?'🔇 Unmute speaker':'🔊 Mute speaker'},
  pttDown(){if(this.busy||this.speaking)return;this.micMuted=false;this.listen()},pttUp(){this.rec?.stop()},
  end(silent){if(!this.active)return;this.active=false;clearTimeout(this.restart);clearInterval(this.tick);cancelAnimationFrame(this.raf);this.abort?.abort();
    try{this.rec?.abort()}catch{}this.rec=null;speechSynthesis?.cancel();this.stream?.getTracks().forEach(t=>t.stop());this.stream=null;this.ctx?.close().catch(()=>{});this.busy=this.speaking=false;
    const mins=(Date.now()-this.t0)/60000;if(mins>=0.2)api('/planner/sessions',{method:'POST',body:{kind:'voice',minutes:Math.round(mins*10)/10}}).catch(()=>{});
    if(!silent)this.set('idle');const s=$('#vstart');if(s){s.hidden=false;$('#vend').hidden=true;$('#vptt').hidden=true}}};

function voicePanel(){
  const p=$('#vp');if(!p.hidden){VS.end();p.hidden=true;return}
  p.hidden=false;p.className='vpanel';
  p.innerHTML=`<div class="row between wrap gap"><b>Voice session</b><span class="vstate idle" id="vst" role="status">Idle</span><span>⏱ <span id="vtm">00:00</span></span></div>
  <small id="vperm">Microphone: not requested yet</small><canvas class="wave" id="vwave"></canvas>
  <div class="row gap wrap"><button class="btn pri" id="vstart">▶ Start voice session</button><button class="btn danger" id="vend" hidden>■ End session</button><button class="btn" id="vptt" hidden>🎤 Hold to talk</button>
  <button class="btn sm" id="vmic">🎤 Mute mic</button><button class="btn sm" id="vspk">🔊 Mute speaker</button><button class="btn sm" id="vskip">⏭ Skip speech</button>
  <label class="chk">Speed <input type="range" id="vsp" min="0.5" max="2" step="0.1" value="${S.settings.speech_rate||1}" style="width:100px"></label></div>
  <p><b>You:</b> <span id="vtr"></span></p><p><b>Last question:</b> <span id="vq"></span></p><p><b>Mentor:</b> <span id="va"></span></p>
  <small>${VS.supported()?'Uses your browser\'s speech recognition and text-to-speech (turn-taking: the mic pauses while the mentor speaks). Availability varies by browser.':'⚠ This browser does not support speech recognition; use the text box instead.'}</small>`;
  $('#vstart').onclick=()=>VS.start();$('#vend').onclick=()=>{VS.end()};$('#vmic').onclick=()=>VS.toggleMic();$('#vspk').onclick=()=>VS.toggleSpk();$('#vskip').onclick=()=>VS.skip();
  $('#vsp').oninput=e=>{S.settings.speech_rate=+e.target.value};
  const b=$('#vptt');b.onmousedown=b.ontouchstart=e=>{e.preventDefault();VS.pttDown()};b.onmouseup=b.onmouseleave=b.ontouchend=()=>VS.pttUp();
  if(VS.supported()===false)VS.set('error','Unsupported browser');
}
addEventListener('hashchange',()=>{if(VS.active&&!location.hash.startsWith('#/mentor'))VS.end(true)});
addEventListener('beforeunload',()=>speechSynthesis?.cancel());
