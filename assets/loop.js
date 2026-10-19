/* musicmatter.art loop toggle (v7.2)
   A small "Loop" button next to every <audio>. When loop is on, playback is gapless and click-free:
   the sound is fetched + decoded once and played by a WebAudio AudioBufferSourceNode (loop=true,
   loopStart/loopEnd = the manifest's "loop" region, with the manifest's equal-power crossfade of the
   tail into the pre-roll). The <audio> element stays the transport: its play/pause/seek/volume drive
   the loop and it keeps running silently. If anything fails (no WebAudio, no manifest loop entry,
   fetch/CORS/decode error) it falls back to the native loop attribute. Last choice is remembered. */
(function(){
  "use strict";
  var KEY="mm-loop", pref=false;
  try{pref=localStorage.getItem(KEY)==="1"}catch(e){}
  var SVG='<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 2.64-6.36"/><path d="M3 3v5h5"/></svg>';
  var ctx=null, XF=0.008;

  function getCtx(){
    if(ctx) return ctx;
    var C=window.AudioContext||window.webkitAudioContext; if(!C) return null;
    try{ctx=new C({sampleRate:48000})}catch(e){try{ctx=new C()}catch(e2){return null}}
    return ctx;
  }
  /* The loop buffer: audio[0, loop_end) with its last N frames crossfaded (equal power) into the frames
     that precede loop_start. Identical to the offline tool used to verify the loops. */
  function buildLoop(c,buf,lp){
    var sr=buf.sampleRate, r=sr/(lp.sample_rate||sr);
    var S=Math.round(lp.loop_start*r), E=Math.min(buf.length,Math.round(lp.loop_end*r)), N=Math.max(1,Math.min(Math.round(lp.crossfade*r),E-S));
    var out=c.createBuffer(buf.numberOfChannels,E,sr);
    for(var ch=0;ch<buf.numberOfChannels;ch++){
      var d=buf.getChannelData(ch), o=out.getChannelData(ch);
      o.set(d.subarray(0,E));
      for(var i=0;i<N;i++){
        var t=(i+1)/N, k=S-N+i, pre=k>=0?d[k]:0;
        o[E-N+i]=d[E-N+i]*Math.cos(Math.PI/2*t)+pre*Math.sin(Math.PI/2*t);
      }
    }
    return {buffer:out,start:S/sr,end:E/sr};
  }
  function manifestURL(a){
    var f=a.closest&&a.closest("figure"), l=f&&f.querySelector('a[href$=".nc.json"]');
    return l?l.href:null;
  }
  function absURL(u,base){try{return new URL(u,base).href}catch(e){return u}}
  window.mmLoopAttach=function(root){var l=(root||document).querySelectorAll("audio");for(var i=0;i<l.length;i++)add(l[i])};  // for lazily stamped players (sections.js)

  function Player(a,b){
    this.a=a; this.b=b; this.on=false; this.ready=null; this.L=null; this.failed=false;
    this.src=null; this.gain=null; this.elGain=null; this.t0=0; this.off0=0; this.guard=false; this.last=0;
    var s=this;
    ["play","playing"].forEach(function(ev){a.addEventListener(ev,function(){s.onPlay()})});
    a.addEventListener("pause",function(){s.stopSrc()});
    a.addEventListener("seeked",function(){s.onSeeked()});
    a.addEventListener("timeupdate",function(){s.onTime()});
    a.addEventListener("volumechange",function(){s.vol()});
    a.addEventListener("emptied",function(){s.stopSrc()});
  }
  Player.prototype.engaged=function(){return this.on&&this.L&&!this.failed};
  Player.prototype.prepare=function(){
    var s=this; if(s.ready) return s.ready;
    var c=getCtx(), mu=manifestURL(s.a);
    if(!c||!mu||!window.fetch){s.failed=true; return s.ready=Promise.resolve(false)}
    s.ready=fetch(mu).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(m){
      var lp=m.loop; if(!lp||!(lp.loop_end>lp.loop_start))throw 0;
      var url=s.a.currentSrc||s.a.src||absURL(lp.audio||m.audio,mu);
      return fetch(url,{mode:"cors"}).then(function(r){if(!r.ok)throw 0;return r.arrayBuffer()}).then(function(ab){
        return new Promise(function(res,rej){var p=c.decodeAudioData(ab,res,rej); if(p&&p.then)p.then(res,rej)});
      }).then(function(buf){
        s.L=buildLoop(c,buf,lp);
        s.gain=c.createGain(); s.gain.connect(c.destination);
        try{ s.elGain=c.createGain(); c.createMediaElementSource(s.a).connect(s.elGain); s.elGain.connect(c.destination);}catch(e){s.elGain=null}
        s.vol(); return true;
      });
    }).catch(function(){s.failed=true; s.L=null; s.route(false); s.apply(); return false});
    return s.ready;
  };
  Player.prototype.vol=function(){ if(this.gain&&ctx) this.gain.gain.setTargetAtTime(this.a.muted?0:this.a.volume,ctx.currentTime,0.005) };
  Player.prototype.route=function(loopAudible){
    if(!ctx||!this.elGain){ if(loopAudible){this.a.muted=true;this._muted=true} else if(this._muted){this.a.muted=false;this._muted=false} return }
    this.elGain.gain.setTargetAtTime(loopAudible?0:1,ctx.currentTime,XF/3);
  };
  Player.prototype.pos=function(){
    if(!this.src) return this.a.currentTime;
    var L=this.L, p=this.off0+(ctx.currentTime-this.t0);
    return p<L.end?p:L.start+((p-L.start)%(L.end-L.start));
  };
  Player.prototype.startAt=function(t){
    var s=this, L=s.L, c=ctx; if(!L||!c) return;
    if(c.state!=="running") c.resume();
    s.stopSrc();
    var off=Math.max(0,t<L.end?t:L.start+((t-L.start)%(L.end-L.start))), now=c.currentTime;
    var n=c.createBufferSource(), g=c.createGain();
    n.buffer=L.buffer; n.loop=true; n.loopStart=L.start; n.loopEnd=L.end;
    // a 4 ms fade-in when starting mid-sound (seek, or switching over from the element); none at the very top
    if(off>0.001){g.gain.setValueAtTime(0,now); g.gain.linearRampToValueAtTime(1,now+0.004)}
    n.connect(g); g.connect(s.gain); n.start(now,off);
    s.src=n; s.srcGain=g; s.t0=now; s.off0=off;
    s.route(true);
  };
  Player.prototype.stopSrc=function(){
    var n=this.src, g=this.srcGain; if(!n) return; this.src=null; this.srcGain=null;
    try{ var now=ctx.currentTime; g.gain.cancelScheduledValues(now); g.gain.setValueAtTime(g.gain.value,now);
         g.gain.linearRampToValueAtTime(0,now+0.004); n.stop(now+0.006);}catch(e){try{n.stop()}catch(e2){}}
    n.onended=function(){try{n.disconnect();g.disconnect()}catch(e){}};
  };
  Player.prototype.onPlay=function(){
    var s=this; if(ctx&&ctx.state!=="running") ctx.resume();
    if(s.engaged()){ if(!s.src) s.startAt(s.a.currentTime) }
    else if(s.on&&!s.failed) s.prepare().then(function(ok){ if(ok&&s.on&&!s.a.paused&&!s.src) s.startAt(s.a.currentTime) });
  };
  Player.prototype.onSeeked=function(){
    var s=this, a=s.a;
    if(s.guard){s.guard=false; s.last=a.currentTime; return}
    if(s.engaged()&&s.src){
      var wrapped=a.loop&&a.currentTime<0.35&&s.nearEnd;   // the silent element's own loop wrap, not a user seek
      if(!wrapped&&!a.paused) s.startAt(a.currentTime);
    }
    s.last=a.currentTime; s.nearEnd=false;
  };
  Player.prototype.onTime=function(){
    var s=this, a=s.a;
    if(a.duration&&a.currentTime>a.duration-0.6) s.nearEnd=true;
    if(s.engaged()&&s.src&&!a.paused&&!a.seeking){
      // keep the silent element's progress bar on the loop region
      if(a.currentTime>s.L.end+0.05&&s.L.end<a.duration-0.3){s.guard=true; a.currentTime=s.pos(); return}
    }
    s.last=a.currentTime;
  };
  Player.prototype.apply=function(){
    var s=this, a=s.a;
    a.loop=s.on;                                   // native loop: the fallback, and the silent transport's own loop
    s.b.setAttribute("aria-pressed",s.on?"true":"false");
    s.b.setAttribute("data-mode",s.on?(s.engaged()?"webaudio":"native"):"off");
  };
  Player.prototype.set=function(on){
    var s=this, a=s.a; s.on=on; s.apply();
    if(on){
      if(s.failed) return;
      s.prepare().then(function(ok){ s.apply(); if(!ok||!s.on) return; if(!a.paused&&!s.src) s.startAt(a.currentTime); else s.route(true) });
    } else if(s.src){
      var p=s.pos(); s.stopSrc(); s.route(false); s.guard=true; try{a.currentTime=p}catch(e){s.guard=false}
    } else s.route(false);
  };

  function add(a){
    if(a.dataset.mmLoop) return; a.dataset.mmLoop="1";
    // CORS-mode media so WebAudio can tap the element (both musicmatter hosts send Access-Control-Allow-Origin: *)
    if(!a.crossOrigin&&a.readyState===0) a.crossOrigin="anonymous";
    var row=document.createElement("span"); row.className="mm-row";
    a.parentNode.insertBefore(row,a); row.appendChild(a);
    var b=document.createElement("button");
    b.type="button"; b.className="mm-loop"; b.title="Loop"; b.setAttribute("aria-label","Loop"); b.innerHTML=SVG;
    row.appendChild(b);
    var p=new Player(a,b); a._mmLoop=p;
    p.on=pref||a.loop; p.apply();
    b.addEventListener("click",function(){
      getCtx(); if(ctx&&ctx.state!=="running") ctx.resume();   // user gesture: unlock audio
      var on=!p.on; p.set(on); pref=on;
      try{localStorage.setItem(KEY,on?"1":"0")}catch(e){}
    });
  }
  function init(){var l=document.querySelectorAll("audio");for(var i=0;i<l.length;i++)add(l[i])}
  window.mmLoop={buildLoop:buildLoop,version:"7.2"};
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();
