/* musicmatter.art loop toggle (v7.1): adds a small "Loop" button next to every <audio>.
   Uses the native loop attribute (gapless for FLAC). Remembers the last choice in localStorage. */
(function(){
  var KEY="mm-loop", pref=false;
  try{pref=localStorage.getItem(KEY)==="1"}catch(e){}
  var SVG='<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 2.64-6.36"/><path d="M3 3v5h5"/></svg>';
  function set(a,b,on){a.loop=on;b.setAttribute("aria-pressed",on?"true":"false")}
  function add(a){
    if(a.dataset.mmLoop)return; a.dataset.mmLoop="1";
    var row=document.createElement("span"); row.className="mm-row";
    a.parentNode.insertBefore(row,a); row.appendChild(a);
    var b=document.createElement("button");
    b.type="button"; b.className="mm-loop"; b.title="Loop"; b.setAttribute("aria-label","Loop"); b.innerHTML=SVG;
    set(a,b,pref||a.loop);
    b.addEventListener("click",function(){
      var on=!a.loop; set(a,b,on); pref=on;
      try{localStorage.setItem(KEY,on?"1":"0")}catch(e){}
    });
    row.appendChild(b);
  }
  function init(){var l=document.querySelectorAll("audio");for(var i=0;i<l.length;i++)add(l[i])}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();
