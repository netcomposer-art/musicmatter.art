/* musicmatter.art collapsible sections (mobile-fast home page).
   Each chord's players live in an inert <template> inside a closed <details>, so the page loads without
   creating 1,356 media elements. Opening a section (tap, jump link, #hash, Open all) stamps its players
   and hands them to loop.js (window.mmLoopAttach) for the loop button. */
(function(){
  "use strict";
  function stamp(d){
    var t=d.querySelector(":scope>template"); if(!t) return;
    d.appendChild(document.importNode(t.content,true)); t.remove();   // import (not move): media elements must be created in this document
    if(window.mmLoopAttach) window.mmLoopAttach(d);
  }
  function openId(id,scroll){
    var d=id&&document.getElementById(id); if(!d||!d.classList.contains("mm-sec")) return false;
    d.open=true; stamp(d); if(scroll) d.scrollIntoView({block:"start"}); return true;
  }
  var secs=document.querySelectorAll("details.mm-sec");
  for(var i=0;i<secs.length;i++) secs[i].addEventListener("toggle",function(e){ if(e.target.open) stamp(e.target) });
  function fromHash(){ try{ openId(decodeURIComponent(location.hash.slice(1)),true) }catch(e){} }
  window.addEventListener("hashchange",fromHash); fromHash();
  document.addEventListener("click",function(e){
    var a=e.target.closest&&e.target.closest('a[href^="#"]');
    if(a&&location.hash===a.getAttribute("href")){ if(openId(a.getAttribute("href").slice(1),true)) e.preventDefault() }
    var b=e.target.closest&&e.target.closest("button[data-all]"); if(!b) return;
    var on=b.dataset.all==="1"; for(var j=0;j<secs.length;j++){ secs[j].open=on; if(on) stamp(secs[j]) }
  });
  window.mmSections={open:openId,version:"1"};
})();
