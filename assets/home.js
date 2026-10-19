/* musicmatter.art instrument home.
   Reads /netcomposer.json. An instrument appears when an offering has `instrument`
   (plus root, quality, chord, voicing) or is the v4 piano set (collection
   full-chord-set-v4, audio under /fullchords/<Root>/). Players are built only
   when a quality section, or a search row, is shown. */
(function(global){
  "use strict";
  var ROOT_ORDER=["C","Db","D","Eb","E","F","F#","G","Ab","A","Bb","B"];
  var ROOT_PRETTY={C:"C","C#":"C♯",Db:"D♭",D:"D","D#":"D♯",Eb:"E♭",E:"E",F:"F","F#":"F♯",Gb:"G♭",G:"G","G#":"G♯",Ab:"A♭",A:"A","A#":"A♯",Bb:"B♭",B:"B"};
  var ROOT_DIR={C:"C",Db:"Db",D:"D",Eb:"Eb",E:"E",F:"F",Fsharp:"F#",G:"G",Ab:"Ab",A:"A",Bb:"Bb",B:"B"};
  var ENH={"C#":"Db","D#":"Eb","Gb":"F#","G#":"Ab","A#":"Bb"};
  var Q_ORDER=["maj","m","7","m7","maj7","dim","dim7","aug","m6","m7b5","9","m9","maj9","13","m13","maj13","7#11","7#9","7alt","7b13","7b5","7b9","7sus4","9sus4","sus2","sus4","6-9","6","m6-9","add9","m-add9","m-maj7","maj7#11","maj7#5","m11"];
  var Q_NAME={"13":"dominant 13th","6":"major 6th","6-9":"6/9","7":"dominant 7th","7#11":"7♯11","7#9":"7♯9","7alt":"7 altered","7b13":"7♭13","7b5":"7♭5","7b9":"7♭9","7sus4":"7sus4","9":"dominant 9th","9sus4":"9sus4","add9":"add9","aug":"augmented","dim":"diminished","dim7":"diminished 7th","m":"minor","m-add9":"minor add9","m-maj7":"minor-major 7th","m11":"minor 11th","m13":"minor 13th","m6":"minor 6th","m6-9":"minor 6/9","m7":"minor 7th","m7b5":"half-diminished (m7♭5)","m9":"minor 9th","maj":"major","maj13":"major 13th","maj7":"major 7th","maj7#11":"major 7♯11","maj7#5":"major 7♯5","maj9":"major 9th","sus2":"sus2","sus4":"sus4"};
  /* Chord-symbol suffix (filename spelling, "sharp" not "#") → quality code. Built from the v4 manifests. */
  var SUFFIX={"":"maj","13":"13","6":"6","6-9":"6-9","7":"7","7alt":"7alt","7b13":"7b13","7b5":"7b5","7b9":"7b9","7sharp11":"7#11","7sharp9":"7#9","7sus4":"7sus4","9":"9","9sus4":"9sus4","add9":"add9","aug":"aug","dim":"dim","dim7":"dim7","m":"m","m-add9":"m-add9","m-maj7":"m-maj7","m11":"m11","m13":"m13","m6":"m6","m6-9":"m6-9","m7":"m7","m7b5":"m7b5","m9":"m9","maj13":"maj13","maj7":"maj7","maj7sharp11":"maj7#11","maj7sharp5":"maj7#5","maj9":"maj9","sus2":"sus2","sus4":"sus4"};
  var Q_ALIAS={"maj":"maj","major":"maj","maj7":"maj7","major7":"maj7","ma7":"maj7","major7th":"maj7","m":"m","min":"m","minor":"m","m7":"m7","min7":"m7","minor7":"m7","m7b5":"m7b5","halfdiminished":"m7b5","halfdim":"m7b5","dim":"dim","diminished":"dim","dim7":"dim7","diminished7":"dim7","aug":"aug","augmented":"aug","sus2":"sus2","sus4":"sus4","sus":"sus4","7":"7","dom":"7","dominant":"7","dom7":"7","9":"9","m9":"m9","min9":"m9","minor9":"m9","maj9":"maj9","major9":"maj9","13":"13","m13":"m13","maj13":"maj13","7#11":"7#11","7sharp11":"7#11","7#9":"7#9","7sharp9":"7#9","7alt":"7alt","7b9":"7b9","7b13":"7b13","7b5":"7b5","7sus4":"7sus4","9sus4":"9sus4","6":"6","69":"6-9","6-9":"6-9","m6":"m6","m69":"m6-9","add9":"add9","madd9":"m-add9","mmaj7":"m-maj7","minormajor7":"m-maj7","maj7#11":"maj7#11","maj7#5":"maj7#5","m11":"m11","min11":"m11","minor11":"m11"};
  var ALIASES=[["jacobs choir","jacobschoir"],["jacobschoir","jacobschoir"],["fat synth","fatsynth"],["fatsynth","fatsynth"],["synth arp","syntharp"],["syntharp","syntharp"],["full chord","piano"],["choir","jacobschoir"],["jacobs","jacobschoir"],["piano","piano"],["synth","syntharp"],["fat","fatsynth"],["arp","syntharp"]];
  var ROOT_TOKENS=["c#","db","d#","eb","f#","gb","g#","ab","a#","bb","c","d","e","f","g","a","b"];
  var RESULT_CAP=48;

  function canonRoot(r){
    if(!r) return "";
    var s=String(r).replace(/♯/g,"#").replace(/♭/g,"b").replace(/sharp/ig,"#");
    if(ROOT_DIR[s]) s=ROOT_DIR[s];
    if(s.length===1) s=s.toUpperCase();
    else if(s.length>=2) s=s.charAt(0).toUpperCase()+s.slice(1).toLowerCase().replace("sharp","#");
    if(s==="F#") return "F#";
    if(ENH[s]) return ENH[s];
    return s;
  }
  function prettyRoot(r){return ROOT_PRETTY[r]||r}
  function prettyChord(sym){
    return String(sym||"").replace(/#/g,"♯").replace(/([A-G])b/g,"$1♭").replace(/b([0-9])/g,"♭$1");
  }
  function qName(q){return Q_NAME[q]||q||"major"}
  function qIndex(q){var i=Q_ORDER.indexOf(q);return i<0?1000:i}
  function rootIndex(r){var i=ROOT_ORDER.indexOf(r);return i<0?1000:i}
  function voicingLabel(v){
    if(!v) return "voicing";
    var known={"1_root":"root","2_inv1":"1st inversion","3_inv2":"2nd inversion","4_inv3":"3rd inversion","4_root_8va":"root, octave up","5_inv1_8va":"1st inversion, octave up","5_root_8va":"root, octave up","6_inv1_8va":"1st inversion, octave up","6_inv2_8va":"2nd inversion, octave up","inv1":"1st inversion","inv2":"2nd inversion","inv3":"3rd inversion","root":"root","drop2":"drop 2","drop2_root":"drop 2, root","drop2_inv1":"drop 2, 1st inversion","drop2_inv2":"drop 2, 2nd inversion","drop2_inv3":"drop 2, 3rd inversion","open":"open","shell_R-3-7":"shell R–3–7","shell_R-7-3":"shell R–7–3","shell_11top":"shell, 11 on top"};
    if(known[v]) return known[v];
    return v.replace(/_/g," ").replace(/sharp/g,"♯").replace(/inv1/g,"1st inv").replace(/inv2/g,"2nd inv").replace(/inv3/g,"3rd inv");
  }
  function voicingRank(v){
    var order=["1_root","root","2_inv1","inv1","3_inv2","inv2","4_inv3","inv3","4_root_8va","5_root_8va","5_inv1_8va","6_inv1_8va","6_inv2_8va","drop2","drop2_root","drop2_inv1","drop2_inv2","drop2_inv3","open"];
    var i=order.indexOf(v); return i<0?500:i;
  }

  function parseNamedFile(rootDir, file){
    var root=ROOT_DIR[rootDir]||canonRoot(rootDir);
    var rest=file.replace(/^[0-9]+[a-z]?_[^_]+_/,"");
    if(rest.indexOf(rootDir)!==0) return null;
    var after=rest.slice(rootDir.length), suf, voicing;
    if(after.charAt(0)==="_"){suf=""; voicing=after.slice(1)}
    else{
      var cut=after.indexOf("_");
      suf=cut<0?after:after.slice(0,cut);
      voicing=cut<0?"":after.slice(cut+1);
    }
    if(!(suf in SUFFIX)) return null;
    var quality=SUFFIX[suf];
    var chord=root+(suf.replace(/sharp/g,"#"));
    return {root:root, quality:quality, chord:chord, voicing:voicing};
  }

  function soundFromOffering(o){
    if(!o||!o.audio) return null;
    var path=String(o.audio).split("/fullchords/")[1]||"";
    var segs=path?path.split("/"):[];
    var file=segs.length?segs[segs.length-1].replace(/\.flac$/,""):"";
    var parsed=null;
    if(segs.length===2 && ROOT_DIR[segs[0]]) parsed=parseNamedFile(segs[0], file);
    else if(segs.length===3 && ROOT_DIR[segs[1]]) parsed=parseNamedFile(segs[1], file);
    if(o.instrument || (segs.length===3 && !ROOT_DIR[segs[0]])){
      var id=o.instrument||segs[0];
      var root=canonRoot(o.root||(parsed&&parsed.root)||(segs.length===3?segs[1]:""));
      var quality;
      if(Object.prototype.hasOwnProperty.call(o,"quality")) quality=o.quality?String(o.quality):"maj";
      else quality=parsed?parsed.quality:"maj";
      if(quality==="") quality="maj";
      return {
        id:id, name:o.instrument_name||id, root:root, quality:quality,
        chord:o.chord||(parsed&&parsed.chord)||root,
        voicing:o.voicing||(parsed&&parsed.voicing)||"",
        def:!!o.default_voicing, audio:o.audio, manifest:o.manifest||""
      };
    }
    if(o.collection==="full-chord-set-v4" || parsed){
      if(!parsed) return null;
      return {
        id:"piano", name:"Piano", root:parsed.root, quality:parsed.quality,
        chord:parsed.chord, voicing:parsed.voicing, def:parsed.voicing==="1_root",
        audio:o.audio, manifest:o.manifest||""
      };
    }
    return null;
  }

  function ensureDefaults(list){
    var by={};
    list.forEach(function(s){
      var k=s.id+"\0"+s.chord;
      (by[k]||(by[k]=[])).push(s);
    });
    Object.keys(by).forEach(function(k){
      var arr=by[k];
      if(arr.some(function(s){return s.def})) return;
      arr.sort(function(a,b){return voicingRank(a.voicing)-voicingRank(b.voicing)||a.voicing.localeCompare(b.voicing)});
      arr[0].def=true;
    });
  }

  function indexCatalog(data){
    var sounds=[], cols=data.collections||[];
    (data.offerings||[]).forEach(function(o){
      var s=soundFromOffering(o);
      if(s) sounds.push(s);
    });
    ensureDefaults(sounds);
    var order=[], groups={};
    sounds.forEach(function(s){
      if(!groups[s.id]){
        groups[s.id]={id:s.id, name:s.name, sounds:[], col:null};
        order.push(s.id);
      }
      if(s.name && s.name!==s.id) groups[s.id].name=s.name;
      groups[s.id].sounds.push(s);
    });
    cols.forEach(function(c){
      if(c.instrument && groups[c.instrument]) groups[c.instrument].col=c;
      if(c.id==="full-chord-set-v4" && groups.piano) groups.piano.col=c;
    });
    order.sort(function(a,b){
      if(a==="piano") return -1;
      if(b==="piano") return 1;
      return 0;
    });
    return {sounds:sounds, groups:groups, order:order};
  }

  function normalizeQuery(q){
    var s=String(q||"").toLowerCase().trim();
    s=s.replace(/♯/g,"#").replace(/♭/g,"b");
    s=s.replace(/\bsharp\b/g,"#").replace(/\bflat\b/g,"b");
    s=s.replace(/fsharp/g,"f#");
    s=s.replace(/([a-g])\s*([#b])/g,"$1$2");
    return s.replace(/\s+/g," ").trim();
  }
  function takeInst(s){
    var best=null, phrase="", bestLen=0;
    ALIASES.forEach(function(pair){
      var re=new RegExp("(^|\\s)"+pair[0].replace(/ /g,"\\s+")+"(?=\\s|$)");
      if(!re.test(s)) return;
      if(pair[0].length>bestLen){bestLen=pair[0].length; best=pair[1]; phrase=pair[0]; }
    });
    if(!best) return {id:null, rest:s};
    var re2=new RegExp("(^|\\s)"+phrase.replace(/ /g,"\\s+")+"(?=\\s|$)");
    return {id:best, rest:s.replace(re2," ").replace(/\s+/g," ").trim()};
  }
  function takeRoot(compact){
    for(var i=0;i<ROOT_TOKENS.length;i++){
      var t=ROOT_TOKENS[i];
      if(compact.indexOf(t)!==0) continue;
      var rest=compact.slice(t.length);
      if(rest==="" || Q_ALIAS[rest]){
        var root=canonRoot(t);
        return {root:root, rest:rest};
      }
    }
    return {root:null, rest:compact};
  }
  function parseQuery(q){
    var spaced=normalizeQuery(q);
    if(!spaced) return {empty:true};
    var inst=takeInst(spaced);
    var compact=(inst.rest||"").replace(/[\s_\-]/g,"");
    var root=takeRoot(compact);
    var quality=root.rest?Q_ALIAS[root.rest]||null:null;
    return {empty:false, inst:inst.id, root:root.root, quality:quality, free:(quality||!root.rest)?"":root.rest, raw:spaced};
  }

  function search(index, query, instFilter){
    var parsed=parseQuery(query);
    var filter=instFilter&&instFilter!=="all"?instFilter:null;
    if(parsed.empty && !filter) return {items:[], total:0, showing:0, parsed:parsed};
    var pool=index.sounds.filter(function(s){
      if(filter && s.id!==filter) return false;
      if(parsed.empty) return true;
      if(parsed.inst && s.id!==parsed.inst) return false;
      if(parsed.root && s.root!==parsed.root) return false;
      if(parsed.quality && s.quality!==parsed.quality) return false;
      if(parsed.free){
        var hay=(s.chord+" "+s.quality+" "+qName(s.quality)+" "+s.voicing+" "+s.name+" "+s.id).toLowerCase().replace(/♯/g,"#").replace(/♭/g,"b").replace(/\s+/g,"");
        if(hay.indexOf(parsed.free)<0) return false;
      }
      return true;
    });
    pool.sort(function(a,b){
      if(a.def!==b.def) return a.def?-1:1;
      var io=index.order.indexOf(a.id)-index.order.indexOf(b.id);
      if(io) return io;
      var rr=rootIndex(a.root)-rootIndex(b.root); if(rr) return rr;
      var qq=qIndex(a.quality)-qIndex(b.quality); if(qq) return qq;
      return voicingRank(a.voicing)-voicingRank(b.voicing)||a.voicing.localeCompare(b.voicing);
    });
    var items=pool, note="";
    if(pool.length>RESULT_CAP){
      var defs=pool.filter(function(s){return s.def});
      if(defs.length && defs.length<pool.length){
        items=defs.length>RESULT_CAP?defs.slice(0,RESULT_CAP):defs;
        note="Showing "+items.length+" default voicing"+(items.length===1?"":"s")+" of "+pool.length+" matches."+(parsed.root&&!parsed.quality?" Add a chord type to see every voicing.":" Add a root or a chord to narrow.");
      } else {
        items=pool.slice(0,RESULT_CAP);
        note="Showing "+items.length+" of "+pool.length+" matches.";
      }
    }
    return {items:items, total:pool.length, showing:items.length, parsed:parsed, note:note};
  }

  function el(tag, cls, text){
    var n=document.createElement(tag);
    if(cls) n.className=cls;
    if(text!=null) n.textContent=text;
    return n;
  }
  function playerFigure(s){
    var fig=el("figure");
    var cap=el("figcaption");
    cap.appendChild(document.createTextNode(s.name+" · "+prettyChord(s.chord)+" · "+voicingLabel(s.voicing)+(s.def?" · default":"")+" · "));
    if(s.manifest){
      var a=el("a"); a.href=s.manifest; a.textContent="manifest"; cap.appendChild(a);
    }
    var audio=document.createElement("audio");
    audio.controls=true; audio.preload="none"; audio.crossOrigin="anonymous"; audio.src=s.audio;
    fig.appendChild(cap); fig.appendChild(audio);
    return fig;
  }
  function attach(node){ if(global.mmLoopAttach) global.mmLoopAttach(node); }

  function boot(){
    var browse=document.getElementById("mm-browse");
    var results=document.getElementById("mm-results");
    var status=document.getElementById("mm-status");
    var input=document.getElementById("mm-q");
    var filters=document.getElementById("mm-filters");
    var stop=document.getElementById("mm-stop");
    if(!browse) return;
    var index=null, instFilter="all";

    function stopNodes(root){
      var list=(root||document).querySelectorAll("audio"), i;
      for(i=0;i<list.length;i++){ try{list[i].pause()}catch(e){} }
    }

    stop.addEventListener("click", function(){
      if(global.mmStopAll) global.mmStopAll();
      else stopNodes(document);
    });

    function setStatus(t){ status.textContent=t }

    function groupSounds(g){
      var roots={};
      g.sounds.forEach(function(s){
        if(!roots[s.root]) roots[s.root]={root:s.root, qualities:{}};
        if(!roots[s.root].qualities[s.quality]) roots[s.root].qualities[s.quality]=[];
        roots[s.root].qualities[s.quality].push(s);
      });
      Object.keys(roots).forEach(function(r){
        Object.keys(roots[r].qualities).forEach(function(q){
          roots[r].qualities[q].sort(function(a,b){
            if(a.def!==b.def) return a.def?-1:1;
            return voicingRank(a.voicing)-voicingRank(b.voicing)||a.voicing.localeCompare(b.voicing);
          });
        });
      });
      return roots;
    }

    function buildPlayers(box, sounds){
      if(box.dataset.built) return;
      sounds.forEach(function(s){ box.appendChild(playerFigure(s)) });
      attach(box);
      box.dataset.built="1";
    }

    function buildQualities(body, rootRec){
      if(body.dataset.built) return;
      var qs=Object.keys(rootRec.qualities).sort(function(a,b){return qIndex(a)-qIndex(b)||a.localeCompare(b)});
      qs.forEach(function(q){
        var sounds=rootRec.qualities[q];
        var det=el("details","mm-q");
        det.id="q-"+sounds[0].id+"-"+rootRec.root+"-"+q;
        var sum=el("summary");
        var h=el("h3");
        h.appendChild(document.createTextNode(prettyChord(sounds[0].chord)+" "));
        h.appendChild(el("span","mm-n", qName(q)+" · "+sounds.length+" voicing"+(sounds.length===1?"":"s")));
        sum.appendChild(h);
        var box=el("div");
        det.appendChild(sum); det.appendChild(box);
        det.addEventListener("toggle", function(){ if(det.open) buildPlayers(box, sounds) });
        body.appendChild(det);
      });
      body.dataset.built="1";
    }

    function buildRoots(g, body){
      if(body.dataset.built) return;
      var roots=groupSounds(g);
      var jump=el("nav","mm-jump");
      jump.setAttribute("aria-label","Jump to a root");
      var p=el("p");
      ROOT_ORDER.forEach(function(r){
        if(!roots[r]) return;
        var b=el("button"); b.type="button"; b.textContent=prettyRoot(r);
        b.addEventListener("click", function(){
          var d=document.getElementById("root-"+g.id+"-"+r);
          if(!d) return;
          d.open=true; buildQualities(d.querySelector(".mm-root-body"), roots[r]);
          d.scrollIntoView({block:"start"});
        });
        p.appendChild(b);
      });
      jump.appendChild(p);
      body.appendChild(jump);
      ROOT_ORDER.forEach(function(r){
        if(!roots[r]) return;
        var n=0; Object.keys(roots[r].qualities).forEach(function(q){ n+=roots[r].qualities[q].length });
        var det=el("details","mm-root");
        det.id="root-"+g.id+"-"+r;
        var sum=el("summary");
        var h=el("h3");
        h.appendChild(document.createTextNode(prettyRoot(r)+" "));
        h.appendChild(el("span","mm-n", Object.keys(roots[r].qualities).length+" chord types · "+n+" sounds"));
        sum.appendChild(h);
        var box=el("div","mm-root-body");
        det.appendChild(sum); det.appendChild(box);
        det.addEventListener("toggle", function(){ if(det.open) buildQualities(box, roots[r]) });
        body.appendChild(det);
      });
      body.dataset.built="1";
    }

    function renderBrowse(){
      browse.textContent="";
      index.order.forEach(function(id){
        if(instFilter!=="all" && instFilter!==id) return;
        var g=index.groups[id];
        var roots={}; g.sounds.forEach(function(s){roots[s.root]=1});
        var det=el("details","mm-inst");
        det.id="inst-"+id;
        var sum=el("summary");
        var h=el("h2");
        var title=id==="piano"?"Piano":g.name;
        h.appendChild(document.createTextNode(title+" "));
        var sub=id==="piano"?"full chord set v4 · ":"";
        h.appendChild(el("span","mm-n", sub+g.sounds.length+" sounds · "+Object.keys(roots).length+" roots · Petrus, CC BY-SA 4.0"));
        sum.appendChild(h);
        var body=el("div");
        var credit=el("p","mm-credit","Petrus, CC BY-SA 4.0");
        body.appendChild(credit);
        if(g.col && g.col.excluded_note) body.appendChild(el("p","mm-note", g.col.excluded_note));
        var holder=el("div");
        body.appendChild(holder);
        det.appendChild(sum); det.appendChild(body);
        det.addEventListener("toggle", function(){ if(det.open) buildRoots(g, holder) });
        browse.appendChild(det);
      });
    }

    function renderFilters(){
      filters.textContent="";
      function chip(id, label){
        var b=el("button"); b.type="button"; b.textContent=label; b.setAttribute("aria-pressed", instFilter===id?"true":"false");
        b.addEventListener("click", function(){ instFilter=id; renderFilters(); renderBrowse(); runSearch(); });
        filters.appendChild(b);
      }
      chip("all","All instruments");
      index.order.forEach(function(id){
        var g=index.groups[id];
        chip(id, id==="piano"?"Piano":g.name);
      });
    }

    function runSearch(){
      var q=input.value;
      if(!q.trim()){
        results.hidden=true; results.textContent=""; browse.hidden=false; return;
      }
      var found=search(index, q, instFilter);
      browse.hidden=true; results.hidden=false; results.textContent="";
      var h=el("h2", null, found.total? found.showing+" of "+found.total : "No matches");
      results.appendChild(h);
      if(found.note) results.appendChild(el("p","mm-note", found.note));
      if(!found.total) results.appendChild(el("p","mm-note","Try a chord (Cmaj7), a root with a quality (f sharp minor), or an instrument (choir, arp, fat synth)."));
      found.items.forEach(function(s){ results.appendChild(playerFigure(s)) });
      attach(results);
    }

    input.addEventListener("input", function(){
      stopNodes(results);
      runSearch();
    });
    input.form.addEventListener("submit", function(e){ e.preventDefault(); runSearch(); });

    setStatus("Loading the catalog…");
    fetch("/netcomposer.json").then(function(r){ if(!r.ok) throw 0; return r.json() }).then(function(data){
      index=indexCatalog(data);
      var n=index.sounds.length, k=index.order.length;
      setStatus(k+" instrument"+(k===1?"":"s")+" · "+n+" sounds. Sections stay closed until you open them.");
      renderFilters();
      renderBrowse();
      if(input.value.trim()) runSearch();
    }).catch(function(){
      setStatus("Could not load /netcomposer.json.");
    });
  }

  global.mmHome={indexCatalog:indexCatalog, search:search, parseQuery:parseQuery, soundFromOffering:soundFromOffering, parseNamedFile:parseNamedFile};
  if(global.document && global.document.getElementById("mm-browse")){
    if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", boot);
    else boot();
  }
})(typeof window!=="undefined"?window:globalThis);
