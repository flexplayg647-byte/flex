import asyncio
import pygame
import sys
import math
import random
import json
import os
os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "1")
import time as _time
import traceback
import hashlib
import hmac
import re


def _asset(nom):
    """Chemin d'un fichier du jeu (image, son) : dossier courant d'abord, sinon le dossier de main.py.
    Pydroid lance parfois le jeu depuis un autre dossier, et les images ne se chargeaient alors pas."""
    if os.path.exists(nom):
        return nom
    try:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), nom)
        if os.path.exists(p):
            return p
    except Exception:
        pass
    return nom


# Dossier des sauvegardes : sur Android (APK) c'est le stockage privé de l'application (conservé lors des mises à jour) ;
# sur Pydroid ou PC, rien ne change : les fichiers restent à côté du jeu.
IS_WEB = sys.platform == "emscripten"
_DOSSIER_DONNEES = os.environ.get("ANDROID_PRIVATE", "")
if IS_WEB:
    _DOSSIER_DONNEES = "/data/data/flexcyber"   # dossier persistant du navigateur (pygbag)
    try:
        os.makedirs(_DOSSIER_DONNEES, exist_ok=True)
    except Exception:
        _DOSSIER_DONNEES = ""


# --- Web : le dossier de jeu est une mémoire temporaire. On recopie donc les sauvegardes dans le localStorage du navigateur
#     (mémoire permanente) et on les restaure au démarrage.
_CLOUD = {"mode": "guest", "dirty": False, "last": 0.0, "gel": False}
_LS = None
_SYNC_ETAT = {}
if IS_WEB:
    try:
        import platform as _pfs
        _LS = _pfs.window.localStorage
    except Exception:
        _LS = None


def _restaurer_sauvegardes():
    if _LS is None:
        return
    try:
        brut = _LS.getItem("flexsave:index")
        noms = json.loads(str(brut)) if brut is not None else []
        for nom in noms:
            nom = os.path.basename(str(nom))
            val = _LS.getItem("flexsave:" + nom)
            if not nom.endswith(".json") or val is None:
                continue
            with open(os.path.join(_DOSSIER_DONNEES or ".", nom), "w", encoding="utf-8") as f:
                f.write(str(val))
            _SYNC_ETAT[nom] = str(val)
    except Exception as e:
        print("restauration impossible :", e)


def _sync_sauvegardes():
    if _LS is None or _CLOUD["gel"]:
        return
    try:
        base = _DOSSIER_DONNEES or "."
        for nom in os.listdir(base):
            if not nom.endswith(".json"):
                continue
            with open(os.path.join(base, nom), "r", encoding="utf-8") as f:
                txt = f.read()
            if _SYNC_ETAT.get(nom) != txt:
                _LS.setItem("flexsave:" + nom, txt)
                _SYNC_ETAT[nom] = txt
                _LS.setItem("flexsave:index", json.dumps(sorted(_SYNC_ETAT.keys())))
                _LS.setItem("flexsave_t", str(int(_time.time() * 1000)))
                _CLOUD["dirty"] = True
    except Exception:
        pass


if IS_WEB:
    _restaurer_sauvegardes()


# ==================== CONNEXION GOOGLE + SAUVEGARDE EN LIGNE (Firebase) — version web uniquement ====================
_JS_FIREBASE = r"""
(function(){
if(window.flexAuth){return;}
var A=window.flexAuth={ready:false,uid:"",name:"",err:"",busy:false,cloud:"",cloudState:"",pushState:"",pseudo:""};
var CFG={apiKey:"AIzaSyCVozZHuFiU0Ho64lJhpNkE2V7B9JdPVWw",authDomain:"flex-cyberpunk-c49e8.firebaseapp.com",projectId:"flex-cyberpunk-c49e8",storageBucket:"flex-cyberpunk-c49e8.firebasestorage.app",messagingSenderId:"62235176856",appId:"1:62235176856:web:eef7cda18333fe1a3645ed"};
var V="10.14.1";
var urls=["app","auth","firestore"].map(function(n){return "https://www.gstatic.com/firebasejs/"+V+"/firebase-"+n+"-compat.js";});
function code(e){return (e&&e.code)?e.code:String(e);}
function fail(m){A.err=m;A.ready=true;}
function load(i){
  if(i>=urls.length){init();return;}
  var s=document.createElement("script");
  s.src=urls[i];
  s.onload=function(){load(i+1);};
  s.onerror=function(){fail("chargement-script-"+i);};
  document.head.appendChild(s);
}
function init(){
  try{
    firebase.initializeApp(CFG);
    A.auth=firebase.auth();
    A.db=firebase.firestore();
    A.auth.onAuthStateChanged(function(u){
      if(u){A.uid=u.uid;A.name=u.displayName||u.email||"Joueur";try{if(!sessionStorage.getItem("flex_login")){sessionStorage.setItem("flex_login","1");A.log("login",0);try{A.db.collection("profils").doc(u.uid).set({email:String(u.email||"").slice(0,120),nom:String(u.displayName||"").slice(0,80),last:firebase.firestore.FieldValue.serverTimestamp()}).catch(function(){});}catch(x){}}}catch(e){}try{A.profile(u);}catch(e){}try{A.loadSkins();}catch(e){}}else{A.uid="";A.name="";A.pseudo="";A.skins=[];A.skinActif="";}
      A.ready=true;
    });
    setTimeout(function(){A.ready=true;},6000);
  }catch(e){fail(String(e));}
}
A.signIn=function(){
  A.err="";A.busy=true;
  try{
    var p=new firebase.auth.GoogleAuthProvider();
    A.auth.signInWithPopup(p).then(function(){A.busy=false;}).catch(function(e){A.busy=false;A.err=code(e);});
  }catch(e){A.busy=false;A.err=String(e);}
};
A.signOut=function(){try{A.auth.signOut();}catch(e){}};
A.pull=function(){
  A.cloudState="loading";A.cloud="";
  try{
    A.db.collection("saves").doc(A.auth.currentUser.uid).get().then(function(d){
      A.cloud=d.exists?JSON.stringify(d.data()):"";A.cloudState="done";
    }).catch(function(e){A.err=code(e);A.cloudState="error";});
  }catch(e){A.err=String(e);A.cloudState="error";}
};
A.push=function(txt){
  A.pushState="loading";
  try{
    var data=JSON.parse(txt);
    A.db.collection("saves").doc(A.auth.currentUser.uid).set(data).then(function(){A.pushState="done";}).catch(function(e){A.err=code(e);A.pushState="error";});
  }catch(e){A.err=String(e);A.pushState="error";}
};
var B=document.createElement("button");
B.id="flexgbtn";
B.setAttribute("aria-label","Se connecter avec Google");
B.style.cssText="position:fixed;display:none;opacity:0;z-index:100000;border:0;padding:0;margin:0;background:transparent;";
document.body.appendChild(B);
B.onclick=function(){A.signIn();};
A.showBtn=function(x,y,w,h,rw){
  var c=document.getElementById("canvas")||document.querySelector("canvas");
  if(!c){return;}
  var r=c.getBoundingClientRect();var k=r.width/rw;
  B.style.left=(r.left+x*k)+"px";B.style.top=(r.top+y*k)+"px";
  B.style.width=(w*k)+"px";B.style.height=(h*k)+"px";B.style.display="block";
};
A.hideBtn=function(){B.style.display="none";};
var Q=[];
var vid="";
try{vid=localStorage.getItem("flex_vid")||"";if(!vid){vid=Math.random().toString(36).slice(2)+Date.now().toString(36);localStorage.setItem("flex_vid",vid);}}catch(e){vid="anon";}
function send(e){
  try{
    A.db.collection("events").add({t:firebase.firestore.FieldValue.serverTimestamp(),type:e.type,lvl:e.lvl|0,vid:vid,uid:A.uid||""}).catch(function(){});
    if((e.type==="level_win"||e.type==="level_lose")&&A.uid&&A.pseudo){
      var f={last:firebase.firestore.FieldValue.serverTimestamp()};
      f[e.type==="level_win"?"wins":"losses"]=firebase.firestore.FieldValue.increment(1);
      A.db.collection("players").doc(A.uid).set(f,{merge:true}).catch(function(){});
    }
  }catch(x){}
}
function esc(t){return String(t).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c];});}
var CSS="*{box-sizing:border-box;margin:0;padding:0}html,body{height:100%}"+
"body{display:flex;align-items:center;justify-content:center;font-family:Arial,Helvetica,sans-serif;color:#eaf0ff;background:radial-gradient(ellipse at center,rgba(22,8,44,.94),rgba(3,4,12,.98) 70%);overflow:hidden}"+
"body:before{content:'';position:fixed;left:0;top:0;right:0;bottom:0;background:repeating-linear-gradient(0deg,rgba(0,235,255,.05) 0,rgba(0,235,255,.05) 1px,transparent 1px,transparent 4px);pointer-events:none}"+
".pn{position:relative;width:min(92%,460px);max-height:94%;overflow:auto;padding:16px 18px;text-align:center;background:linear-gradient(160deg,rgba(14,18,40,.97),rgba(6,8,20,.97));border:2px solid #00ebff;border-radius:16px;box-shadow:0 0 24px rgba(0,235,255,.45),inset 0 0 22px rgba(255,0,180,.12)}"+
".pn.col{display:flex;flex-direction:column;overflow:hidden}"+
".t{font-size:clamp(22px,6vw,32px);font-weight:900;letter-spacing:2px;color:#fff;text-shadow:-3px 0 #ff00b4,3px 0 #00ebff}"+
".s{margin:4px 0 10px;font-size:12px;letter-spacing:3px;color:#ff00b4;font-weight:700}"+
".av{width:56px;height:56px;border-radius:50%;border:2px solid #00ff80;box-shadow:0 0 12px rgba(0,255,128,.6);margin:0 auto 8px;display:block;object-fit:cover}"+
".h{font-size:14px;color:#b8c4ee;margin-bottom:10px;line-height:1.35}"+
"input{width:100%;padding:12px 14px;font-size:20px;text-align:center;color:#fff;font-weight:700;letter-spacing:1px;background:#070a18;border:2px solid #00ebff;border-radius:10px;outline:none;box-shadow:0 0 10px rgba(0,235,255,.35)}"+
"input:focus{border-color:#ff00b4;box-shadow:0 0 14px rgba(255,0,180,.6)}"+
".r{font-size:11px;color:#7f8bbd;margin-top:6px}"+
".e{min-height:18px;margin:8px 0 2px;font-size:13px;color:#ff3a6e;font-weight:700}"+
".ok{color:#00ff80}"+
".b{display:flex;gap:10px;margin-top:8px}"+
"button{flex:1;padding:13px 8px;font-size:16px;font-weight:900;letter-spacing:1px;border-radius:10px;cursor:pointer;font-family:inherit}"+
".bp{background:#ff00b4;color:#05050a;border:2px solid #ff00b4;box-shadow:0 0 16px rgba(255,0,180,.7);animation:pu 1.6s infinite}"+
".bs{background:transparent;color:#00ebff;border:2px solid #00ebff}"+
"button:disabled{opacity:.5}@keyframes pu{50%{box-shadow:0 0 26px rgba(255,0,180,1)}}"+
".lg{text-align:left;margin:6px 0;overflow-y:auto;flex:1 1 auto;min-height:0;-webkit-overflow-scrolling:touch}"+
".rw{display:flex;align-items:center;gap:10px;padding:6px 10px;margin:5px 0;background:rgba(0,235,255,.06);border:1px solid rgba(0,235,255,.25);border-radius:10px}"+
".rw.me{background:rgba(255,0,180,.16);border-color:#ff00b4;box-shadow:0 0 10px rgba(255,0,180,.5)}"+
".rw.first{border-color:#ffdc00;box-shadow:0 0 12px rgba(255,220,0,.5)}"+
".n{width:34px;text-align:center;font-size:22px;font-weight:900;color:#ff00b4}"+
".nm{flex:1;min-width:0;font-weight:800;font-size:17px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"+
".sc{text-align:right;font-size:12px;color:#8a94c8;line-height:1.3}.sc b{color:#00ff80;font-size:15px}"+
".mo{font-size:13px;color:#00ebff;margin:6px 0 2px;font-weight:700;text-align:center}";
function fermer(){var f=document.getElementById("flexui");if(f&&f.parentNode){f.parentNode.removeChild(f);}window.flexModal=false;}
function sortirPleinEcran(cb){
  try{
    if(document.fullscreenElement&&document.exitFullscreen){
      var r=document.exitFullscreen();
      if(r&&r.then){r.then(function(){setTimeout(cb,250);}).catch(function(){setTimeout(cb,250);});return;}
    }
  }catch(e){}
  setTimeout(cb,50);
}
var TACT=(("ontouchstart" in window)||(navigator.maxTouchPoints>0));
var PRIVURL="confidentialite.html";
try{PRIVURL=new URL("confidentialite.html",location.href).href;}catch(e){}
function saisir(inp,question,cb){
  sortirPleinEcran(function(){
    var v=null;
    try{v=window.prompt(question,inp.value||"");}catch(e){}
    if(v!==null&&v!==undefined){inp.value=String(v).trim();}
    if(cb){cb();}
  });
}
function pseudoAlea(){
  var a=["Neo","Cyber","Ghost","Nova","Volt","Zero","Apex","Rogue","Pixel","Storm","Blaze","Hex","Echo","Viper","Onyx","Flux"];
  var b=["Wolf","Fox","Hawk","Rider","Blade","Spark","Byte","Drone","Raven","Titan","Ninja","Pilot"];
  return a[Math.floor(Math.random()*a.length)]+b[Math.floor(Math.random()*b.length)]+(10+Math.floor(Math.random()*90));
}
function ouvrir(cb){
  fermer();
  window.flexModal=true;
  var f=document.createElement("iframe");
  f.id="flexui";
  f.style.cssText="position:fixed;left:0;top:0;width:100%;height:100%;border:0;z-index:2147483647;background:transparent";
  f.srcdoc="<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><style>"+CSS+"</style></head><body><div id='box'></div></body></html>";
  f.onload=function(){try{cb(f.contentDocument);}catch(e){fermer();}};
  document.body.appendChild(f);
}
var MSG={invalid:"Pseudo invalide : 3 &agrave; 16 caract&egrave;res (lettres, chiffres, espace, _ ou -).",taken:"Ce pseudo est d&eacute;j&agrave; pris ou refus&eacute;. Essaies-en un autre.",error:"Erreur. R&eacute;essaie dans un instant.",auth:"Tu n'es plus connect&eacute;."};
A.savePseudo=function(p,cb){
  var u=A.auth.currentUser;
  if(!u){cb("auth");return;}
  p=String(p||"").trim();
  if(!/^[A-Za-z0-9_ -]{3,16}$/.test(p)){cb("invalid");return;}
  var b=A.db.batch();
  b.set(A.db.collection("pseudos").doc(p.toLowerCase()),{uid:u.uid});
  b.set(A.db.collection("players").doc(u.uid),{pseudo:p,photo:(u.photoURL||"").slice(0,400),wins:0,losses:0,last:firebase.firestore.FieldValue.serverTimestamp()});
  b.commit().then(function(){A.pseudo=p;cb("ok");}).catch(function(e){cb(code(e)==="permission-denied"?"taken":"error");});
};
function dlgPseudo(u){
  ouvrir(function(d){
    var photo=u.photoURL?"<img class='av' referrerpolicy='no-referrer' src='"+esc(u.photoURL)+"'>":"";
    d.getElementById("box").className="kbd";
    d.getElementById("box").innerHTML="<div class='pn kbp'><div class='t'>FLEX CYBERPUNK</div><div class='s'>IDENTIT&Eacute; DU JOUEUR</div>"+photo+
      "<div class='h'>Choisis ton pseudo pour le classement.<br>Il sera visible par tous les joueurs.</div>"+
      "<input id='p' maxlength='16' autocomplete='off' autocapitalize='off' autocorrect='off' spellcheck='false' enterkeyhint='done' inputmode='text' placeholder='"+(TACT?"TOUCHE ICI POUR &Eacute;CRIRE":"TON PSEUDO")+"'"+(TACT?" readonly":"")+">"+
      "<div class='r'>3 &agrave; 16 caract&egrave;res : lettres, chiffres, espace, _ ou -</div><div class='e' id='e'></div>"+
      "<div class='b'><button id='ok' class='bp'>VALIDER</button><button id='al' class='bs'>&#127922; AL&Eacute;ATOIRE</button><button id='no' class='bs'>PLUS TARD</button></div>"+
      "<div class='pv'>En continuant, tu acceptes la <a href='"+PRIVURL+"' target='_blank'>confidentialit&eacute; et les conditions</a>.</div></div>";
    var inp=d.getElementById("p"),e=d.getElementById("e"),ok=d.getElementById("ok");
    d.getElementById("al").onclick=function(){inp.value=pseudoAlea();e.className="e";e.innerHTML="";};
    ok.onclick=function(){
      e.className="e";e.innerHTML="Enregistrement...";ok.disabled=true;
      A.savePseudo(inp.value,function(r){
        if(r==="ok"){e.className="e ok";e.innerHTML="Bienvenue, "+esc(A.pseudo)+" !";setTimeout(fermer,1100);}
        else{e.className="e";e.innerHTML=MSG[r]||MSG.error;ok.disabled=false;}
      });
    };
    inp.onkeydown=function(ev){if(ev.key==="Enter"){ok.onclick();}};
    d.getElementById("no").onclick=fermer;
    if(TACT){
      inp.onclick=function(){saisir(inp,"Choisis ton pseudo (3 \u00e0 16 caract\u00e8res : lettres, chiffres, espace, _ ou -) :");};
    }else{
      sortirPleinEcran(function(){try{inp.focus();}catch(x){}});
    }
  });
}
function plur(n,s){return n+" "+s+(n>1?"s":"");}
function dlgInfo(titre,texte){
  ouvrir(function(d){
    d.getElementById("box").innerHTML="<div class='pn'><div class='t'>"+titre+"</div><div class='h' style='margin-top:14px'>"+texte+"</div><div class='b'><button id='x' class='bs'>FERMER</button></div></div>";
    d.getElementById("x").onclick=fermer;
  });
}
A.showRank=function(){
  if(!A.uid){dlgInfo("CLASSEMENT","Connecte-toi avec ton compte Google pour voir le classement et y participer.");return;}
  ouvrir(function(d){
    var box=d.getElementById("box");
    box.innerHTML="<div class='pn'><div class='t'>CLASSEMENT</div><div class='h' style='margin-top:14px'>Chargement...</div></div>";
    A.db.collection("players").orderBy("wins","desc").limit(300).get().then(function(snap){
      var j=[];
      snap.forEach(function(x){var v=x.data();j.push({id:x.id,p:v.pseudo||"?",w:v.wins||0,l:v.losses||0});});
      j=j.filter(function(x){return x.w+x.l>0;});
      j.sort(function(a,b){return (b.w-a.w)||(a.l-b.l);});
      var top=j.slice(0,10),med=["&#129351;","&#129352;","&#129353;"],html="";
      top.forEach(function(x,i){
        html+="<div class='rw"+(x.id===A.uid?" me":"")+(i===0?" first":"")+"'><div class='n'>"+(i<3?med[i]:(i+1))+"</div><div class='nm'>"+esc(x.p)+"</div><div class='sc'><b>"+plur(x.w,"victoire")+"</b><br>"+plur(x.l,"d&eacute;faite")+"</div></div>";
      });
      if(!top.length){html="<div class='h' style='text-align:center;margin-top:10px'>Personne n'est encore class&eacute;. Sois le premier !</div>";}
      var moi="",idx=-1,i2;
      for(i2=0;i2<j.length;i2++){if(j[i2].id===A.uid){idx=i2;break;}}
      var bouton="<button id='x' class='bs'>FERMER</button>";
      if(!A.pseudo){
        moi="<div class='mo'>Tu n'as pas encore de pseudo.</div>";
        bouton="<button id='ps' class='bp'>CHOISIR MON PSEUDO</button><button id='x' class='bs'>FERMER</button>";
      }else if(idx>=10){
        moi="<div class='mo'>Ton rang : #"+(idx+1)+" - "+plur(j[idx].w,"victoire")+", "+plur(j[idx].l,"d&eacute;faite")+"</div>";
      }else if(idx<0){
        moi="<div class='mo'>Gagne un niveau pour entrer au classement !</div>";
      }
      box.innerHTML="<div class='pn col'><div class='t'>CLASSEMENT</div><div class='s'>TOP 10 DES JOUEURS</div><div class='lg'>"+html+"</div>"+moi+"<div class='b'>"+bouton+"</div></div>";
      d.getElementById("x").onclick=fermer;
      var ps=d.getElementById("ps");
      if(ps){ps.onclick=function(){var u=A.auth.currentUser;if(u){dlgPseudo(u);}};}
    }).catch(function(){
      box.innerHTML="<div class='pn'><div class='t'>CLASSEMENT</div><div class='h' style='margin-top:14px'>Classement indisponible pour le moment.</div><div class='b'><button id='x' class='bs'>FERMER</button></div></div>";
      d.getElementById("x").onclick=fermer;
    });
  });
};
A.profile=function(u){
  var ref=A.db.collection("players").doc(u.uid);
  ref.get().then(function(d){
    if(d.exists){
      var x=d.data();
      A.pseudo=x.pseudo||"";
      var ph=(u.photoURL||"").slice(0,400);
      if(ph&&x.photo!==ph){ref.update({photo:ph}).catch(function(){});}
    }else{
      dlgPseudo(u);
    }
  }).catch(function(){});
};
var WORKER="https://flex-licence.flexplayg647.workers.dev";
var BUY="https://eiuforef.mychariow.shop/prd_uj80vrr1/checkout";
var SKD=[{"id":"recrue","n":"Recrue","r":"C","s":"H","l":[["p","survie","PEAU D'ACIER","Survit \u00e0 1 drone de plus avant de tomber."]]},{"id":"sergent_du_desert","n":"Sergent du D\u00e9sert","r":"C","s":"H","l":[["p","bouclier","BOUCLIER LOURD","Absorbe 1 coup de boss avant de subir des d\u00e9g\u00e2ts."],["e","grenades","GRENADES x3","Explosion en zone anti-drones."]]},{"id":"rodeur_urbain","n":"R\u00f4deur Urbain","r":"C","s":"H","l":[["p","sprint","TURBO","Course ultra-rapide pendant 3 secondes \u00e0 chaque niveau."]]},{"id":"fantassin_polaire","n":"Fantassin Polaire","r":"C","s":"H","l":[["p","or","CHASSEUR D'OR","+10 % de pi\u00e8ces gagn\u00e9es \u00e0 chaque mission."]]},{"id":"chasseur_de_primes","n":"Chasseur de Primes","r":"C","s":"H","l":[["p","perforant","TIR PERFORANT","Chaque balle traverse 1 drone d'un seul coup."],["e","munitions","MUNITIONS","Tir 20 % plus rapide."]]},{"id":"mercenaire_rouge","n":"Mercenaire Rouge","r":"R","s":"H","l":[["p","sprint","TURBO","Course ultra-rapide pendant 5 secondes \u00e0 chaque niveau."],["e","grenades","GRENADES x3 + MUNITIONS","Explosion en zone anti-drones. Tir 20 % plus rapide."]]},{"id":"tireur_delite","n":"Tireur d'\u00c9lite","r":"R","s":"H","l":[["p","perforant","TIR PERFORANT","Chaque balle traverse 2 drones d'un seul coup."],["t","faufile","FAUFIL\u00c9","30 % plus fin. Au mur : +20 % vitesse, boss rat\u00e9 1 fois sur 2."],["e","antenne","BROUILLEUR","Ralentit les drones proches de 25 %."]]},{"id":"punk_anarchiste","n":"Punk Anarchiste","r":"R","s":"H","l":[["p","radar","RADAR TACTIQUE","R\u00e9v\u00e8le tous les drones pendant 4 secondes, une fois par niveau."],["e","grenades","GRENADES x3","Explosion en zone anti-drones."]]},{"id":"pilote_jet","n":"Pilote Jet","r":"R","s":"H","l":[["p","fantome","PHASE","Traverse les murs pendant 2 secondes, une fois par niveau."],["e","holo","\u00c9CRAN HOLO","Piratage +50 % et alerte drones."]]},{"id":"gladiateur","n":"Gladiateur","r":"R","s":"H","l":[["p","survie","PEAU D'ACIER","Survit \u00e0 2 drones de plus avant de tomber."]]},{"id":"cow_boy_cyber","n":"Cow-boy Cyber","r":"R","s":"H","l":[["p","or","CHASSEUR D'OR","+20 % de pi\u00e8ces gagn\u00e9es \u00e0 chaque mission."],["e","holo","\u00c9CRAN HOLO + MUNITIONS","Piratage +50 % et alerte drones. Tir 20 % plus rapide."]]},{"id":"colosse_dacier","n":"Colosse d'Acier","r":"E","s":"H","l":[["p","bouclier","BOUCLIER LOURD","Absorbe 3 coups de boss avant de subir des d\u00e9g\u00e2ts."],["e","roquettes","ROQUETTES x2","Gros d\u00e9g\u00e2ts sur le boss."]]},{"id":"cyber_ninja","n":"Cyber-Ninja","r":"E","s":"H","l":[["p","fantome","PHASE","Traverse les murs pendant 4 secondes, une fois par niveau."],["t","faufile","FAUFIL\u00c9","30 % plus fin. Au mur : +20 % vitesse, boss rat\u00e9 1 fois sur 2."],["e","drone","DRONE ALLI\u00c9","Tire seul sur les ennemis proches."]]},{"id":"fantome","n":"Fant\u00f4me","r":"E","s":"H","l":[["p","ralenti","TEMPS RALENTI","Ralentit les ennemis pendant 4 secondes, une fois par niveau."],["e","antenne","BROUILLEUR","Ralentit les drones proches de 25 %."]]},{"id":"samourai_neon","n":"Samoura\u00ef N\u00e9on","r":"E","s":"H","l":[["p","sprint","TURBO","Course ultra-rapide pendant 6 secondes \u00e0 chaque niveau."],["e","holo","\u00c9CRAN HOLO","Piratage +50 % et alerte drones."]]},{"id":"chevalier_toxique","n":"Chevalier Toxique","r":"E","s":"H","l":[["p","survie","PEAU D'ACIER","Survit \u00e0 3 drones de plus avant de tomber."],["e","roquettes","ROQUETTES x2 + GRENADES x3","Gros d\u00e9g\u00e2ts sur le boss. Explosion en zone anti-drones."]]},{"id":"commandant_dore","n":"Commandant Dor\u00e9","r":"L","s":"H","l":[["p","bouclier","BOUCLIER LOURD","Absorbe 2 coups de boss avant de subir des d\u00e9g\u00e2ts."],["p","or","CHASSEUR D'OR","+30 % de pi\u00e8ces gagn\u00e9es \u00e0 chaque mission."],["e","munitions","MUNITIONS","Tir 20 % plus rapide."]]},{"id":"titan_solaire","n":"Titan Solaire","r":"L","s":"H","l":[["p","bouclier","BOUCLIER LOURD","Absorbe 3 coups de boss avant de subir des d\u00e9g\u00e2ts."],["p","survie","PEAU D'ACIER","Survit \u00e0 3 drones de plus avant de tomber."],["e","roquettes","ROQUETTES x2 + MUNITIONS","Gros d\u00e9g\u00e2ts sur le boss. Tir 20 % plus rapide."]]},{"id":"seigneur_du_vide","n":"Seigneur du Vide","r":"L","s":"H","l":[["p","fantome","PHASE","Traverse les murs pendant 6 secondes, une fois par niveau."],["p","ralenti","TEMPS RALENTI","Ralentit les ennemis pendant 4 secondes, une fois par niveau."],["e","drone","DRONE ALLI\u00c9","Tire seul sur les ennemis proches."]]},{"id":"eclaireur_bronze","n":"\u00c9claireur Bronze","r":"C","s":"H","l":[["p","radar","RADAR TACTIQUE","R\u00e9v\u00e8le tous les drones pendant 3 secondes, une fois par niveau."],["t","faufile","FAUFIL\u00c9","30 % plus fin. Au mur : +20 % vitesse, boss rat\u00e9 1 fois sur 2."],["e","antenne","BROUILLEUR","Ralentit les drones proches de 25 %."]]},{"id":"eclaireuse","n":"\u00c9claireuse","r":"C","s":"F","l":[["p","sprint","TURBO","Course ultra-rapide pendant 3 secondes \u00e0 chaque niveau."],["t","faufile","FAUFIL\u00c9","30 % plus fin. Au mur : +20 % vitesse, boss rat\u00e9 1 fois sur 2."],["e","grenades","GRENADES x3","Explosion en zone anti-drones."]]},{"id":"amazone_des_neiges","n":"Amazone des Neiges","r":"R","s":"F","l":[["p","ralenti","TEMPS RALENTI","Ralentit les ennemis pendant 3 secondes, une fois par niveau."],["e","munitions","MUNITIONS","Tir 20 % plus rapide."]]},{"id":"pilote_rose","n":"Pilote Rose","r":"R","s":"F","l":[["p","fantome","PHASE","Traverse les murs pendant 2 secondes, une fois par niveau."],["t","faufile","FAUFIL\u00c9","30 % plus fin. Au mur : +20 % vitesse, boss rat\u00e9 1 fois sur 2."],["e","holo","\u00c9CRAN HOLO","Piratage +50 % et alerte drones."]]},{"id":"chasseresse_verte","n":"Chasseresse Verte","r":"R","s":"F","l":[["p","perforant","TIR PERFORANT","Chaque balle traverse 2 drones d'un seul coup."],["e","munitions","MUNITIONS","Tir 20 % plus rapide."]]},{"id":"alchimiste","n":"Alchimiste","r":"R","s":"F","l":[["p","or","CHASSEUR D'OR","+20 % de pi\u00e8ces gagn\u00e9es \u00e0 chaque mission."],["t","faufile","FAUFIL\u00c9","30 % plus fin. Au mur : +20 % vitesse, boss rat\u00e9 1 fois sur 2."],["e","holo","\u00c9CRAN HOLO","Piratage +50 % et alerte drones."]]},{"id":"valkyrie","n":"Valkyrie","r":"E","s":"F","l":[["p","fantome","PHASE","Traverse les murs pendant 5 secondes, une fois par niveau."]]},{"id":"ninja_violette","n":"Ninja Violette","r":"E","s":"F","l":[["p","sprint","TURBO","Course ultra-rapide pendant 6 secondes \u00e0 chaque niveau."],["t","faufile","FAUFIL\u00c9","30 % plus fin. Au mur : +20 % vitesse, boss rat\u00e9 1 fois sur 2."],["e","holo","\u00c9CRAN HOLO","Piratage +50 % et alerte drones."]]},{"id":"cyber_chat","n":"Cyber-Chat","r":"E","s":"F","l":[["p","radar","RADAR TACTIQUE","R\u00e9v\u00e8le tous les drones pendant 6 secondes, une fois par niveau."],["t","faufile","FAUFIL\u00c9","30 % plus fin. Au mur : +20 % vitesse, boss rat\u00e9 1 fois sur 2."],["e","drone","DRONE ALLI\u00c9","Tire seul sur les ennemis proches."]]},{"id":"reine_ecarlate","n":"Reine \u00c9carlate","r":"L","s":"F","l":[["p","or","CHASSEUR D'OR","+30 % de pi\u00e8ces gagn\u00e9es \u00e0 chaque mission."],["p","ralenti","TEMPS RALENTI","Ralentit les ennemis pendant 4 secondes, une fois par niveau."]]},{"id":"deesse_solaire","n":"D\u00e9esse Solaire","r":"L","s":"F","l":[["p","bouclier","BOUCLIER LOURD","Absorbe 3 coups de boss avant de subir des d\u00e9g\u00e2ts."],["p","fantome","PHASE","Traverse les murs pendant 5 secondes, une fois par niveau."],["e","drone","DRONE ALLI\u00c9","Tire seul sur les ennemis proches."]]}];
var SHEET="skins_sheet.png";
try{SHEET=new URL("skins_sheet.png",location.href).href;}catch(e){}
A.skins=[];A.skinActif="";
try{A.equipped=localStorage.getItem("flex_skin")||"";}catch(e){A.equipped="";}
var RN={C:["COMMUN","C",1,"#aab0be"],R:["RARE","B",2,"#00c8ff"],E:["\u00c9PIQUE","A",3,"#be46ff"],L:["L\u00c9GENDAIRE","S",4,"#ffc828"]};
var ICO={bouclier:"&#128737;",survie:"&#10084;",fantome:"&#128123;",sprint:"&#9889;",perforant:"&#127919;",or:"&#128176;",radar:"&#128225;",ralenti:"&#9203;",faufile:"&#127939;",grenades:"&#128163;",roquettes:"&#128640;",holo:"&#128187;",drone:"&#129302;",antenne:"&#128225;",munitions:"&#128165;"};
var LBL={p:"SUPER POUVOIR",t:"TALENT NATUREL",e:"&Eacute;QUIPEMENT ACTIF"};
var LCOL={p:"#ffd646",t:"#78ffaa",e:"#ff8c3c"};
var MSG2={auth:"Tu n'es plus connect&eacute;. Reconnecte-toi avec Google.",format:"Cl&eacute; invalide : v&eacute;rifie les caract&egrave;res.",cle_inconnue:"Cl&eacute; introuvable. V&eacute;rifie qu'elle est copi&eacute;e en entier.",cle_deja_utilisee:"Cette cl&eacute; a d&eacute;j&agrave; servi.",deja_possede:"Tu poss&egrave;des d&eacute;j&agrave; ce personnage.",revoquee:"Cette cl&eacute; n'est plus valide.",expiree:"Cette cl&eacute; n'est plus valide.",mauvais_produit:"Cette cl&eacute; ne correspond pas &agrave; ce produit.",trop_d_essais:"Trop d'essais. R&eacute;essaie dans une heure.",skin:"Personnage inconnu.",serveur:"Service indisponible. R&eacute;essaie dans un instant.",reseau:"Pas de connexion. R&eacute;essaie dans un instant.",activation_refusee:"Activation refus&eacute;e. Contacte le support.",chariow:"Service indisponible. R&eacute;essaie dans un instant."};
CSS+=".pv{font-size:11px;color:#8fa0d8;margin-top:6px}.pv a{color:#00ebff}"+
"@media (max-height:440px){#box.kbd{align-items:flex-start}.pn.kbp{margin-top:6px;padding:10px 14px}.pn.kbp .av,.pn.kbp .s,.pn.kbp .h,.pn.kbp .r{display:none}.pn.kbp .t{font-size:20px}.pn.kbp input{padding:9px 10px;font-size:18px}.pn.kbp .e{min-height:16px;margin:4px 0 0}.pn.kbp button{padding:10px 6px;font-size:14px}.pn.kbp .b{margin-top:6px}}"+
"#box{width:100%;height:100%;display:flex;align-items:center;justify-content:center}"+
".pn.wide{width:min(96%,920px)}"+
".hd{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;gap:10px}"+
".hd .t{font-size:clamp(18px,4.5vw,26px)}"+
".gr{display:grid;grid-template-columns:repeat(auto-fill,minmax(118px,1fr));gap:8px;overflow-y:auto;flex:1 1 auto;min-height:0;padding:4px 2px;-webkit-overflow-scrolling:touch}"+
".tl{background:rgba(8,10,24,.9);border:2px solid;border-radius:12px;padding:6px 4px 8px;text-align:center;cursor:pointer}"+
".sp{margin:0 auto}"+
".tn{font-size:12px;font-weight:800;margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"+
".tb{font-size:10px;font-weight:800;letter-spacing:1px;margin-top:2px}"+
".dt{display:flex;gap:12px;flex:1 1 auto;min-height:0;overflow:hidden}"+
".dl{width:42%;max-width:230px;text-align:center;flex:none}"+
".dr{flex:1;min-width:0;overflow-y:auto;text-align:left;-webkit-overflow-scrolling:touch}"+
".ln{display:flex;gap:8px;align-items:center;background:rgba(10,14,32,.95);border:1px solid rgba(0,235,255,.3);border-radius:10px;padding:7px 9px;margin:0 0 6px}"+
".ln .ic{font-size:22px;width:30px;text-align:center}"+
".ln .lb{font-size:9px;letter-spacing:1px;color:#00ebff;font-weight:800}"+
".ln .tt{font-size:14px;font-weight:900}"+
".ln .ds{font-size:12px;color:#d7def5}"+
".rr{display:inline-block;padding:2px 10px;border-radius:8px;font-weight:900;font-size:12px;color:#05070f;margin-top:4px}"+
".kb{font-size:20px;letter-spacing:2px;text-transform:uppercase}"+
"@media (max-width:560px){.dt{flex-direction:column;overflow-y:auto}.dl{width:100%;max-width:none}.dr{overflow:visible}}";
function spr(i,sz){var c=i%6,r=Math.floor(i/6);return "width:"+sz+"px;height:"+sz+"px;background:url("+SHEET+") -"+(c*sz)+"px -"+(r*sz)+"px / "+(6*sz)+"px "+(6*sz)+"px no-repeat;";}
function refreshActive(){A.skinActif=(A.equipped&&A.skins.indexOf(A.equipped)>=0)?A.equipped:"";}
A.estAdmin=function(){try{var u=A.auth.currentUser;return !!(u&&u.email==="flexplayg647@gmail.com");}catch(e){return false;}};
MSG2.interdit="R&eacute;serv&eacute; &agrave; l'administrateur.";
function possede(id){return id===""||A.skins.indexOf(id)>=0;}
A.equip=function(id){A.equipped=id;try{localStorage.setItem("flex_skin",id);}catch(e){}refreshActive();};
function tokenThen(cb){try{A.auth.currentUser.getIdToken().then(cb).catch(function(){cb(null);});}catch(e){cb(null);}}
function api(path,body,cb){
  fetch(WORKER+path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}).then(function(r){return r.json();}).then(cb).catch(function(){cb({ok:false,error:"reseau"});});
}
A.loadSkins=function(cb){
  tokenThen(function(t){
    if(!t){if(cb){cb();}return;}
    api("/me",{idToken:t},function(r){
      if(r&&r.ok){A.skins=r.skins||[];}
      refreshActive();
      if(cb){cb();}
    });
  });
};
var gridOpen=false;
function skinDe(i){return i===30?{id:"",n:"CLASSIQUE",r:"C",s:"H",l:[]}:SKD[i];}
function dlgSkins(){
  gridOpen=true;
  ouvrir(function(d){
    var h="",ordre=[30],i;
    for(i=0;i<30;i++){ordre.push(i);}
    ordre.forEach(function(i){
      var s=skinDe(i),rn=RN[s.r],own=possede(s.id),eq=(A.skinActif===s.id);
      var badge=eq?"<span style='color:#ff00b4'>&Eacute;QUIP&Eacute;</span>":own?"<span style='color:#00ff80'>POSS&Eacute;D&Eacute;</span>":"<span style='color:#8a94c8'>&#128274; VERROUILL&Eacute;</span>";
      h+="<div class='tl' data-i='"+i+"' style='border-color:"+rn[3]+"'><div class='sp' style='"+spr(i,96)+"'></div><div class='tn'>"+esc(s.n)+"</div><div class='tb'>"+badge+"</div></div>";
    });
    d.getElementById("box").innerHTML="<div class='pn col wide'><div class='hd'><div class='t'>PERSONNAGES</div><button id='x' class='bs' style='flex:none;padding:8px 14px'>FERMER</button></div><div class='gr'>"+h+"</div></div>";
    d.getElementById("x").onclick=function(){gridOpen=false;fermer();};
    var tl=d.querySelectorAll(".tl"),k;
    for(k=0;k<tl.length;k++){(function(el){el.onclick=function(){dlgDetail(parseInt(el.getAttribute("data-i"),10));};})(tl[k]);}
  });
}
function dlgDetail(i){
  gridOpen=false;
  var s=skinDe(i);
  ouvrir(function(d){
    var rn=RN[s.r],own=possede(s.id),eq=(A.skinActif===s.id),lines="",k;
    for(k=0;k<s.l.length;k++){
      var L=s.l[k];
      lines+="<div class='ln'><div class='ic'>"+(ICO[L[1]]||"")+"</div><div><div class='lb'>"+LBL[L[0]]+"</div><div class='tt' style='color:"+LCOL[L[0]]+"'>"+esc(L[2])+"</div><div class='ds'>"+esc(L[3])+"</div></div></div>";
    }
    if(!s.l.length){lines="<div class='ln'><div class='ic'>&#127894;</div><div><div class='lb'>PERSONNAGE DE BASE</div><div class='ds'>Le soldat classique, gratuit pour tous.</div></div></div>";}
    var stars="",q;
    for(q=0;q<4;q++){stars+=(q<rn[2]?"&#9733;":"&#9734;");}
    var btn="<button id='bk' class='bs'>RETOUR</button>";
    if(own){btn+=eq?"<button class='bp' disabled>&Eacute;QUIP&Eacute;</button>":"<button id='eq' class='bp'>&Eacute;QUIPER</button>";}
    else{btn+="<button id='ob' class='bp'>OBTENIR</button><button id='ck' class='bs'>J'AI UNE CL&Eacute;</button>";}
    if(!own&&A.estAdmin()){btn+="<button id='ad' class='bs' style='border-color:#78ffaa;color:#78ffaa'>ADMIN : D&Eacute;BLOQUER</button>";}
    d.getElementById("box").innerHTML="<div class='pn col wide' style='border-color:"+rn[3]+"'><div class='hd'><div class='t'>"+esc(s.n.toUpperCase())+"</div><div class='rr' style='background:"+rn[3]+"'>"+rn[0]+" &middot; RANG "+rn[1]+" "+stars+"</div></div>"+
      "<div class='dt'><div class='dl'><div class='sp' style='"+spr(i,160)+"'></div></div><div class='dr' id='dr'>"+lines+"</div></div><div class='e' id='e'></div><div class='b'>"+btn+"</div></div>";
    d.getElementById("bk").onclick=dlgSkins;
    var eqb=d.getElementById("eq");
    if(eqb){eqb.onclick=function(){A.equip(s.id);dlgDetail(i);};}
    var ad=d.getElementById("ad");
    if(ad){ad.onclick=function(){
      ad.disabled=true;
      tokenThen(function(t){
        api("/grant",{idToken:t,skin:s.id},function(r){
          if(r&&r.ok){A.skins=r.skins||A.skins;A.equip(s.id);dlgDetail(i);}
          else{ad.disabled=false;d.getElementById("e").innerHTML=MSG2[(r&&r.error)||"serveur"]||MSG2.serveur;}
        });
      });
    };}
    var ob=d.getElementById("ob");
    if(ob){ob.onclick=function(){window.open(BUY,"_blank");};}
    var ck=d.getElementById("ck");
    if(ck){ck.onclick=function(){
      if(!A.uid){d.getElementById("e").innerHTML="Connecte-toi d'abord avec Google pour utiliser une cl&eacute;.";return;}
      panneauCle(d,i,s);
    };}
  });
}
function panneauCle(d,i,s){
  d.getElementById("dr").innerHTML="<div class='h'>Colle la cl&eacute; re&ccedil;ue par e-mail apr&egrave;s ton achat. Elle d&eacute;bloquera : <b>"+esc(s.n)+"</b>.</div><input id='kc' class='kb' maxlength='64' autocomplete='off' autocapitalize='characters' autocorrect='off' spellcheck='false' enterkeyhint='done' placeholder='"+(TACT?"TOUCHE ICI POUR COLLER":"XXXX-XXXX-XXXX-XXXX")+"'"+(TACT?" readonly":"")+"><div class='r'>Une cl&eacute; = un personnage, une seule utilisation.</div>";
  d.getElementById("box").className="kbd";
  var pn=d.querySelector(".pn");if(pn){pn.className="pn col wide kbp";}
  var b=d.querySelector(".b");
  b.innerHTML="<button id='bk2' class='bs'>ANNULER</button><button id='cl' class='bs'>COLLER</button><button id='vl' class='bp'>VALIDER</button>";
  var e=d.getElementById("e"),vl=d.getElementById("vl"),inp=d.getElementById("kc");
  d.getElementById("bk2").onclick=function(){dlgDetail(i);};
  vl.onclick=function(){
    e.className="e";e.innerHTML="V&eacute;rification...";vl.disabled=true;
    tokenThen(function(t){
      if(!t){e.innerHTML=MSG2.auth;vl.disabled=false;return;}
      api("/redeem",{idToken:t,key:inp.value,skin:s.id},function(r){
        if(r&&r.ok){
          A.skins=r.skins||A.skins;A.equip(s.id);
          e.className="e ok";e.innerHTML="D&eacute;bloqu&eacute; ! Ton personnage est &eacute;quip&eacute;.";
          setTimeout(function(){dlgDetail(i);},1400);
        }else{
          if(r&&r.error==="deja_possede"&&r.skins){A.skins=r.skins;refreshActive();}
          e.className="e";e.innerHTML=MSG2[(r&&r.error)||"serveur"]||MSG2.serveur;vl.disabled=false;
        }
      });
    });
  };
  inp.onkeydown=function(ev){if(ev.key==="Enter"){vl.onclick();}};
  d.getElementById("cl").onclick=function(){
    try{
      d.defaultView.navigator.clipboard.readText().then(function(t){inp.value=String(t||"").trim().slice(0,64);}).catch(function(){e.className="e";e.innerHTML="Colle la cl&eacute; avec un appui long dans le champ.";});
    }catch(x){e.className="e";e.innerHTML="Colle la cl&eacute; avec un appui long dans le champ.";}
  };
  if(TACT){
    inp.onclick=function(){saisir(inp,"Colle ou \u00e9cris ta cl\u00e9 de licence :");};
  }else{
    sortirPleinEcran(function(){try{inp.focus();}catch(x){}});
  }
}
A.showSkins=function(){
  dlgSkins();
  if(A.uid){A.loadSkins(function(){if(gridOpen&&document.getElementById("flexui")){dlgSkins();}});}
};
A.log=function(type,lvl){
  var e={type:String(type),lvl:lvl|0};
  if(A.db){send(e);}else{if(Q.length<50){Q.push(e);}}
};
A.flush=function(){while(Q.length){send(Q.shift());}};
var T0=setInterval(function(){
  if(A.db){
    clearInterval(T0);
    try{
      if(!sessionStorage.getItem("flex_visit")){sessionStorage.setItem("flex_visit","1");A.log("visit",0);}
    }catch(e){A.log("visit",0);}
    A.flush();
  }
},500);
load(0);
})();
"""


_JS_HEURE = r"""
(function(){
if(window.flexHeure){return;}
var H=window.flexHeure={ok:false,off:0};
try{
  fetch(location.href.split("#")[0],{method:"HEAD",cache:"no-store"}).then(function(r){
    var d=r.headers.get("Date");
    if(d){var t=Date.parse(d);if(!isNaN(t)){H.off=t-Date.now();H.ok=true;}}
  }).catch(function(){});
}catch(e){}
})();
"""
_HEURE = {"off": 0.0, "maj": -100.0}


def heure_serveur_s():
    """Heure UTC en secondes. Sur le web, corrigée avec l'heure du serveur (le joueur ne peut pas la tricher en changeant l'heure du téléphone)."""
    now = _time.time()
    if IS_WEB:
        if now - _HEURE["maj"] > 5.0:
            _HEURE["maj"] = now
            try:
                h = _pfs.window.flexHeure
                if bool(h.ok):
                    _HEURE["off"] = float(h.off) / 1000.0
            except Exception:
                pass
        return now + _HEURE["off"]
    return now



# ==================== MULTIJOUEUR EN LIGNE (Firebase Realtime Database) — version web uniquement ====================
_JS_MULTI = r"""
(function(){
if(window.flexMP){return;}
var DBURL="https://flex-cyberpunk-c49e8-default-rtdb.firebaseio.com";
var V="10.14.1";
var LOBBY=25000, MAXMS=960000, RESULT=20000, ROOM="main";
var M=window.flexMP={status:"idle",err:"",room:"",seed:0,level:0,json:"[]",ver:0,n:0,rtt:0,startAt:0,endAt:0,round:0,roundVer:0,offset:0,en:"",enHas:false,enVer:0,rest:0};
var db=null,myRef=null,listRef=null,connRef=null,roundRef=null,hitsRef=null,uid="",pseudo="",skin="",entered=false,
    lastSend=0,pending=false,pendT=0,lastX=-1e9,lastY=-1e9,lastA=-1e9,lastF=-1,lastFA=0,lastH=-1,hitsIn=[];
function charger(cb){
  if(window.firebase&&firebase.database){cb();return;}
  var s=document.createElement("script");
  s.src="https://www.gstatic.com/firebasejs/"+V+"/firebase-database-compat.js";
  s.onload=cb;
  s.onerror=function(){M.status="err";M.err="script";};
  document.head.appendChild(s);
}
function nowSrv(){return Date.now()+M.offset;}
function nouvelle(id){return {id:id,seed:Math.floor(Math.random()*2000000000),startAt:nowSrv()+LOBBY,endAt:0};}
function appliquer(v){v=v||{};M.round=v.id|0;M.seed=v.seed|0;M.startAt=+v.startAt||0;M.endAt=+v.endAt||0;M.roundVer++;}
M.join=function(level){
  if(M.status==="joining"||M.status==="ok"){return;}
  var A=window.flexAuth;
  if(!A||!A.uid||!A.pseudo){M.status="err";M.err="login";return;}
  uid=A.uid;pseudo=A.pseudo;skin=String(A.skinActif||"").slice(0,40);
  M.status="joining";M.err="";M.json="[]";M.n=0;M.level=level|0;
  charger(function(){
    try{
      db=firebase.app().database(DBURL);
      db.ref(".info/serverTimeOffset").once("value",function(o){
        M.offset=+o.val()||0;
        roundRef=db.ref("rooms/"+ROOM+"/round");
        roundRef.transaction(function(cur){
          var now=nowSrv();
          if(cur===null||typeof cur!=="object"||!cur.id){return nouvelle(1);}
          if((cur.endAt&&now>=cur.endAt)||now>=cur.startAt+MAXMS){return nouvelle((cur.id|0)+1);}
          return cur;
        },function(err,committed,snap){
          if(err){M.status="err";M.err="reseau";return;}
          appliquer(snap.val());
          roundRef.on("value",function(s){appliquer(s.val());});
          M.room=ROOM;M.status="ok";
        },false);
      },function(){M.status="err";M.err="reseau";});
    }catch(e){M.status="err";M.err=String(e).slice(0,60);}
  });
};
M.enter=function(){
  if(M.status!=="ok"||entered){return;}
  entered=true;
  var rid=M.round;
  myRef=db.ref("rooms/"+ROOM+"/players/"+uid);
  myRef.set({p:pseudo,s:skin,x:0,y:0,a:0,f:0,fa:0,h:100,r:rid});
  myRef.onDisconnect().remove();
  db.ref("rooms/"+ROOM+"/hits/"+uid).remove();
  hitsRef=db.ref("rooms/"+ROOM+"/hits/"+uid);
  hitsRef.on("child_added",function(s){var v=s.val()||{};if((v.r|0)===M.round){hitsIn.push({f:String(v.f||""),d:+v.d||0});}try{s.ref.remove();}catch(e){}});
  listRef=db.ref("rooms/"+ROOM+"/players");
  listRef.on("value",function(s){
    var a=[];
    s.forEach(function(c){var v=c.val()||{};a.push({u:c.key,p:String(v.p||"?").slice(0,16),s:String(v.s||"").slice(0,40),x:+v.x||0,y:+v.y||0,a:+v.a||0,f:v.f|0,fa:+v.fa||0,h:(v.h===undefined?100:+v.h),r:v.r|0});});
    M.json=JSON.stringify(a);M.n=a.length;M.ver++;
  });
  connRef=db.ref(".info/connected");
  connRef.on("value",function(s){if(s.val()===true&&entered&&myRef){myRef.onDisconnect().remove();myRef.update({p:pseudo,s:skin,r:rid});}});
};
M.exit=function(){
  entered=false;
  try{if(listRef){listRef.off();listRef=null;}}catch(e){}
  try{if(hitsRef){hitsRef.off();hitsRef=null;}}catch(e){}
  try{if(connRef){connRef.off();connRef=null;}}catch(e){}
  try{if(myRef){myRef.onDisconnect().cancel();myRef.remove();myRef=null;}}catch(e){}
  hitsIn=[];M.json="[]";M.n=0;M.ver++;M.rtt=0;pending=false;lastX=-1e9;lastY=-1e9;lastA=-1e9;lastF=-1;lastH=-1;
};
M.leave=function(){
  M.exit();
  try{if(roundRef){roundRef.off();roundRef=null;}}catch(e){}
  M.status="idle";M.err="";M.room="";M.round=0;M.startAt=0;M.endAt=0;
};
M.endRound=function(id){
  if(M.status!=="ok"||!roundRef){return;}
  roundRef.transaction(function(cur){
    if(cur&&(cur.id|0)===(id|0)&&!cur.endAt){cur.endAt=nowSrv()+RESULT;}
    return cur;
  });
};
M.nextRound=function(id){
  if(M.status!=="ok"||!roundRef){return;}
  roundRef.transaction(function(cur){
    var now=nowSrv();
    if(cur&&(cur.id|0)===(id|0)&&((cur.endAt&&now>=cur.endAt)||now>=cur.startAt+MAXMS)){return nouvelle((cur.id|0)+1);}
    return cur;
  });
};
M.hit=function(u,d){
  if(M.status!=="ok"||!db||!entered){return;}
  try{db.ref("rooms/"+ROOM+"/hits/"+u).push({f:uid,d:d|0,r:M.round});}catch(e){}
};
M.takeHits=function(){var a=hitsIn;hitsIn=[];return JSON.stringify(a);};
M.send=function(x,y,a,f,fa,h){
  if(M.status!=="ok"||!myRef||!entered){return;}
  var t=Date.now();
  if(pending&&t-pendT<3000){return;}
  if(t-lastSend<80){return;}
  x=Math.round(x);y=Math.round(y);a=Math.round(a*10)/10;f=f|0;fa=Math.round(fa*10)/10;h=(h===undefined)?100:(h|0);
  if(x===lastX&&y===lastY&&a===lastA&&f===lastF&&h===lastH){return;}
  lastSend=t;lastX=x;lastY=y;lastA=a;lastF=f;lastFA=fa;lastH=h;pending=true;pendT=t;
  try{
    myRef.update({x:x,y:y,a:a,f:f,fa:fa,h:h}).then(function(){pending=false;M.rtt=Date.now()-t;}).catch(function(){pending=false;});
  }catch(e){pending=false;}
};
M.setHost=function(){};
M.takeKills=function(){return "[]";};
M.kill=function(){};
M.sendDrones=function(){};
})();
"""

MP_NIVEAU = 6          # mission utilisée pour la salle en ligne (provisoire, avant la grande salle dédiée)
MP_MAX = 6             # joueurs maximum par salle
MP = {"actif": False, "etat": "idle", "seed": 0, "niveau": MP_NIVEAU, "salle": "", "autres": [], "ver": -1,
      "n": 1, "msg": [], "t0": 0, "lisse": {}, "pseudo": "", "uid": "", "sprites": {}, "t_dessin": 0, "rtt": 0, "tick": 0,
      "hote": False, "en_cible": {}, "en_lisse": {}, "en_ver": -1, "en_recu": False, "rest": 0, "next_id": 1,
      "tues": {}, "nb_base": 0, "f": 0, "fa": 0.0, "f_vu": {}, "balles_d": [], "t_en": 0, "t_maj": 0, "dbg": "", "n_prev": 0}
_MP_COULEURS = [(0, 255, 255), (255, 60, 200), (255, 230, 60), (120, 255, 120), (255, 140, 40), (170, 120, 255)]
_MP_ERREURS = {
    "login": ["Connecte-toi avec Google et choisis", "ton pseudo (icône profil) pour jouer en ligne."],
    "pleines": ["Toutes les salles sont pleines.", "Réessaie dans un instant."],
    "reseau": ["Réseau indisponible.", "Vérifie ta connexion et réessaie."],
    "script": ["Impossible de charger le multijoueur.", "Vérifie ta connexion et réessaie."],
}


def _mp_js():
    if not IS_WEB:
        return None
    try:
        return _pfs.window.flexMP
    except Exception:
        return None


def mp_chercher_salle():
    """Clic sur MULTIJOUEUR : lance la recherche automatique d'une salle (aucun code à saisir)."""
    MP.update(actif=False, etat="recherche", msg=[], autres=[], ver=-1, n=1, lisse={}, t0=pygame.time.get_ticks())
    j = _mp_js()
    fa = _fa()
    if j is None or fa is None:
        MP.update(etat="erreur", msg=["Le multijoueur est disponible", "dans la version en ligne du jeu."])
        return
    try:
        MP["pseudo"], MP["uid"] = str(fa.pseudo or ""), str(fa.uid or "")
        j.join(int(MP_NIVEAU))
    except Exception:
        MP.update(etat="erreur", msg=_MP_ERREURS["reseau"])


def mp_quitter():
    j = _mp_js()
    try:
        if j is not None:
            j.leave()
    except Exception:
        pass
    MP.update(actif=False, etat="idle", autres=[], ver=-1, n=1, salle="", lisse={})
    _mp_reset_partie()


def _mp_tick():
    """Appelé à chaque image : suit la recherche de salle, puis échange les positions avec les autres joueurs."""
    if MP["etat"] == "recherche":
        if etat_actuel != ETAT_MULTI or TRANS["actif"]:
            return
        j = _mp_js()
        try:
            st = str(j.status)
        except Exception:
            st = "err"
        if st == "ok":
            try:
                MP["seed"], MP["niveau"], MP["salle"] = int(j.seed), int(j.level), str(j.room)
            except Exception:
                MP["seed"], MP["salle"] = 1, ""
            MP["actif"], MP["etat"] = True, "jeu"
            lancer_transition(("arene",))
        elif st == "err":
            try:
                code = str(j.err)
            except Exception:
                code = "reseau"
            MP.update(etat="erreur", msg=_MP_ERREURS.get(code, _MP_ERREURS["reseau"]))
            try:
                j.leave()
            except Exception:
                pass
        elif pygame.time.get_ticks() - MP["t0"] > 20000:
            MP.update(etat="erreur", msg=_MP_ERREURS["reseau"])
            try:
                j.leave()
            except Exception:
                pass
        return
    if not MP["actif"]:
        return
    if etat_actuel == ETAT_MENU:
        mp_quitter()
        return
    if etat_actuel != ETAT_JEU:
        return
    j = _mp_js()
    if j is None:
        return
    try:
        j.send(float(joueur_x), float(joueur_y), math.atan2(angle_visée_y, angle_visée_x), int(MP["f"]), float(MP["fa"]))
        v = int(j.ver)
        if v != MP["ver"]:
            MP["ver"] = v
            tous = json.loads(str(j.json))
            MP["n"] = len(tous)
            MP["autres"] = [o for o in tous if o.get("u") != MP["uid"]]
            for o in MP["autres"]:                                   # tirs des autres joueurs (affichage)
                u, f = o.get("u"), int(o.get("f", 0))
                vu = MP["f_vu"].get(u)
                MP["f_vu"][u] = f
                if vu is not None and f > vu:
                    ang = float(o.get("fa", 0))
                    for q in range(min(f - vu, 3)):
                        MP["balles_d"].append([float(o.get("x", 0)) - math.cos(ang) * 39 * q, float(o.get("y", 0)) - math.sin(ang) * 39 * q,
                                               math.cos(ang) * 13, math.sin(ang) * 13, 50, _mp_couleur(u)])
                    if len(MP["balles_d"]) > 60:
                        del MP["balles_d"][:20]
            uids = sorted(str(o.get("u")) for o in tous)               # l'hôte = le plus petit identifiant présent
            hote = bool(uids) and uids[0] == MP["uid"]
            if hote and not MP["hote"]:
                _mp_devenir_hote(len(tous))
            elif not hote and MP["hote"]:
                MP["hote"] = False
                j.setHost(False)
            if MP["hote"] and len(tous) > MP["n_prev"] > 0:           # un joueur de plus : on ajoute des drones
                global ennemis_restants_a_spawner
                ennemis_restants_a_spawner += MP["nb_base"] // 2
            MP["n_prev"] = len(tous)
        MP["tick"] += 1
        if MP["tick"] % 30 == 0:
            MP["rtt"] = int(j.rtt)
    except Exception:
        pass
    try:
        _mp_sync_drones(j)
    except Exception as e:
        MP["dbg"] = repr(e)[:70]


def _mp_couleur(u):
    return _MP_COULEURS[sum(ord(c) for c in str(u)) % len(_MP_COULEURS)]


def _mp_client():
    """Vrai si on est en multijoueur sans être l'hôte (l'hôte est le seul à déplacer les drones)."""
    return MP["actif"] and not MP["hote"]


def _mp_id():
    if not MP["actif"]:
        return 0
    MP["next_id"] += 1
    return MP["next_id"]


def _mp_cible(x, y):
    """Position du joueur le plus proche d'un drone : le joueur local ou un autre joueur de la salle."""
    cx, cy = joueur_x, joueur_y
    if MP["actif"]:
        meilleur = (cx - x) ** 2 + (cy - y) ** 2
        for o in MP["autres"]:
            ax, ay = float(o.get("x", 0)), float(o.get("y", 0))
            if ax == 0 and ay == 0:
                continue                                  # joueur pas encore placé
            d = (ax - x) ** 2 + (ay - y) ** 2
            if d < meilleur:
                meilleur, cx, cy = d, ax, ay
    return cx, cy


def _mp_tuer(ex):
    """Un drone vient d'être détruit chez ce joueur : l'hôte est prévenu et le retire pour tout le monde."""
    if not MP["actif"] or len(ex) < 4 or MP["hote"]:
        return
    MP["tues"][ex[3]] = pygame.time.get_ticks()
    j = _mp_js()
    try:
        if j is not None:
            j.kill(int(ex[3]))
    except Exception:
        pass


def _mp_tir_local(b):
    """Un tir vient de partir : le compteur de tirs et sa direction sont envoyés aux autres joueurs."""
    MP["f"] += 1
    MP["fa"] = math.atan2(b[3], b[2])


def _mp_reset_partie():
    j = _mp_js()
    try:
        if j is not None:
            j.setHost(False)
    except Exception:
        pass
    MP.update(hote=False, en_cible={}, en_lisse={}, en_ver=-1, en_recu=False, rest=0, tues={}, f=0, fa=0.0,
              f_vu={}, balles_d=[], t_en=0, t_maj=0, dbg="", n_prev=0)


def _mp_devenir_hote(n_joueurs):
    """Ce joueur devient l'hôte : il fait vivre les drones pour toute la salle."""
    global ennemis_restants_a_spawner, minuteur_spawn
    j = _mp_js()
    if j is not None:
        j.setHost(True)
    MP["hote"] = True
    if MP["en_recu"]:                                     # l'ancien hôte est parti : on reprend ses drones
        liste_ennemis[:] = [[x, y, vitesse_ennemis_niveau, i] for i, (x, y) in MP["en_cible"].items()]
        ennemis_restants_a_spawner = MP["rest"]
        MP["next_id"] = max(list(MP["en_cible"]) + [MP["next_id"]]) + 1
    else:
        liste_ennemis[:] = []
        ennemis_restants_a_spawner = int(MP["nb_base"] * max(1, n_joueurs))
    minuteur_spawn = 60


def _mp_sync_drones(j):
    """Hôte : envoie l'état des drones à tous et retire ceux détruits par les autres. Autres joueurs : reçoivent et affichent."""
    global ennemis_restants_a_spawner
    maintenant = pygame.time.get_ticks()
    if MP["hote"]:
        ids = json.loads(str(j.takeKills()))
        if ids:
            ids = set(int(i) for i in ids)
            for ex in liste_ennemis[:]:
                if len(ex) > 3 and ex[3] in ids:
                    liste_ennemis.remove(ex)
                    creer_explosion(ex[0], ex[1], ROUGE_ALERTE, 24, 7.0, 3.0)
        if maintenant - MP["t_en"] >= 160:                 # environ 6 envois par seconde
            MP["t_en"] = maintenant
            txt = ";".join(f"{e[3]},{int(e[0])},{int(e[1])}" for e in liste_ennemis[:80] if len(e) > 3)
            j.sendDrones(txt, int(ennemis_restants_a_spawner))
        return
    v = int(j.enVer)
    if v != MP["en_ver"]:
        MP["en_ver"] = v
        cible = {}
        for part in str(j.en).split(";"):
            if part:
                try:
                    i, x, y = part.split(",")
                    cible[int(i)] = (float(x), float(y))
                except Exception:
                    pass
        MP["en_cible"] = cible
        MP["en_recu"] = bool(j.enHas)
        MP["rest"] = int(j.rest)
    ennemis_restants_a_spawner = MP["rest"]
    dt = min(0.25, max(0.0, (maintenant - MP["t_maj"]) / 1000.0)) if MP["t_maj"] else 0.016
    MP["t_maj"] = maintenant
    k = 1.0 - math.exp(-dt * 12.0)
    cible, lisse, tues = MP["en_cible"], MP["en_lisse"], MP["tues"]
    for i in list(lisse):
        if i not in cible:
            if i not in tues:
                creer_explosion(lisse[i][0], lisse[i][1], ROUGE_ALERTE, 24, 7.0, 3.0)
            del lisse[i]
    sortie = []
    for i, (tx, ty) in cible.items():
        if i in tues:
            continue
        pos = lisse.get(i)
        if pos is None or abs(tx - pos[0]) + abs(ty - pos[1]) > 400:
            pos = lisse[i] = [tx, ty]
        pos[0] += (tx - pos[0]) * k
        pos[1] += (ty - pos[1]) * k
        sortie.append([pos[0], pos[1], vitesse_ennemis_niveau, i])
    liste_ennemis[:] = sortie
    for i in [i for i, t in tues.items() if maintenant - t > 6000]:
        del tues[i]


def _mp_dessiner_balles(ox, oy):
    """Tirs des autres joueurs (affichage seulement : ce sont leurs téléphones qui comptent les touches)."""
    restantes = []
    for b in MP["balles_d"]:
        b[0] += b[2]
        b[1] += b[3]
        b[4] -= 1
        cx, cy = int(b[0] // TAILLE_CASE), int(b[1] // TAILLE_CASE)
        if b[4] <= 0 or not (0 <= cx < len(CARTE[0]) and 0 <= cy < len(CARTE)) or CARTE[cy][cx] == 1:
            continue
        restantes.append(b)
        sx, sy = int(b[0] + ox), int(b[1] + oy)
        DRAW.line(ecran, b[5], (sx, sy), (int(sx - b[2] * 1.6), int(sy - b[3] * 1.6)), 4)
    MP["balles_d"] = restantes


def _mp_sprites(sid):
    """Sprites (droite, gauche) du skin d'un joueur, gardés en mémoire."""
    global _planche_skins
    c = MP["sprites"].get(sid)
    if c is not None:
        return c
    try:
        if sid in SKIN_IDS:
            if _planche_skins is None:
                _planche_skins = pygame.image.load(_asset("skins_sheet.png")).convert_alpha()
            i = SKIN_IDS.index(sid)
            morceau = _planche_skins.subsurface(pygame.Rect((i % 6) * 160, (i // 6) * 160, 160, 160)).copy()
            img = pygame.transform.smoothscale(morceau, (TAILLE_PERSO, TAILLE_PERSO))
        else:
            img = _img_joueur_defaut
        c = (img, pygame.transform.flip(img, True, False))
    except Exception:
        c = (img_joueur_droite, img_joueur_gauche)
    MP["sprites"][sid] = c
    return c


def _mp_dessiner_autres(ox, oy):
    """Dessine les autres joueurs (leur personnage, leur pseudo au-dessus) et le pseudo du joueur local."""
    lisse = MP["lisse"]
    maintenant = pygame.time.get_ticks()
    dt = min(0.25, max(0.0, (maintenant - MP["t_dessin"]) / 1000.0)) if MP["t_dessin"] else 0.016
    MP["t_dessin"] = maintenant
    k = 1.0 - math.exp(-dt * 10.0)                  # lissage indépendant du nombre d'images par seconde
    _mp_dessiner_balles(ox, oy)
    vus = set()
    for o in MP["autres"]:
        u = str(o.get("u", ""))
        vus.add(u)
        tx, ty = float(o.get("x", 0)), float(o.get("y", 0))
        p = lisse.get(u)
        if p is None or abs(tx - p[0]) + abs(ty - p[1]) > 500:
            p = lisse[u] = [tx, ty]                 # trop loin (réapparition) : on le replace d'un coup
        p[0] += (tx - p[0]) * k
        p[1] += (ty - p[1]) * k
        sx, sy = int(p[0] + ox), int(p[1] + oy)
        if sx < -80 or sx > LARGEUR + 80 or sy < -90 or sy > HAUTEUR + 80:
            continue
        col = _MP_COULEURS[sum(ord(c) for c in u) % len(_MP_COULEURS)]
        a = float(o.get("a", 0))
        dessiner_halo(sx, sy, 46, col, 0.45)
        if MODE_GRAPHIQUE == "REALISTE":
            spr = _mp_sprites(str(o.get("s", "")))
            img = spr[0] if math.cos(a) >= 0 else spr[1]
            ecran.blit(img, (sx - img.get_width() // 2, sy - img.get_height() // 2))
        else:
            DRAW.rect(ecran, col, (sx - TAILLE_PERSO // 2, sy - TAILLE_PERSO // 2, TAILLE_PERSO, TAILLE_PERSO))
        DRAW.circle(ecran, col, (int(sx + 34 * math.cos(a)), int(sy + 34 * math.sin(a))), 4)     # petit point : direction de visée
        tag_j = rendu_texte(police_petite, str(o.get("p", "?")), True, col)
        ecran.blit(tag_j, (sx - tag_j.get_width() // 2, sy - 52))
    for u in list(lisse):
        if u not in vus:
            del lisse[u]
    if MP["pseudo"]:
        tag_moi = rendu_texte(police_petite, MP["pseudo"], True, VERT_FLUO)
        ecran.blit(tag_moi, (int(joueur_x + ox) - tag_moi.get_width() // 2, int(joueur_y + oy) - 52))
    rtt = MP["rtt"]
    txt = f"EN LIGNE  •  {max(1, MP['n'])}/{MP_MAX} joueurs"
    if rtt > 0:
        txt += f"  •  {rtt} ms"
    if MP["hote"]:
        txt += "  •  HÔTE"
    col_info = VERT_FLUO if rtt < 200 else (JAUNE_CYBER if rtt < 500 else ROUGE_ALERTE)
    info = rendu_texte(police_petite, txt, True, col_info)
    ecran.blit(info, (LARGEUR // 2 - info.get_width() // 2, HAUTEUR - 36))
    if MP["dbg"]:
        err = rendu_texte(police_petite, "ERR " + MP["dbg"], True, ROUGE_ALERTE)
        ecran.blit(err, (LARGEUR // 2 - err.get_width() // 2, HAUTEUR - 66))


def dessiner_multi_attente():
    """Écran de recherche de salle (ou message d'erreur)."""
    dessiner_fond_menu()
    dessiner_panneau_neon((LARGEUR - 500) // 2, 500, VERT_FLUO, False, 150)
    dessiner_titre_glitch("MULTIJOUEUR", police_titre, LARGEUR // 2, HAUTEUR // 4)
    if MP["etat"] == "erreur":
        y = HAUTEUR // 2 - 20
        for ligne in MP["msg"]:
            t = rendu_texte(police_petite, ligne, True, ROUGE_ALERTE)
            ecran.blit(t, (LARGEUR // 2 - t.get_width() // 2, y))
            y += 34
    else:
        points = "." * (1 + (pygame.time.get_ticks() // 400) % 3)
        t = rendu_texte(police_jeu, "RECHERCHE D'UNE SALLE" + points, True, BLANC_NEON)
        ecran.blit(t, (LARGEUR // 2 - t.get_width() // 2, HAUTEUR // 2 - 30))
        t2 = rendu_texte(police_petite, "Tu rejoins automatiquement les autres joueurs", True, VERT_FLUO)
        ecran.blit(t2, (LARGEUR // 2 - t2.get_width() // 2, HAUTEUR // 2 + 20))
    bouton_neon(rect_retour_niveaux, ROUGE_ALERTE, "< RETOUR", police_bouton)
    dessiner_marque(HAUTEUR - 84)


# ==================== PARC : très grande carte en vue du dessus, créée par zones (test solo) ====================
# Le monde est découpé en zones (« chunks ») de 640 px. Chaque zone est fabriquée à partir du numéro de la partie
# et de ses coordonnées : deux téléphones avec le même numéro obtiennent exactement le même parc (arbres, bâtiments...).
# Seules les zones proches du joueur existent en mémoire ; les autres sont déchargées.
# Le monde est divisé en grandes régions de 4x4 zones qui ont chacune un « biome » (prairie, forêt, ville, lac, rocailles).
PARC_CH = 640                      # taille d'une zone
PARC_NC = 48                       # nombre de zones par côté
PARC_MONDE = PARC_CH * PARC_NC     # 30 720 px de côté (environ 10 fois la surface de la première version)
PARC_PAS, PARC_DEC, PARC_NAXES = 3200, 1600, 10     # allées tous les 3 200 px (10 axes dans chaque sens)
PARC_LARG_ALLEE = 150
PARC_R_PLACE = 330                 # rayon des places (fontaine), placées à certains croisements
PARC_REGION = 4                    # une région = 4x4 zones
PARC = {"actif": False, "seed": 1, "x": 0.0, "y": 0.0, "face": 1, "donnees": {}, "surf": {}, "mini": None,
        "ms_gen": 0.0, "vus": set(), "wip": {}}
_PC_HERBE, _PC_HERBE_CL, _PC_HERBE_FO = (16, 22, 40), (84, 156, 84), (62, 126, 66)     # _PC_HERBE : couleur d'une zone pas encore prête
_PC_SABLE, _PC_SABLE_BORD = (208, 192, 152), (172, 154, 114)
_PC_EAU, _PC_EAU_CL = (52, 122, 198), (110, 170, 226)
_PC_TOITS = [((170, 84, 62), (130, 60, 44)), ((96, 108, 128), (66, 76, 94)), ((196, 168, 108), (150, 124, 74)),
             ((120, 140, 120), (84, 102, 86)), ((176, 120, 150), (132, 84, 108))]
_PC_FLEURS = [(250, 250, 250), (250, 220, 70), (240, 120, 170), (170, 130, 240), (250, 150, 70)]
_PC_BIOMES = ["Parc", "Bois", "Centre néon", "Canal", "Zone industrielle"]
_PC_BIOME_COUL = [(30, 120, 108), (20, 84, 76), (130, 70, 210), (30, 100, 220), (220, 130, 40)]
# paramètres par biome : essais d'arbres, proba de bâtiment, proba d'étang, essais de rochers, de buissons, de fleurs
_PC_BIOME_P = {0: (30, 0.28, 0.05, 4, 24, 22), 1: (70, 0.05, 0.04, 5, 36, 10), 2: (7, 0.95, 0.0, 1, 10, 8),
               3: (24, 0.08, 0.55, 4, 20, 14), 4: (16, 0.05, 0.05, 26, 12, 6)}


def _parc_biome(cx, cy):
    t = random.Random(PARC["seed"] * 131 + (cx // PARC_REGION) * 7919 + (cy // PARC_REGION) * 104729).random()
    return 0 if t < 0.34 else 1 if t < 0.58 else 2 if t < 0.74 else 3 if t < 0.86 else 4


def _parc_dist_axe(v):
    k = min(PARC_NAXES - 1, max(0, round((v - PARC_DEC) / PARC_PAS)))
    return abs(v - (PARC_DEC + k * PARC_PAS))


def _parc_place_proche(x, y):
    """Centre de la place la plus proche (une place sur 3 croisements dans chaque sens), ou None."""
    i, j = round((x - PARC_DEC) / PARC_PAS), round((y - PARC_DEC) / PARC_PAS)
    if 0 <= i < PARC_NAXES and 0 <= j < PARC_NAXES and i % 3 == 1 and j % 3 == 1:
        return PARC_DEC + i * PARC_PAS, PARC_DEC + j * PARC_PAS
    return None


def _parc_sur_allee(x, y, marge=0):
    """Vrai si le point est sur une allée ou sur une place (avec une marge)."""
    m = PARC_LARG_ALLEE // 2 + marge
    if _parc_dist_axe(x) < m or _parc_dist_axe(y) < m:
        return True
    pl = _parc_place_proche(x, y)
    return pl is not None and (x - pl[0]) ** 2 + (y - pl[1]) ** 2 < (PARC_R_PLACE + marge) ** 2


def _parc_bande(v0, v1, m):
    k0 = int((v0 - PARC_DEC) // PARC_PAS)
    for k in (k0, k0 + 1):
        if 0 <= k < PARC_NAXES:
            a = PARC_DEC + k * PARC_PAS
            if v0 < a + m and v1 > a - m:
                return True
    return False


def _parc_rect_sur_allee(x, y, w, h, marge):
    m = PARC_LARG_ALLEE // 2 + marge
    if _parc_bande(x, x + w, m) or _parc_bande(y, y + h, m):
        return True
    pl = _parc_place_proche(x + w / 2, y + h / 2)
    if pl is None:
        return False
    nx, ny = min(max(pl[0], x), x + w), min(max(pl[1], y), y + h)
    return (nx - pl[0]) ** 2 + (ny - pl[1]) ** 2 < (PARC_R_PLACE + marge) ** 2


def _parc_gen(cx, cy):
    """Contenu d'une zone : objets et obstacles (calcul léger, identique sur tous les téléphones)."""
    d = PARC["donnees"].get((cx, cy))
    if d is not None:
        return d
    rng = random.Random(PARC["seed"] * 73856093 ^ cx * 19349663 ^ cy * 83492791)
    x0, y0 = cx * PARC_CH, cy * PARC_CH
    M = 30                                                   # aucun objet ne touche le bord de la zone
    bio = _parc_biome(cx, cy)
    n_arb, p_bat, p_etg, n_roc, n_bus, n_fle = _PC_BIOME_P[bio]
    d = {"biome": bio, "batiments": [], "etangs": [], "arbres": [], "buissons": [], "rochers": [], "bancs": [], "fleurs": [],
         "taches": [], "fontaine": None, "obs_c": [], "obs_r": []}
    for _ in range(rng.randint(8, 13)):
        d["taches"].append((x0 + rng.randint(0, PARC_CH), y0 + rng.randint(0, PARC_CH), rng.randint(50, 130), rng.randint(40, 100), rng.randint(0, 1)))
    pl = _parc_place_proche(x0 + PARC_CH // 2, y0 + PARC_CH // 2)
    if pl is not None and (pl[0] // PARC_CH, pl[1] // PARC_CH) == (cx, cy):
        d["fontaine"] = (pl[0], pl[1], 80)
        d["obs_c"].append((pl[0], pl[1], 88))
    # bâtiments (vus du dessus : simples toits)
    n_bat = (1 + (1 if rng.random() < 0.5 else 0) + (1 if rng.random() < 0.2 else 0)) if rng.random() < p_bat else 0
    if bio == 2:                                                     # centre-ville : 2 x 2 parcelles séparées par des ruelles de 56 px
        n_bat = 0
        lot = (PARC_CH - 2 * M - 56) // 2
        for li in range(2):
            for lj in range(2):
                if rng.random() > 0.9:
                    continue
                bw_, bh_ = rng.randint(190, lot), rng.randint(180, lot)
                bx_ = x0 + M + li * (lot + 56) + rng.randint(0, lot - bw_)
                by_ = y0 + M + lj * (lot + 56) + rng.randint(0, lot - bh_)
                if _parc_rect_sur_allee(bx_, by_, bw_, bh_, 34):
                    continue
                d["batiments"].append((bx_, by_, bw_, bh_, rng.randint(0, len(_PC_TOITS) - 1)))
                d["obs_r"].append((bx_, by_, bw_, bh_))
    for _ in range(n_bat):
        for _essai in range(20):
            w, h = (rng.randint(140, 260), rng.randint(120, 220)) if bio == 2 else (rng.randint(180, 330), rng.randint(150, 270))
            bx, by = x0 + rng.randint(M, PARC_CH - M - w), y0 + rng.randint(M, PARC_CH - M - h)
            if _parc_rect_sur_allee(bx, by, w, h, 34):
                continue
            if any(bx < o[0] + o[2] + 40 and bx + w + 40 > o[0] and by < o[1] + o[3] + 40 and by + h + 40 > o[1] for o in d["batiments"]):
                continue
            d["batiments"].append((bx, by, w, h, rng.randint(0, len(_PC_TOITS) - 1)))
            d["obs_r"].append((bx, by, w, h))
            break
    # étang (grands dans les régions « Lac »)
    if rng.random() < p_etg:
        for _essai in range(6):
            rx, ry = (rng.randint(140, 240), rng.randint(110, 200)) if bio == 3 else (rng.randint(90, 150), rng.randint(70, 120))
            ex, ey = x0 + rng.randint(M + rx + 10, PARC_CH - M - rx - 10), y0 + rng.randint(M + ry + 10, PARC_CH - M - ry - 10)
            if _parc_rect_sur_allee(ex - rx - 10, ey - ry - 10, rx * 2 + 20, ry * 2 + 20, 20):
                continue
            if any(ex - rx < o[0] + o[2] + 30 and ex + rx > o[0] - 30 and ey - ry < o[1] + o[3] + 30 and ey + ry > o[1] - 30 for o in d["batiments"]):
                continue
            d["etangs"].append((ex, ey, rx, ry))
            d["obs_c"].append((ex, ey, int(min(rx, ry) * 0.85)))
            break

    def libre(x, y, r, marge_allee):
        if _parc_sur_allee(x, y, marge_allee):
            return False
        for bx, by, bw, bh, _c in d["batiments"]:
            if bx - r - 14 < x < bx + bw + r + 14 and by - r - 14 < y < by + bh + r + 14:
                return False
        for ex, ey, rx, ry in d["etangs"]:
            if ((x - ex) / (rx + r + 10)) ** 2 + ((y - ey) / (ry + r + 10)) ** 2 < 1.0:
                return False
        return True

    for _ in range(n_arb):                                   # arbres (plus petits, en bac, dans les quartiers urbains)
        r = rng.randint(18, 30) if bio in (2, 3, 4) else rng.randint(26, 48)
        x, y = x0 + rng.randint(M + r, PARC_CH - M - r), y0 + rng.randint(M + r, PARC_CH - M - r)
        if not libre(x, y, r, int(r * 0.5) + 6):
            continue
        if any((x - o[0]) ** 2 + (y - o[1]) ** 2 < (0.5 * (r + o[2])) ** 2 for o in d["arbres"]):
            continue
        d["arbres"].append((x, y, r))
        d["obs_c"].append((x, y, max(9, int(r * 0.3))))
    for _ in range(n_bus):                                   # buissons (on peut passer dessus)
        r = rng.randint(12, 20)
        x, y = x0 + rng.randint(M + r, PARC_CH - M - r), y0 + rng.randint(M + r, PARC_CH - M - r)
        if libre(x, y, r, r):
            d["buissons"].append((x, y, r))
    for _ in range(n_roc):                                   # rochers
        r = rng.randint(14, 34 if bio == 4 else 26)
        x, y = x0 + rng.randint(M + r, PARC_CH - M - r), y0 + rng.randint(M + r, PARC_CH - M - r)
        if libre(x, y, r, r + 4):
            d["rochers"].append((x, y, r))
            d["obs_c"].append((x, y, int(r * 0.9)))
    for _ in range(1):                                       # bancs le long des allées
        ax = PARC_DEC + min(PARC_NAXES - 1, max(0, round((x0 + PARC_CH // 2 - PARC_DEC) / PARC_PAS))) * PARC_PAS
        if x0 <= ax < x0 + PARC_CH and rng.random() < 0.6:
            d["bancs"].append((ax + rng.choice((-96, 96)) - 9, y0 + rng.randint(M, PARC_CH - M - 44), 18, 44))
        ay = PARC_DEC + min(PARC_NAXES - 1, max(0, round((y0 + PARC_CH // 2 - PARC_DEC) / PARC_PAS))) * PARC_PAS
        if y0 <= ay < y0 + PARC_CH and rng.random() < 0.6:
            d["bancs"].append((x0 + rng.randint(M, PARC_CH - M - 44), ay + rng.choice((-96, 96)) - 9, 44, 18))
    for _ in range(n_fle):                                   # fleurs
        x, y = x0 + rng.randint(M, PARC_CH - M), y0 + rng.randint(M, PARC_CH - M)
        if libre(x, y, 4, 4):
            d["fleurs"].append((x, y, rng.randint(0, len(_PC_FLEURS) - 1)))
    PARC["donnees"][(cx, cy)] = d
    return d


def parc_bloque(x, y, r=16):
    """Vrai si un joueur de rayon r à (x, y) touche un obstacle (arbre, bâtiment, rocher, étang, bord du monde)."""
    if x < 60 or y < 60 or x > PARC_MONDE - 60 or y > PARC_MONDE - 60:
        return True
    d = _parc_gen(int(x // PARC_CH), int(y // PARC_CH))
    for ox_, oy_, rr in d["obs_c"]:
        s_ = rr + r
        if (x - ox_) ** 2 + (y - oy_) ** 2 < s_ * s_:
            return True
    for bx, by, bw, bh in d["obs_r"]:
        if bx - r < x < bx + bw + r and by - r < y < by + bh + r:
            return True
    return False


# ---------- style « quartier néon » : décor de nuit dessiné une seule fois par zone, en 3 étapes pour ne jamais faire saccader le jeu ----------
_NEON = [(0, 230, 255), (255, 40, 200), (150, 90, 255), (255, 175, 50), (255, 60, 90)]
_PX_ROUTE, _PX_TROTT, _PX_BORD = (13, 17, 33), (34, 42, 70), (52, 64, 104)
_PX_TOITS = [((30, 38, 68), (60, 74, 120)), ((42, 34, 70), (86, 68, 132)), ((26, 50, 66), (52, 98, 126)),
             ((52, 36, 56), (112, 72, 114)), ((34, 44, 54), (74, 94, 110))]
_PX_FEN = [(255, 190, 70), (0, 220, 255), (255, 60, 200), (28, 36, 62), (28, 36, 62), (28, 36, 62), (28, 36, 62)]
_PX_CARROSS = [(100, 30, 78), (28, 74, 108), (70, 72, 90), (116, 64, 30), (40, 40, 60)]
_GLOW = {}
_TEX = {}


def _glow(couleur, rayon):
    """Tache de lumière (fondu radial) à ajouter sur le décor ; fabriquée une seule fois."""
    cle = (couleur, rayon)
    g = _GLOW.get(cle)
    if g is None:
        g = pygame.Surface((rayon * 2, rayon * 2))
        g.fill((0, 0, 0))
        n = 12
        for i in range(n):
            k = (((i + 1) / n) ** 2.2) * 0.7
            pygame.draw.circle(g, (int(couleur[0] * k), int(couleur[1] * k), int(couleur[2] * k)), (rayon, rayon), max(1, int(rayon * (1.0 - i / n))))
        _GLOW[cle] = g
    return g


def _px_halo(surf, x, y, couleur, rayon):
    surf.blit(_glow(couleur, rayon), (int(x - rayon), int(y - rayon)), special_flags=pygame.BLEND_RGB_ADD)


def _parc_texture(nom):
    t = _TEX.get(nom)
    if t is None:
        t = pygame.Surface((128, 128))
        rng = random.Random(nom)
        if nom == "pave":
            base, p1, p2, ligne = (19, 25, 43), (25, 33, 55), (14, 19, 34), (27, 35, 60)
        else:
            base, p1, p2, ligne = (13, 38, 40), (18, 52, 50), (9, 28, 32), None
        t.fill(base)
        for _ in range(70):
            pygame.draw.rect(t, p1 if rng.random() < 0.5 else p2, (rng.randint(0, 124), rng.randint(0, 124), rng.randint(2, 7), rng.randint(2, 7)))
        if ligne:
            pygame.draw.line(t, ligne, (0, 0), (127, 0), 1)
            pygame.draw.line(t, ligne, (0, 0), (0, 127), 1)
            pygame.draw.line(t, ligne, (0, 64), (127, 64), 1)
            pygame.draw.line(t, ligne, (64, 0), (64, 127), 1)
        _TEX[nom] = t
    return t


def _pe_terrain(cx, cy, d, w):
    """Étape 1 : sol, rues, trottoirs, places, eau, puis les pools de lumière posés sur le sol."""
    q = QUALITE["niveau"]
    surf = pygame.Surface((PARC_CH, PARC_CH))
    w["surf"] = surf
    dr = pygame.draw
    x0, y0 = cx * PARC_CH, cy * PARC_CH
    bio = d["biome"]
    ville = bio in (2, 3, 4)
    tex = _parc_texture("pave" if ville else "parc")
    for tx in range(0, PARC_CH, 128):
        for ty in range(0, PARC_CH, 128):
            surf.blit(tex, (tx, ty))
    for x, y, rx, ry, c in d["taches"]:
        col = ((23, 31, 53), (16, 22, 38))[c] if ville else ((19, 60, 56), (9, 32, 36))[c]
        dr.ellipse(surf, col, (x - x0 - rx, y - y0 - ry, rx * 2, ry * 2))
    lum = w["lum"]
    if ville:                                                            # rues de quartier le long des bords de la zone
        for r_ in ((0, 0, PARC_CH, 30), (0, PARC_CH - 30, PARC_CH, 30), (0, 0, 30, PARC_CH), (PARC_CH - 30, 0, 30, PARC_CH)):
            dr.rect(surf, _PX_ROUTE, r_)
        dr.line(surf, _PX_BORD, (0, 30), (PARC_CH, 30), 2)
        dr.line(surf, _PX_BORD, (0, PARC_CH - 31), (PARC_CH, PARC_CH - 31), 2)
        dr.line(surf, _PX_BORD, (30, 0), (30, PARC_CH), 2)
        dr.line(surf, _PX_BORD, (PARC_CH - 31, 0), (PARC_CH - 31, PARC_CH), 2)
        for t in range(10, PARC_CH, 56):
            dr.line(surf, (150, 128, 52), (t, 1), (t + 26, 1), 2)
            dr.line(surf, (150, 128, 52), (1, t), (1, t + 26), 2)
        if q >= 1:
            for (lx, ly), nc in zip(((15, 15), (PARC_CH - 15, 15), (15, PARC_CH - 15), (PARC_CH - 15, PARC_CH - 15)), (_NEON[(cx + cy) % 5], _NEON[(cx + cy + 2) % 5], _NEON[(cx + cy + 3) % 5], _NEON[(cx + cy + 1) % 5])):
                lum.append((lx, ly, nc, 70))
    kx = round((x0 + PARC_CH // 2 - PARC_DEC) / PARC_PAS)
    ky = round((y0 + PARC_CH // 2 - PARC_DEC) / PARC_PAS)
    ax = PARC_DEC + kx * PARC_PAS if 0 <= kx < PARC_NAXES and x0 - 80 < PARC_DEC + kx * PARC_PAS < x0 + PARC_CH + 80 else None
    ay = PARC_DEC + ky * PARC_PAS if 0 <= ky < PARC_NAXES and y0 - 80 < PARC_DEC + ky * PARC_PAS < y0 + PARC_CH + 80 else None
    w["avenues"] = (ax, ay)
    if ax is not None:                                                   # avenue verticale : trottoirs, chaussée, ligne jaune, lampadaires néon
        xc = ax - x0
        dr.rect(surf, _PX_TROTT, (xc - 75, 0, 150, PARC_CH))
        dr.rect(surf, _PX_ROUTE, (xc - 61, 0, 122, PARC_CH))
        dr.line(surf, (200, 160, 50), (xc - 2, 0), (xc - 2, PARC_CH), 2)
        dr.line(surf, (200, 160, 50), (xc + 2, 0), (xc + 2, PARC_CH), 2)
        dr.line(surf, (44, 56, 92), (xc - 58, 0), (xc - 58, PARC_CH), 1)
        dr.line(surf, (44, 56, 92), (xc + 58, 0), (xc + 58, PARC_CH), 1)
        if q >= 1:
            for gy in range((y0 // 220 + 1) * 220, y0 + PARC_CH, 220):
                lum.append((xc - 42, gy - y0, _NEON[0], 78))
                lum.append((xc + 42, gy - y0 + 110, _NEON[1], 78))
                w["lampes"].append((xc - 68, gy - y0, _NEON[0]))
                w["lampes"].append((xc + 68, gy - y0 + 110, _NEON[1]))
    if ay is not None:                                                   # avenue horizontale
        yc = ay - y0
        dr.rect(surf, _PX_TROTT, (0, yc - 75, PARC_CH, 150))
        dr.rect(surf, _PX_ROUTE, (0, yc - 61, PARC_CH, 122))
        dr.line(surf, (200, 160, 50), (0, yc - 2), (PARC_CH, yc - 2), 2)
        dr.line(surf, (200, 160, 50), (0, yc + 2), (PARC_CH, yc + 2), 2)
        dr.line(surf, (44, 56, 92), (0, yc - 58), (PARC_CH, yc - 58), 1)
        dr.line(surf, (44, 56, 92), (0, yc + 58), (PARC_CH, yc + 58), 1)
        if q >= 1:
            for gx in range((x0 // 220 + 1) * 220, x0 + PARC_CH, 220):
                lum.append((gx - x0, yc - 42, _NEON[0], 78))
                lum.append((gx - x0 + 110, yc + 42, _NEON[1], 78))
                w["lampes"].append((gx - x0, yc - 68, _NEON[0]))
                w["lampes"].append((gx - x0 + 110, yc + 68, _NEON[1]))
    if ax is not None and ay is not None:                                # carrefour : on efface les lignes du milieu et on trace les passages piétons
        xc, yc = ax - x0, ay - y0
        dr.rect(surf, _PX_ROUTE, (xc - 75, yc - 75, 150, 150))
        for i in range(10):
            dr.rect(surf, (140, 152, 186), (xc - 55 + i * 11, yc - 112, 7, 26))
            dr.rect(surf, (140, 152, 186), (xc - 55 + i * 11, yc + 86, 7, 26))
            dr.rect(surf, (140, 152, 186), (xc - 112, yc - 55 + i * 11, 26, 7))
            dr.rect(surf, (140, 152, 186), (xc + 86, yc - 55 + i * 11, 26, 7))
    pl = _parc_place_proche(x0 + PARC_CH // 2, y0 + PARC_CH // 2)
    if pl is not None:                                                   # place centrale : dalles sombres et anneaux néon
        nx, ny = min(max(pl[0], x0), x0 + PARC_CH), min(max(pl[1], y0), y0 + PARC_CH)
        if (nx - pl[0]) ** 2 + (ny - pl[1]) ** 2 < (PARC_R_PLACE + 6) ** 2:
            c = (int(pl[0] - x0), int(pl[1] - y0))
            dr.circle(surf, _PX_BORD, c, PARC_R_PLACE + 5)
            dr.circle(surf, (22, 28, 50), c, PARC_R_PLACE)
            for rr, col in ((PARC_R_PLACE - 22, (0, 140, 180)), (PARC_R_PLACE - 60, (140, 36, 140)), (PARC_R_PLACE - 98, (0, 110, 150))):
                dr.circle(surf, col, c, rr, 3)
    if d["fontaine"]:
        fx, fy, fr = d["fontaine"]
        c = (int(fx - x0), int(fy - y0))
        dr.circle(surf, (60, 70, 112), c, fr + 14)
        dr.circle(surf, (0, 150, 200), c, fr + 6)
        dr.circle(surf, (6, 30, 70), c, fr)
        dr.circle(surf, (10, 60, 120), c, int(fr * 0.62))
        dr.circle(surf, (210, 250, 255), c, 14)
        if q >= 1:
            lum.append((c[0], c[1], _NEON[0], 150))
    for ex, ey, rx, ry in d["etangs"]:                                   # canal / bassin : eau noire, bord néon, reflets
        e0, e1 = ex - x0, ey - y0
        dr.ellipse(surf, (0, 150, 200), (e0 - rx - 7, e1 - ry - 7, rx * 2 + 14, ry * 2 + 14))
        dr.ellipse(surf, (5, 22, 58), (e0 - rx, e1 - ry, rx * 2, ry * 2))
        dr.ellipse(surf, (9, 42, 96), (e0 - rx * 0.62, e1 - ry * 0.55, rx * 1.1, ry * 0.8))
        for k_, col in enumerate(((120, 30, 120), (0, 120, 150), (120, 30, 120))):
            dr.line(surf, col, (e0 - rx * 0.5 + k_ * rx * 0.4, e1 - ry * 0.3 + k_ * ry * 0.25), (e0 - rx * 0.2 + k_ * rx * 0.4, e1 - ry * 0.3 + k_ * ry * 0.25), 2)
        if q >= 1:
            lum.append((e0, e1, _NEON[(cx + cy) % 3], int(max(rx, ry) * 1.3)))
    # halos des enseignes des bâtiments (posés sur le sol : les toits viendront par-dessus)
    w["neon_b"] = []
    for i, (bx, by, bw, bh, ci) in enumerate(d["batiments"]):
        nc = _NEON[(bx // 7 + by // 5) % len(_NEON)] if ((bx * 31 + by * 17) % 100) < 70 else None
        w["neon_b"].append(nc)
        if nc is not None and q >= 1:
            lum.append((bx - x0 + bw / 2, by - y0 + bh / 2, nc, int(min(200, max(bw, bh) * 0.8 + 40))))
    if q >= 1:
        for lx, ly, nc, rr in lum:
            _px_halo(surf, lx, ly, nc, rr)


def _pe_batiment(surf, b, x0, y0, nc, q):
    bx, by, bw, bh, ci = b
    dr = pygame.draw
    rx, ry = bx - x0, by - y0
    rng = random.Random(bx * 31 + by * 17)
    mur = max(14, min(28, bh // 6))                                      # façade visible (mur sud) à l'intérieur de l'emprise : la collision ne change pas
    th = bh - mur
    c_toit, c_bord = _PX_TOITS[ci]
    dr.rect(surf, _PX_TROTT, (rx - 7, ry - 7, bw + 14, bh + 14))        # trottoir
    dr.rect(surf, (6, 8, 16), (rx + 9, ry + 13, bw, bh))                 # ombre portée
    dr.rect(surf, (11, 14, 28), (rx, ry + th, bw, mur))                  # façade
    dr.line(surf, (24, 30, 54), (rx, ry + th), (rx + bw, ry + th), 2)
    if q >= 1:
        wy = ry + th + mur // 2 - 3
        for wx in range(rx + 10, rx + bw - 12, 16):
            dr.rect(surf, rng.choice(_PX_FEN), (wx, wy, 8, 6))
    dr.rect(surf, c_bord, (rx, ry, bw, th))                              # toit
    dr.rect(surf, c_toit, (rx + 4, ry + 4, bw - 8, th - 8))
    dr.line(surf, c_bord, (rx + 8, ry + th // 2), (rx + bw - 8, ry + th // 2), 2)
    if q >= 1:
        for _ in range(rng.randint(2, 4)):                               # climatiseurs
            ux, uy = rx + rng.randint(12, max(13, bw - 44)), ry + rng.randint(10, max(11, th - 34))
            dr.rect(surf, (20, 24, 44), (ux + 3, uy + 4, 30, 20))
            dr.rect(surf, (70, 84, 124), (ux, uy, 30, 20))
            dr.rect(surf, (36, 44, 76), (ux + 4, uy + 4, 22, 12))
            for g_ in range(3):
                dr.line(surf, (90, 106, 150), (ux + 6, uy + 7 + g_ * 4), (ux + 24, uy + 7 + g_ * 4), 1)
        if bw >= 170 and th >= 110:                                      # local technique en relief (ombre, face, voyant rouge)
            ux, uy = rx + rng.randint(14, max(15, bw - 70)), ry + rng.randint(12, max(13, th - 50))
            dr.rect(surf, (14, 18, 34), (ux + 6, uy + 8, 52, 34))
            dr.rect(surf, c_bord, (ux, uy, 52, 34))
            dr.rect(surf, (c_toit[0] + 18, c_toit[1] + 18, c_toit[2] + 26), (ux + 3, uy + 3, 46, 28))
            dr.circle(surf, (255, 60, 90), (ux + 44, uy + 8), 3)
        for _ in range(rng.randint(1, 3)):                               # aérations rondes
            vx, vy = rx + rng.randint(14, max(15, bw - 14)), ry + rng.randint(12, max(13, th - 12))
            dr.circle(surf, (24, 30, 52), (vx + 2, vy + 3), 9)
            dr.circle(surf, (78, 92, 134), (vx, vy), 9)
            dr.circle(surf, (28, 34, 60), (vx, vy), 5)
        if bw >= 210 and th >= 120 and rng.random() < 0.6:               # panneaux solaires
            sx, sy = rx + bw - 96, ry + th - 62
            dr.rect(surf, (14, 30, 76), (sx, sy, 80, 44))
            for k_ in range(1, 4):
                dr.line(surf, (40, 74, 150), (sx + k_ * 20, sy), (sx + k_ * 20, sy + 44), 1)
            dr.line(surf, (40, 74, 150), (sx, sy + 22), (sx + 80, sy + 22), 1)
        if bw >= 270 and th >= 190 and rng.random() < 0.5:               # héliport
            hx, hy = rx + bw // 2, ry + th // 2
            dr.circle(surf, (50, 60, 98), (hx, hy), 42)
            dr.circle(surf, (0, 190, 230), (hx, hy), 42, 3)
            dr.line(surf, (0, 190, 230), (hx - 12, hy - 16), (hx - 12, hy + 16), 4)
            dr.line(surf, (0, 190, 230), (hx + 12, hy - 16), (hx + 12, hy + 16), 4)
            dr.line(surf, (0, 190, 230), (hx - 12, hy), (hx + 12, hy), 4)
    if nc is not None:                                                   # enseigne néon sur l'arête du toit
        dr.rect(surf, nc, (rx + 1, ry + 1, bw - 2, th - 2), 2)
        dr.line(surf, nc, (rx + 10, ry + th + 3), (rx + bw - 10, ry + th + 3), 3)


def _pe_objets(cx, cy, d, w):
    """Étape 2 : mobilier, rochers/caisses, bâtiments, arbres, voitures, lampadaires."""
    q = QUALITE["niveau"]
    surf, dr = w["surf"], pygame.draw
    x0, y0 = cx * PARC_CH, cy * PARC_CH
    bio = d["biome"]
    ville = bio in (2, 3, 4)
    rng = random.Random(cx * 1009 + cy * 9176)
    for bx, by, bw, bh in d["bancs"]:                                    # bancs lumineux
        dr.rect(surf, (54, 64, 104), (bx - x0, by - y0, bw, bh))
        dr.rect(surf, (0, 200, 230), (bx - x0 + 1, by - y0 + 1, max(2, bw - 2), max(2, bh - 2)), 1)
    for x, y, c in d["fleurs"]:
        dr.circle(surf, _NEON[c % len(_NEON)], (x - x0, y - y0), 3)
    for x, y, r in d["buissons"]:
        if ville:                                                        # grille d'aération lumineuse
            dr.circle(surf, (22, 28, 48), (x - x0, y - y0), r)
            dr.circle(surf, (0, 120, 160), (x - x0, y - y0), r, 2)
            dr.line(surf, (0, 120, 160), (x - x0 - r + 3, y - y0), (x - x0 + r - 3, y - y0), 1)
        else:
            dr.circle(surf, (6, 28, 32), (x - x0 + 3, y - y0 + 4), r)
            dr.circle(surf, (12, 54, 56), (x - x0, y - y0), r)
            dr.circle(surf, (26, 96, 92), (x - x0 - r // 3, y - y0 - r // 3), max(3, r // 3))
    for x, y, r in d["rochers"]:
        px_, py_ = x - x0, y - y0
        if bio == 4 and r >= 22:                                         # conteneur
            col = _PX_CARROSS[(x + y) % 4]
            dr.rect(surf, (6, 8, 16), (px_ - r * 1.1 + 6, py_ - r * 0.6 + 8, r * 2.2, r * 1.2))
            dr.rect(surf, col, (px_ - r * 1.1, py_ - r * 0.6, r * 2.2, r * 1.2))
            for k_ in range(1, 5):
                dr.line(surf, (min(255, col[0] + 50), min(255, col[1] + 50), min(255, col[2] + 50)), (px_ - r * 1.1 + k_ * r * 0.44, py_ - r * 0.6), (px_ - r * 1.1 + k_ * r * 0.44, py_ + r * 0.6), 1)
            dr.rect(surf, (200, 210, 230), (px_ - r * 1.1, py_ - r * 0.6, r * 2.2, r * 1.2), 1)
        elif bio == 4:                                                   # baril
            dr.circle(surf, (6, 8, 16), (px_ + 4, py_ + 5), r)
            dr.circle(surf, (200, 100, 30) if (x + y) % 2 else (0, 140, 170), (px_, py_), r)
            dr.circle(surf, (250, 190, 100), (px_, py_), max(3, r - 6), 2)
        else:                                                            # bloc de béton avec marque lumineuse
            dr.rect(surf, (6, 8, 16), (px_ - r + 5, py_ - r + 6, r * 2, r * 2))
            dr.rect(surf, (62, 72, 108), (px_ - r, py_ - r, r * 2, r * 2))
            dr.rect(surf, (88, 102, 148), (px_ - r + 3, py_ - r + 3, r * 2 - 6, r * 2 - 6), 2)
            dr.circle(surf, _NEON[(x + y) % 5], (px_ - r + 7, py_ - r + 7), 3)
    for i, b in enumerate(d["batiments"]):
        _pe_batiment(surf, b, x0, y0, w["neon_b"][i], q)
    for x, y, r in sorted(d["arbres"], key=lambda t: t[1]):
        px_, py_ = x - x0, y - y0
        if ville:
            dr.circle(surf, _PX_TROTT, (px_, py_), int(r * 0.55) + 6)    # bac
        dr.circle(surf, (4, 18, 24), (px_ + 8, py_ + 10), r)
        dr.circle(surf, (12, 58, 64), (px_, py_), r)
        dr.circle(surf, (20, 90, 96), (px_ - r // 6, py_ - r // 6), int(r * 0.72))
        dr.circle(surf, (56, 168, 158), (px_ - r // 3, py_ - r // 3), max(4, int(r * 0.3)))
        if (x * 13 + y * 7) % 100 < 24:                                  # arbres luminescents
            nc = _NEON[(x + y) % 3]
            for k_ in range(3):
                a = k_ * 2.1 + (x % 7)
                dr.circle(surf, nc, (int(px_ + math.cos(a) * r * 0.7), int(py_ + math.sin(a) * r * 0.7)), 2)
    if w["avenues"][0] is not None and w["avenues"][1] is None:          # voitures garées le long de l'avenue verticale
        xc = w["avenues"][0] - x0
        for _ in range(rng.randint(0, 2)):
            cy_, side = rng.randint(80, PARC_CH - 80), rng.choice((-1, 1))
            col = _PX_CARROSS[rng.randint(0, 4)]
            px_ = xc + side * 40
            dr.rect(surf, (6, 8, 16), (px_ - 11, cy_ - 26, 26, 54))
            dr.rect(surf, col, (px_ - 13, cy_ - 28, 26, 56))
            dr.rect(surf, (60, 100, 136), (px_ - 9, cy_ - 12, 18, 14))
            dr.rect(surf, (255, 240, 170), (px_ - 11, cy_ - 28, 6, 3))
            dr.rect(surf, (255, 240, 170), (px_ + 5, cy_ - 28, 6, 3))
            dr.rect(surf, (255, 50, 70), (px_ - 11, cy_ + 25, 6, 3))
            dr.rect(surf, (255, 50, 70), (px_ + 5, cy_ + 25, 6, 3))
    elif w["avenues"][1] is not None and w["avenues"][0] is None:        # ... et le long de l'avenue horizontale
        yc = w["avenues"][1] - y0
        for _ in range(rng.randint(0, 2)):
            cx_, side = rng.randint(80, PARC_CH - 80), rng.choice((-1, 1))
            col = _PX_CARROSS[rng.randint(0, 4)]
            py_ = yc + side * 40
            dr.rect(surf, (6, 8, 16), (cx_ - 26, py_ - 11, 54, 26))
            dr.rect(surf, col, (cx_ - 28, py_ - 13, 56, 26))
            dr.rect(surf, (60, 100, 136), (cx_ - 12, py_ - 9, 14, 18))
            dr.rect(surf, (255, 240, 170), (cx_ + 25, py_ - 11, 3, 6))
            dr.rect(surf, (255, 240, 170), (cx_ + 25, py_ + 5, 3, 6))
            dr.rect(surf, (255, 50, 70), (cx_ - 28, py_ - 11, 3, 6))
            dr.rect(surf, (255, 50, 70), (cx_ - 28, py_ + 5, 3, 6))
    for lx, ly, nc in w["lampes"]:                                       # lampadaires
        dr.circle(surf, (70, 82, 120), (lx, ly), 5)
        dr.circle(surf, nc, (lx, ly), 3)


def _pe_accents(cx, cy, d, w):
    """Étape 3 : petites lueurs néon sur les toits et les antennes, puis la zone est prête."""
    q = QUALITE["niveau"]
    surf = w["surf"]
    x0, y0 = cx * PARC_CH, cy * PARC_CH
    if q >= 1:
        for i, (bx, by, bw, bh, ci) in enumerate(d["batiments"]):
            nc = w["neon_b"][i]
            if nc is not None:
                _px_halo(surf, bx - x0 + bw / 2, by - y0 + 6, nc, 34)
                _px_halo(surf, bx - x0 + bw / 2, by - y0 + bh - 6, nc, 30)


def _parc_peindre_etape(cx, cy, w):
    """Fait avancer d'une étape la fabrication d'une zone (w : son état de fabrication)."""
    d = _parc_gen(cx, cy)
    if w["etape"] == 0:
        _pe_terrain(cx, cy, d, w)
    elif w["etape"] == 1:
        _pe_objets(cx, cy, d, w)
    else:
        _pe_accents(cx, cy, d, w)
    w["etape"] += 1


def _parc_peindre(cx, cy):
    """Fabrique une zone complète d'un coup (départ du jeu)."""
    w = {"etape": 0, "surf": None, "lum": [], "lampes": [], "avenues": (None, None), "neon_b": []}
    while w["etape"] < 3:
        _parc_peindre_etape(cx, cy, w)
    return w["surf"].convert()


def _parc_gerer(cam_x, cam_y, complet=False):
    """Crée au plus une zone par image (la plus proche du joueur) et décharge les zones lointaines."""
    t0 = _time.perf_counter()
    c0x, c1x = max(0, int((cam_x - 320) // PARC_CH)), min(PARC_NC - 1, int((cam_x + LARGEUR + 320) // PARC_CH))
    c0y, c1y = max(0, int((cam_y - 320) // PARC_CH)), min(PARC_NC - 1, int((cam_y + HAUTEUR + 320) // PARC_CH))
    manquantes = [(cx, cy) for cx in range(c0x, c1x + 1) for cy in range(c0y, c1y + 1) if (cx, cy) not in PARC["surf"]]
    if manquantes:
        px, py = PARC["x"] / PARC_CH, PARC["y"] / PARC_CH
        manquantes.sort(key=lambda c: (c[0] + 0.5 - px) ** 2 + (c[1] + 0.5 - py) ** 2)
        cle = manquantes[0]
        w = PARC["wip"].get(cle)
        if w is None:
            w = PARC["wip"][cle] = {"etape": 0, "surf": None, "lum": [], "lampes": [], "avenues": (None, None), "neon_b": []}
        while True:                                                       # une étape par image (toutes d'un coup au départ du jeu)
            _parc_peindre_etape(cle[0], cle[1], w)
            if w["etape"] >= 3 or not complet:
                break
        if w["etape"] >= 3:
            PARC["surf"][cle] = w["surf"].convert()
            del PARC["wip"][cle]
        PARC["ms_gen"] = (_time.perf_counter() - t0) * 1000.0
    for cle in [c for c in PARC["surf"] if c[0] < c0x - 1 or c[0] > c1x + 1 or c[1] < c0y - 1 or c[1] > c1y + 1]:
        del PARC["surf"][cle]
        PARC["donnees"].pop(cle, None)
    for cle in [c for c in PARC["wip"] if c[0] < c0x - 1 or c[0] > c1x + 1 or c[1] < c0y - 1 or c[1] > c1y + 1]:
        del PARC["wip"][cle]
    pcx, pcy = int(PARC["x"] // PARC_CH), int(PARC["y"] // PARC_CH)
    for cle in [c for c in PARC["donnees"] if abs(c[0] - pcx) > 3 or abs(c[1] - pcy) > 3]:
        PARC["donnees"].pop(cle, None)


_PC_MINI = 168                                               # taille de la mini-carte


def _parc_mini_axes():
    mini, k = PARC["mini"], _PC_MINI / PARC_MONDE
    for i in range(PARC_NAXES):
        a = int((PARC_DEC + i * PARC_PAS) * k)
        pygame.draw.line(mini, (120, 110, 88), (a, 0), (a, _PC_MINI), 1)
        pygame.draw.line(mini, (120, 110, 88), (0, a), (_PC_MINI, a), 1)


def _parc_decouvrir(x, y):
    """La mini-carte ne montre que les régions déjà visitées : il faut explorer pour les découvrir."""
    rx, ry = int(x // (PARC_CH * PARC_REGION)), int(y // (PARC_CH * PARC_REGION))
    if (rx, ry) in PARC["vus"] or PARC["mini"] is None:
        return
    PARC["vus"].add((rx, ry))
    PARC["mini_ver"] = PARC.get("mini_ver", 0) + 1
    k, taille = _PC_MINI / PARC_MONDE, PARC_CH * PARC_REGION
    bio = _parc_biome(rx * PARC_REGION, ry * PARC_REGION)
    pygame.draw.rect(PARC["mini"], _PC_BIOME_COUL[bio], (int(rx * taille * k), int(ry * taille * k), int(taille * k) + 1, int(taille * k) + 1))
    _parc_mini_axes()


def parc_demarrer(seed=None, spawn_fn=None):
    PARC.update(actif=True, seed=seed or random.randint(1, 999999), face=1, donnees={}, surf={}, ms_gen=0.0, vus=set(), wip={})
    PARC["x"], PARC["y"] = float(PARC_DEC + 4 * PARC_PAS), float(PARC_DEC + 4 * PARC_PAS + 450)   # sous la place du milieu
    if spawn_fn is not None:
        PARC["x"], PARC["y"] = spawn_fn()
    cam_x, cam_y = PARC["x"] - LARGEUR // 2, PARC["y"] - HAUTEUR // 2
    for _ in range(4):                                       # quelques zones tout de suite (l'écran de chargement masque le délai)
        _parc_gerer(cam_x, cam_y, True)
    PARC["mini"] = pygame.Surface((_PC_MINI, _PC_MINI))
    PARC["mini"].fill((16, 30, 22))
    _parc_mini_axes()
    pygame.draw.rect(PARC["mini"], (230, 240, 230), (0, 0, _PC_MINI, _PC_MINI), 2)


def parc_liberer():
    PARC.update(actif=False, donnees={}, surf={}, mini=None, vus=set(), wip={})


def jouer_parc():
    """Boucle du parc (test solo) : déplacement, collisions, zones créées au fil du déplacement, affichage."""
    if not PARC["actif"]:
        return
    if ARENE["actif"]:
        jouer_arene()
        return
    if (clic_detecte and rect_bouton_pause.collidepoint(clic_x, clic_y)) or pygame.key.get_pressed()[pygame.K_ESCAPE]:
        parc_liberer()
        lancer_transition(("etat", ETAT_MENU))
        return
    dx = dy = 0.0
    vit = joueur_vitesse * _facteur_vitesse()
    if joystick_actif:
        vx, vy = manette_x - JOY_CENTRE_X, manette_y - JOY_CENTRE_Y
        dist = math.hypot(vx, vy)
        if dist > CTRL["dz"]:
            dx, dy = vx / dist * vit, vy / dist * vit
            if vx < -15:
                PARC["face"] = 0
            elif vx > 15:
                PARC["face"] = 1
    im = _in_deplacement()
    if im is not None:
        dx, dy = im[0] * vit, im[1] * vit
        if im[0] < -0.2:
            PARC["face"] = 0
        elif im[0] > 0.2:
            PARC["face"] = 1
    if dx != 0 and not parc_bloque(PARC["x"] + dx, PARC["y"]):
        PARC["x"] += dx
    if dy != 0 and not parc_bloque(PARC["x"], PARC["y"] + dy):
        PARC["y"] += dy
    cam_x = int(min(max(PARC["x"] - LARGEUR // 2, 0), PARC_MONDE - LARGEUR))
    cam_y = int(min(max(PARC["y"] - HAUTEUR // 2, 0), PARC_MONDE - HAUTEUR))
    _parc_gerer(cam_x, cam_y)
    _parc_decouvrir(PARC["x"], PARC["y"])
    for cx in range(max(0, cam_x // PARC_CH), min(PARC_NC - 1, (cam_x + LARGEUR) // PARC_CH) + 1):
        for cy in range(max(0, cam_y // PARC_CH), min(PARC_NC - 1, (cam_y + HAUTEUR) // PARC_CH) + 1):
            surf = PARC["surf"].get((cx, cy))
            px, py = cx * PARC_CH - cam_x, cy * PARC_CH - cam_y
            if surf is not None:
                ecran.blit(surf, (px, py))
            else:
                ecran.fill(_PC_HERBE, (px, py, PARC_CH, PARC_CH))        # zone pas encore prête : herbe unie
    sx, sy = int(PARC["x"] - cam_x), int(PARC["y"] - cam_y)
    pygame.draw.ellipse(ecran, (2, 4, 12), (sx - 18, sy + 8, 36, 14))
    if MODE_GRAPHIQUE == "REALISTE":
        img = img_joueur_droite if PARC["face"] else img_joueur_gauche
        ecran.blit(img, (sx - img.get_width() // 2, sy - img.get_height() // 2))
    else:
        pygame.draw.rect(ecran, VERT_FLUO, (sx - 16, sy - 16, 32, 32))
    # mini-carte du côté opposé au bouton pause
    mx0 = 24 if rect_bouton_pause.centerx > LARGEUR // 2 else LARGEUR - _PC_MINI - 24
    if PARC["mini"] is not None:
        ecran.blit(PARC["mini"], (mx0, 24))
        k = _PC_MINI / PARC_MONDE
        pygame.draw.circle(ecran, ROUGE_ALERTE, (mx0 + int(PARC["x"] * k), 24 + int(PARC["y"] * k)), 4)
    # joystick tactile (le bouton TIR viendra avec le combat)
    ecran.blit(SURF_SOCLE_JOY, (JOY_CENTRE_X - JOY_RAYON_SOCLE - 6, JOY_CENTRE_Y - JOY_RAYON_SOCLE - 6))
    DRAW.circle(ecran, VERT_FLUO, (JOY_CENTRE_X, JOY_CENTRE_Y), JOY_RAYON_SOCLE, 4)
    DRAW.circle(ecran, (0, 120, 190), (int(manette_x), int(manette_y)), JOY_RAYON_MANETTE)
    DRAW.circle(ecran, CYAN_NEON, (int(manette_x), int(manette_y)), max(2, JOY_RAYON_MANETTE - 4))
    bouton_neon(rect_bouton_pause, ROUGE_ALERTE, "X", police_bouton)
    bio = _PC_BIOMES[_parc_biome(int(PARC["x"] // PARC_CH), int(PARC["y"] // PARC_CH))]
    info = rendu_texte(police_petite, f"{bio.upper()}  •  {int(clock.get_fps())} FPS  •  {len(PARC['surf'])} zones  •  {PARC['ms_gen']:.0f} ms", True, BLANC_NEON)
    ecran.blit(info, (LARGEUR // 2 - info.get_width() // 2, HAUTEUR - 36))


# ==================== ARÈNE EN LIGNE : combat entre joueurs dans le Parc (visée manuelle L2 / R2) ====================
ARENE_PV = 100                     # points de vie
ARENE_DEGATS = 12                  # dégâts d'un tir qui touche
ARENE_PORTEE = 950.0               # portée d'un tir (px)
ARENE_V_BALLE = 1050.0             # vitesse d'un tir (px par seconde : identique sur tous les téléphones)
ARENE_CADENCE = 0.18               # secondes entre deux tirs
ARENE_R_JOUEUR = 20                # rayon de touche d'un joueur
ARENE_LOCK = 1200.0                # distance maximale du verrouillage automatique (bouton L)
ARENE_R0 = 21800                   # rayon de la zone au départ : le cercle contient TOUTE la carte, coins compris (demi-diagonale = 21 720 px)
# phases de la zone : (secondes de calme, secondes d'alerte rouge, secondes de rétrécissement, rayon visé, dégâts par seconde hors zone)
# la zone se referme sur toute l'étendue de la carte, par étapes, en restant toujours plus lente qu'un joueur qui court (environ 390 px/s)
ARENE_PHASES = [(90, 10, 80, 13500, 1.0), (60, 10, 70, 8500, 2.0), (50, 10, 60, 5000, 3.0), (40, 10, 50, 2800, 5.0),
                (35, 10, 45, 1400, 7.0), (30, 10, 40, 700, 9.0), (25, 10, 35, 300, 11.0), (20, 10, 30, 120, 13.0)]
ARENE_DPS_FINAL = 15.0             # dégâts par seconde hors de la dernière zone
_AR_RBTN = 48                      # rayon des boutons L2 / R2
_AR_RADAR_R = 66                   # rayon du radar rond (coin bas gauche)
_AR_TS = 40                        # taille (px) d'une zone sur le radar
ARENE = {"actif": False, "phase": "lobby", "debut": 0, "off": 0, "n0": 0, "hp": ARENE_PV, "mort": False, "rang": 0, "kills": 0,
         "balles": [], "balles_d": [], "t_tir": 0.0, "viser": False, "tir": False, "aim_actif": False, "aim_ang": 0.0,
         "aim_utilise": False, "aim_kx": 0.0, "aim_ky": 0.0, "id_aim": None, "id_viser": None, "id_tir": None, "lisse": {},
         "fx": [], "t_last": 0.0, "degat_t": -9.0, "cam_dx": 0.0, "cam_dy": 0.0, "dirx": 1.0, "diry": 0.0, "fin": "",
         "hits": {}, "vivants_vu": {}, "f_vu": {}, "voile": None, "rouge": None, "t_combat": 0.0, "centre": (0, 0),
         "plan": [], "strips": [], "radar_zone": None, "carte_zone": None,
         "bots": [], "bots_idx": {}, "balles_bot": [], "pvel": [0.0, 0.0], "xp_fait": False, "skill_base": 0.12, "t_ajust": 0.0,
         "manche": 0, "endAt": 0, "spectateur": False, "bots_ok": False, "t_fin0": 0.0, "fin_envoye": False, "t_next": 0.0,
         "carte": False, "carte_rect": None, "k_m": False, "menu": None, "k_esc": False, "radar": None, "radar_masque": None, "carte_surf": None,
         "carte_t": 0, "decouv": set(), "thumbs": {}, "lock": None, "vel": {}, "carte_cache": None, "carte_ver": -1, "carte_taille": 0}


def _arene_centre(seed):
    r = random.Random(int(seed) * 31 + 7)
    return r.randint(5, 42) * PARC_CH + PARC_CH // 2, r.randint(5, 42) * PARC_CH + PARC_CH // 2


def _arene_spawn(seed, uid, zone=None):
    """Point de départ d'un joueur : tiré au hasard sur TOUTE la carte (ou dans la zone encore ouverte si on arrive en cours de manche)."""
    r = random.Random(f"{seed}:{uid}")
    for _ in range(200):
        x, y = r.randint(2000, PARC_MONDE - 2000), r.randint(2000, PARC_MONDE - 2000)
        if zone is not None and math.hypot(x - zone["c"][0], y - zone["c"][1]) > zone["r"] * 0.9:
            continue
        if not parc_bloque(x, y, 26):
            return float(x), float(y)
    if zone is not None:
        return float(min(max(zone["c"][0], 2000), PARC_MONDE - 2000)), float(min(max(zone["c"][1], 2000), PARC_MONDE - 2000))
    return float(PARC_MONDE // 2), float(PARC_MONDE // 2 + 450)


def arene_demarrer():
    """Entrée dans la manche en cours de la salle unique : au départ, ou en cours de manche tant que la zone est grande ; sinon on attend la suivante."""
    j = _mp_js()
    try:
        rid, seed, debut, fin_at, off = int(j.round), int(j.seed), int(j.startAt), int(j.endAt), int(j.offset)
    except Exception:
        rid, seed, debut, fin_at, off = 0, MP["seed"] or 1, 0, 0, 0
    maintenant = int(_time.time() * 1000) + off
    if debut <= 0:
        debut = maintenant + 8000
    seed = seed or 1
    MP["seed"] = seed
    try:
        if j is not None:
            j.exit()                                                   # on quitte la manche précédente avant de rejoindre la nouvelle
    except Exception:
        pass
    plan = _arene_zone_plan(seed)
    ARENE["plan"] = plan
    t = (maintenant - debut) / 1000.0
    attente = fin_at > 0 or t > plan[2]["t_fin"]                      # manche déjà finie, ou zone trop petite pour arriver maintenant
    zone = _arene_zone_etat(t)
    if attente:
        spawn = lambda: (float(zone["c"][0]), float(zone["c"][1]))
    else:
        spawn = lambda: _arene_spawn(seed, MP["uid"], zone if t >= 0 else None)
    parc_demarrer(seed=seed, spawn_fn=spawn)
    ARENE.update(actif=True, phase="lobby" if t < 0 else "combat", debut=debut, off=off, n0=0, hp=ARENE_PV, mort=False, rang=0, kills=0,
                 balles=[], balles_d=[], t_tir=0.0, viser=False, tir=False, aim_actif=False, aim_ang=0.0, aim_utilise=False, aim_kx=0.0,
                 aim_ky=0.0, id_aim=None, id_viser=None, id_tir=None, lisse={}, fx=[], t_last=_time.perf_counter(), degat_t=-9.0,
                 cam_dx=0.0, cam_dy=0.0, dirx=1.0, diry=0.0, fin="", hits={}, vivants_vu={}, f_vu={},
                 t_combat=_time.perf_counter() if t >= 0 else 0.0, centre=_arene_centre(seed), carte=False,
                 carte_rect=pygame.Rect(0, 0, 0, 0), k_m=False, menu=None, k_esc=False, plan=plan, bots=[], bots_idx={}, balles_bot=[],
                 pvel=[0.0, 0.0], xp_fait=False, t_ajust=0.0, lock=None, vel={}, carte_cache=None, carte_ver=-1, carte_taille=0,
                 manche=rid, endAt=fin_at, spectateur=attente, bots_ok=False, t_fin0=0.0, fin_envoye=False, t_next=0.0)
    ARENE["voile"] = pygame.Surface((LARGEUR, HAUTEUR), pygame.SRCALPHA)
    ARENE["voile"].fill((0, 0, 0, 150))
    ARENE["rouge"] = pygame.Surface((LARGEUR, HAUTEUR), pygame.SRCALPHA)
    ARENE["rouge"].fill((255, 0, 0, 60))
    MP.update(f=0, fa=0.0, ver=-1, autres=[], n=1, rtt=0, tick=0)
    _arene_surfaces_init()
    if not attente:
        try:
            if j is not None:
                j.enter()
        except Exception:
            pass


def _arene_suivi_manche(j, now_srv, t_now):
    """Suit la manche partagée : nouvelle manche détectée, fin annoncée, et manche suivante lancée quand le compte à rebours est terminé."""
    A = ARENE
    if j is None:
        return
    try:
        rid, fin_at = int(j.round), int(j.endAt)
    except Exception:
        return
    A["endAt"] = fin_at
    if rid > 0 and rid != A["manche"]:
        if not TRANS["actif"]:
            lancer_transition(("arene",))                              # nouvelle manche : nouvelle carte pour tout le monde
        return
    if fin_at > 0 and now_srv >= fin_at and t_now - A["t_next"] > 1.0:
        A["t_next"] = t_now
        try:
            j.nextRound(A["manche"])
        except Exception:
            pass


def _arene_fin_manche(j, now_srv, t_now):
    """Annonce la fin de la manche : dernier joueur en vie, joueur seul éliminé ou vainqueur de ses bots, ou durée maximale."""
    A = ARENE
    if A["phase"] != "combat" or j is None or A["fin_envoye"] or A["endAt"] > 0 or not A["bots_ok"]:
        return
    participants = max(1, MP["n"])
    vivants_h = (0 if A["mort"] else 1) + sum(1 for o in MP["autres"] if int(o.get("h", 100)) > 0)
    t = (now_srv - A["debut"]) / 1000.0
    fini = (participants >= 2 and vivants_h <= 1) or (participants == 1 and (A["mort"] or A["fin"] == "victoire")) or t > A["plan"][-1]["t_fin"] + 60
    if not fini:
        A["t_fin0"] = 0.0
        return
    if A["t_fin0"] == 0.0:
        A["t_fin0"] = t_now
    elif t_now - A["t_fin0"] > 3.0:
        A["fin_envoye"] = True
        try:
            j.endRound(A["manche"])
        except Exception:
            pass


def _arene_spectateur(t_now):
    """Manche déjà trop avancée : on attend la suivante, qu'on rejoint automatiquement (le drone pour regarder viendra ensuite)."""
    A = ARENE
    j = _mp_js()
    now_srv = int(_time.time() * 1000) + A["off"]
    esc = bool(pygame.key.get_pressed()[pygame.K_ESCAPE])
    if (clic_detecte and (rect_bouton_quitter_defaite.collidepoint(clic_x, clic_y) or rect_bouton_pause.collidepoint(clic_x, clic_y))) or (esc and not A["k_esc"]):
        A["k_esc"] = esc
        _arene_quitter()
        return
    A["k_esc"] = esc
    _arene_suivi_manche(j, now_srv, t_now)
    zone = _arene_zone_etat((now_srv - A["debut"]) / 1000.0)
    PARC["x"], PARC["y"] = float(zone["c"][0]), float(zone["c"][1])
    cam_x = int(min(max(PARC["x"] - LARGEUR // 2, 0), PARC_MONDE - LARGEUR))
    cam_y = int(min(max(PARC["y"] - HAUTEUR // 2, 0), PARC_MONDE - HAUTEUR))
    _parc_gerer(cam_x, cam_y)
    for cx in range(max(0, cam_x // PARC_CH), min(PARC_NC - 1, (cam_x + LARGEUR) // PARC_CH) + 1):
        for cy in range(max(0, cam_y // PARC_CH), min(PARC_NC - 1, (cam_y + HAUTEUR) // PARC_CH) + 1):
            surf = PARC["surf"].get((cx, cy))
            px, py = cx * PARC_CH - cam_x, cy * PARC_CH - cam_y
            if surf is not None:
                ecran.blit(surf, (px, py))
            else:
                ecran.fill(_PC_HERBE, (px, py, PARC_CH, PARC_CH))
    ecran.blit(A["voile"], (0, 0))
    dessiner_titre_glitch("MANCHE EN COURS", police_titre, LARGEUR // 2, int(HAUTEUR * 0.24))
    if A["endAt"] > 0:
        txt = f"PROCHAINE MANCHE DANS {max(0, int(math.ceil((A['endAt'] - now_srv) / 1000.0)))}"
    else:
        txt = "Tu rejoindras automatiquement la prochaine manche" + "." * (1 + (pygame.time.get_ticks() // 500) % 3)
    t = rendu_texte(police_jeu, txt, True, JAUNE_CYBER)
    ecran.blit(t, (LARGEUR // 2 - t.get_width() // 2, HAUTEUR // 2 - 40))
    bouton_neon(rect_bouton_quitter_defaite, ROUGE_ALERTE, "QUITTER", police_bouton)


def _arene_quitter():
    ARENE.update(actif=False, id_aim=None, id_viser=None, id_tir=None, voile=None, rouge=None)
    mp_quitter()
    parc_liberer()
    lancer_transition(("etat", ETAT_MENU))


def _arene_geo():
    """Position des commandes tactiles : stick de visée (droite), L2 VISER au-dessus du stick gauche, R2 TIR au-dessus du stick droit."""
    aim = (LARGEUR - 230, HAUTEUR - 190)
    viser = (72, 76)                                         # L : coin haut gauche
    tir = (LARGEUR - 72, 76)                                 # R : coin haut droit
    return aim, viser, tir


def _arene_placer_aim(x, y):
    A = ARENE
    aim = _arene_geo()[0]
    vx, vy = x - aim[0], y - aim[1]
    dist = math.hypot(vx, vy)
    if dist > JOY_RAYON_SOCLE:
        vx, vy = vx / dist * JOY_RAYON_SOCLE, vy / dist * JOY_RAYON_SOCLE
    A["aim_kx"], A["aim_ky"] = vx, vy
    if dist > 12:
        A["aim_ang"], A["aim_utilise"] = math.atan2(vy, vx), True


def arene_evenement(event):
    """Multi-toucher : stick de visée, L2 (viser) et R2 (tirer). Le stick gauche garde son code habituel."""
    A = ARENE
    if event.type not in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP):
        return
    x, y = event.x * LARGEUR, event.y * HAUTEUR
    fid = event.finger_id
    if A["menu"] is not None and event.type == pygame.FINGERDOWN:
        return                                               # menu pause ouvert : les commandes ne réagissent pas
    aim, viser, tir = _arene_geo()
    if event.type == pygame.FINGERDOWN:
        if A["id_tir"] is None and math.hypot(x - tir[0], y - tir[1]) <= _AR_RBTN + 28:
            A["id_tir"], A["tir"] = fid, True
        elif A["id_viser"] is None and math.hypot(x - viser[0], y - viser[1]) <= _AR_RBTN + 28:
            A["id_viser"], A["viser"] = fid, True
        elif A["id_aim"] is None and math.hypot(x - aim[0], y - aim[1]) <= JOY_RAYON_SOCLE + 45:
            A["id_aim"], A["aim_actif"] = fid, True
            _arene_placer_aim(x, y)
    elif event.type == pygame.FINGERMOTION:
        if fid == A["id_aim"]:
            _arene_placer_aim(x, y)
    else:
        if fid == A["id_tir"]:
            A["id_tir"], A["tir"] = None, False
        if fid == A["id_viser"]:
            A["id_viser"], A["viser"] = None, False
        if fid == A["id_aim"]:
            A["id_aim"], A["aim_actif"], A["aim_kx"], A["aim_ky"] = None, False, 0.0, 0.0


# ==================== BOTS : adversaires simulés sur ton téléphone (personne d'autre ne les voit) ====================
BOTS_PROCHE = 1800.0               # moins de 1 800 px du joueur : simulation détaillée ; plus loin : simulation très légère
BOT_VIT = 390.0                    # vitesse de référence (px par seconde) = celle du joueur
_BOT_NOMS = ["Kira77", "ShadowK", "NeoWolf", "Zed_X", "Lyra", "Vortex", "Mako", "Blaze22", "Nyx", "HexOne", "Ronin", "Sparky", "Echo9",
             "Drako", "Jinx", "Kaito", "Toxic", "Raven", "Pixel", "Onyx", "Rex_99", "Vega", "Cobra", "Falco", "Storm", "Ghost47", "Titan",
             "Viper", "Luna", "Axel", "Nova", "Ryker", "Zeno", "Bolt", "Mira", "Orion", "Kobra", "Dash", "Frost", "Wraith"]
_XP_MEM = {}


def _xp_lire():
    """Expérience du joueur en Arène (gardée sur l'appareil)."""
    d = {"parties": 0, "kills": 0, "victoires": 0, "top3": 0, "recents": []}
    try:
        if IS_WEB:
            txt = _pfs.window.localStorage.getItem("flex_arene_xp")
            if txt:
                d.update(json.loads(str(txt)))
        else:
            d.update(_XP_MEM)
    except Exception:
        pass
    return d


def _xp_ecrire(d):
    try:
        if IS_WEB:
            _pfs.window.localStorage.setItem("flex_arene_xp", json.dumps(d))
        else:
            _XP_MEM.update(d)
    except Exception:
        pass


def _arene_skill_base():
    """Niveau des bots (0 = très faibles, 1 = redoutables) : monte avec l'expérience du joueur, s'ajuste selon ses derniers résultats."""
    d = _xp_lire()
    xp = d["parties"] * 10 + d["kills"] * 4 + d["victoires"] * 50 + d["top3"] * 15
    try:
        xp += min(250, 8 * int(niveau_max_atteint))                      # l'avancée dans le mode Solo compte aussi
    except Exception:
        pass
    base = 0.12 + 0.83 * (1.0 - math.exp(-xp / 900.0))
    r = d["recents"][-6:]
    if r:
        base += (0.5 - sum(r) / len(r)) * 0.3                           # il gagne souvent : un peu plus dur ; il perd tôt : un peu plus facile
    return min(0.9, max(0.08, base))


def _arene_xp_enregistrer(rang, n0, kills, victoire):
    if n0 < 2:
        return
    d = _xp_lire()
    d["parties"] += 1
    d["kills"] += int(kills)
    d["victoires"] += 1 if victoire else 0
    d["top3"] += 1 if rang <= 3 else 0
    d["recents"] = (d["recents"] + [(rang - 1) / max(1, n0 - 1)])[-8:]
    _xp_ecrire(d)


def _bot_nouveau(i, rng, skill, x, y):
    return {"id": f"bot:{i}", "p": rng.choice(_BOT_NOMS) + (str(rng.randint(2, 99)) if rng.random() < 0.4 else ""), "s": rng.choice(SKIN_IDS),
            "x": float(x), "y": float(y), "a": rng.random() * 6.2832, "hp": 100.0, "vivant": True, "skill": skill, "wp": None, "t_wp": 0.0,
            "cible": None, "los": False, "react": 0.0, "t_tir": rng.random() * 0.5, "t_perc": rng.random() * 0.25, "t_esq": 0.0,
            "t_dodge": 0.0, "dodge": (0.0, 0.0), "strafe": 1.0, "t_strafe": 1.0, "stuck": 0.0, "t_ia": 0.0, "fuite_wp": None,
            "side": rng.choice((1.0, -1.0)), "t_detour": 0.0, "detour_a": 0.0, "t_prog": 0.0, "pos_prog": (float(x), float(y)), "t_steer": 0.0, "steer_off": 0.0}


def _bots_creer():
    """Au départ du combat : seul, 13 bots ; ils disparaissent à mesure que des joueurs sont connectés (aucun à partir de 6 joueurs)."""
    A = ARENE
    n = max(0, 16 - 3 * max(1, MP["n"]))
    base = _arene_skill_base()
    A["skill_base"], A["bots"], A["balles_bot"] = base, [], []
    rng = random.Random(f"{MP['seed']}:{MP['uid']}:bots:{pygame.time.get_ticks()}")
    for i in range(n):
        x = y = PARC_MONDE // 2
        for _ in range(60):
            x, y = rng.randint(2000, PARC_MONDE - 2000), rng.randint(2000, PARC_MONDE - 2000)
            if math.hypot(x - PARC["x"], y - PARC["y"]) >= 2500 and not parc_bloque(x, y, 26):
                break
        A["bots"].append(_bot_nouveau(i, rng, min(0.98, max(0.05, base + rng.uniform(-0.15, 0.15))), x, y))
    A["bots_idx"] = {b["id"]: b for b in A["bots"]}


def _bots_cibles():
    return [(b["id"], b["x"], b["y"], {"p": b["p"], "s": b["s"], "a": b["a"], "h": int(b["hp"])}) for b in ARENE["bots"] if b["vivant"]]


def _bot_toucher(bid, degats):
    """Un tir du joueur touche un bot."""
    A = ARENE
    b = A["bots_idx"].get(bid)
    if b is None or not b["vivant"]:
        return
    b["hp"] -= degats
    if b["cible"] is None:
        b["cible"], b["react"] = "j", 0.25 + 0.5 * (1.0 - b["skill"])      # touché : il riposte
    if b["hp"] <= 0:
        b["vivant"] = False
        A["kills"] += 1
        A["fx"].append([b["x"], b["y"], pygame.time.get_ticks() / 1000.0, (255, 180, 60)])


def _bot_los(x0, y0, x1, y1):
    d = math.hypot(x1 - x0, y1 - y0)
    for i in range(1, int(d // 60) + 1):
        t = i * 60.0 / d
        if parc_bloque(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, 3):
            return False
    return True


def _bot_deplacer(b, dx, dy):
    ok = False
    if not parc_bloque(b["x"] + dx, b["y"], 16):
        b["x"] += dx
        ok = True
    if not parc_bloque(b["x"], b["y"] + dy, 16):
        b["y"] += dy
        ok = True
    return ok


def _bot_liberer(b):
    """Un bot qui se retrouve dans un obstacle en est sorti."""
    for r in (30, 60, 90, 130):
        for k in range(8):
            x, y = b["x"] + math.cos(k * 0.785) * r, b["y"] + math.sin(k * 0.785) * r
            if not parc_bloque(x, y, 16):
                b["x"], b["y"] = x, y
                return


def _bot_nouveau_wp(b, zone):
    """Destination suivante : dans la zone (ou la prochaine zone) ; 35 % du temps vers le joueur, pour qu'il y ait de l'action."""
    px, py = PARC["x"], PARC["y"]
    for _ in range(6):
        if random.random() < 0.35:
            a, d = random.random() * 6.2832, 3000.0 * math.sqrt(random.random())
            x, y = px + math.cos(a) * d, py + math.sin(a) * d
        else:
            if zone["cible"] is not None and random.random() < 0.5:
                (cx, cy), r = zone["cible"][0], zone["cible"][1] * 0.85
            else:
                (cx, cy), r = zone["c"], zone["r"] * 0.85
            a, d = random.random() * 6.2832, r * math.sqrt(random.random())
            x, y = cx + math.cos(a) * d, cy + math.sin(a) * d
        x, y = min(max(x, 800.0), PARC_MONDE - 800.0), min(max(y, 800.0), PARC_MONDE - 800.0)
        if math.hypot(x - zone["c"][0], y - zone["c"][1]) < zone["r"] * 0.95:
            break
    b["wp"], b["t_wp"] = (x, y), 0.0


def _bot_hors_zone(b, zone):
    """Vrai si le bot doit rejoindre la zone : dehors, ou trop près du bord quand elle se referme."""
    if math.hypot(b["x"] - zone["c"][0], b["y"] - zone["c"][1]) > zone["r"] - 250:
        return True
    if zone["etat"] in ("alerte", "retrecit") and zone["cible"] is not None:
        return math.hypot(b["x"] - zone["cible"][0][0], b["y"] - zone["cible"][0][1]) > zone["cible"][1] - 250
    return False


def _bot_ia_loin(b, dt, zone):
    """Bot loin du joueur : un pas léger 4 fois par seconde (une seule vérification d'obstacle), aucune balle."""
    b["t_ia"] += dt
    if b["t_ia"] < 0.25:
        return
    pas, b["t_ia"] = b["t_ia"], 0.0
    if _bot_hors_zone(b, zone):
        if b["fuite_wp"] is None:
            cx, cy = zone["cible"][0] if zone["cible"] is not None else zone["c"]
            r = (zone["cible"][1] if zone["cible"] is not None else zone["r"]) * 0.5
            a, d = random.random() * 6.2832, r * math.sqrt(random.random())
            b["fuite_wp"] = (cx + math.cos(a) * d, cy + math.sin(a) * d)
        wp = b["fuite_wp"]
    else:
        b["fuite_wp"] = None
        if b["wp"] is None or math.hypot(b["wp"][0] - b["x"], b["wp"][1] - b["y"]) < 200:
            _bot_nouveau_wp(b, zone)
        wp = b["wp"]
    dx, dy = wp[0] - b["x"], wp[1] - b["y"]
    d = math.hypot(dx, dy) or 1.0
    v = BOT_VIT * (0.70 + 0.25 * b["skill"]) * pas
    nx, ny = b["x"] + dx / d * v, b["y"] + dy / d * v
    b["a"] = math.atan2(dy, dx)
    if not parc_bloque(nx, ny, 16):
        b["x"], b["y"] = nx, ny
    else:
        b["fuite_wp"] = None
        _bot_nouveau_wp(b, zone)                                         # bloqué : on change de destination


def _bot_ia_proche(b, dt, t_now, zone, bots_vivants):
    """Bot proche du joueur : perception, combat (déplacement latéral), esquive, tir, fuite de la zone."""
    A = ARENE
    sk = b["skill"]
    px, py = PARC["x"], PARC["y"]
    joueur_vivant = not A["mort"] and not A["fin"]
    # ---- perception (4 fois par seconde)
    b["t_perc"] -= dt
    if b["t_perc"] <= 0:
        b["t_perc"] = 0.25
        vue = (800.0 + 100.0 * sk) ** 2
        meilleur = None
        if joueur_vivant:
            d2 = ((px - b["x"]) ** 2 + (py - b["y"]) ** 2) * 0.64          # il préfère le joueur
            if d2 < vue:
                meilleur = (d2, "j", px, py)
        for o in bots_vivants:
            if o is not b:
                d2 = (o["x"] - b["x"]) ** 2 + (o["y"] - b["y"]) ** 2
                if d2 < vue and (meilleur is None or d2 < meilleur[0]):
                    meilleur = (d2, o["id"], o["x"], o["y"])
        if meilleur is not None and _bot_los(b["x"], b["y"], meilleur[2], meilleur[3]):
            if b["cible"] != meilleur[1]:
                b["react"] = 0.95 - 0.7 * sk                              # temps de réaction : bien plus court pour un bot fort
            b["cible"], b["los"] = meilleur[1], True
        else:
            b["cible"], b["los"] = None, False
    cible_pos = None
    if b["cible"] == "j" and joueur_vivant:
        cible_pos = (px, py, A["pvel"][0], A["pvel"][1])
    elif b["cible"] not in (None, "j"):
        o = A["bots_idx"].get(b["cible"])
        if o is not None and o["vivant"]:
            vv = A["vel"].get(o["id"], (0.0, 0.0))
            cible_pos = (o["x"], o["y"], vv[0], vv[1])
    if cible_pos is None:
        b["cible"], b["los"] = None, False
    # ---- esquive : un tir qui arrive sur lui
    b["t_esq"] -= dt
    b["t_dodge"] -= dt
    if b["t_esq"] <= 0:
        b["t_esq"] = 0.12
        if random.random() < 0.15 + 0.8 * sk:
            menaces = A["balles"] + A["balles_bot"]
            for bl in menaces:
                rx, ry = b["x"] - bl[0], b["y"] - bl[1]
                if rx * rx + ry * ry > 320 ** 2 or (len(bl) > 5 and bl[5] == b["id"]):
                    continue
                v2 = bl[2] * bl[2] + bl[3] * bl[3]
                t_star = (rx * bl[2] + ry * bl[3]) / v2 if v2 else -1.0
                if 0.0 < t_star < 0.5 and math.hypot(rx - bl[2] * t_star, ry - bl[3] * t_star) < 50:
                    nxp, nyp = -bl[3], bl[2]
                    if nxp * rx + nyp * ry < 0:
                        nxp, nyp = -nxp, -nyp
                    nn = math.hypot(nxp, nyp) or 1.0
                    b["dodge"], b["t_dodge"] = (nxp / nn, nyp / nn), 0.3
                    break
    # ---- direction
    vit = BOT_VIT * (0.70 + 0.25 * sk) * dt
    dx = dy = 0.0
    if b["t_dodge"] > 0:
        dx, dy = b["dodge"][0] * 1.25, b["dodge"][1] * 1.25
    elif _bot_hors_zone(b, zone):
        if b["fuite_wp"] is None:
            cx, cy = zone["cible"][0] if zone["cible"] is not None else zone["c"]
            r = (zone["cible"][1] if zone["cible"] is not None else zone["r"]) * 0.5
            a, d = random.random() * 6.2832, r * math.sqrt(random.random())
            b["fuite_wp"] = (cx + math.cos(a) * d, cy + math.sin(a) * d)
        dx, dy = b["fuite_wp"][0] - b["x"], b["fuite_wp"][1] - b["y"]
    elif cible_pos is not None and b["los"]:
        b["fuite_wp"] = None
        vx, vy = cible_pos[0] - b["x"], cible_pos[1] - b["y"]
        d = math.hypot(vx, vy) or 1.0
        ux, uy = vx / d, vy / d
        b["t_strafe"] -= dt
        if b["t_strafe"] <= 0:
            b["strafe"], b["t_strafe"] = -b["strafe"], 1.0 + random.random() * 1.4
        sx_, sy_ = -uy * b["strafe"], ux * b["strafe"]
        if d > 560:
            dx, dy = ux * 0.7 + sx_ * 0.5, uy * 0.7 + sy_ * 0.5
        elif d < 260:
            dx, dy = -ux * 0.7 + sx_ * 0.5, -uy * 0.7 + sy_ * 0.5
        else:
            dx, dy = sx_, sy_
    else:
        b["fuite_wp"] = None
        b["t_wp"] += dt
        if b["wp"] is None or b["t_wp"] > 14.0 or math.hypot(b["wp"][0] - b["x"], b["wp"][1] - b["y"]) < 200:
            _bot_nouveau_wp(b, zone)
        dx, dy = b["wp"][0] - b["x"], b["wp"][1] - b["y"]
    b["t_detour"] -= dt
    if b["t_detour"] > 0:                                                # bloqué à l'instant : il part dans une autre direction un moment
        dx, dy = math.cos(b["detour_a"]), math.sin(b["detour_a"])
    n = math.hypot(dx, dy)
    if n > 1e-6:
        a0 = math.atan2(dy, dx)
        b["t_steer"] -= dt
        if b["t_steer"] <= 0:                                            # 5 fois par seconde : il cherche la direction la plus dégagée vers sa destination
            b["t_steer"] = 0.2
            meilleur = None
            for k_ in (0, b["side"], -b["side"], 2 * b["side"], -2 * b["side"], 3 * b["side"], -3 * b["side"], 4 * b["side"], -4 * b["side"],
                       5 * b["side"], -5 * b["side"], 6 * b["side"], -6 * b["side"], 8 * b["side"], -8 * b["side"]):
                a1 = a0 + k_ * 0.39
                clair = 0
                for d_ in (45, 90, 140):
                    if parc_bloque(b["x"] + math.cos(a1) * d_, b["y"] + math.sin(a1) * d_, 16):
                        break
                    clair = d_
                score = clair - abs(k_) * 18
                if meilleur is None or score > meilleur[0]:
                    meilleur = (score, a1 - a0)
            b["steer_off"] = meilleur[1]
        a1 = a0 + b["steer_off"]
        dx, dy = math.cos(a1) * vit, math.sin(a1) * vit
        av = (b["x"], b["y"])
        if parc_bloque(b["x"], b["y"], 16):
            _bot_liberer(b)
        if _bot_deplacer(b, dx, dy):
            b["stuck"] = max(0.0, b["stuck"] - dt)
            A["vel"][b["id"]] = [(b["x"] - av[0]) / dt, (b["y"] - av[1]) / dt]
        else:
            b["stuck"] += dt
            A["vel"][b["id"]] = [0.0, 0.0]
            if b["stuck"] > 0.5:
                b["stuck"], b["strafe"], b["side"], b["fuite_wp"] = 0.0, -b["strafe"], -b["side"], None
                b["t_detour"], b["detour_a"] = 0.9, random.random() * 6.2832
                _bot_nouveau_wp(b, zone)
        if cible_pos is None or not b["los"]:
            b["a"] = math.atan2(dy, dx)
        b["t_prog"] += dt
        if b["t_prog"] >= 0.5:
            fait = math.hypot(b["x"] - b["pos_prog"][0], b["y"] - b["pos_prog"][1])
            b["t_prog"], b["pos_prog"] = 0.0, (b["x"], b["y"])
            if fait < 0.3 * vit / dt * 0.5 and b["t_detour"] <= 0:
                b["side"], b["fuite_wp"] = -b["side"], None
                b["t_detour"], b["detour_a"] = 0.9, random.random() * 6.2832
    # ---- tir
    b["t_tir"] -= dt
    b["react"] -= dt
    if cible_pos is not None and b["los"] and b["react"] <= 0 and b["t_tir"] <= 0 and A["phase"] == "combat":
        d = math.hypot(cible_pos[0] - b["x"], cible_pos[1] - b["y"])
        if d <= 700.0 + 150.0 * sk:
            b["t_tir"] = ARENE_CADENCE * (1.6 - 0.6 * sk)
            t_vol = d / ARENE_V_BALLE
            lead = min(1.0, sk * 1.2)
            ax = cible_pos[0] + cible_pos[2] * t_vol * lead
            ay = cible_pos[1] + cible_pos[3] * t_vol * lead
            ang = math.atan2(ay - b["y"], ax - b["x"]) + random.gauss(0.0, (0.28 - 0.25 * sk) * min(2.0, d / 500.0))
            b["a"] = ang
            A["balles_bot"].append([b["x"] + math.cos(ang) * 26, b["y"] + math.sin(ang) * 26, math.cos(ang) * ARENE_V_BALLE,
                                    math.sin(ang) * ARENE_V_BALLE, ARENE_PORTEE / ARENE_V_BALLE, b["id"]])


def _bots_maj(dt, t_now, zone):
    """Fait vivre tous les bots : détaillé près du joueur, léger au loin ; combats lointains résolus par calcul ; dégâts de zone ; tirs."""
    A = ARENE
    px, py = PARC["x"], PARC["y"]
    bots = [b for b in A["bots"] if b["vivant"]]
    # nombre de bots selon les joueurs connectés (aucun à partir de 6 joueurs)
    A["t_ajust"] -= dt
    if A["t_ajust"] <= 0:
        A["t_ajust"] = 1.0
        cible_n = max(0, 16 - 3 * max(1, MP["n"]))
        if len(bots) > cible_n:
            bots.sort(key=lambda b: -((b["x"] - px) ** 2 + (b["y"] - py) ** 2))
            for b in bots[:len(bots) - cible_n]:
                b["vivant"] = False                                      # les plus éloignés quittent la partie
            bots = [b for b in bots if b["vivant"]]
    proches = [b for b in bots if (b["x"] - px) ** 2 + (b["y"] - py) ** 2 < BOTS_PROCHE ** 2]
    loin = [b for b in bots if b not in proches]
    for b in proches:
        _bot_ia_proche(b, dt, t_now, zone, proches)
    for b in loin:
        _bot_ia_loin(b, dt, zone)
    # combats entre bots éloignés du joueur : résolus par un calcul (aucune balle)
    for i in range(len(loin)):
        for j_ in range(i + 1, len(loin)):
            a_, b_ = loin[i], loin[j_]
            if (a_["x"] - b_["x"]) ** 2 + (a_["y"] - b_["y"]) ** 2 < 500 ** 2:
                a_["hp"] -= 5.0 * (0.5 + b_["skill"]) * dt
                b_["hp"] -= 5.0 * (0.5 + a_["skill"]) * dt
    # zone : mêmes dégâts que pour un joueur
    if zone["dps"] > 0:
        for b in bots:
            if math.hypot(b["x"] - zone["c"][0], b["y"] - zone["c"][1]) > zone["r"]:
                b["hp"] -= zone["dps"] * dt
    for b in bots:
        if b["hp"] <= 0:
            b["vivant"] = False
    # tirs des bots
    nouvelles = []
    for bl in A["balles_bot"]:
        bl[4] -= dt
        if bl[4] <= 0:
            continue
        n = int(ARENE_V_BALLE * dt / 14.0) + 1
        sx_, sy_ = bl[2] * dt / n, bl[3] * dt / n
        fini = False
        for _ in range(n):
            bl[0] += sx_
            bl[1] += sy_
            if parc_bloque(bl[0], bl[1], 2):
                fini = True
                break
            if not A["mort"] and not A["fin"] and A["phase"] == "combat" and (bl[0] - px) ** 2 + (bl[1] - py) ** 2 < (ARENE_R_JOUEUR + 4) ** 2:
                A["hp"] -= ARENE_DEGATS
                A["degat_t"] = t_now
                A["fx"].append([bl[0], bl[1], t_now, ROUGE_ALERTE])
                if A["hp"] <= 0:
                    A["hp"], A["mort"], A["rang"] = 0, True, max(1, _arene_vivants())
                fini = True
                break
            for o in proches:
                if o["vivant"] and o["id"] != bl[5] and (bl[0] - o["x"]) ** 2 + (bl[1] - o["y"]) ** 2 < (ARENE_R_JOUEUR + 4) ** 2:
                    o["hp"] -= ARENE_DEGATS
                    A["fx"].append([bl[0], bl[1], t_now, (255, 180, 60)])
                    if o["hp"] <= 0:
                        o["vivant"] = False
                    fini = True
                    break
            if fini:
                break
        if not fini:
            nouvelles.append(bl)
    A["balles_bot"] = nouvelles
    if len(A["bots"]) != len(bots) or any(not b["vivant"] for b in A["bots"]):
        A["bots"] = [b for b in A["bots"] if b["vivant"]]
        A["bots_idx"] = {b["id"]: b for b in A["bots"]}


def _bots_dessiner_balles(ox, oy):
    for bl in ARENE["balles_bot"]:
        bx, by = int(bl[0] + ox), int(bl[1] + oy)
        if -50 < bx < LARGEUR + 50 and -50 < by < HAUTEUR + 50:
            DRAW.line(ecran, (255, 170, 60), (bx, by), (int(bx - bl[2] * 0.03), int(by - bl[3] * 0.03)), 4)


def _arene_zone_plan(seed):
    """Plan complet de la zone, calculé à partir du numéro de la partie : identique sur tous les téléphones, aucun échange réseau."""
    rng = random.Random(f"zone:{seed}")
    plan, t = [], 0.0
    c_prev, r_prev = (PARC_MONDE / 2.0, PARC_MONDE / 2.0), float(ARENE_R0)   # on part du milieu de la carte
    lo, hi = 4000.0, PARC_MONDE - 4000.0                                     # les centres restent loin des bords : la zone finale est toujours sur la carte
    for i, (calme, alerte, retrec, r_new, dps) in enumerate(ARENE_PHASES):
        marge = r_prev - r_new                                           # la nouvelle zone reste dans l'ancienne
        a, d = rng.random() * 6.2832, marge * math.sqrt(rng.random()) * 0.9
        c_new = (min(max(c_prev[0] + math.cos(a) * d, lo), hi), min(max(c_prev[1] + math.sin(a) * d, lo), hi))
        plan.append({"i": i, "t_alerte": t + calme, "t_debut": t + calme + alerte, "t_fin": t + calme + alerte + retrec,
                     "c0": c_prev, "r0": r_prev, "c1": c_new, "r1": float(r_new), "dps": dps})
        t += calme + alerte + retrec
        c_prev, r_prev = c_new, float(r_new)
    return plan


def _arene_zone_etat(t):
    """Zone à l'instant t (secondes depuis le début du combat) : cercle, état (calme / alerte / retrecit / finale), dégâts, prochaine zone."""
    plan = ARENE["plan"]
    if not plan:
        return {"etat": "lobby", "phase": 0, "c": (0.0, 0.0), "r": 1e9, "cible": None, "dps": 0.0, "debut_dans": 0.0, "depuis_debut": 0.0, "prochaine": 0.0}
    if t < 0:
        p = plan[0]
        return {"etat": "lobby", "phase": 0, "c": p["c0"], "r": p["r0"], "cible": (p["c1"], p["r1"]), "dps": 0.0,
                "debut_dans": 0.0, "depuis_debut": 0.0, "prochaine": p["t_alerte"]}
    for p in plan:
        if t < p["t_fin"]:
            cible = (p["c1"], p["r1"])
            if t < p["t_alerte"]:
                return {"etat": "calme", "phase": p["i"], "c": p["c0"], "r": p["r0"], "cible": cible, "dps": p["dps"],
                        "debut_dans": 0.0, "depuis_debut": 0.0, "prochaine": p["t_alerte"] - t}
            if t < p["t_debut"]:
                return {"etat": "alerte", "phase": p["i"], "c": p["c0"], "r": p["r0"], "cible": cible, "dps": p["dps"],
                        "debut_dans": p["t_debut"] - t, "depuis_debut": 0.0, "prochaine": 0.0}
            f = (t - p["t_debut"]) / (p["t_fin"] - p["t_debut"])
            return {"etat": "retrecit", "phase": p["i"],
                    "c": (p["c0"][0] + (p["c1"][0] - p["c0"][0]) * f, p["c0"][1] + (p["c1"][1] - p["c0"][1]) * f),
                    "r": p["r0"] + (p["r1"] - p["r0"]) * f, "cible": cible, "dps": p["dps"],
                    "debut_dans": 0.0, "depuis_debut": t - p["t_debut"], "prochaine": 0.0}
    p = plan[-1]
    return {"etat": "finale", "phase": len(plan), "c": p["c1"], "r": p["r1"], "cible": None, "dps": ARENE_DPS_FINAL,
            "debut_dans": 0.0, "depuis_debut": 0.0, "prochaine": 0.0}


def _arene_zone_sur(tint, centre, rayon, cible, zone, largeur):
    """Dessine sur une surface transparente (radar ou grande carte) : teinte rouge hors de la zone, anneau de la zone, anneau de la prochaine zone.
    En alerte, tout clignote en rouge."""
    ticks = pygame.time.get_ticks()
    alerte = zone["etat"] == "alerte"
    flash = alerte and (ticks // 220) % 2 == 0
    alpha = (150 if flash else 70) if alerte else (110 if zone["etat"] == "retrecit" else 90)
    tint.fill((220, 20, 30, alpha))
    pygame.draw.circle(tint, (0, 0, 0, 0), (int(centre[0]), int(centre[1])), max(1, int(rayon)))
    rouge = flash or zone["etat"] == "retrecit"
    pygame.draw.circle(tint, (255, 50, 50, 255) if rouge else (245, 245, 255, 255), (int(centre[0]), int(centre[1])), max(1, int(rayon)), largeur)
    if cible is not None:
        pygame.draw.circle(tint, (255, 90, 90, 255) if flash else (255, 255, 255, 255), (int(cible[0][0]), int(cible[0][1])), max(1, int(cible[1])), 1)


def _arene_anneau_monde(c, r, ox, oy, couleur, largeur):
    """Anneau de la zone dans le monde : seul l'arc visible à l'écran est tracé (léger pour le téléphone)."""
    cx, cy = c[0] + ox, c[1] + oy
    px, py = PARC["x"] + ox, PARC["y"] + oy
    d = math.hypot(px - cx, py - cy)
    if abs(d - r) > 900:
        return
    if r < 340:
        pts = [(cx + math.cos(a * 6.2832 / 48) * r, cy + math.sin(a * 6.2832 / 48) * r) for a in range(49)]
    else:
        centre = math.atan2(py - cy, px - cx)
        demi = min(3.1416, 1100.0 / r)
        n = max(10, min(70, int(2 * demi * r / 36)))
        pts = [(cx + math.cos(centre - demi + 2 * demi * i / n) * r, cy + math.sin(centre - demi + 2 * demi * i / n) * r) for i in range(n + 1)]
    pygame.draw.lines(ecran, couleur, False, pts, largeur)


def _arene_vignette(intensite):
    for surf, pos in ARENE["strips"]:
        surf.set_alpha(int(intensite))
        ecran.blit(surf, pos)


def _arene_zone_hud(zone, dehors):
    """Alerte rouge « la zone rétrécit dans 10, 9... 0 », puis état de la zone."""
    ticks = pygame.time.get_ticks()
    et = zone["etat"]
    nb = len(ARENE_PHASES)
    y = 72
    if et == "alerte":
        n = int(zone["debut_dans"] + 0.5)
        col = (255, 40, 40) if (ticks // 250) % 2 == 0 else (255, 190, 190)
        t = rendu_texte(police_jeu, f"ALERTE : LA ZONE RÉTRÉCIT DANS {n}", True, col)
        ecran.blit(t, (LARGEUR // 2 - t.get_width() // 2, y + 6))
        y += 44
    elif et == "retrecit" and zone["depuis_debut"] < 4.0:
        t = rendu_texte(police_jeu, "LA ZONE RÉTRÉCIT !", True, (255, 40, 40))
        ecran.blit(t, (LARGEUR // 2 - t.get_width() // 2, y + 6))
        y += 44
    else:
        if et == "calme":
            m, sec = divmod(int(zone["prochaine"]) + 1, 60)
            txt = f"ZONE {zone['phase'] + 1}/{nb}   •   PROCHAINE ALERTE DANS {m}:{sec:02d}"
        elif et == "retrecit":
            txt = f"ZONE {zone['phase'] + 1}/{nb}   •   EN RÉTRÉCISSEMENT"
        elif et == "finale":
            txt = "ZONE FINALE"
        else:
            txt = ""
        if txt:
            t = rendu_texte(police_petite, txt, True, BLANC_NEON)
            ecran.blit(t, (LARGEUR // 2 - t.get_width() // 2, y))
            y += 30
    if dehors:
        col = (255, 60, 60) if (ticks // 300) % 2 == 0 else (255, 200, 200)
        t = rendu_texte(police_petite, f"HORS ZONE !   -{zone['dps']:.0f} PV par seconde", True, col)
        ecran.blit(t, (LARGEUR // 2 - t.get_width() // 2, y))


def _arene_cap(ang):
    return ["E", "SE", "S", "SO", "O", "NO", "N", "NE"][int(round(ang / (math.pi / 4))) % 8]


def _arene_verrouiller(cibles):
    """Bouton L : verrouille le joueur le plus proche (et le garde tant qu'il reste à portée) ; retourne (identifiant, x, y) visés un peu devant lui."""
    A = ARENE
    x, y = PARC["x"], PARC["y"]
    choisi = None
    if A["lock"] is not None:
        for u, px, py, o in cibles:
            if u == A["lock"] and math.hypot(px - x, py - y) <= ARENE_LOCK * 1.25:
                choisi = (u, px, py)
                break
    if choisi is None:
        meilleur = None
        for u, px, py, o in cibles:
            d2 = (px - x) ** 2 + (py - y) ** 2
            if d2 <= ARENE_LOCK ** 2 and (meilleur is None or d2 < meilleur[0]):
                meilleur = (d2, u, px, py)
        if meilleur is not None:
            choisi = (meilleur[1], meilleur[2], meilleur[3])
    A["lock"] = choisi[0] if choisi else None
    if choisi is None:
        return None
    u, px, py = choisi
    vx, vy = A["vel"].get(u, (0.0, 0.0))
    t = min(0.8, math.hypot(px - x, py - y) / ARENE_V_BALLE)       # temps de vol du tir : on vise là où il sera
    return u, px + vx * t, py + vy * t


def _arene_silhouette(surf, cx, cy, ox, oy, k, arbres):
    """Silhouette d'une zone (routes, bâtiments, eau, rochers, arbres) à l'échelle k, avec son coin haut gauche en (ox, oy)."""
    d = _parc_gen(cx, cy)
    x0, y0 = cx * PARC_CH, cy * PARC_CH
    dr = pygame.draw
    route = (46, 58, 98)
    lr = max(1, int(PARC_LARG_ALLEE * k))
    kx = round((x0 + PARC_CH // 2 - PARC_DEC) / PARC_PAS)
    ky = round((y0 + PARC_CH // 2 - PARC_DEC) / PARC_PAS)
    if 0 <= kx < PARC_NAXES:
        ax = PARC_DEC + kx * PARC_PAS
        if x0 - 80 < ax < x0 + PARC_CH + 80:
            dr.rect(surf, route, (ox + (ax - x0) * k - lr / 2, oy, lr, PARC_CH * k))
    if 0 <= ky < PARC_NAXES:
        ay = PARC_DEC + ky * PARC_PAS
        if y0 - 80 < ay < y0 + PARC_CH + 80:
            dr.rect(surf, route, (ox, oy + (ay - y0) * k - lr / 2, PARC_CH * k, lr))
    pl = _parc_place_proche(x0 + PARC_CH // 2, y0 + PARC_CH // 2)
    if pl is not None:
        dr.circle(surf, route, (int(ox + (pl[0] - x0) * k), int(oy + (pl[1] - y0) * k)), max(2, int(PARC_R_PLACE * k)))
    for ex, ey, rx, ry in d["etangs"]:
        dr.ellipse(surf, (30, 84, 150), (ox + (ex - x0 - rx) * k, oy + (ey - y0 - ry) * k, max(2, rx * 2 * k), max(2, ry * 2 * k)))
    for x, y, r in d["rochers"]:
        dr.circle(surf, (120, 90, 190), (int(ox + (x - x0) * k), int(oy + (y - y0) * k)), max(1, int(r * k)))
    if arbres:
        for x, y, r in d["arbres"]:
            dr.circle(surf, (22, 92, 86), (int(ox + (x - x0) * k), int(oy + (y - y0) * k)), max(1, int(r * k * 0.8)))
    for bx, by, bw, bh, _c in d["batiments"]:
        rect = (ox + (bx - x0) * k, oy + (by - y0) * k, max(2, bw * k), max(2, bh * k))
        dr.rect(surf, (96, 78, 190), rect)
        if bw * k >= 6:
            dr.rect(surf, (0, 225, 255), rect, 1)
    if d["fontaine"]:
        fx, fy, fr = d["fontaine"]
        dr.circle(surf, (40, 100, 170), (int(ox + (fx - x0) * k), int(oy + (fy - y0) * k)), max(2, int(fr * k)))


def _arene_surfaces_init():
    """Surfaces de l'arène : radar rond (avec son masque), grande carte (qui se remplit au fil de l'exploration)."""
    A = ARENE
    R = _AR_RADAR_R
    rad = pygame.Surface((R * 2, R * 2))
    rad.set_colorkey((255, 0, 255))
    masque = pygame.Surface((R * 2, R * 2), pygame.SRCALPHA)
    masque.fill((255, 0, 255, 255))
    pygame.draw.circle(masque, (0, 0, 0, 0), (R, R), R)
    t = min(HAUTEUR - 80, int(LARGEUR * 0.55), 560)
    carte = pygame.Surface((t, t))
    carte.fill((10, 16, 22))
    k = t / PARC_MONDE
    for i in range(PARC_NAXES):                                          # grille des allées (repères discrets)
        a = int((PARC_DEC + i * PARC_PAS) * k)
        pygame.draw.line(carte, (30, 40, 52), (a, 0), (a, t), 1)
        pygame.draw.line(carte, (30, 40, 52), (0, a), (t, a), 1)
    for i in range(1, PARC_NAXES, 3):                                    # places avec fontaine
        for j in range(1, PARC_NAXES, 3):
            pygame.draw.circle(carte, (46, 60, 76), (int((PARC_DEC + i * PARC_PAS) * k), int((PARC_DEC + j * PARC_PAS) * k)), max(3, int(PARC_R_PLACE * k)))
    A["radar"], A["radar_masque"], A["carte_surf"], A["carte_t"], A["decouv"], A["thumbs"] = rad, masque, carte, t, set(), {}
    A["radar_zone"] = pygame.Surface((R * 2, R * 2), pygame.SRCALPHA)
    A["carte_zone"] = pygame.Surface((t, t), pygame.SRCALPHA)
    e = 36                                                               # bandes rouges sur les bords de l'écran (zone / alerte)
    bandes = []
    for w, h, pos in ((LARGEUR, e, (0, 0)), (LARGEUR, e, (0, HAUTEUR - e)), (e, HAUTEUR, (0, 0)), (e, HAUTEUR, (LARGEUR - e, 0))):
        b = pygame.Surface((w, h), pygame.SRCALPHA)
        b.fill((255, 0, 0, 255))
        bandes.append((b, pos))
    A["strips"] = bandes


def _arene_carte_maj():
    """Dessine sur la grande carte la silhouette des zones que tu viens de découvrir (une zone par image)."""
    A = ARENE
    if A["carte_surf"] is None:
        return
    for cle in PARC["surf"]:
        if cle not in A["decouv"]:
            k = A["carte_t"] / PARC_MONDE
            _arene_silhouette(A["carte_surf"], cle[0], cle[1], cle[0] * PARC_CH * k, cle[1] * PARC_CH * k, k, False)
            A["decouv"].add(cle)
            return


def _arene_thumb(cx, cy):
    A = ARENE
    th = A["thumbs"].get((cx, cy))
    if th is None:
        th = pygame.Surface((_AR_TS, _AR_TS))
        th.fill((12, 22, 30))
        _arene_silhouette(th, cx, cy, 0, 0, _AR_TS / PARC_CH, True)
        A["thumbs"][(cx, cy)] = th
    return th


def _arene_radar_dessiner(cibles, ang, zone=None):
    """Radar rond (coin bas gauche) : la vraie silhouette du lieu où tu te trouves, en temps réel. Bleu = toi, rouge = adversaires (position approximative)."""
    A = ARENE
    R = _AR_RADAR_R
    cxs, cys = R + 16, HAUTEUR - R - 14
    px, py = PARC["x"], PARC["y"]
    k = _AR_TS / PARC_CH
    rad = A["radar"]
    rad.fill((12, 22, 30))
    portee = R / k
    for cx in range(max(0, int((px - portee) // PARC_CH)), min(PARC_NC - 1, int((px + portee) // PARC_CH)) + 1):
        for cy in range(max(0, int((py - portee) // PARC_CH)), min(PARC_NC - 1, int((py + portee) // PARC_CH)) + 1):
            rad.blit(_arene_thumb(cx, cy), (int((cx * PARC_CH - px) * k + R), int((cy * PARC_CH - py) * k + R)))
    if zone is not None and A["radar_zone"] is not None:
        zc = ((zone["c"][0] - px) * k + R, (zone["c"][1] - py) * k + R)
        zt = None if zone["cible"] is None else (((zone["cible"][0][0] - px) * k + R, (zone["cible"][0][1] - py) * k + R), zone["cible"][1] * k)
        _arene_zone_sur(A["radar_zone"], zc, zone["r"] * k, zt, zone, 2)
        rad.blit(A["radar_zone"], (0, 0))
    rad.blit(A["radar_masque"], (0, 0))
    pcx, pcy = int(px // PARC_CH), int(py // PARC_CH)
    for cle in [c for c in A["thumbs"] if abs(c[0] - pcx) > 3 or abs(c[1] - pcy) > 3]:
        del A["thumbs"][cle]
    ecran.blit(rad, (cxs - R, cys - R))
    DRAW.circle(ecran, (0, 70, 95), (cxs, cys), R // 2, 1)
    a_b = pygame.time.get_ticks() / 900.0
    DRAW.line(ecran, (0, 150, 110), (cxs, cys), (int(cxs + math.cos(a_b) * (R - 3)), int(cys + math.sin(a_b) * (R - 3))), 2)
    DRAW.circle(ecran, BLEU_CYBER, (cxs, cys), R, 3)
    pulse = 8 + int(3 * abs(math.sin(pygame.time.get_ticks() / 300.0)))
    for u, ex, ey, o in cibles:
        ex, ey = round(ex / 100.0) * 100.0, round(ey / 100.0) * 100.0                # position approximative
        dx_, dy_ = (ex - px) * k, (ey - py) * k
        d_ = math.hypot(dx_, dy_)
        if d_ <= R - 8:
            pos = (int(cxs + dx_), int(cys + dy_))
            DRAW.circle(ecran, (255, 130, 130), pos, pulse, 1)
            DRAW.circle(ecran, (0, 0, 0), pos, 7)
            DRAW.circle(ecran, (235, 40, 50), pos, 5)
        else:                                                                       # hors du radar : flèche rouge sur le bord
            ux, uy = dx_ / d_, dy_ / d_
            bx, by = cxs + ux * (R - 13), cys + uy * (R - 13)
            pygame.draw.polygon(ecran, (235, 40, 50), [(cxs + ux * (R - 2), cys + uy * (R - 2)), (bx - uy * 6, by + ux * 6), (bx + uy * 6, by - ux * 6)])
    DRAW.line(ecran, BLANC_NEON, (cxs, cys), (int(cxs + math.cos(ang) * 15), int(cys + math.sin(ang) * 15)), 2)
    DRAW.circle(ecran, BLANC_NEON, (cxs, cys), 8)
    DRAW.circle(ecran, (40, 140, 255), (cxs, cys), 6)


def _arene_dessiner_carte(cibles, ang, vivants, nom_biome, zone=None):
    """Grande carte (menu pause) : ce que tu as exploré, toi en bleu, les adversaires en rouge (positions approximatives)."""
    A = ARENE
    t = A["carte_t"]
    x0, y0 = LARGEUR // 2 - t // 2, (HAUTEUR - t) // 2 + 10
    ecran.blit(A["carte_surf"], (x0, y0))
    k = t / PARC_MONDE
    if zone is not None and A["carte_zone"] is not None:
        zt = None if zone["cible"] is None else ((zone["cible"][0][0] * k, zone["cible"][0][1] * k), zone["cible"][1] * k)
        _arene_zone_sur(A["carte_zone"], (zone["c"][0] * k, zone["c"][1] * k), zone["r"] * k, zt, zone, 3)
        ecran.blit(A["carte_zone"], (x0, y0))
    DRAW.rect(ecran, (230, 240, 230), (x0, y0, t, t), 3)
    mx, my = x0 + PARC["x"] * k, y0 + PARC["y"] * k
    pulse = 9 + int(3 * abs(math.sin(pygame.time.get_ticks() / 300.0)))
    proche = None
    for u, px, py, o in cibles:
        ex, ey = x0 + round(px / 100.0) * 100.0 * k, y0 + round(py / 100.0) * 100.0 * k
        DRAW.circle(ecran, (255, 130, 130), (int(ex), int(ey)), pulse, 1)
        DRAW.circle(ecran, (0, 0, 0), (int(ex), int(ey)), 8)
        DRAW.circle(ecran, (235, 40, 50), (int(ex), int(ey)), 6)
        d = math.hypot(px - PARC["x"], py - PARC["y"])
        if proche is None or d < proche[0]:
            proche = (d, ex, ey, math.atan2(py - PARC["y"], px - PARC["x"]))
    if proche is not None:
        DRAW.line(ecran, (255, 255, 255), (int(mx), int(my)), (int(proche[1]), int(proche[2])), 1)
    DRAW.line(ecran, BLANC_NEON, (int(mx), int(my)), (int(mx + math.cos(ang) * 16), int(my + math.sin(ang) * 16)), 2)
    DRAW.circle(ecran, BLANC_NEON, (int(mx), int(my)), 9)
    DRAW.circle(ecran, (40, 140, 255), (int(mx), int(my)), 7)
    DRAW.rect(ecran, (8, 12, 18), (x0, y0, t, 26))
    if zone is not None and zone["etat"] == "alerte":
        t1 = rendu_texte(police_petite, f"ALERTE : LA ZONE RÉTRÉCIT DANS {int(zone['debut_dans'] + 0.5)}", True,
                         (255, 40, 40) if (pygame.time.get_ticks() // 250) % 2 == 0 else (255, 190, 190))
    elif zone is not None and zone["etat"] == "retrecit":
        t1 = rendu_texte(police_petite, "LA ZONE RÉTRÉCIT", True, (255, 40, 40))
    else:
        t1 = rendu_texte(police_petite, "CARTE", True, BLANC_NEON)
    ecran.blit(t1, (x0 + t // 2 - t1.get_width() // 2, y0 + 3))
    DRAW.rect(ecran, (8, 12, 18), (x0, y0 + t - 78, t, 78))
    txt = f"PLUS PROCHE : à environ {int(proche[0] / 40)} m ({_arene_cap(proche[3])})" if proche is not None else "AUCUN ADVERSAIRE EN VIE"
    t2 = rendu_texte(police_petite, txt, True, JAUNE_CYBER)
    ecran.blit(t2, (x0 + t // 2 - t2.get_width() // 2, y0 + t - 74))
    t3 = rendu_texte(police_petite, f"EN VIE {vivants}   •   {nom_biome.upper()}   •   ZONES EXPLORÉES {len(A['decouv'])}", True, BLANC_NEON)
    ecran.blit(t3, (x0 + t // 2 - t3.get_width() // 2, y0 + t - 50))
    lx, ly = x0 + 12, y0 + t - 18
    for coul, lab in (((40, 140, 255), "TOI"), ((235, 40, 50), "ADVERSAIRES (approx.)")):
        DRAW.circle(ecran, coul, (lx + 6, ly), 6)
        tn = rendu_texte(police_petite, lab, True, BLANC_NEON)
        ecran.blit(tn, (lx + 18, ly - 12))
        lx += 18 + tn.get_width() + 20
    DRAW.circle(ecran, (245, 245, 255), (lx + 6, ly), 6, 2)
    tn = rendu_texte(police_petite, "ZONE SÛRE", True, BLANC_NEON)
    ecran.blit(tn, (lx + 18, ly - 12))


def _arene_rects_menu():
    cx, y = LARGEUR // 2, int(HAUTEUR * 0.36)
    return {"reprendre": pygame.Rect(cx - 150, y, 300, 56), "carte": pygame.Rect(cx - 150, y + 72, 300, 56),
            "quitter": pygame.Rect(cx - 150, y + 144, 300, 56), "retour": pygame.Rect(24, 24, 190, 56)}


def _arene_menu(nom):
    """Ouvre / ferme le menu pause (la partie continue pour les autres) ; les commandes tactiles sont relâchées."""
    A = ARENE
    A["menu"] = nom
    if nom is not None:
        A.update(tir=False, viser=False, aim_actif=False, id_tir=None, id_viser=None, id_aim=None, aim_kx=0.0, aim_ky=0.0)


def _arene_dessiner_menu(cibles, ang, vivants, zone=None):
    A = ARENE
    ecran.blit(A["voile"], (0, 0))
    r = _arene_rects_menu()
    if A["menu"] == "pause":
        dessiner_titre_glitch("PAUSE", police_titre, LARGEUR // 2, int(HAUTEUR * 0.18))
        t = rendu_texte(police_petite, "La partie continue pour les autres joueurs", True, JAUNE_CYBER)
        ecran.blit(t, (LARGEUR // 2 - t.get_width() // 2, int(HAUTEUR * 0.18) + 56))
        bouton_neon(r["reprendre"], VERT_FLUO, "REPRENDRE", police_bouton)
        bouton_neon(r["carte"], CYAN_NEON, "CARTE", police_bouton)
        bouton_neon(r["quitter"], ROUGE_ALERTE, "QUITTER", police_bouton)
    else:
        _arene_dessiner_carte(cibles, ang, vivants, _PC_BIOMES[_parc_biome(int(PARC["x"] // PARC_CH), int(PARC["y"] // PARC_CH))], zone)
        bouton_neon(r["retour"], JAUNE_CYBER, "< RETOUR", police_bouton)


def _arene_echanger(j, ang):
    """Envoie notre état (position, tirs, vie), reçoit celui des autres joueurs et les coups qu'on nous a portés."""
    A = ARENE
    j.send(float(PARC["x"]), float(PARC["y"]), float(ang), int(MP["f"]), float(MP["fa"]), int(max(0, A["hp"])))
    v = int(j.ver)
    if v != MP["ver"]:
        MP["ver"] = v
        tous = [o for o in json.loads(str(j.json)) if int(o.get("r", 0)) == A["manche"]]
        MP["n"] = len(tous)
        MP["autres"] = [o for o in tous if o.get("u") != MP["uid"]]
        for o in MP["autres"]:                               # tirs des autres joueurs (affichage seulement)
            u, f = o.get("u"), int(o.get("f", 0))
            vu = A["f_vu"].get(u)
            A["f_vu"][u] = f
            if vu is not None and f > vu and int(o.get("h", 100)) > 0:
                a = float(o.get("fa", 0))
                for q in range(min(f - vu, 3)):
                    A["balles_d"].append([float(o.get("x", 0)) + math.cos(a) * (26 - 40 * q), float(o.get("y", 0)) + math.sin(a) * (26 - 40 * q),
                                          math.cos(a) * ARENE_V_BALLE, math.sin(a) * ARENE_V_BALLE, ARENE_PORTEE / ARENE_V_BALLE, _mp_couleur(u)])
                if len(A["balles_d"]) > 60:
                    del A["balles_d"][:20]
    MP["tick"] += 1
    if MP["tick"] % 30 == 0:
        MP["rtt"] = int(j.rtt)
    return json.loads(str(j.takeHits()))


def _arene_maj_autres(dt, maintenant):
    """Lisse la position des autres joueurs et retourne ceux qui sont encore en vie."""
    A = ARENE
    lisse = A["lisse"]
    k = 1.0 - math.exp(-dt * 10.0)
    vus, cibles = set(), []
    for o in MP["autres"]:
        u = str(o.get("u", ""))
        vus.add(u)
        tx, ty = float(o.get("x", 0)), float(o.get("y", 0))
        p = lisse.get(u)
        if p is None or abs(tx - p[0]) + abs(ty - p[1]) > 500:
            p = lisse[u] = [tx, ty]
            A["vel"][u] = [0.0, 0.0]
        ax_, ay_ = p[0], p[1]
        p[0] += (tx - p[0]) * k
        p[1] += (ty - p[1]) * k
        v_ = A["vel"].setdefault(u, [0.0, 0.0])
        v_[0] = v_[0] * 0.85 + (p[0] - ax_) / dt * 0.15
        v_[1] = v_[1] * 0.85 + (p[1] - ay_) / dt * 0.15
        vivant = int(o.get("h", 100)) > 0
        if A["vivants_vu"].get(u, True) and not vivant and maintenant - A["hits"].get(u, -99.0) < 3.0:
            A["kills"] += 1                                  # il vient de mourir juste après un de nos tirs
        A["vivants_vu"][u] = vivant
        if vivant:
            cibles.append((u, p[0], p[1], o))
    for u in list(lisse):
        if u not in vus:
            del lisse[u]
    return cibles


def _arene_vivants():
    return (0 if ARENE["mort"] else 1) + sum(1 for o in MP["autres"] if int(o.get("h", 100)) > 0) + sum(1 for b in ARENE["bots"] if b["vivant"])


def _arene_dessiner_joueurs(cibles, ox, oy):
    for u, px, py, o in cibles:
        sx, sy = int(px + ox), int(py + oy)
        if sx < -80 or sx > LARGEUR + 80 or sy < -90 or sy > HAUTEUR + 80:
            continue
        col = _mp_couleur(u)
        a = float(o.get("a", 0))
        dessiner_halo(sx, sy, 46, col, 0.45)
        pygame.draw.ellipse(ecran, (2, 4, 12), (sx - 18, sy + 8, 36, 14))
        if MODE_GRAPHIQUE == "REALISTE":
            spr = _mp_sprites(str(o.get("s", "")))
            img = spr[0] if math.cos(a) >= 0 else spr[1]
            ecran.blit(img, (sx - img.get_width() // 2, sy - img.get_height() // 2))
        else:
            DRAW.rect(ecran, col, (sx - TAILLE_PERSO // 2, sy - TAILLE_PERSO // 2, TAILLE_PERSO, TAILLE_PERSO))
        tag = rendu_texte(police_petite, str(o.get("p", "?")), True, col)
        ecran.blit(tag, (sx - tag.get_width() // 2, sy - 64))
        h = max(0, min(100, int(o.get("h", 100))))
        DRAW.rect(ecran, (40, 10, 14), (sx - 24, sy - 46, 48, 6))
        DRAW.rect(ecran, (60, 220, 90) if h > 40 else ROUGE_ALERTE, (sx - 24, sy - 46, int(48 * h / 100), 6))


def _arene_dessiner_commandes():
    A = ARENE
    aim, viser, tir = _arene_geo()
    ecran.blit(SURF_SOCLE_JOY, (aim[0] - JOY_RAYON_SOCLE - 6, aim[1] - JOY_RAYON_SOCLE - 6))
    DRAW.circle(ecran, ROUGE_ALERTE, aim, JOY_RAYON_SOCLE, 4)
    kx, ky = int(aim[0] + A["aim_kx"]), int(aim[1] + A["aim_ky"])
    DRAW.circle(ecran, (170, 30, 40), (kx, ky), JOY_RAYON_MANETTE)
    DRAW.circle(ecran, (255, 120, 120), (kx, ky), max(2, JOY_RAYON_MANETTE - 4))
    for pos, lab, col, actif in ((viser, "AUTO" if A["lock"] is not None else "VISER", (0, 170, 255), A["viser"]), (tir, "TIR", ROUGE_ALERTE, A["tir"])):
        if actif:
            DRAW.circle(ecran, (col[0] // 2, col[1] // 2, col[2] // 2), pos, _AR_RBTN)
        DRAW.circle(ecran, col, pos, _AR_RBTN, 4)
        t = rendu_texte(police_petite, lab, True, BLANC_NEON)
        ecran.blit(t, (pos[0] - t.get_width() // 2, pos[1] - t.get_height() // 2))


def jouer_arene():
    """Boucle de l'arène : départ commun, déplacement, visée manuelle, tirs, coups reçus, élimination, victoire."""
    A = ARENE
    t_now = _time.perf_counter()
    dt = min(0.05, max(0.001, t_now - A["t_last"]))
    A["t_last"] = t_now
    if A["spectateur"]:
        _arene_spectateur(t_now)
        return
    quitter = False
    esc = bool(pygame.key.get_pressed()[pygame.K_ESCAPE])
    if A["fin"] or A["mort"]:
        A["menu"] = None
        if clic_detecte and (rect_bouton_quitter_defaite.collidepoint(clic_x, clic_y) or rect_bouton_pause.collidepoint(clic_x, clic_y)):
            quitter = True
    else:
        r_m = _arene_rects_menu()
        if esc and not A["k_esc"]:
            _arene_menu(None if A["menu"] == "pause" else "pause")
        elif clic_detecte:
            if A["menu"] is None:
                if rect_bouton_pause.collidepoint(clic_x, clic_y):
                    _arene_menu("pause")                         # la carte ne s'ouvre que depuis ce menu : aucune ouverture accidentelle
            elif A["menu"] == "pause":
                if rect_bouton_pause.collidepoint(clic_x, clic_y) or r_m["reprendre"].collidepoint(clic_x, clic_y):
                    _arene_menu(None)
                elif r_m["carte"].collidepoint(clic_x, clic_y):
                    _arene_menu("carte")
                elif r_m["quitter"].collidepoint(clic_x, clic_y):
                    quitter = True
            elif r_m["retour"].collidepoint(clic_x, clic_y):
                _arene_menu("pause")
    A["k_esc"] = esc
    if quitter:
        _arene_quitter()
        return
    j = _mp_js()
    now_srv = int(_time.time() * 1000) + A["off"]
    _arene_suivi_manche(j, now_srv, t_now)
    if A["phase"] == "lobby" and now_srv >= A["debut"]:
        A["phase"], A["t_combat"] = "combat", t_now
    if A["phase"] == "combat" and not A["bots_ok"] and MP["ver"] >= 0:    # une fois la liste des joueurs connue : bots (13 seul, moins avec d'autres joueurs)
        _bots_creer()
        A["n0"] = max(1, MP["n"]) + len(A["bots"])
        A["bots_ok"] = True
    zone = _arene_zone_etat((now_srv - A["debut"]) / 1000.0)     # la zone ne dépend que de l'heure du serveur : identique pour tous
    dehors = math.hypot(PARC["x"] - zone["c"][0], PARC["y"] - zone["c"][1]) > zone["r"]
    # ---------- déplacement (vitesse indépendante du nombre d'images par seconde : même vitesse pour tous)
    dx = dy = 0.0
    vit = joueur_vitesse * dt * 60.0 * (0.6 if A["viser"] else 1.0)
    if joystick_actif:
        vx, vy = manette_x - JOY_CENTRE_X, manette_y - JOY_CENTRE_Y
        dist = math.hypot(vx, vy)
        if dist > CTRL["dz"]:
            dx, dy = vx / dist * vit, vy / dist * vit
    im = _in_deplacement()
    if im is not None:
        dx, dy = im[0] * vit, im[1] * vit
    if A["mort"] or A["menu"] is not None:
        dx = dy = 0.0
    if dx or dy:
        A["dirx"], A["diry"] = dx / (math.hypot(dx, dy) or 1.0), dy / (math.hypot(dx, dy) or 1.0)
    x_av, y_av = PARC["x"], PARC["y"]
    if dx != 0 and not parc_bloque(PARC["x"] + dx, PARC["y"]):
        PARC["x"] += dx
    if dy != 0 and not parc_bloque(PARC["x"], PARC["y"] + dy):
        PARC["y"] += dy
    A["pvel"] = [(PARC["x"] - x_av) / dt, (PARC["y"] - y_av) / dt]        # vitesse du joueur (les bots visent un peu devant lui)
    # ---------- visée : stick de droite (ou manette), sinon la direction du déplacement
    if IN["src"] in ("pad", "key"):
        vis = _in_visee()
        if vis is not None:
            A["aim_ang"], A["aim_utilise"] = math.atan2(vis[1], vis[0]), True
    ang = A["aim_ang"] if A["aim_utilise"] else math.atan2(A["diry"], A["dirx"])
    PARC["face"] = 1 if math.cos(ang) >= 0 else 0
    # ---------- réseau
    coups = []
    if j is not None:
        try:
            coups = _arene_echanger(j, ang)
        except Exception as e:
            MP["dbg"] = repr(e)[:70]
    cibles = _arene_maj_autres(dt, t_now)
    if A["phase"] == "combat" and not A["mort"] and not A["fin"]:
        _bots_maj(dt, t_now, zone)
    cibles = cibles + _bots_cibles()
    # ---------- bouton L : visée automatique sur le joueur le plus proche (sinon, visée manuelle au stick)
    verrou = None
    if A["viser"] and not A["mort"]:
        verrou = _arene_verrouiller(cibles)
        if verrou is not None:
            ang = math.atan2(verrou[2] - PARC["y"], verrou[1] - PARC["x"])
    else:
        A["lock"] = None
    # ---------- coups reçus
    for c in coups:
        if A["phase"] == "combat" and not A["mort"] and not A["fin"]:
            A["hp"] -= min(20, max(0, int(c.get("d", 0))))
            A["degat_t"] = t_now
            if A["hp"] <= 0:
                A["hp"], A["mort"], A["rang"] = 0, True, max(1, _arene_vivants())      # place = joueurs encore en vie, moi compris
    # ---------- zone : dégâts continus hors du cercle
    if A["phase"] == "combat" and not A["mort"] and not A["fin"] and dehors and zone["dps"] > 0:
        A["hp"] -= zone["dps"] * dt
        if A["hp"] <= 0:
            A["hp"], A["mort"], A["rang"] = 0, True, max(1, _arene_vivants())
    # ---------- tirs
    A["t_tir"] -= dt
    veut = (A["tir"] or (IN["src"] in ("pad", "key") and _in_tir())) and A["menu"] is None
    if veut and A["phase"] == "combat" and not A["mort"] and not A["fin"] and A["t_tir"] <= 0:
        A["t_tir"] = ARENE_CADENCE
        a = ang + random.uniform(-0.012, 0.012) if A["viser"] else ang + random.uniform(-0.07, 0.07)
        A["balles"].append([PARC["x"] + math.cos(a) * 26, PARC["y"] + math.sin(a) * 26, math.cos(a) * ARENE_V_BALLE, math.sin(a) * ARENE_V_BALLE,
                            ARENE_PORTEE / ARENE_V_BALLE])
        MP["f"] += 1
        MP["fa"] = a
        try:
            if SON_ACTIF:
                son_tir.play()
        except Exception:
            pass
    restantes = []
    for b in A["balles"]:
        b[4] -= dt
        if b[4] <= 0:
            continue
        n = int(ARENE_V_BALLE * dt / 14.0) + 1                # petits pas : un tir ne traverse ni obstacle ni joueur
        sx_, sy_ = b[2] * dt / n, b[3] * dt / n
        fini = False
        for _ in range(n):
            b[0] += sx_
            b[1] += sy_
            if parc_bloque(b[0], b[1], 2):
                A["fx"].append([b[0], b[1], t_now, (255, 220, 120)])
                fini = True
                break
            for u, px, py, o in cibles:
                if (b[0] - px) ** 2 + (b[1] - py) ** 2 < (ARENE_R_JOUEUR + 4) ** 2:
                    A["fx"].append([b[0], b[1], t_now, ROUGE_ALERTE])
                    if str(u).startswith("bot:"):
                        _bot_toucher(u, ARENE_DEGATS)
                    else:
                        A["hits"][u] = t_now
                        try:
                            j.hit(u, ARENE_DEGATS)
                        except Exception:
                            pass
                    fini = True
                    break
            if fini:
                break
        if not fini:
            restantes.append(b)
    A["balles"] = restantes
    # ---------- fin de partie
    vivants = _arene_vivants()
    h_viv = (0 if A["mort"] else 1) + sum(1 for o in MP["autres"] if int(o.get("h", 100)) > 0)
    vivants_fin = vivants if MP["n"] <= 1 else h_viv                  # seul : les bots comptent ; à plusieurs : seuls les joueurs décident de la fin
    if A["phase"] == "combat" and A["bots_ok"] and A["n0"] >= 2 and vivants_fin <= 1 and not A["fin"]:
        A["fin"] = "defaite" if A["mort"] else "victoire"
        if A["fin"] == "victoire":
            A["rang"] = 1
    if (A["mort"] or A["fin"]) and not A["xp_fait"]:                 # l'expérience du joueur (donc la difficulté des bots) est mise à jour
        A["xp_fait"] = True
        _arene_xp_enregistrer(A["rang"], A["n0"], A["kills"], A["fin"] == "victoire")
    _arene_fin_manche(j, now_srv, t_now)
    # ---------- caméra : un peu en avant quand on vise
    decal = 280.0
    if verrou is not None:
        decal = min(280.0, math.hypot(verrou[1] - PARC["x"], verrou[2] - PARC["y"]) * 0.5)
    cdx = math.cos(ang) * decal if A["viser"] else 0.0
    cdy = math.sin(ang) * decal if A["viser"] else 0.0
    A["cam_dx"] += (cdx - A["cam_dx"]) * min(1.0, dt * 6.0)
    A["cam_dy"] += (cdy - A["cam_dy"]) * min(1.0, dt * 6.0)
    cam_x = int(min(max(PARC["x"] + A["cam_dx"] - LARGEUR // 2, 0), PARC_MONDE - LARGEUR))
    cam_y = int(min(max(PARC["y"] + A["cam_dy"] - HAUTEUR // 2, 0), PARC_MONDE - HAUTEUR))
    _parc_gerer(cam_x, cam_y)
    _parc_decouvrir(PARC["x"], PARC["y"])
    # ---------- affichage
    for cx in range(max(0, cam_x // PARC_CH), min(PARC_NC - 1, (cam_x + LARGEUR) // PARC_CH) + 1):
        for cy in range(max(0, cam_y // PARC_CH), min(PARC_NC - 1, (cam_y + HAUTEUR) // PARC_CH) + 1):
            surf = PARC["surf"].get((cx, cy))
            px, py = cx * PARC_CH - cam_x, cy * PARC_CH - cam_y
            if surf is not None:
                ecran.blit(surf, (px, py))
            else:
                ecran.fill(_PC_HERBE, (px, py, PARC_CH, PARC_CH))
    ox, oy = -cam_x, -cam_y
    ticks_ = pygame.time.get_ticks()
    flash_ = zone["etat"] == "alerte" and (ticks_ // 220) % 2 == 0
    _arene_anneau_monde(zone["c"], zone["r"], ox, oy, (255, 50, 50) if (flash_ or zone["etat"] == "retrecit") else (245, 245, 255), 6)
    if zone["cible"] is not None:
        _arene_anneau_monde(zone["cible"][0], zone["cible"][1], ox, oy, (255, 120, 120) if flash_ else (255, 255, 255), 2)
    restantes = []                                           # tirs des autres joueurs
    for b in A["balles_d"]:
        b[0] += b[2] * dt
        b[1] += b[3] * dt
        b[4] -= dt
        if b[4] <= 0 or parc_bloque(b[0], b[1], 2):
            continue
        restantes.append(b)
        bx, by = int(b[0] + ox), int(b[1] + oy)
        DRAW.line(ecran, b[5], (bx, by), (int(bx - b[2] * 0.03), int(by - b[3] * 0.03)), 4)
    A["balles_d"] = restantes
    _bots_dessiner_balles(ox, oy)
    _arene_dessiner_joueurs(cibles, ox, oy)
    sx, sy = int(PARC["x"] + ox), int(PARC["y"] + oy)
    if not A["mort"]:
        pygame.draw.ellipse(ecran, (2, 4, 12), (sx - 18, sy + 8, 36, 14))
        if MODE_GRAPHIQUE == "REALISTE":
            img = img_joueur_droite if PARC["face"] else img_joueur_gauche
            ecran.blit(img, (sx - img.get_width() // 2, sy - img.get_height() // 2))
        else:
            pygame.draw.rect(ecran, VERT_FLUO, (sx - 16, sy - 16, 32, 32))
        if MP["pseudo"]:
            tag = rendu_texte(police_petite, MP["pseudo"], True, VERT_FLUO)
            ecran.blit(tag, (sx - tag.get_width() // 2, sy - 52))
        if verrou is not None:                               # cible verrouillée : viseur sur l'adversaire
            for u_, px_, py_, o_ in cibles:
                if u_ == verrou[0]:
                    cx_, cy_ = int(px_ + ox), int(py_ + oy)
                    DRAW.circle(ecran, (255, 60, 60), (cx_, cy_), 34, 3)
                    DRAW.line(ecran, (255, 60, 60), (cx_ - 44, cy_), (cx_ - 22, cy_), 3)
                    DRAW.line(ecran, (255, 60, 60), (cx_ + 22, cy_), (cx_ + 44, cy_), 3)
                    DRAW.line(ecran, (255, 60, 60), (cx_, cy_ - 44), (cx_, cy_ - 22), 3)
                    DRAW.line(ecran, (255, 60, 60), (cx_, cy_ + 22), (cx_, cy_ + 44), 3)
                    DRAW.line(ecran, (255, 120, 120), (sx, sy), (cx_, cy_), 1)
        elif A["viser"]:                                     # ligne de visée (L2, manuelle)
            lx, ly, d_ = PARC["x"], PARC["y"], 0
            while d_ < 620 and not parc_bloque(lx, ly, 2):
                lx += math.cos(ang) * 20
                ly += math.sin(ang) * 20
                d_ += 20
            DRAW.line(ecran, (255, 70, 70), (sx, sy), (int(lx + ox), int(ly + oy)), 2)
            DRAW.circle(ecran, (255, 70, 70), (int(lx + ox), int(ly + oy)), 5)
        elif A["aim_actif"] or A["aim_utilise"]:
            DRAW.line(ecran, (255, 255, 255), (int(sx + math.cos(ang) * 34), int(sy + math.sin(ang) * 34)),
                      (int(sx + math.cos(ang) * 70), int(sy + math.sin(ang) * 70)), 2)
    for b in A["balles"]:                                    # nos tirs
        bx, by = int(b[0] + ox), int(b[1] + oy)
        DRAW.line(ecran, (255, 230, 120), (bx, by), (int(bx - b[2] * 0.03), int(by - b[3] * 0.03)), 4)
    nouv = []
    for f in A["fx"]:
        age = t_now - f[2]
        if age < 0.25:
            DRAW.circle(ecran, f[3], (int(f[0] + ox), int(f[1] + oy)), int(5 + 70 * age), 2)
            nouv.append(f)
    A["fx"] = nouv
    if t_now - A["degat_t"] < 0.22 and A["rouge"] is not None:
        ecran.blit(A["rouge"], (0, 0))
    if A["phase"] == "combat" and not A["mort"]:                  # bords rouges : hors zone (pulse) ou alerte (clignote)
        if dehors:
            _arene_vignette(70 + 60 * abs(math.sin(ticks_ / 220.0)))
        elif flash_:
            _arene_vignette(60)
    # ---------- radar rond (coin bas gauche : le toucher ne fait rien), barre de vie en haut au centre
    if A["menu"] is None:
        _arene_radar_dessiner(cibles, ang, zone)
    _arene_carte_maj()
    hp = int(max(0, A["hp"]))
    bx0 = LARGEUR // 2 - 115
    DRAW.rect(ecran, (40, 10, 14), (bx0, 14, 230, 22))
    DRAW.rect(ecran, (60, 220, 90) if hp > 40 else ROUGE_ALERTE, (bx0, 14, int(230 * hp / ARENE_PV), 22))
    DRAW.rect(ecran, BLANC_NEON, (bx0, 14, 230, 22), 2)
    t_pv = rendu_texte(police_petite, f"PV {hp}", True, BLANC_NEON)
    ecran.blit(t_pv, (bx0 + 8, 16))
    if A["phase"] == "combat":
        t_info = rendu_texte(police_petite, f"EN VIE {vivants}/{max(A['n0'], vivants)}   ÉLIMINATIONS {A['kills']}", True, BLANC_NEON)
    else:
        t_info = rendu_texte(police_petite, f"JOUEURS {max(1, MP['n'])}/{MP_MAX}", True, BLANC_NEON)
    ecran.blit(t_info, (LARGEUR // 2 - t_info.get_width() // 2, 42))
    if A["phase"] == "combat" and not A["mort"] and not A["fin"]:
        _arene_zone_hud(zone, dehors)
    if A["phase"] == "lobby":
        reste = max(0, int(math.ceil((A["debut"] - now_srv) / 1000.0)))
        t = rendu_texte(police_titre, f"DÉPART DANS {reste}", True, JAUNE_CYBER)
        ecran.blit(t, (LARGEUR // 2 - t.get_width() // 2, int(HAUTEUR * 0.30)))
        t = rendu_texte(police_petite, "Cherche un endroit pour te placer : les tirs commencent au départ", True, BLANC_NEON)
        ecran.blit(t, (LARGEUR // 2 - t.get_width() // 2, int(HAUTEUR * 0.30) + 74))
    elif t_now - A["t_combat"] < 2.0:
        t = rendu_texte(police_titre, "COMBAT !" if A["n0"] >= 2 else "ENTRAÎNEMENT", True, ROUGE_ALERTE)
        ecran.blit(t, (LARGEUR // 2 - t.get_width() // 2, int(HAUTEUR * 0.30)))
    if A["menu"] is not None:
        _arene_dessiner_menu(cibles, ang, vivants, zone)
    elif not _in_masquer_tactile():
        ecran.blit(SURF_SOCLE_JOY, (JOY_CENTRE_X - JOY_RAYON_SOCLE - 6, JOY_CENTRE_Y - JOY_RAYON_SOCLE - 6))
        DRAW.circle(ecran, VERT_FLUO, (JOY_CENTRE_X, JOY_CENTRE_Y), JOY_RAYON_SOCLE, 4)
        DRAW.circle(ecran, (0, 120, 190), (int(manette_x), int(manette_y)), JOY_RAYON_MANETTE)
        DRAW.circle(ecran, CYAN_NEON, (int(manette_x), int(manette_y)), max(2, JOY_RAYON_MANETTE - 4))
        _arene_dessiner_commandes()
    DRAW.circle(ecran, (10, 10, 20), (BTN_PAUSE_X, BTN_PAUSE_Y), BTN_PAUSE_RAYON)             # bouton pause (même dessin qu'en solo)
    DRAW.circle(ecran, BLEU_CYBER, (BTN_PAUSE_X, BTN_PAUSE_Y), BTN_PAUSE_RAYON, 3)
    DRAW.rect(ecran, BLEU_CYBER, (BTN_PAUSE_X - 9, BTN_PAUSE_Y - 10, 6, 20))
    DRAW.rect(ecran, BLEU_CYBER, (BTN_PAUSE_X + 3, BTN_PAUSE_Y - 10, 6, 20))
    rtt = MP["rtt"]
    if rtt > 0:
        col_i = VERT_FLUO if rtt < 200 else (JAUNE_CYBER if rtt < 500 else ROUGE_ALERTE)
        t = rendu_texte(police_petite, f"{rtt} ms  •  {int(clock.get_fps())} FPS", True, col_i)
        ecran.blit(t, (LARGEUR // 2 - t.get_width() // 2, HAUTEUR - 36))
    if MP["dbg"]:
        t = rendu_texte(police_petite, "ERR " + MP["dbg"], True, ROUGE_ALERTE)
        ecran.blit(t, (LARGEUR // 2 - t.get_width() // 2, HAUTEUR - 66))
    # ---------- fin : éliminé ou victoire
    if A["mort"] or A["fin"]:
        ecran.blit(A["voile"], (0, 0))
        gagne = A["fin"] == "victoire"
        dessiner_titre_glitch("VICTOIRE" if gagne else "ÉLIMINÉ", police_titre, LARGEUR // 2, int(HAUTEUR * 0.24))
        t = rendu_texte(police_jeu, f"Place n°{A['rang']}   •   {A['kills']} élimination(s)", True, BLANC_NEON)
        ecran.blit(t, (LARGEUR // 2 - t.get_width() // 2, HAUTEUR // 2 - 40))
        if A["endAt"] > 0:
            info_m = f"PROCHAINE MANCHE DANS {max(0, int(math.ceil((A['endAt'] - now_srv) / 1000.0)))}"
        elif A["fin"] or MP["n"] <= 1:
            info_m = "La manche se termine..."
        else:
            info_m = "La manche continue pour les autres joueurs"
        t = rendu_texte(police_petite, info_m, True, JAUNE_CYBER)
        ecran.blit(t, (LARGEUR // 2 - t.get_width() // 2, HAUTEUR // 2 + 8))
        bouton_neon(rect_bouton_quitter_defaite, VERT_FLUO if gagne else ROUGE_ALERTE, "QUITTER", police_bouton)


def _injecter_firebase():
    try:
        _pfs.window.eval(_JS_HEURE)
    except Exception:
        pass
    try:
        _pfs.window.eval(_JS_MULTI)
    except Exception:
        pass
    try:
        _pfs.window.eval(_JS_FIREBASE)
    except Exception:
        try:
            s = _pfs.window.document.createElement("script")
            s.textContent = _JS_FIREBASE
            _pfs.window.document.head.appendChild(s)
        except Exception as e:
            print("Firebase indisponible :", e)


SKIN_IDS = ["recrue", "sergent_du_desert", "rodeur_urbain", "fantassin_polaire", "chasseur_de_primes", "mercenaire_rouge", "tireur_delite", "punk_anarchiste", "pilote_jet", "gladiateur", "cow_boy_cyber", "colosse_dacier", "cyber_ninja", "fantome", "samourai_neon", "chevalier_toxique", "commandant_dore", "titan_solaire", "seigneur_du_vide", "eclaireur_bronze", "eclaireuse", "amazone_des_neiges", "pilote_rose", "chasseresse_verte", "alchimiste", "valkyrie", "ninja_violette", "cyber_chat", "reine_ecarlate", "deesse_solaire"]
_skin_courant = None
_planche_skins = None


def _appliquer_skin():
    """Met le sprite du joueur selon le skin équipé (planche skins_sheet.png)."""
    global img_joueur_droite, img_joueur_gauche, img_joueur_actuel, _skin_courant, _planche_skins
    if not IS_WEB:
        return
    try:
        sid = str(_pfs.window.flexAuth.skinActif or "")
    except Exception:
        sid = ""
    if sid == _skin_courant:
        return
    try:
        if sid in SKIN_IDS:
            if _planche_skins is None:
                _planche_skins = pygame.image.load(_asset("skins_sheet.png")).convert_alpha()
            i = SKIN_IDS.index(sid)
            morceau = _planche_skins.subsurface(pygame.Rect((i % 6) * 160, (i // 6) * 160, 160, 160)).copy()
            img = pygame.transform.smoothscale(morceau, (TAILLE_PERSO, TAILLE_PERSO))
        else:
            img = _img_joueur_defaut
        img_joueur_droite = img
        img_joueur_gauche = pygame.transform.flip(img, True, False)
        img_joueur_actuel = img_joueur_droite
        _skin_courant = sid
    except Exception as e:
        print("Skin indisponible :", e)


_inst_visible = False
_inst_tick = 0


def _install_visible():
    """Vrai tant que le jeu n'est pas installé (vérifié 1 fois par seconde)."""
    global _inst_visible, _inst_tick
    if not IS_WEB:
        return False
    _inst_tick += 1
    if _inst_tick % 60 == 1:
        try:
            _inst_visible = bool(_pfs.window.flexInstall.peut)
        except Exception:
            _inst_visible = False
    return _inst_visible


def _ouvrir_install():
    """Bouton INSTALLER : ouvre la fenêtre d'installation ou l'animation guide."""
    if not IS_WEB:
        return
    try:
        _pfs.window.flexInstall.ouvrir()
    except Exception:
        pass


def _install_rappel_victoire():
    """Petit rappel d'installation après une première victoire (une seule fois)."""
    if not IS_WEB:
        return
    try:
        _pfs.window.flexInstall.victoire()
    except Exception:
        pass


def _ouvrir_skins():
    """Ouvre l'écran des personnages (page web par-dessus le jeu)."""
    if not IS_WEB:
        return
    try:
        _pfs.window.flexAuth.showSkins()
    except Exception:
        pass


def _ouvrir_classement():
    """Ouvre la fenêtre du classement (page web par-dessus le jeu)."""
    if not IS_WEB:
        return
    try:
        _pfs.window.flexAuth.showRank()
    except Exception:
        pass


def _stat(type_, niveau=0):
    """Envoie une statistique anonyme (visite, connexion, début/fin de niveau). Ne plante jamais le jeu."""
    if not IS_WEB or MP["actif"]:
        return
    try:
        _pfs.window.flexAuth.log(type_, int(niveau))
    except Exception:
        pass


def _fa():
    try:
        return _pfs.window.flexAuth
    except Exception:
        return None


def _cloud_local():
    files = {}
    base = _DOSSIER_DONNEES or "."
    try:
        for nom in os.listdir(base):
            if nom.endswith(".json"):
                with open(os.path.join(base, nom), "r", encoding="utf-8") as f:
                    files[nom] = f.read()
    except Exception:
        pass
    niveau = 0
    try:
        niveau = int(json.loads(files.get("progression_flex.json", "{}")).get("niveau", 0))
    except Exception:
        pass
    t = 0
    try:
        t = int(float(str(_LS.getItem("flexsave_t") or 0)))
    except Exception:
        pass
    return files, niveau, t


def _cloud_push(fa):
    files, niveau, t = _cloud_local()
    if not files:
        return
    if not t:
        t = int(_time.time() * 1000)
        try:
            _LS.setItem("flexsave_t", str(t))
        except Exception:
            pass
    fa.push(json.dumps({"files": files, "niveau": niveau, "t": t}))
    try:
        _LS.setItem("flexsave_owner", str(fa.uid or ""))
    except Exception:
        pass


def _cloud_appliquer(cloud):
    """Copie la sauvegarde en ligne dans la mémoire du navigateur ; elle sera relue au rechargement."""
    _CLOUD["gel"] = True
    noms = []
    for nom, txt in (cloud.get("files") or {}).items():
        nom = os.path.basename(str(nom))
        if nom.endswith(".json"):
            _LS.setItem("flexsave:" + nom, str(txt))
            noms.append(nom)
    _LS.setItem("flexsave:index", json.dumps(sorted(noms)))
    _LS.setItem("flexsave_t", str(int(cloud.get("t", 0) or 0)))
    try:
        _LS.setItem("flexsave_owner", str(_fa().uid or ""))
        _pfs.window.sessionStorage.setItem("flexskip", "1")
    except Exception:
        pass


def _cloud_decider(fa, brut):
    """Compare la sauvegarde locale et celle en ligne. Retourne 'reload' (le jeu doit redémarrer) ou 'ok'."""
    uid = str(fa.uid or "")
    files, niveau, t = _cloud_local()
    proprio = ""
    try:
        proprio = str(_LS.getItem("flexsave_owner") or "")
    except Exception:
        pass
    etranger = bool(proprio) and proprio != uid
    if etranger:                       # ces données locales appartiennent à un AUTRE compte : on ne les mélange jamais
        files, niveau, t = {}, 0, 0
    cloud = None
    if brut:
        try:
            cloud = json.loads(brut)
        except Exception:
            cloud = None

    def _redemarrer():
        try:
            _pfs.window.sessionStorage.setItem("flexskip", "1")
            _pfs.window.location.reload()
        except Exception:
            pass

    if not cloud or not cloud.get("files"):
        if etranger:                   # nouveau compte sans sauvegarde : on repart de zéro
            _CLOUD["gel"] = True
            _cloud_effacer_local()
            _LS.setItem("flexsave_owner", uid)
            _redemarrer()
            return "reload"
        if files:
            _cloud_push(fa)
        else:
            _LS.setItem("flexsave_owner", uid)
        return "ok"
    try:
        c_niveau = int(cloud.get("niveau", 0) or 0)
        c_t = int(cloud.get("t", 0) or 0)
    except Exception:
        c_niveau, c_t = 0, 0
    if (not files) or c_niveau > niveau or (c_niveau == niveau and c_t > t):
        _cloud_appliquer(cloud)
        try:
            _pfs.window.location.reload()
        except Exception:
            pass
        return "reload"
    if niveau > c_niveau or t > c_t:
        _cloud_push(fa)
    else:
        _LS.setItem("flexsave_owner", uid)
    return "ok"


def _cloud_tick():
    c = _CLOUD
    if c["mode"] != "user" or not c["dirty"] or c["gel"]:
        return
    now = _time.time()
    if now - c["last"] < 8:
        return
    fa = _fa()
    if fa is None or not str(fa.uid or ""):
        return
    c["dirty"] = False
    c["last"] = now
    try:
        _cloud_push(fa)
    except Exception:
        pass


def _cloud_effacer_local():
    try:
        brut = _LS.getItem("flexsave:index")
        for nom in (json.loads(str(brut)) if brut is not None else []):
            _LS.removeItem("flexsave:" + os.path.basename(str(nom)))
        _LS.removeItem("flexsave:index")
        _LS.removeItem("flexsave_t")
        _LS.removeItem("flexsave_owner")
    except Exception:
        pass


_MSG_ERREURS = {
    "auth/popup-blocked": "Fenêtre bloquée : autorise les pop-ups pour ce site",
    "auth/popup-closed-by-user": "Connexion annulée",
    "auth/cancelled-popup-request": "Connexion annulée",
    "auth/unauthorized-domain": "Domaine non autorisé dans Firebase",
    "auth/network-request-failed": "Pas de connexion internet",
    "permission-denied": "Accès refusé par les règles de sécurité",
    "unavailable": "Service en ligne indisponible",
}


async def ecran_connexion():
    _CLOUD["gate"] = True          # pas de plein écran pendant la connexion (sinon la fenêtre Google peut être bloquée)
    try:
        await _ecran_connexion_interne()
    finally:
        _CLOUD["gate"] = False
        try:
            _fa().hideBtn()
        except Exception:
            pass


async def _ecran_connexion_interne():
    """Écran affiché avant le menu : connexion Google ou 'Jouer sans compte'. Sans effet hors navigateur."""
    if not IS_WEB or _LS is None:
        return
    try:
        if str(_pfs.window.sessionStorage.getItem("flexskip") or "") == "1":      # on vient de restaurer la sauvegarde en ligne
            _pfs.window.sessionStorage.removeItem("flexskip")
            _CLOUD["mode"] = "user"
            return
    except Exception:
        pass
    W, H = ecran.get_width(), ecran.get_height()
    f_titre = pygame.font.SysFont(None, max(36, int(H * 0.17)))
    f_btn = pygame.font.SysFont(None, max(24, int(H * 0.065)))
    f_pet = pygame.font.SysFont(None, max(18, int(H * 0.042)))
    ROSE, CYAN, BLANC, GRIS = (255, 0, 170), (0, 190, 255), (240, 245, 255), (140, 150, 170)
    etat, t_etat, t0, dernier = "menu", _time.time(), _time.time(), 0.0
    lance = False
    erreur_txt = ""
    horloge = pygame.time.Clock()
    while True:
        await asyncio.sleep(0)
        fa = _fa()
        now = _time.time()
        pret = bool(fa is not None and fa.ready) or (now - t0 > 8)
        uid = str(fa.uid or "") if fa is not None else ""
        nom = str(fa.name or "") if fa is not None else ""
        err = str(fa.err or "") if fa is not None else ""
        occupe = bool(fa.busy) if fa is not None else False
        if etat == "menu" and occupe and not uid:        # le clic sur le bouton HTML a lancé la connexion
            etat, t_etat = "connexion", now
        message, boutons = "", []
        if etat == "menu":
            if not pret:
                message, boutons = "Chargement du service de connexion...", [("Jouer sans compte", "guest", CYAN)]
            elif uid:
                message, boutons = "Connecté : " + nom, [("Continuer", "go", ROSE), ("Se déconnecter", "out", CYAN)]
            else:
                message = _MSG_ERREURS.get(err, err) if err else "Connecte-toi pour garder ta progression sur tous tes téléphones"
                boutons = [("Se connecter avec Google", "google", ROSE), ("Jouer sans compte", "guest", CYAN)]
        elif etat == "connexion":
            message, boutons = "Connexion en cours...", [("Annuler", "annuler", CYAN)]
            if uid:
                etat, lance, t_etat = "pull", False, now
            elif not occupe and now - t_etat > 1.0:
                etat = "menu"
        elif etat == "pull":
            message = "Synchronisation de ta sauvegarde..."
            if not lance:
                lance = True
                fa.pull()
            else:
                cs = str(fa.cloudState or "")
                if cs == "done":
                    if _cloud_decider(fa, str(fa.cloud or "")) == "reload":
                        etat, t_etat = "reload", now
                    else:
                        _CLOUD["mode"] = "user"
                        return
                elif cs == "error" or now - t_etat > 12:
                    erreur_txt = _MSG_ERREURS.get(err, err or "délai dépassé")
                    etat = "erreur"
        elif etat == "erreur":
            message, boutons = "Sauvegarde en ligne indisponible : " + erreur_txt, [("Continuer quand même", "go_err", ROSE)]
        elif etat == "reload":
            message = "Restauration de ta sauvegarde... le jeu redémarre"
        elif etat == "out_push":
            message = "Envoi de ta sauvegarde avant déconnexion..."
            if not lance:
                lance = True
                try:
                    _cloud_push(fa)
                except Exception:
                    pass
            elif str(fa.pushState or "") != "loading" or now - t_etat > 4:
                _CLOUD["gel"] = True
                fa.signOut()
                etat, t_etat = "out_wait", now
        elif etat == "out_wait":
            message = "Déconnexion..."
            if not uid or now - t_etat > 3:
                _cloud_effacer_local()
                try:
                    _pfs.window.location.reload()
                except Exception:
                    pass
                etat = "reload"
        # --- dessin ---
        ecran.fill((4, 4, 12))
        for i in range(8):
            y = int(H * (0.62 + i * i * 0.0065))
            pygame.draw.line(ecran, (10, 40, 70), (0, y), (W, y), 1)
        cx = W // 2
        for dx, couleur in ((-3, ROSE), (3, CYAN), (0, BLANC)):
            t = f_titre.render("FLEX CYBERPUNK", True, couleur)
            ecran.blit(t, (cx - t.get_width() // 2 + dx, int(H * 0.10)))
        rects = []
        bw, bh = int(H * 1.05), int(H * 0.13)
        y0 = int(H * 0.36)
        for i, (lib, cle, couleur) in enumerate(boutons):
            r = pygame.Rect(cx - bw // 2, y0 + i * int(H * 0.19), bw, bh)
            rects.append((r, cle))
            plein = (couleur == ROSE)
            pygame.draw.rect(ecran, couleur if plein else (10, 12, 24), r, border_radius=18)
            pygame.draw.rect(ecran, couleur, r, 4, border_radius=18)
            t = f_btn.render(lib, True, (0, 0, 0) if plein else couleur)
            ecran.blit(t, (r.centerx - t.get_width() // 2, r.centery - t.get_height() // 2))
        try:
            g_rect = None
            for r, cle in rects:
                if cle == "google":
                    g_rect = r
            if fa is not None and g_rect is not None and etat == "menu" and not occupe:
                f = _FX
                fa.showBtn(f["ox"] + g_rect.x * f["sc"], f["oy"] + g_rect.y * f["sc"], g_rect.w * f["sc"], g_rect.h * f["sc"], f["rw"])
            elif fa is not None:
                fa.hideBtn()
        except Exception:
            pass
        if message:
            t = f_pet.render(message, True, BLANC)
            ecran.blit(t, (cx - t.get_width() // 2, int(H * 0.86)))
        if err and etat == "menu" and not message.startswith(_MSG_ERREURS.get(err, "§§")):
            t = f_pet.render(err, True, GRIS)
            ecran.blit(t, (cx - t.get_width() // 2, int(H * 0.92)))
        pygame.display.flip()
        horloge.tick(30)
        # --- clics ---
        clic = None
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            px = py = None
            if e.type == pygame.MOUSEBUTTONDOWN:
                px, py = e.pos
            elif e.type == pygame.FINGERDOWN:
                px, py = e.x * W, e.y * H
            if px is not None and now - dernier > 0.4:
                for r, cle in rects:
                    if r.collidepoint(px, py):
                        clic, dernier = cle, now
                        break
        if clic == "guest":
            _CLOUD["mode"] = "guest"
            return
        if clic == "google" and fa is not None:
            fa.signIn()
            etat, t_etat = "connexion", now
        elif clic == "annuler":
            etat = "menu"
        elif clic == "go":
            etat, lance, t_etat = "pull", False, now
        elif clic == "go_err":
            _CLOUD["mode"] = "user"
            return
        elif clic == "out":
            etat, lance, t_etat = "out_push", False, now


if IS_WEB:
    _injecter_firebase()


def chemin_donnees(nom):
    return os.path.join(_DOSSIER_DONNEES, nom) if _DOSSIER_DONNEES else nom


# ==================== PROTECTION DU JEU (dissuasion) ====================
# Empreinte du code officiel : calculée à la livraison. Si main.py est modifié, le jeu affiche « VERSION MODIFIÉE ».
# (Tu modifies toi-même le code ? Lance le jeu, copie « Empreinte actuelle » affichée dans la console, colle-la ci-dessous.)
EMPREINTE_OFFICIELLE = "8dab48080207a2804f6d29540e03e628ce8aa40564b78a95394fc9854bd761d3"


def _empreinte_du_fichier():
    try:
        with open(__file__, "rb") as f:
            texte = f.read().decode("utf-8", "ignore").lstrip("\ufeff")
    except Exception:
        return None                      # impossible de lire le fichier (autre environnement) : pas de vérification
    texte = texte.replace("\r\n", "\n").replace("\r", "\n")
    texte = re.sub(r'^EMPREINTE_OFFICIELLE = "[0-9a-f]*"$', 'EMPREINTE_OFFICIELLE = ""', texte, flags=re.M)
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


_empreinte_actuelle = _empreinte_du_fichier()
VERSION_MODIFIEE = False if IS_WEB else (_empreinte_actuelle is not None and _empreinte_actuelle != EMPREINTE_OFFICIELLE)
if VERSION_MODIFIEE:
    print("⚠️ Version modifiée. Empreinte actuelle :", _empreinte_actuelle)

# Sauvegardes signées : un fichier modifié à la main (pièces, niveaux...) est refusé et remis à zéro.
_SECRET = b"flex" + b"play" + bytes([37, 91, 12, 77, 205, 8]) + b"-cyber-2026"
AVERTISSEMENT = {"texte": "", "debut": None}


def _signature(donnees):
    msg = json.dumps(donnees, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_SECRET, msg, hashlib.sha256).hexdigest()[:32]


def ecrire_json_signe(chemin, donnees):
    d = dict(donnees)
    d.pop("sig", None)
    d["v"] = 2
    d["sig"] = _signature(d)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(d, f)


def lire_json_signe(chemin):
    """Retourne (données, statut) ; statut : 'absent', 'ok', 'ancien' (ancienne sauvegarde non signée) ou 'altere'."""
    if not os.path.exists(chemin):
        return None, "absent"
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return None, "altere"
    if not isinstance(d, dict):
        return None, "altere"
    if d.get("v") == 2:
        sig = d.pop("sig", None)
        if sig != _signature(d):
            return None, "altere"
        d.pop("v", None)
        return d, "ok"
    return d, "ancien"


def signaler_sauvegarde_alteree():
    AVERTISSEMENT["texte"] = "Sauvegarde modifiée ou illisible : remise à zéro"
    print("⚠️", AVERTISSEMENT["texte"])


def _journal_erreur(type_, valeur, tb):
    """Écrit l'erreur dans crash_flex.log (à côté du jeu) avant que le programme se ferme."""
    try:
        with open(chemin_donnees("crash_flex.log"), "a", encoding="utf-8") as f:
            f.write("\n=== " + _time.strftime("%Y-%m-%d %H:%M:%S") + " ===\n")
            traceback.print_exception(type_, valeur, tb, file=f)
    except Exception:
        pass
    sys.__excepthook__(type_, valeur, tb)


sys.excepthook = _journal_erreur

# 1. INITIALISATION DE PYGAME & PLEIN ÉCRAN
pygame.init()
info_ecran = pygame.display.Info()
LARGEUR, HAUTEUR = info_ecran.current_w, info_ecran.current_h
if HAUTEUR > LARGEUR:
    LARGEUR, HAUTEUR = HAUTEUR, LARGEUR
if IS_WEB:
    # Résolution virtuelle : tout est dessiné comme sur ton téléphone (1080 px de haut),
    # puis le navigateur adapte l'image à l'écran du joueur. Plus grand = interface plus petite.
    try:
        import platform as _pf
        _w, _h = float(_pf.window.innerWidth), float(_pf.window.innerHeight)
    except Exception:
        _w, _h = float(LARGEUR), float(HAUTEUR)
    _INNER = (int(_w), int(_h))
    try:
        _SEARCH = str(_pf.window.location.search)
    except Exception:
        _SEARCH = ""
    import re as _re

    def _param(nom, defaut):
        try:
            m = _re.search(r"[?&]" + nom + r"=([0-9.]+)", _SEARCH)
            return float(m.group(1)) if m else defaut
        except Exception:
            return defaut

    _DBG = "dbg=1" in _SEARCH          # ...?dbg=1 : étiquette de diagnostic
    _CSS = _param("css", 0) >= 0.5     # ...?css=1 : force la taille d'affichage du canvas (secours)
    try:
        _DPR = float(_pf.window.devicePixelRatio)
    except Exception:
        _DPR = 1.0
    _DPR = max(1.0, min(3.0, _DPR))
    _K = _DPR if _param("hd", 1) >= 0.5 else 1.0     # canvas à la vraie résolution de l'écran
    if _h > _w:
        _w, _h = _h, _w
    try:     # taille de l'écran entier du téléphone : le jeu est préparé pour le plein écran
        _sw, _sh = float(_pf.window.screen.width), float(_pf.window.screen.height)
    except Exception:
        _sw, _sh = _w, _h
    if _sh > _sw:
        _sw, _sh = _sh, _sw
    _K = min(_K, (2800000.0 / max(1.0, _sw * _sh)) ** 0.5)     # plafond de pixels (fluidité)
    _U = max(0.5, min(3.0, _param("u", 1.0)))                  # ...?u=1.2 : interface 20% plus grande
    # taille du jeu = taille de l'écran (en px CSS) x 1.64 : même taille réelle des boutons sur tous les téléphones
    _VW_F, _VH_F = _sw * 1.64 / _U, _sh * 1.64 / _U
    _hq = _param("h", 0)
    if 500 <= _hq <= 3200:
        _VH_F = _hq
        _VW_F = _hq * (_sw / _sh)
    HAUTEUR = max(400, int(round(_VH_F)))
    LARGEUR = max(400, int(round(_VW_F)))
    _REQ = (max(200, int(_sw * _K)), max(200, int(_sh * _K)))   # canvas = écran entier (le navigateur l'adapte à la fenêtre)

ecran = pygame.display.set_mode(_REQ if IS_WEB else (LARGEUR, HAUTEUR), 0 if IS_WEB else pygame.FULLSCREEN)
# Sur certains téléphones (encoche / caméra) la surface réellement affichée est plus petite que celle annoncée :
# on utilise sa vraie taille, sinon les boutons à droite sont coupés et le toucher est décalé.
if IS_WEB:
    _VW, _VH = LARGEUR, HAUTEUR
    ecran = pygame.Surface((_VW, _VH)).convert()
    _FX = {"ox": 0, "oy": 0, "sc": 0.0, "rw": 1, "rh": 1, "w": _VW, "h": _VH, "n": 0}
    _FLIP_REEL = pygame.display.flip
    _EVENT_REEL = pygame.event.get
    _POLICE_DBG = {"f": None}

    def _maj_fx():
        reel = pygame.display.get_surface()
        rw, rh = reel.get_size()
        sc = min(rw / float(_VW), rh / float(_VH))
        w, h = max(1, int(_VW * sc)), max(1, int(_VH * sc))
        _FX.update(ox=(rw - w) // 2, oy=(rh - h) // 2, sc=sc, rw=rw, rh=rh, w=w, h=h)
        return reel

    def _flip_web():
        _FX["k"] = _FX.get("k", 0) + 1
        _tn = _time.time()
        if "t0" not in _FX:
            _FX["t0"] = _FX["tf"] = _tn
            _FX["fps"] = 0
        if _FX["k"] % 30 == 0:
            _dt = _tn - _FX["tf"]
            _FX["tf"] = _tn
            if _dt > 0:
                _FX["fps"] = int(30 / _dt)
        if _FX["k"] % 30 == 0:
            _sync_sauvegardes()
            _cloud_tick()
        if _FX["k"] % 20 == 0:      # la fenêtre a changé (rotation du téléphone...) : on réajuste le canvas
            try:
                _FX["port"] = bool(_pf.window.innerHeight > _pf.window.innerWidth)
            except Exception:
                pass
        reel = _maj_fx()
        f = _FX
        if f["ox"] or f["oy"]:
            reel.fill((0, 0, 0))
        if abs(f["w"] - _VW) <= 2 and abs(f["h"] - _VH) <= 2:
            reel.blit(ecran, (f["ox"], f["oy"]))
        else:
            pygame.transform.scale(ecran, (f["w"], f["h"]), reel.subsurface((f["ox"], f["oy"], f["w"], f["h"])))
        f["n"] += 1
        try:
            if _POLICE_DBG["f"] is None:
                _POLICE_DBG["f"] = pygame.font.Font(None, 30)
            if _DBG:     # étiquette de version + tailles (diagnostic)
                t = _POLICE_DBG["f"].render("w18 R%dx%d V%dx%d I%s S%s F%s T%d" % (f["rw"], f["rh"], _VW, _VH, str(globals().get("_INNER")), "-" if _LS is None else len(_SYNC_ETAT), f.get("fps", 0), int(_time.time() - f.get("t0", _time.time()))), True, (255, 255, 0), (0, 0, 0))
                reel.blit(t, (4, max(0, f["rh"] - t.get_height() - 4)))
                if f["n"] < 1200:
                    pygame.draw.rect(reel, (255, 255, 0), (0, 0, f["rw"], f["rh"]), 3)
            if f.get("port"):
                t = _POLICE_DBG["f"].render("Tourne le telephone en paysage, puis recharge la page", True, (255, 255, 255), (200, 0, 80))
                reel.blit(t, (max(0, (f["rw"] - t.get_width()) // 2), f["rh"] - 60))
        except Exception:
            pass
        _FLIP_REEL()

    def _modal_web():
        try:
            return bool(getattr(_pf.window, "flexModal", False))
        except Exception:
            return False

    def _event_get_web(*a, **k):
        evs = _EVENT_REEL(*a, **k)
        f = _FX
        for e in evs:
            try:
                if e.type in (pygame.FINGERDOWN, pygame.MOUSEBUTTONDOWN) and not _CLOUD.get("gate") and not _modal_web() and not _pf.window.document.fullscreenElement:
                    _pf.window.document.documentElement.requestFullscreen()      # cache la barre de Chrome
                    try:
                        _pf.window.screen.orientation.lock("landscape")
                    except Exception:
                        pass
                break
            except Exception:
                break
        if f["sc"]:
            for e in evs:
                try:
                    if e.type in (pygame.FINGERDOWN, pygame.FINGERUP, pygame.FINGERMOTION):
                        e.x = ((e.x * f["rw"] - f["ox"]) / f["sc"]) / float(_VW)
                        e.y = ((e.y * f["rh"] - f["oy"]) / f["sc"]) / float(_VH)
                    elif e.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
                        e.pos = (int((e.pos[0] - f["ox"]) / f["sc"]), int((e.pos[1] - f["oy"]) / f["sc"]))
                except Exception:
                    pass
        return evs

    def _style_canvas(w, h):
        if not _CSS:
            return
        try:      # on garde la taille d'affichage = fenêtre, même si le canvas a plus de pixels
            _c = _pf.window.canvas
            _c.style.width = "%dpx" % w
            _c.style.height = "%dpx" % h
        except Exception:
            pass

    _maj_fx()
    _style_canvas(_INNER[0], _INNER[1])
    _FX["req"] = (_INNER[0], _INNER[1])
    pygame.display.flip = _flip_web
    pygame.display.update = lambda *a, **k: _flip_web()
    pygame.event.get = _event_get_web
LARGEUR, HAUTEUR = ecran.get_size()
pygame.display.set_caption("Flex Cyberpunk Réaliste 🚀 - MODE INFINI")

# TAILLES DU JEU
TAILLE_CASE = 100
TAILLE_PERSO = 45

# QUALITÉ DES EFFETS :  0 = léger (très bas de gamme)  |  1 = équilibré (par défaut)  |  2 = complet (téléphones puissants)
# Avec AUTO_QUALITE = True, le jeu baisse tout seul le niveau s'il détecte que ça rame.
QUALITE_EFFETS = 1
AUTO_QUALITE = True
QUALITE = {"niveau": QUALITE_EFFETS}

# ---- Résolution réduite : le jeu est dessiné en petit puis agrandi (ça allège beaucoup les téléphones faibles).
# Le reste du code dessine comme d'habitude : CibleEchelle convertit les coordonnées à la volée.
_cache_reduits = {}


class CibleEchelle:
    """Reçoit les ordres de dessin dans le repère du jeu (taille normale) et les convertit à l'échelle de la vraie surface."""

    def __init__(self, s, surf=None):
        self.s = s
        self.surf = surf if surf is not None else pygame.Surface((max(1, int(LARGEUR * s)), max(1, int(HAUTEUR * s)))).convert()

    def get_size(self):
        return (LARGEUR, HAUTEUR)

    def fill(self, c, *a, **k):
        self.surf.fill(c, *a, **k)

    def set_clip(self, r):
        if r is None:
            self.surf.set_clip(None)
            return
        s = self.s
        x, y, w, h = r
        nx, ny = math.floor(x * s), math.floor(y * s)
        self.surf.set_clip((nx, ny, max(1, int(round((x + w) * s)) - nx), max(1, int(round((y + h) * s)) - ny)))

    def blit(self, src, dest, area=None, special_flags=0):
        s = self.s
        cle = (id(src), s)
        v = _cache_reduits.get(cle)
        if v is None:
            if len(_cache_reduits) > 700:
                _cache_reduits.clear()
            w, h = src.get_size()
            taille = (max(1, int(round(w * s))), max(1, int(round(h * s))))
            try:
                r = pygame.transform.smoothscale(src, taille)
            except Exception:
                r = pygame.transform.scale(src, taille)
            v = (src, r)
            _cache_reduits[cle] = v
        self.surf.blit(v[1], (math.floor(dest[0] * s), math.floor(dest[1] * s)), None, special_flags)


_cible_monde = None


def obtenir_cible_monde():
    global _cible_monde
    if _cible_monde is None or _cible_monde.s != ECHELLE:
        _cible_monde = CibleEchelle(ECHELLE)
    return _cible_monde


def _pt(p, s):
    return (int(round(p[0] * s)), int(round(p[1] * s)))


def _lw(w, s):
    return max(1, int(round(w * s))) if w else 0


class _Dessin:
    def rect(self, surf, couleur, rect, width=0, **kw):
        if isinstance(surf, CibleEchelle):
            s = surf.s
            x, y, w, h = rect
            nx, ny = math.floor(x * s), math.floor(y * s)
            nw = max(1, int(round((x + w) * s)) - nx)
            nh = max(1, int(round((y + h) * s)) - ny)
            if "border_radius" in kw:
                kw["border_radius"] = int(kw["border_radius"] * s)
            return pygame.draw.rect(surf.surf, couleur, (nx, ny, nw, nh), _lw(width, s), **kw)
        return pygame.draw.rect(surf, couleur, rect, width, **kw)

    def circle(self, surf, couleur, centre, rayon, width=0, **kw):
        if isinstance(surf, CibleEchelle):
            s = surf.s
            return pygame.draw.circle(surf.surf, couleur, _pt(centre, s), max(1, int(round(rayon * s))), _lw(width, s), **kw)
        return pygame.draw.circle(surf, couleur, centre, rayon, width, **kw)

    def line(self, surf, couleur, a, b, width=1):
        if isinstance(surf, CibleEchelle):
            s = surf.s
            return pygame.draw.line(surf.surf, couleur, _pt(a, s), _pt(b, s), max(1, int(round(width * s))))
        return pygame.draw.line(surf, couleur, a, b, width)

    def lines(self, surf, couleur, ferme, points, width=1):
        if isinstance(surf, CibleEchelle):
            s = surf.s
            return pygame.draw.lines(surf.surf, couleur, ferme, [_pt(p, s) for p in points], max(1, int(round(width * s))))
        return pygame.draw.lines(surf, couleur, ferme, points, width)

    def polygon(self, surf, couleur, points, width=0):
        if isinstance(surf, CibleEchelle):
            s = surf.s
            return pygame.draw.polygon(surf.surf, couleur, [_pt(p, s) for p in points], _lw(width, s))
        return pygame.draw.polygon(surf, couleur, points, width)

    def ellipse(self, surf, couleur, rect, width=0):
        if isinstance(surf, CibleEchelle):
            s = surf.s
            x, y, w, h = rect
            return pygame.draw.ellipse(surf.surf, couleur, (int(x * s), int(y * s), max(1, int(w * s)), max(1, int(h * s))), _lw(width, s))
        return pygame.draw.ellipse(surf, couleur, rect, width)

    def arc(self, surf, couleur, rect, debut, fin, width=1):
        if isinstance(surf, CibleEchelle):
            s = surf.s
            x, y, w, h = rect
            return pygame.draw.arc(surf.surf, couleur, (int(x * s), int(y * s), max(1, int(w * s)), max(1, int(h * s))), debut, fin, max(1, int(round(width * s))))
        return pygame.draw.arc(surf, couleur, rect, debut, fin, width)


_DESSIN_ECHELLE = _Dessin()
DRAW = pygame.draw


# ==================== RÉSOLUTION MATÉRIELLE ====================
# Le jeu garde son repère habituel (LARGEUR x HAUTEUR) mais la vraie surface est plus petite : le téléphone dessine
# 2 à 4 fois moins de pixels, et SDL (carte graphique) agrandit gratuitement l'image à la fin.
def _lire_prefs_boot():
    try:
        with open(chemin_donnees("parametres_flex.json"), "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _ecrire_prefs_boot(maj):
    d = _lire_prefs_boot()
    d.update(maj)
    try:
        with open(chemin_donnees("parametres_flex.json"), "w", encoding="utf-8") as f:
            json.dump(d, f)
    except Exception:
        pass


def _mini_benchmark_ecran():
    """Mesure la vitesse réelle de l'écran (remplissage + 120 tuiles + affichage) pour choisir la résolution."""
    try:
        tuile = pygame.Surface((100, 100)).convert()
        tuile.fill((30, 40, 70))
        travail, affichage = [], []
        for _ in range(12):
            t0 = _time.perf_counter()
            ecran.fill((8, 10, 20))
            for a in range(15):
                for b in range(8):
                    ecran.blit(tuile, (a * 100, b * 90))
            t1 = _time.perf_counter()
            pygame.display.flip()
            affichage.append((_time.perf_counter() - t1) * 1000.0)
            travail.append((t1 - t0) * 1000.0)
        cout = sum(travail[4:]) / len(travail[4:]) + max(0.0, sum(affichage[4:]) / len(affichage[4:]) - 15.0)
    except Exception:
        return 1.0
    return 1.0 if cout <= 7 else (0.75 if cout <= 14 else 0.5)


_PB = _lire_prefs_boot()
EXTRA = {"echelle_auto": _PB.get("echelle_auto"), "_essai": int(_PB.get("_essai", 0) or 0), "suggere": False}
ECHELLE = 1.0
MOUSE_K = {"k": 1.0}
CAL = {"f": None, "m": None}
_idx_res = _PB.get("resolution", 0)
if not isinstance(_idx_res, int) or not 0 <= _idx_res <= 3:
    _idx_res = 0
if EXTRA["_essai"] >= 2:
    # deux lancements de suite n'ont pas tenu avec une résolution réduite : retour sécurisé à 100 %
    _idx_res, EXTRA["echelle_auto"], EXTRA["_essai"] = 1, 1.0, 0
    _ecrire_prefs_boot({"resolution": 1, "echelle_auto": 1.0, "_essai": 0})
_cible_ech = 1.0
if _idx_res == 2:
    _cible_ech = 0.75
elif _idx_res == 3:
    _cible_ech = 0.5
elif _idx_res == 0:
    if EXTRA["echelle_auto"] in (0.75, 0.5, 1.0):
        _cible_ech = EXTRA["echelle_auto"]
    else:
        _cible_ech = 1.0 if IS_WEB else _mini_benchmark_ecran()
        EXTRA["echelle_auto"] = _cible_ech
        _ecrire_prefs_boot({"echelle_auto": _cible_ech})
if IS_WEB:
    _cible_ech = 1.0
if _cible_ech < 0.99:
    try:
        _taille_petite = (int(LARGEUR * _cible_ech), int(HAUTEUR * _cible_ech))
        _petit = pygame.display.set_mode(_taille_petite, pygame.FULLSCREEN | pygame.SCALED)
        if _petit.get_size() != _taille_petite:
            raise RuntimeError("taille de surface inattendue : " + str(_petit.get_size()))
        ECHELLE = _cible_ech
        ecran = CibleEchelle(ECHELLE, _petit)
        DRAW = _DESSIN_ECHELLE
        MOUSE_K["k"] = 1.0 / ECHELLE
        EXTRA["_essai"] += 1
        _ecrire_prefs_boot({"_essai": EXTRA["_essai"]})
    except Exception as _e:
        print("⚠️ Résolution réduite indisponible, on reste à 100% :", _e)
        ecran = pygame.display.set_mode((LARGEUR, HAUTEUR), 0 if IS_WEB else pygame.FULLSCREEN)
        LARGEUR, HAUTEUR = ecran.get_size()


def pos_ev(event):
    """Position d'un événement souris dans le repère du jeu."""
    k = MOUSE_K["k"]
    return (event.pos[0] * k, event.pos[1] * k)


def _calibrer_souris(event):
    """Un toucher envoie un événement doigt ET souris : on compare les deux pour vérifier l'échelle de la souris."""
    if ECHELLE >= 0.99:
        return
    t = pygame.time.get_ticks()
    if event.type == pygame.FINGERDOWN:
        CAL["f"] = (event.x * LARGEUR, event.y * HAUTEUR, t)
    elif event.type == pygame.MOUSEBUTTONDOWN:
        CAL["m"] = (event.pos[0], event.pos[1], t)
    else:
        return
    f, m = CAL["f"], CAL["m"]
    if f and m and abs(f[2] - m[2]) < 80:
        for fv, mv in ((f[0], m[0]), (f[1], m[1])):
            if mv > 120 and fv > 120 and 0.9 <= fv / float(mv) <= 2.3:
                MOUSE_K["k"] = fv / float(mv)
        CAL["f"] = CAL["m"] = None



# ==================== ÉCRAN IMMÉDIAT ====================
# Dès que la fenêtre existe, on affiche le logo : le joueur ne reste jamais devant un écran noir pendant que les fichiers se chargent.
DEMARRAGE = {"actif": True}


def _ecran_precoce():
    try:
        police_logo = pygame.font.SysFont(None, 110)
        police_info = pygame.font.SysFont(None, 34)
        ecran.fill((4, 5, 14))
        cx, cy = LARGEUR // 2, int(HAUTEUR * 0.40)
        for dx, couleur in ((-4, (255, 60, 190)), (4, (0, 220, 255)), (0, (255, 255, 255))):
            t = police_logo.render("FLEXPLAY", True, couleur)
            ecran.blit(t, (cx - t.get_width() // 2 + dx, cy - t.get_height() // 2))
        t = police_info.render("présente", True, (0, 200, 240))
        ecran.blit(t, (cx - t.get_width() // 2, cy + 52))
        t = police_info.render("Chargement des ressources...", True, (235, 240, 255))
        ecran.blit(t, (cx - t.get_width() // 2, HAUTEUR - 112))
        bw = min(460, LARGEUR - 120)
        bx, by = cx - bw // 2, HAUTEUR - 64
        DRAW.rect(ecran, (16, 20, 40), (bx, by, bw, 12), border_radius=6)
        DRAW.rect(ecran, (0, 220, 255), (bx, by, bw // 6, 12), border_radius=6)
        DRAW.rect(ecran, (0, 150, 190), (bx, by, bw, 12), 2, border_radius=6)
        pygame.display.flip()
        pygame.event.pump()
    except Exception as e:
        print("⚠️ Écran de démarrage immédiat indisponible :", e)


_ecran_precoce()


# 2. CHARGEMENT DES SONS (fichiers déposés dans le dossier du jeu)
try:
    pygame.mixer.init()
    son_tir = pygame.mixer.Sound(_asset("tir.wav"))
    son_explosion = pygame.mixer.Sound(_asset("explosion.ogg" if IS_WEB else "explosion.mp3"))
    son_echec = pygame.mixer.Sound(_asset("echec.wav"))
    son_victoire = pygame.mixer.Sound(_asset("victoire.wav"))
    son_tir.set_volume(0.5)
    son_explosion.set_volume(0.6)
    son_echec.set_volume(0.7)
    son_victoire.set_volume(0.7)
    SON_ACTIF = True
except Exception as e:
    print(f"⚠️ Sons indisponibles : {e}")
    SON_ACTIF = False

try:
    pygame.mixer.music.load(_asset("musique_ambiance.ogg" if IS_WEB else "musique_ambiance.mp3"))
    pygame.mixer.music.set_volume(0.4)
    MUSIQUE_ACTIVE = True
except Exception as e:
    print(f"⚠️ Musique d'ambiance indisponible : {e}")
    MUSIQUE_ACTIVE = False

musique_lancee = False

# 3. CHARGEMENT DES SPRITES AVEC LES NOMS DE FICHIERS REMOVEBG
try:
    img_joueur_droite = pygame.image.load(_asset("perso-removebg-preview.png")).convert_alpha()
    img_joueur_droite = pygame.transform.scale(img_joueur_droite, (TAILLE_PERSO, TAILLE_PERSO))
    img_joueur_gauche = pygame.transform.flip(img_joueur_droite, True, False)
    img_joueur_actuel = img_joueur_droite
    _img_joueur_defaut = img_joueur_droite

    img_drone = pygame.image.load(_asset("drone__23_-removebg-preview.png")).convert_alpha()
    img_drone = pygame.transform.scale(img_drone, (40, 40))

    img_core = pygame.image.load(_asset("core.png")).convert_alpha()
    img_core = pygame.transform.scale(img_core, (TAILLE_CASE, TAILLE_CASE))

    MODE_GRAPHIQUE = "REALISTE"
except Exception as e:
    print(f"⚠️ Mode réaliste indisponible (fichiers manquants) : {e}")
    MODE_GRAPHIQUE = "NEON"

# 3bis. CHARGEMENT DU BOSS
TAILLE_BOSS = 260
RAYON_CORPS_BOSS = TAILLE_BOSS * 0.30
try:
    img_boss = pygame.image.load(_asset("boss.png")).convert_alpha()
    img_boss = pygame.transform.smoothscale(img_boss, (TAILLE_BOSS, TAILLE_BOSS))
    BOSS_IMAGE_DISPONIBLE = True
except Exception as e:
    print(f"⚠️ Image du boss indisponible : {e}")
    BOSS_IMAGE_DISPONIBLE = False

# COULEURS
NOIR_ESPACE = (5, 5, 10)
GRIS_HACKER = (20, 25, 35)
BLANC_NEON = (240, 245, 255)
VERT_FLUO = (0, 255, 128)
ROUGE_ALERTE = (255, 0, 85)
VIOLET_CYBER = (180, 0, 255)
BLEU_CYBER = (0, 190, 255)
ORANGE_MEC = (255, 130, 0)
ROSE_SYNTH = (255, 0, 180)
JAUNE_CYBER = (255, 220, 0)
CYAN_NEON = (0, 235, 255)

NOMS = [
    "TRON GRID", "TRACKERS REZ", "SYSTEM OVERLOAD", "INFILTRATION CORE", "CYBER STREETS",
    "GHOST IN THE NET", "BLACKOUT HEIST", "THE MAINFRAME", "NEON DISTRICT", "OVERLORD INTRUSION",
    "PROXY GATE", "QUANTUM FIREWALL", "DATA CORRUPTION", "CYBERDOME FALL", "THE FINAL FLEX"
]
COULEURS = [BLEU_CYBER, ORANGE_MEC, ROUGE_ALERTE, VIOLET_CYBER, BLEU_CYBER, ORANGE_MEC, ROUGE_ALERTE,
            VERT_FLUO, ROSE_SYNTH, JAUNE_CYBER, BLEU_CYBER, ORANGE_MEC, ROUGE_ALERTE, VIOLET_CYBER, JAUNE_CYBER]


# ==================== MOTEUR D'EFFETS VISUELS ====================
# Halos lumineux (additifs), tuiles néon pré-rendues, particules, secousse d'écran.
# Tout est mis en cache : très peu de calculs par image, même sur téléphone.
def melange(c1, c2, a):
    a = max(0.0, min(1.0, a))
    return (int(c1[0] * (1 - a) + c2[0] * a), int(c1[1] * (1 - a) + c2[1] * a), int(c1[2] * (1 - a) + c2[2] * a))


def eclaircir(c, a):
    a = max(0.0, a)
    return (min(255, int(c[0] * a)), min(255, int(c[1] * a)), min(255, int(c[2] * a)))


_cache_halos = {}


def obtenir_halo(rayon, couleur, intensite=1.0):
    rayon = max(4, int(rayon) // 4 * 4)
    intensite = max(0.0, min(1.0, round(intensite * 6) / 6.0))
    cle = (rayon, couleur, intensite)
    surf = _cache_halos.get(cle)
    if surf is None:
        base_r = 24
        petit = pygame.Surface((base_r * 2, base_r * 2))
        petit.fill((0, 0, 0))
        for r in range(base_r, 0, -1):
            f = min(1.0, (1 - r / float(base_r)) ** 2 * intensite)
            DRAW.circle(petit, (int(couleur[0] * f), int(couleur[1] * f), int(couleur[2] * f)), (base_r, base_r), r)
        petit = petit.convert()
        if rayon == base_r:
            surf = petit
        else:
            try:
                surf = pygame.transform.smoothscale(petit, (rayon * 2, rayon * 2))
            except Exception:
                surf = pygame.transform.scale(petit, (rayon * 2, rayon * 2))
            surf = surf.convert()
        _cache_halos[cle] = surf
    return surf


def dessiner_halo(x, y, rayon, couleur, intensite=1.0, min_q=1):
    """Lueur additive. N'est dessinée que si la qualité actuelle >= min_q."""
    if intensite < 0.08 or QUALITE["niveau"] < min_q:
        return
    rayon_q = max(4, int(rayon) // 4 * 4)
    ecran.blit(obtenir_halo(rayon, couleur, intensite), (int(x) - rayon_q, int(y) - rayon_q),
               special_flags=pygame.BLEND_RGB_ADD)


_cache_tuiles = {}


def tuile_mur(couleur, masque):
    """Mur sombre avec arête néon du côté des couloirs. masque : 1=haut 2=bas 4=gauche 8=droite."""
    cle = ("m", couleur, masque)
    t = _cache_tuiles.get(cle)
    if t is None:
        T = TAILLE_CASE
        base = (12, 15, 27)
        t = pygame.Surface((T, T))
        t.fill(base)
        DRAW.rect(t, (22, 28, 46), (14, 14, T - 28, T - 28), 2)
        DRAW.line(t, (17, 22, 38), (14, 14), (T - 14, T - 14), 1)
        DRAW.line(t, (17, 22, 38), (T - 14, 14), (14, T - 14), 1)
        DRAW.circle(t, (30, 38, 64), (T // 2, T // 2), 6, 1)
        for i in range(14):
            a = (1 - i / 14.0) ** 2
            col = melange(base, couleur, a)
            if i == 0:
                col = melange(couleur, BLANC_NEON, 0.55)
            if masque & 1:
                DRAW.line(t, col, (0, i), (T, i))
            if masque & 2:
                DRAW.line(t, col, (0, T - 1 - i), (T, T - 1 - i))
            if masque & 4:
                DRAW.line(t, col, (i, 0), (i, T))
            if masque & 8:
                DRAW.line(t, col, (T - 1 - i, 0), (T - 1 - i, T))
        t = t.convert()
        _cache_tuiles[cle] = t
    return t


def tuile_sol(couleur, variante, masque=0):
    """Sol sombre teinté. masque (1=haut 2=bas 4=gauche 8=droite) : murs voisins qui projettent une ombre."""
    cle = ("s", couleur, variante, masque)
    t = _cache_tuiles.get(cle)
    if t is None:
        T = TAILLE_CASE
        fond = melange((5, 7, 14), couleur, 0.07 + 0.02 * variante)
        t = pygame.Surface((T, T))
        t.fill(fond)
        DRAW.rect(t, melange(fond, couleur, 0.22), (0, 0, T, T), 1)
        coin = melange(fond, couleur, 0.55)
        for cx_, cy_, sx, sy in ((0, 0, 1, 1), (T - 1, 0, -1, 1), (0, T - 1, 1, -1), (T - 1, T - 1, -1, -1)):
            DRAW.line(t, coin, (cx_, cy_), (cx_ + sx * 9, cy_), 2)
            DRAW.line(t, coin, (cx_, cy_), (cx_, cy_ + sy * 9), 2)
        if variante:
            DRAW.rect(t, melange(fond, couleur, 0.10), (20, 20, T - 40, T - 40), 1)
        if masque:
            ombre = pygame.Surface((T, T), pygame.SRCALPHA)
            for i in range(18):
                a = int(150 * (1 - i / 18.0) ** 2)
                if masque & 1:
                    DRAW.line(ombre, (0, 0, 8, a), (0, i), (T, i))
                if masque & 4:
                    DRAW.line(ombre, (0, 0, 8, a), (i, 0), (i, T))
            for i in range(10):
                a = int(95 * (1 - i / 10.0) ** 2)
                if masque & 2:
                    DRAW.line(ombre, (0, 0, 8, a), (0, T - 1 - i), (T, T - 1 - i))
                if masque & 8:
                    DRAW.line(ombre, (0, 0, 8, a), (T - 1 - i, 0), (T - 1 - i, T))
            t.blit(ombre, (0, 0))
        t = t.convert()
        _cache_tuiles[cle] = t
    return t


# ---- Particules, ondes de choc, secousse d'écran
particules_fx = []   # [x, y, vx, vy, vie, vie_max, couleur, taille]
ondes_fx = []        # [x, y, rayon, rayon_max, couleur, vie, vie_max]
ETAT_FX = {"secousse": 0.0}
CAM = {"x": 0.0, "y": 0.0}   # position lissée de la caméra
def max_particules():
    return (40, 90, 200)[QUALITE["niveau"]]


def creer_explosion(x, y, couleur, nombre=24, vitesse=7.0, secousse=3.0):
    if PARAMS["secousse"]:
        ETAT_FX["secousse"] = min(14.0, max(ETAT_FX["secousse"], secousse))
    if not PARAMS["particules"]:
        return
    palette = [couleur, couleur, BLANC_NEON, JAUNE_CYBER if couleur != VERT_FLUO else (180, 255, 210)]
    for _ in range(nombre):
        if len(particules_fx) >= max_particules():
            break
        ang = random.uniform(0, math.tau)
        v = random.uniform(1.0, vitesse)
        vie = random.randint(18, 40)
        particules_fx.append([x, y, math.cos(ang) * v, math.sin(ang) * v, vie, vie,
                              random.choice(palette), random.uniform(1.5, 3.6)])
    ondes_fx.append([x, y, 6.0, 40.0 + nombre * 1.2, couleur, 20, 20])


def creer_etincelles(x, y, couleur, nombre=6):
    if not PARAMS["particules"]:
        return
    for _ in range(nombre):
        if len(particules_fx) >= max_particules():
            break
        ang = random.uniform(0, math.tau)
        v = random.uniform(0.8, 4.0)
        vie = random.randint(8, 18)
        particules_fx.append([x, y, math.cos(ang) * v, math.sin(ang) * v, vie, vie,
                              random.choice([couleur, BLANC_NEON]), random.uniform(1.2, 2.4)])


def creer_propulsion(x, y, vx, vy, couleur):
    if not PARAMS["particules"]:
        return
    if len(particules_fx) < max_particules():
        vie = random.randint(10, 18)
        particules_fx.append([x - vx * 1.5 + random.uniform(-5, 5), y - vy * 1.5 + random.uniform(-5, 5),
                              -vx * 0.12 + random.uniform(-0.4, 0.4), -vy * 0.12 + random.uniform(-0.4, 0.4),
                              vie, vie, couleur, 2.6])


def mettre_a_jour_fx():
    for p in particules_fx:
        p[0] += p[2]
        p[1] += p[3]
        p[2] *= 0.93
        p[3] *= 0.93
        p[4] -= 1
    particules_fx[:] = [p for p in particules_fx if p[4] > 0]
    for o in ondes_fx:
        o[2] += (o[3] - o[2]) * 0.2
        o[5] -= 1
    ondes_fx[:] = [o for o in ondes_fx if o[5] > 0]
    s = ETAT_FX["secousse"]
    ETAT_FX["secousse"] = s * 0.86 if s > 0.4 else 0.0


def dessiner_fx(ox, oy):
    for o in ondes_fx:
        a = o[5] / float(o[6])
        ex_, ey_ = int(o[0] + ox), int(o[1] + oy)
        dessiner_halo(ex_, ey_, int(o[2]) + 24, o[4], 0.8 * a, 2)
        DRAW.circle(ecran, eclaircir(o[4], a), (ex_, ey_), max(2, int(o[2])), max(1, int(4 * a)))
    for p in particules_fx:
        a = p[4] / float(p[5])
        x, y = int(p[0] + ox), int(p[1] + oy)
        DRAW.line(ecran, eclaircir(p[6], a), (x, y), (int(x - p[2] * 2), int(y - p[3] * 2)),
                         max(1, int(p[7] * a + 0.5)))


_cache_textes = {}


def rendu_texte(police, texte, aa, couleur):
    """Comme police.render() mais mémorise le résultat (gros gain : le texte n'est dessiné qu'une fois)."""
    cle = (id(police), texte, couleur)
    s = _cache_textes.get(cle)
    if s is None:
        if len(_cache_textes) > 500:
            _cache_textes.clear()
        s = police.render(texte, aa, couleur)
        _cache_textes[cle] = s
    return s


_cache_voiles = {}


def obtenir_voile(w, h, rgba):
    """Surface translucide créée une seule fois (au lieu de la recréer à chaque image)."""
    cle = (w, h, rgba)
    s = _cache_voiles.get(cle)
    if s is None:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        s.fill(rgba)
        s = s.convert_alpha()
        _cache_voiles[cle] = s
    return s


_cache_boutons = {}


def bouton_neon(rect, couleur, texte, police, plein=False, pulse=False):
    """Bouton néon pré-rendu (le halo 'respire' sur 4 niveaux mis en cache)."""
    complet = QUALITE["niveau"] >= 1
    niveau_pulse = 3
    if pulse and complet:
        niveau_pulse = int((math.sin(pygame.time.get_ticks() / 280.0) + 1) * 1.5 + 0.5)
    cle = (rect.width, rect.height, couleur, texte, id(police), plein, niveau_pulse, complet)
    s = _cache_boutons.get(cle)
    marge = 22
    if s is None:
        force = 0.55 + 0.15 * niveau_pulse
        s = pygame.Surface((rect.width + marge * 2, rect.height + marge * 2), pygame.SRCALPHA)
        r0 = pygame.Rect(marge, marge, rect.width, rect.height)
        rayon_coin = 12
        for i in (range(6, 0, -1) if complet else (3, 1)):
            a = (1 - i / 7.0) * 0.55 * force
            DRAW.rect(s, eclaircir(couleur, a), r0.inflate(i * 5, i * 5), width=3, border_radius=rayon_coin + i * 2)
        if plein:
            DRAW.rect(s, couleur, r0, border_radius=rayon_coin)
            DRAW.rect(s, melange(couleur, BLANC_NEON, 0.45), (r0.x + 4, r0.y + 4, r0.width - 8, r0.height // 3),
                             border_radius=min(rayon_coin - 3, r0.height // 6))
            couleur_texte = NOIR_ESPACE
        else:
            DRAW.rect(s, (8, 10, 20), r0, border_radius=rayon_coin)
            DRAW.rect(s, couleur, r0, width=3, border_radius=rayon_coin)
            couleur_texte = couleur
        t = rendu_texte(police, texte, True, couleur_texte)
        s.blit(t, (r0.centerx - t.get_width() // 2, r0.centery - t.get_height() // 2))
        s = s.convert_alpha()
        _cache_boutons[cle] = s
    ecran.blit(s, (rect.x - marge, rect.y - marge))


# ==================== FOND DE VILLE (vue du dessus, autour du labyrinthe) ====================
# Une seule tuile est dessinée au démarrage, puis répétée avec un effet de profondeur (parallaxe).
TUILE_VILLE = 480
LARGEUR_ROUTE = 40
_tuile_ville = None


def dessiner_toit(s, rect, couleur, alea):
    x, y, w, h = rect
    base = alea.choice([(10, 9, 24), (12, 10, 28), (8, 11, 24)])
    DRAW.rect(s, base, rect)
    DRAW.rect(s, melange(base, couleur, 0.10), (x - 4, y - 4, w + 8, h + 8), 4)
    DRAW.rect(s, melange(base, couleur, 0.30), rect, 3)
    DRAW.rect(s, melange(couleur, BLANC_NEON, 0.35), rect, 1)
    DRAW.rect(s, melange(base, couleur, 0.16), (x + 10, y + 10, w - 20, h - 20), 1)
    cx_, cy_ = x + w // 2, y + h // 2
    type_toit = alea.randint(0, 3)
    if type_toit == 0:      # héliport
        r = min(w, h) // 5
        DRAW.circle(s, melange(base, couleur, 0.55), (cx_, cy_), r, 3)
        DRAW.line(s, melange(base, couleur, 0.55), (cx_ - r // 2, cy_ - r // 2), (cx_ - r // 2, cy_ + r // 2), 3)
        DRAW.line(s, melange(base, couleur, 0.55), (cx_ + r // 2, cy_ - r // 2), (cx_ + r // 2, cy_ + r // 2), 3)
        DRAW.line(s, melange(base, couleur, 0.55), (cx_ - r // 2, cy_), (cx_ + r // 2, cy_), 3)
    elif type_toit == 1:    # panneaux / ventilateurs
        for gx in range(x + 22, x + w - 40, 38):
            for gy in range(y + 22, y + h - 40, 38):
                DRAW.rect(s, melange(base, (70, 90, 130), 0.30), (gx, gy, 28, 28))
                DRAW.rect(s, melange(base, couleur, 0.35), (gx, gy, 28, 28), 1)
                DRAW.circle(s, melange(base, couleur, 0.40), (gx + 14, gy + 14), 8, 1)
    elif type_toit == 2:    # bandeau néon + antennes
        DRAW.line(s, melange(base, couleur, 0.30), (x + 16, cy_), (x + w - 16, cy_), 7)
        DRAW.line(s, couleur, (x + 16, cy_), (x + w - 16, cy_), 2)
        for ax in (x + w // 4, x + 3 * w // 4):
            DRAW.circle(s, melange(couleur, BLANC_NEON, 0.5), (ax, y + h // 4), 3)
            DRAW.circle(s, melange(base, couleur, 0.5), (ax, y + h // 4), 9, 1)
    else:                   # noyau énergétique
        for k in range(4):
            c_k = melange(base, couleur, 0.15 + 0.12 * k)
            m = 20 + k * 16
            DRAW.rect(s, c_k, (x + m, y + m, w - 2 * m, h - 2 * m), 2)
        DRAW.rect(s, melange(base, couleur, 0.6), (cx_ - 8, cy_ - 8, 16, 16))
    for _ in range(alea.randint(2, 4)):
        bw, bh = alea.randint(12, 22), alea.randint(10, 18)
        bx = alea.randint(x + 14, max(x + 15, x + w - 14 - bw))
        by = alea.randint(y + 14, max(y + 15, y + h - 14 - bh))
        DRAW.rect(s, melange(base, (80, 95, 130), 0.28), (bx, by, bw, bh))
        DRAW.rect(s, melange(base, (80, 95, 130), 0.55), (bx, by, bw, bh), 1)
    for px_, py_ in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
        DRAW.circle(s, melange(couleur, BLANC_NEON, 0.4), (px_, py_), 3)


def construire_tuile_ville():
    T, L = TUILE_VILLE, LARGEUR_ROUTE
    alea = random.Random(21)
    s = pygame.Surface((T, T))
    s.fill((5, 5, 13))
    route = (3, 3, 9)
    DRAW.rect(s, route, (0, 0, T, L))
    DRAW.rect(s, route, (0, 0, L, T))
    c = L // 2
    for d in range(0, T, 30):
        DRAW.line(s, (62, 54, 12), (d, c), (d + 15, c), 2)
        DRAW.line(s, (62, 54, 12), (c, d), (c, d + 15), 2)
    bord = melange((5, 5, 13), BLEU_CYBER, 0.30)
    for d in (3, L - 4):
        DRAW.line(s, bord, (0, d), (T, d), 1)
        DRAW.line(s, bord, (d, 0), (d, T), 1)
    for i in range(5):                                   # passages piétons
        DRAW.rect(s, (34, 34, 52), (L + 8 + i * 8, 7, 4, L - 14))
        DRAW.rect(s, (34, 34, 52), (7, L + 8 + i * 8, L - 14, 4))
    palette = [BLEU_CYBER, ROSE_SYNTH, VIOLET_CYBER]
    ruelle = 16
    cote = (T - L - ruelle) // 2
    for i in range(2):
        for j in range(2):
            marge = alea.randint(7, 12)
            x0 = L + i * (cote + ruelle) + marge
            y0 = L + j * (cote + ruelle) + marge
            dessiner_toit(s, (x0, y0, cote - 2 * marge, cote - 2 * marge), palette[(i * 2 + j + alea.randint(0, 2)) % 3], alea)
    return s.convert()


def dessiner_fond_ville(ox, oy, t_ms, rect_cache=None):
    global _tuile_ville
    if _tuile_ville is None:
        _tuile_ville = construire_tuile_ville()
    T = TUILE_VILLE
    c = LARGEUR_ROUTE // 2
    brut_x, brut_y = int(ox * 0.45), int(oy * 0.45)      # la ville bouge moins vite que le labyrinthe : effet de profondeur
    depart_x, depart_y = brut_x % T - T, brut_y % T - T
    tuile = obtenir_tuile_ville_floue() if PARAMS["dof"] else _tuile_ville
    avec_trafic = QUALITE["niveau"] >= 1 and bool(PARAMS["ville_anim"])
    couleurs_trafic = (ROSE_SYNTH, BLEU_CYBER, JAUNE_CYBER)
    x = depart_x
    while x < LARGEUR:
        y = depart_y
        while y < HAUTEUR:
            if rect_cache is not None and x >= rect_cache[0] and y >= rect_cache[1] \
                    and x + T <= rect_cache[0] + rect_cache[2] and y + T <= rect_cache[1] + rect_cache[3]:
                y += T          # tuile entièrement sous le labyrinthe : inutile de la dessiner
                continue
            ecran.blit(tuile, (x, y))
            if avec_trafic:
                wi, wj = (x - brut_x) // T, (y - brut_y) // T
                h = ((wi * 73856093) ^ (wj * 19349663)) & 0xFFFF
                if h % 3:
                    sens = 1 if h & 4 else -1
                    avance = int((t_ms * (0.16 + (h % 5) * 0.03) + h) % T)
                    tete = x + avance if sens > 0 else x + T - avance
                    ligne_y = y + c + 7 * sens
                    col = couleurs_trafic[h % 3]
                    DRAW.line(ecran, eclaircir(col, 0.35), (tete - sens * 46, ligne_y), (tete, ligne_y), 5)
                    DRAW.line(ecran, eclaircir(col, 1.0), (tete - sens * 30, ligne_y), (tete, ligne_y), 2)
                if (h >> 3) % 3:
                    sens = 1 if h & 8 else -1
                    avance = int((t_ms * (0.14 + (h % 4) * 0.03) + h * 3) % T)
                    tete = y + avance if sens > 0 else y + T - avance
                    ligne_x = x + c + 7 * sens
                    col = couleurs_trafic[(h >> 2) % 3]
                    DRAW.line(ecran, eclaircir(col, 0.35), (ligne_x, tete - sens * 46), (ligne_x, tete), 5)
                    DRAW.line(ecran, eclaircir(col, 1.0), (ligne_x, tete - sens * 30), (ligne_x, tete), 2)
            y += T
        x += T


def _anneau(x, y, w, h, ep, couleur):
    """Cadre d'épaisseur ep AUTOUR du rectangle (x, y, w, h), dessiné uniquement dans la zone visible."""
    X0, Y0, X1, Y1 = x - ep, y - ep, x + w + ep, y + h + ep
    for bx0, by0, bx1, by1 in ((X0, Y0, X1, Y0 + ep), (X0, Y1 - ep, X1, Y1),
                                (X0, Y0 + ep, X0 + ep, Y1 - ep), (X1 - ep, Y0 + ep, X1, Y1 - ep)):
        bx0, by0, bx1, by1 = max(bx0, 0), max(by0, 0), min(bx1, LARGEUR), min(by1, HAUTEUR)
        if bx1 > bx0 and by1 > by0:
            DRAW.rect(ecran, couleur, (bx0, by0, bx1 - bx0, by1 - by0))


def dessiner_cadre_carte(ox, oy, phase):
    """Phase 0 : ombre sombre autour du labyrinthe (avant). Phase 1 : liseré néon (après les murs)."""
    w, h = len(CARTE[0]) * TAILLE_CASE, len(CARTE) * TAILLE_CASE
    if phase == 0:
        _anneau(ox, oy, w, h, 22, (2, 2, 8))
    else:
        _anneau(ox, oy, w, h, 6, eclaircir(COULEUR_MUR, 0.22))
        _anneau(ox, oy, w, h, 3, eclaircir(COULEUR_MUR, 0.55))
        _anneau(ox + 1, oy + 1, w - 2, h - 2, 2, melange(COULEUR_MUR, BLANC_NEON, 0.5))


# ==================== TRANSITIONS D'ÉCRAN, ÉCRAN DE CHARGEMENT ET MARQUE ====================
# Durées en secondes (modifie-les à ta guise)
DUREE_CHARGEMENT = 2.0          # texte « Chargement... » pour un changement d'écran
DUREE_CHARGEMENT_RAPIDE = 0.9   # pour REJOUER / SUIVANT (pour ne pas trop attendre à chaque essai)
DUREE_COUVRIR = 0.35            # le rideau néon se ferme
DUREE_REVELER = 0.45            # le rideau néon s'ouvre sur le nouvel écran

TRANS = {"actif": False, "phase": 0, "t0": 0, "duree": 2000.0, "cible": None}
AIDE = {"scroll": 0.0, "drag": False, "id": None, "y": 0.0}   # défilement vertical du guide


def lancer_transition(cible, duree=None):
    """cible = ('etat', ETAT_X) | ('commencer',) | ('niveau', idx) | ('quitter_partie',) | ('rejouer',) | ('suivant',)"""
    if TRANS["actif"]:
        return
    TRANS["actif"] = True
    TRANS["phase"] = 0
    TRANS["t0"] = pygame.time.get_ticks()
    TRANS["duree"] = (DUREE_CHARGEMENT if duree is None else duree) * 1000.0
    TRANS["cible"] = cible


def dessiner_rideau(w):
    """Deux panneaux sombres bordés de néon qui se ferment (ou s'ouvrent) depuis les côtés."""
    if w <= 0:
        return
    fond = (4, 5, 14)
    DRAW.rect(ecran, fond, (0, 0, w, HAUTEUR))
    DRAW.rect(ecran, fond, (LARGEUR - w, 0, w, HAUTEUR))
    for y in range(0, HAUTEUR, 48):
        DRAW.line(ecran, (10, 16, 34), (0, y), (w, y), 1)
        DRAW.line(ecran, (10, 16, 34), (LARGEUR - w, y), (LARGEUR, y), 1)
    for i in range(8):
        c = eclaircir(BLEU_CYBER, (1 - i / 8.0) ** 2)
        DRAW.line(ecran, c, (w + i, 0), (w + i, HAUTEUR))
        DRAW.line(ecran, c, (LARGEUR - w - i - 1, 0), (LARGEUR - w - i - 1, HAUTEUR))
    bord = melange(BLEU_CYBER, BLANC_NEON, 0.6)
    DRAW.line(ecran, bord, (w, 0), (w, HAUTEUR), 3)
    DRAW.line(ecran, bord, (LARGEUR - w - 1, 0), (LARGEUR - w - 1, HAUTEUR), 3)


def dessiner_chargement(avancement):
    ecran.fill((4, 5, 14))
    t = pygame.time.get_ticks()
    dessiner_halo(LARGEUR // 2, HAUTEUR // 2 - 40, 200, (60, 20, 110), 0.55)
    dessiner_titre_glitch("FLEX CYBERPUNK", police_titre, LARGEUR // 2, HAUTEUR // 2 - 90)
    s2 = rendu_texte(police_petite, "Développé par FlexPlay", True, ROSE_SYNTH)
    ecran.blit(s2, (LARGEUR // 2 - s2.get_width() // 2, HAUTEUR // 2 + 5))

    aff = min(1.0, max(0.0, avancement)) ** 0.85
    nb_points = 1 + (t // 350) % 3
    ref = rendu_texte(police_jeu, "Chargement...", True, BLANC_NEON)
    txt = rendu_texte(police_jeu, "Chargement" + "." * nb_points, True, BLANC_NEON)
    ecran.blit(txt, (LARGEUR // 2 - ref.get_width() // 2, HAUTEUR - 112))

    bw, bh = min(460, LARGEUR - 120), 12
    bx, by = LARGEUR // 2 - bw // 2, HAUTEUR - 64
    DRAW.rect(ecran, (16, 20, 40), (bx, by, bw, bh), border_radius=6)
    rempli = int(bw * aff)
    if rempli > 4:
        DRAW.rect(ecran, BLEU_CYBER, (bx, by, rempli, bh), border_radius=min(6, rempli // 2))
        DRAW.rect(ecran, (170, 235, 255), (bx + 2, by + 2, max(2, rempli - 4), 3), border_radius=1)
        dessiner_halo(bx + rempli, by + bh // 2, 34, BLEU_CYBER, 0.8)
    DRAW.rect(ecran, eclaircir(BLEU_CYBER, 0.55), (bx, by, bw, bh), 2, border_radius=6)
    pct = rendu_texte(police_petite, f"{int(aff * 100)}%", True, BLEU_CYBER)
    ecran.blit(pct, (LARGEUR // 2 - pct.get_width() // 2, by + 18))
    cr = rendu_texte(police_petite, "© 2026 FlexPlay", True, (150, 160, 195))
    ecran.blit(cr, (LARGEUR - cr.get_width() - 24, HAUTEUR - 30))


def lisser(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def dessiner_transition():
    t = pygame.time.get_ticks() - TRANS["t0"]
    phase = TRANS["phase"]
    demi = LARGEUR // 2 + 2
    if phase == 0:
        dessiner_rideau(int(demi * lisser(t / (DUREE_COUVRIR * 1000.0))))
    elif phase == 1:
        dessiner_chargement(t / TRANS["duree"])
    else:
        dessiner_rideau(int(demi * (1.0 - lisser(t / (DUREE_REVELER * 1000.0)))))


def dessiner_marque(y_haut):
    """Signature du créateur (écrans hors jeu)."""
    l1 = rendu_texte(police_jeu, "FLEX CYBERPUNK", True, BLEU_CYBER)
    l2 = rendu_texte(police_petite, "Développé par FlexPlay", True, BLANC_NEON)
    l3 = rendu_texte(police_petite, "© 2026 FlexPlay", True, (150, 160, 195))
    cx = LARGEUR // 2
    ecran.blit(obtenir_voile(320, 84, (5, 6, 16, 150)), (cx - 160, y_haut - 6))
    ecran.blit(l1, (cx - l1.get_width() // 2, y_haut))
    ecran.blit(l2, (cx - l2.get_width() // 2, y_haut + 30))
    ecran.blit(l3, (cx - l3.get_width() // 2, y_haut + 50))


_tuile_ville_floue = None


def _lisser(surf, taille):
    try:
        return pygame.transform.smoothscale(surf, taille)
    except Exception:
        return pygame.transform.scale(surf, taille)


def obtenir_tuile_ville_floue():
    """Version floutée et assombrie de la ville : le décor paraît lointain, le labyrinthe reste net (profondeur de champ)."""
    global _tuile_ville_floue, _tuile_ville
    if _tuile_ville_floue is None:
        if _tuile_ville is None:
            _tuile_ville = construire_tuile_ville()
        T = TUILE_VILLE
        pt = max(8, T // 5)
        petite = _lisser(_tuile_ville, (pt, pt))
        mosaique = pygame.Surface((pt * 3, pt * 3))
        for i in range(3):
            for j in range(3):
                mosaique.blit(petite, (i * pt, j * pt))
        flou = _lisser(mosaique, (T * 3, T * 3))
        res = pygame.Surface((T, T))
        res.blit(flou, (0, 0), (T, T, T, T))
        res.fill((165, 165, 185), special_flags=pygame.BLEND_RGB_MULT)
        _tuile_ville_floue = res.convert()
    return _tuile_ville_floue


_cache_ombres = {}


def dessiner_ombre(cx, cy, w, h):
    """Ombre douce (ellipse dégradée pré-calculée) sous un personnage."""
    cle = (w, h)
    s = _cache_ombres.get(cle)
    if s is None:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(8):
            r = i * 0.09
            DRAW.ellipse(s, (0, 0, 0, 16 + i * 11),
                         (int(w * r / 2), int(h * r / 2), max(2, int(w * (1 - r))), max(2, int(h * (1 - r)))))
        s = s.convert_alpha()
        _cache_ombres[cle] = s
    ecran.blit(s, (int(cx - w // 2), int(cy - h // 2)))


# 4. GÉNÉRATION PROCÉDURALE DE LABYRINTHE (mode infini)
def generer_labyrinthe(largeur_cellules, hauteur_cellules):
    lignes = hauteur_cellules * 2 + 1
    colonnes = largeur_cellules * 2 + 1
    grille = [[1] * colonnes for _ in range(lignes)]

    def voisins_cellule(r, c):
        candidats = []
        for dr, dc in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            nr, nc = r + dr, c + dc
            if 0 < nr < lignes - 1 and 0 < nc < colonnes - 1:
                candidats.append((nr, nc))
        random.shuffle(candidats)
        return candidats

    grille[1][1] = 0
    pile = [(1, 1)]
    while pile:
        r, c = pile[-1]
        suivants = [(nr, nc) for nr, nc in voisins_cellule(r, c) if grille[nr][nc] == 1]
        if suivants:
            nr, nc = suivants[0]
            grille[(r + nr) // 2][(c + nc) // 2] = 0
            grille[nr][nc] = 0
            pile.append((nr, nc))
        else:
            pile.pop()
    return grille


def cellule_la_plus_eloignee(grille, depart):
    lignes, colonnes = len(grille), len(grille[0])
    distances = {depart: 0}
    file = [depart]
    while file:
        r, c = file.pop(0)
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < lignes and 0 <= nc < colonnes and grille[nr][nc] == 0 and (nr, nc) not in distances:
                distances[(nr, nc)] = distances[(r, c)] + 1
                file.append((nr, nc))
    plus_loin = max(distances, key=distances.get)
    return plus_loin, distances


def trouver_position_core(carte):
    for r, ligne in enumerate(carte):
        for c, val in enumerate(ligne):
            if val == 2:
                return r, c
    return 1, 1


def calcul_delais_spawn(niveau):
    delai_min = max(15, 90 - niveau * 3)
    delai_max = max(30, 180 - niveau * 5)
    return delai_min, delai_max


def position_spawn_ennemi(carte):
    colonnes, lignes = len(carte[0]), len(carte)
    largeur_px, hauteur_px = colonnes * TAILLE_CASE, lignes * TAILLE_CASE
    x = random.randint(int(largeur_px * 0.3), max(int(largeur_px * 0.3) + 50, largeur_px - 100))
    y = random.randint(100, max(150, hauteur_px - 100))
    return x, y


DUREE_MISSION_FRAMES = 130 * 60  
NIVEAU_APPARITION_POTIONS = 8  
BONUS_POTION_FRAMES = 5 * 60
TEMPS_MAX_FRAMES = 99 * 60


def position_spawn_potion(carte):
    cellules_libres = [(r, c) for r, ligne in enumerate(carte) for c, val in enumerate(ligne) if val == 0]
    r, c = random.choice(cellules_libres)
    return c * TAILLE_CASE + TAILLE_CASE / 2, r * TAILLE_CASE + TAILLE_CASE / 2


CHEMIN_PROGRESSION = chemin_donnees("progression_flex.json")


def charger_progression():
    d, statut = lire_json_signe(CHEMIN_PROGRESSION)
    if statut == "altere":
        signaler_sauvegarde_alteree()
        return 0
    if d is None:
        return 0
    try:
        return max(0, int(d.get("niveau", 0)))
    except Exception as e:
        print(f"⚠️ Progression illisible : {e}")
        return 0


def sauvegarder_progression(niveau):
    try:
        ecrire_json_signe(CHEMIN_PROGRESSION, {"niveau": niveau})
    except Exception as e:
        print(f"⚠️ Impossible de sauvegarder la progression : {e}")


# ==================== EXTENSION : MODE DEVIL ====================
# Mode à part, façon « troll » : missions infinies, SANS drones, SANS boss, SANS chrono, SANS pouvoirs,
# avec des pièges imprévisibles : décryptage qui retombe à 99 %, clé qui s'enfuit, sol qui disparaît, fausses portes.
# Chaque mission est TOUJOURS la même (graine fixe) : le piège est injuste la 1re fois, mais on peut le mémoriser.
# Décor : une salle 30 x 18 cases (image salle_devil.png étirée dessus). Sauvegarde séparée (progression_devil.json).
# Sons : ambiance_devil en boucle pendant les missions, victoire_devil / defaite_devil à chaque issue (.ogg sur Online).
CHEMIN_DEVIL = chemin_donnees("progression_devil.json")
DEVIL_COLONNES, DEVIL_LIGNES, DEVIL_BORD = 30, 18, 2        # salle : 30 x 18 cases, murs de 2 cases (comme sur l'image)
DEVIL_CHUTE_MS = 750            # durée de la chute dans le vide avant la défaite
DEVIL_RELANCE_MS = 650          # délai avant le redémarrage automatique (après une chute)
DEVIL_RELANCE_MORT_MS = 900     # idem pour les autres morts
DEVIL = {"actif": False, "max": 0, "morts": 0, "morts_total": 0, "niveau_courant": -1,
         "trous": set(), "effondres": set(), "chute": None, "resets": 0, "gel": 0, "tp": 0,
         "sorties": [], "idx_sortie": 0, "rng": random.Random(1), "props": [],
         "relance_t": None, "musique": False, "musique_ko": False, "duck_fin": None, "stat_open": False, "stat_lose_t": -99999}
DEVIL_STAT_LOSE_MS = 10000      # statistiques : au plus 1 défaite envoyée toutes les 10 s (les morts s'enchaînent, on protège le quota Firebase)
DEVIL_COULEURS = [(255, 40, 70), (160, 70, 255), (255, 0, 180), (255, 140, 40)]


def devil_charger():
    """Retourne (mission atteinte, total des morts) depuis la sauvegarde signée du mode Devil."""
    d, statut = lire_json_signe(CHEMIN_DEVIL)
    if statut == "altere":
        signaler_sauvegarde_alteree()
        return 0, 0
    if d is None:
        return 0, 0
    try:
        return max(0, int(d.get("niveau", 0))), max(0, int(d.get("morts", 0)))
    except Exception as e:
        print(f"⚠️ Sauvegarde Devil illisible : {e}")
        return 0, 0


def devil_sauvegarder():
    try:
        ecrire_json_signe(CHEMIN_DEVIL, {"niveau": DEVIL["max"], "morts": DEVIL["morts_total"]})
    except Exception as e:
        print(f"⚠️ Impossible de sauvegarder le mode Devil : {e}")


def _devil_types(niveau):
    """Pièges actifs sur une mission : un par mission au début (appris un à un), puis des combinaisons de plus en plus vicieuses."""
    base = ["hack", "core", "fausse", "sol"]
    if niveau < 4:
        return [base[niveau]]
    r = random.Random(niveau * 977 + 5)
    return r.sample(base, min(4, 2 + (niveau - 4) // 4))


def _devil_bfs(grille, depart, bloques=()):
    """Cases atteignables depuis `depart` (sans traverser les murs, les portes ni les cases `bloques`)."""
    vu, file, i = {depart}, [depart], 0
    while i < len(file):
        r, c = file[i]
        i += 1
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            n = (r + dr, c + dc)
            if n not in vu and n not in bloques and 0 <= n[0] < len(grille) and 0 <= n[1] < len(grille[0]) and grille[n[0]][n[1]] in (0, 2):
                vu.add(n)
                file.append(n)
    return vu


def _devil_interieur(porte, lignes, colonnes):
    """Case de la salle située juste devant une porte (les portes sont sur la rangée intérieure des murs)."""
    r, c = porte
    if r == DEVIL_BORD - 1:
        return (r + 1, c)
    if r == lignes - DEVIL_BORD:
        return (r - 1, c)
    if c == DEVIL_BORD - 1:
        return (r, c + 1)
    return (r, c - 1)


def devil_generer_niveau(niveau):
    """Une SALLE de 30 x 18 cases : murs de 2 cases, caisses d'angle (dessinées sur l'image), mobilier qui sert d'obstacles,
    une clé à trouver, une porte à atteindre."""
    graine = 7919 * (niveau + 1) + 4242
    for tentative in range(60):
        rng = random.Random(graine + tentative * 7919)          # 1re tentative = disposition normale ; sinon on en retire une autre
        colonnes, lignes, B = DEVIL_COLONNES, DEVIL_LIGNES, DEVIL_BORD
        grille = [[1] * colonnes for _ in range(lignes)]
        for r in range(B, lignes - B):
            for c in range(B, colonnes - B):
                grille[r][c] = 0
        depart = (lignes // 2, B)

        props = []
        for r, c in ((B, B), (B, colonnes - B - 2), (lignes - B - 2, B), (lignes - B - 2, colonnes - B - 2)):
            for i in range(2):                                  # les 4 grosses caisses d'angle de l'image
                for j in range(2):
                    grille[r + i][c + j] = 1
            props.append((r, c, 2, 2, "coin", 0))

        nb_obstacles, posees = min(8 + niveau * 2, 36), 0       # mobilier : de plus en plus nombreux
        for _ in range(nb_obstacles * 10):
            if posees >= nb_obstacles:
                break
            h, w = rng.choice([(1, 1), (1, 1), (1, 2), (2, 1), (2, 2), (1, 3), (3, 1)])
            r, c = rng.randint(B, lignes - B - h), rng.randint(B + 2, colonnes - B - w)
            cases = [(r + i, c + j) for i in range(h) for j in range(w)]
            if not all(grille[a][b] == 0 and abs(a - depart[0]) + abs(b - depart[1]) >= 3 for a, b in cases):
                continue
            if (h, w) == (1, 1):
                genre = rng.choice(["caisse", "baril", "chaise", "caisse"])
            elif (h, w) in ((1, 2), (2, 1)):
                genre = "banc"
            elif (h, w) == (2, 2):
                genre = "clim"
            else:
                genre = rng.choice(["etagere", "banc"])
            for a, b in cases:
                grille[a][b] = 1
            props.append((r, c, h, w, genre, rng.randrange(4)))
            posees += 1
        libres = _devil_bfs(grille, depart)
        for r in range(B, lignes - B):                          # poches fermées : on les bouche
            for c in range(B, colonnes - B):
                if grille[r][c] == 0 and (r, c) not in libres:
                    grille[r][c] = 1
                    props.append((r, c, 1, 1, "caisse", rng.randrange(4)))

        types = _devil_types(niveau)
        resets = min(1 + niveau // 10, 3) if "hack" in types else 0
        nb_tp = min(1 + niveau // 8, 3) if "core" in types else 0
        nb_fausses = min(1 + niveau // 9, 3) if "fausse" in types else 0
        nb_sols = min(2 + niveau // 2, 10) if "sol" in types else 0

        # emplacements de portes : rangée intérieure des murs, avec une case libre juste devant
        emplacements = []
        for c in range(B + 1, colonnes - B - 1):
            emplacements += [(B - 1, c), (lignes - B, c)]
        for r in range(B + 1, lignes - B - 1):
            emplacements.append((r, colonnes - B))
            if abs(r - depart[0]) > 2:
                emplacements.append((r, B - 1))
        emplacements = [p for p in emplacements if _devil_interieur(p, lignes, colonnes) in libres]
        droite = [p for p in emplacements if p[1] == colonnes - B]
        if not droite:
            continue                                        # mur de droite bouché par le mobilier : nouvelle disposition
        premiere = rng.choice(sorted(droite))                   # la porte « évidente », à droite
        devant0 = _devil_interieur(premiere, lignes, colonnes)

        def _loin(p, q):                                        # hors de vue l'un de l'autre (la caméra suit le joueur)
            return abs(p[1] - q[1]) >= 11 or abs(p[0] - q[0]) >= 6
        cands = sorted(p for p in libres if _loin(p, depart) and _loin(p, devant0))
        if not cands:
            cands = sorted(p for p in libres if abs(p[0] - depart[0]) + abs(p[1] - depart[1]) >= 5)
        if droite and cands:                                # une porte à droite et une clé possibles : disposition valide
            break
    cle = rng.choice(cands)

    sorties = [premiere]
    if nb_fausses:                                          # fausses portes, puis la vraie, cachée loin d'elles
        def _dist(p, q):
            return abs(p[0] - q[0]) + abs(p[1] - q[1])
        for _ in range(nb_fausses):
            reste = [p for p in sorted(emplacements) if p not in sorties and all(_dist(p, q) >= 10 for q in sorties)]
            if len(sorties) < nb_fausses and reste:
                sorties.append(rng.choice(reste))
        reste = sorted((p for p in emplacements if p not in sorties), key=lambda p: -min(_dist(p, q) for q in sorties))
        sorties.append(rng.choice(reste[:max(1, len(reste) // 4)]) if reste else premiere)
        sorties = list(dict.fromkeys(sorties))
    devants = {_devil_interieur(p, lignes, colonnes) for p in sorties}

    trous = []                                              # sol qui disparaît : salle ouverte, donc toujours contournable
    if nb_sols:
        a, b = cle, devant0

        def _vers_segment(p):
            dx, dy = b[1] - a[1], b[0] - a[0]
            t = max(0.0, min(1.0, ((p[1] - a[1]) * dx + (p[0] - a[0]) * dy) / float(dx * dx + dy * dy or 1)))
            return math.hypot(p[1] - (a[1] + t * dx), p[0] - (a[0] + t * dy))
        cands = [p for p in sorted(libres) if abs(p[0] - depart[0]) + abs(p[1] - depart[1]) > 3 and abs(p[0] - cle[0]) + abs(p[1] - cle[1]) > 2
                 and p not in devants and grille[p[0]][p[1]] == 0]
        cands.sort(key=_vers_segment)                       # les pièges se placent surtout sur le trajet clé -> porte
        pool = cands[:max(nb_sols * 3, len(cands) // 6)]
        rng.shuffle(pool)
        for p in pool:
            if len(trous) >= nb_sols:
                break
            if any(abs(p[0] - q[0]) + abs(p[1] - q[1]) < 3 for q in trous):
                continue
            ok = _devil_bfs(grille, depart, set(trous) | {p})
            if cle in ok and all(d in ok for d in devants):
                trous.append(p)

    grille[cle[0]][cle[1]] = 2
    grille[sorties[0][0]][sorties[0][1]] = 3                # seule la 1re porte est visible : la vraie est cachée dans un mur

    if DEVIL["niveau_courant"] != niveau:
        DEVIL["morts"] = 0
    DEVIL.update(niveau_courant=niveau, trous=set(trous), effondres=set(), chute=None, resets=resets, gel=0, tp=nb_tp,
                 sorties=sorties, idx_sortie=0, rng=random.Random(graine + 99), props=props, relance_t=None)
    _devil_fond_pour(colonnes * TAILLE_CASE, lignes * TAILLE_CASE)        # image + décor préparés ici (écran de chargement)

    cycle = niveau // len(NOMS)
    suffixe = f" [CYCLE {cycle + 1}]" if cycle > 0 else ""
    return {"carte": grille, "couleur_mur": DEVIL_COULEURS[niveau % len(DEVIL_COULEURS)],
            "nom": f"MISSION {niveau + 1:02d} : {NOMS[niveau % len(NOMS)]}{suffixe}",
            "nb_ennemis": 0, "vitesse_ennemis": 1.0, "depart": depart, "est_boss": False,
            "core_cell": cle, "sortie_cell": sorties[0]}


def _niv_max():
    """Mission la plus avancée du mode actif (Devil ou solo) : sert à l'écran des missions."""
    return DEVIL["max"] if DEVIL["actif"] else niveau_max_atteint


def devil_ouvrir():
    """Clic sur l'icône DEVIL : charge la sauvegarde du mode, puis on affiche la ligne des missions (comme le solo)."""
    n, m = devil_charger()
    DEVIL["max"], DEVIL["morts_total"], DEVIL["niveau_courant"] = n, m, -1
    DEVIL["actif"] = True
    if not DEVIL["stat_open"]:
        DEVIL["stat_open"] = True
        _stat("devil_open", n)                              # stats : le joueur a ouvert le mode (lvl = mission atteinte)


def devil_lancer(idx):
    reinitialiser_partie(False, niveau_cible=idx)
    _stat("devil_start", idx)                               # stats : mission lancée depuis la ligne des missions


def _devil_teleporter_core():
    global pos_core_x, pos_core_y
    r0, c0 = niveau_data["core_cell"]
    interdits = set(DEVIL["sorties"]) | DEVIL["trous"] | DEVIL["effondres"] | {tuple(niveau_data["depart"]), (r0, c0)}
    atteignables = _devil_bfs(CARTE, tuple(niveau_data["depart"]), DEVIL["trous"] | DEVIL["effondres"])
    libres = [(r, c) for r, ligne in enumerate(CARTE) for c, v in enumerate(ligne) if v == 0 and (r, c) not in interdits and (r, c) in atteignables]
    loin = [p for p in libres if math.hypot(p[0] - r0, p[1] - c0) >= 7]
    if not loin:
        loin = sorted(libres, key=lambda p: -math.hypot(p[0] - r0, p[1] - c0))[:10]
    if not loin:
        return
    loin.sort()
    r1, c1 = DEVIL["rng"].choice(loin)
    CARTE[r0][c0] = 0
    CARTE[r1][c1] = 2
    niveau_data["core_cell"] = (r1, c1)
    pos_core_x, pos_core_y = c1 * TAILLE_CASE + TAILLE_CASE / 2, r1 * TAILLE_CASE + TAILLE_CASE / 2
    DEVIL["tp"] -= 1
    creer_explosion(c0 * TAILLE_CASE + TAILLE_CASE / 2, r0 * TAILLE_CASE + TAILLE_CASE / 2, VIOLET_CYBER, 34, 8.0, 8.0)
    creer_explosion(pos_core_x, pos_core_y, VIOLET_CYBER, 20, 5.0, 0.0)
    if SON_ACTIF:
        son_echec.play()


def _devil_fausse_sortie(cy, cx):
    global pos_sortie_x, pos_sortie_y, joueur_x, joueur_y
    ir, ic = _devil_interieur((cy, cx), len(CARTE), len(CARTE[0]))
    joueur_x, joueur_y = ic * TAILLE_CASE + TAILLE_CASE / 2, ir * TAILLE_CASE + TAILLE_CASE / 2   # le joueur est repoussé dans la salle
    CARTE[cy][cx] = 1                                       # la fausse porte disparaît : le mur se referme
    DEVIL["idx_sortie"] += 1
    nr, nc = DEVIL["sorties"][DEVIL["idx_sortie"]]
    CARTE[nr][nc] = 3
    niveau_data["sortie_cell"] = (nr, nc)
    pos_sortie_x, pos_sortie_y = nc * TAILLE_CASE + TAILLE_CASE / 2, nr * TAILLE_CASE + TAILLE_CASE / 2
    creer_explosion(cx * TAILLE_CASE + TAILLE_CASE / 2, cy * TAILLE_CASE + TAILLE_CASE / 2, ROUGE_ALERTE, 34, 8.0, 9.0)
    creer_explosion(pos_sortie_x, pos_sortie_y, VERT_FLUO, 20, 5.0, 0.0)
    if SON_ACTIF:
        son_echec.play()


def devil_pas(cx, cy):
    """Un pas de logique du mode Devil (appelé à la place du bloc hack/sortie du solo)."""
    global jauge_hack, hack_reussi, partie_gagnee, partie_perdue, message_defaite, joueur_x, joueur_y
    now = pygame.time.get_ticks()
    if DEVIL["chute"] is not None:                          # le joueur tombe : plus rien ne bouge, puis défaite
        if now - DEVIL["chute"]["t0"] >= DEVIL_CHUTE_MS and not partie_perdue:
            partie_perdue = True
            message_defaite = ""
        return
    if not (0 <= cx < len(CARTE[0]) and 0 <= cy < len(CARTE)) or _collision_reelle(joueur_x, joueur_y):
        dr, dc = niveau_data["depart"]                      # sécurité : jamais coincé dans un mur
        joueur_x, joueur_y = dc * TAILLE_CASE + TAILLE_CASE / 2, dr * TAILLE_CASE + TAILLE_CASE / 2
        return

    if (cy, cx) in DEVIL["trous"]:                          # PIÈGE : le sol disparaît
        DEVIL["trous"].discard((cy, cx))
        DEVIL["effondres"].add((cy, cx))
        DEVIL["chute"] = {"t0": now}
        creer_explosion(cx * TAILLE_CASE + TAILLE_CASE / 2, cy * TAILLE_CASE + TAILLE_CASE / 2, (110, 70, 170), 30, 6.0, 7.0)
        return

    if DEVIL["tp"] > 0 and not hack_reussi and math.hypot(joueur_x - pos_core_x, joueur_y - pos_core_y) < TAILLE_CASE * 2.2:
        _devil_teleporter_core()                            # PIÈGE : la clé s'enfuit quand on s'approche
        jauge_hack = 0.0
        return

    if DEVIL["gel"] > 0 and not hack_reussi:                # PIÈGE : le hack se bloque à 99 % puis retombe à 0
        DEVIL["gel"] -= 1
        jauge_hack = 99.0
        if DEVIL["gel"] == 0:
            jauge_hack = 0.0
            DEVIL["resets"] -= 1
            creer_explosion(joueur_x, joueur_y, ROSE_SYNTH, 30, 7.0, 9.0)
            if SON_ACTIF:
                son_echec.play()
    elif CARTE[cy][cx] == 2 and not hack_reussi:
        jauge_hack = min(jauge_hack + 0.7 * _hack(), 100.0)
        if DEVIL["resets"] > 0 and jauge_hack >= 99.0:
            jauge_hack, DEVIL["gel"] = 99.0, 40
        elif jauge_hack >= 100.0:
            hack_reussi = True
    elif not hack_reussi:
        jauge_hack = max(jauge_hack - 0.3, 0.0)

    if CARTE[cy][cx] == 3 and hack_reussi and not partie_gagnee:
        if DEVIL["idx_sortie"] < len(DEVIL["sorties"]) - 1:
            _devil_fausse_sortie(cy, cx)                    # PIÈGE : fausse porte, la vraie est cachée ailleurs
        else:
            partie_gagnee = True


# ---------------------------------------------------------------- sons
def _devil_volume_musique(facteur=1.0):
    try:
        vm = PARAMS["vol_musique"] / 10.0
        pygame.mixer.music.set_volume(vm * facteur)
        if vm <= 0:
            pygame.mixer.music.pause()                      # musique coupée dans les réglages
        else:
            pygame.mixer.music.unpause()
    except Exception as e:
        print(f"⚠️ Volume musique Devil : {e}")


def devil_musique(actif):
    """Ambiance Devil en boucle pendant les missions ; la musique normale du jeu revient en quittant le mode."""
    try:
        if actif:
            pygame.mixer.music.load(_asset("ambiance_devil.ogg" if IS_WEB else "ambiance_devil.mp3"))
            pygame.mixer.music.play(-1)
            DEVIL["musique"] = True
            _devil_volume_musique()
        else:
            DEVIL["musique"], DEVIL["duck_fin"] = False, None
            if MUSIQUE_ACTIVE:
                pygame.mixer.music.load(_asset("musique_ambiance.ogg" if IS_WEB else "musique_ambiance.mp3"))
                if musique_lancee:
                    pygame.mixer.music.play(-1)
                appliquer_audio()
            else:
                pygame.mixer.music.stop()
    except Exception as e:
        print(f"⚠️ Musique Devil : {e}")
        DEVIL["musique_ko"] = bool(actif)
        DEVIL["musique"] = False


_DEVIL_SONS = {"essai": False, "victoire": None, "defaite": None}


def _devil_jingle(nom):
    """Jingle de fin (victoire_devil / defaite_devil) ; la musique baisse le temps qu'il joue."""
    if not SON_ACTIF:
        return
    try:
        if not _DEVIL_SONS["essai"]:
            _DEVIL_SONS["essai"] = True
            for cle in ("victoire", "defaite"):
                try:
                    _DEVIL_SONS[cle] = pygame.mixer.Sound(_asset(cle + "_devil." + ("ogg" if IS_WEB else "mp3")))
                except Exception as e:
                    print(f"⚠️ Son Devil indisponible ({cle}) : {e}")
        s = _DEVIL_SONS[nom]
        if s is None:
            return
        s.set_volume(min(1.0, 0.9 * PARAMS["vol_effets"] / 10.0))
        s.play()
        if DEVIL["musique"]:
            _devil_volume_musique(0.2)
            DEVIL["duck_fin"] = pygame.time.get_ticks() + int(s.get_length() * 1000) + 200
    except Exception as e:
        print(f"⚠️ Jingle Devil : {e}")


def devil_mort():
    DEVIL["morts"] += 1
    DEVIL["morts_total"] += 1
    devil_sauvegarder()
    if DEVIL["chute"] is None:
        creer_explosion(joueur_x, joueur_y, ROUGE_ALERTE, 46, 9.0, 12.0)
    maintenant = pygame.time.get_ticks()
    DEVIL["relance_t"] = maintenant + (DEVIL_RELANCE_MS if DEVIL["chute"] is not None else DEVIL_RELANCE_MORT_MS)
    if maintenant - DEVIL["stat_lose_t"] >= DEVIL_STAT_LOSE_MS:
        DEVIL["stat_lose_t"] = maintenant
        _stat("devil_lose", niveau_actuel)                  # stats : défaite (le total exact des morts est dans progression_devil.json)
    _devil_jingle("defaite")


def devil_victoire():
    FIN["t0"] = pygame.time.get_ticks()
    if niveau_actuel + 1 > DEVIL["max"]:
        DEVIL["max"] = niveau_actuel + 1                    # la mission suivante est débloquée dès la victoire
    devil_sauvegarder()
    _stat("devil_win", niveau_actuel)                       # stats : mission réussie
    _devil_jingle("victoire")


def devil_hook():
    """Appelé à chaque image en mission : ambiance, fin de la sourdine, redémarrage automatique après une mort."""
    now = pygame.time.get_ticks()
    if not DEVIL["musique"] and not DEVIL["musique_ko"]:
        devil_musique(True)
    if DEVIL["duck_fin"] is not None and now >= DEVIL["duck_fin"]:
        DEVIL["duck_fin"] = None
        _devil_volume_musique()
    if DEVIL["relance_t"] is not None and partie_perdue and now >= DEVIL["relance_t"]:
        DEVIL["relance_t"] = None
        reinitialiser_partie(False)


# ---------------------------------------------------------------- décor
_DEVIL_TUILES = {}
_DEVIL_PROPS = {}
_DEVIL_FOND = {"img": None, "essai": False, "cache": None, "cle": None}


def _devil_tuile(nom):
    """Tuiles du décor, dessinées une seule fois (sol et murs de secours si l'image de salle est absente, portes)."""
    s = _DEVIL_TUILES.get(nom)
    if s is not None:
        return s
    T = TAILLE_CASE
    d = pygame.draw
    if nom in ("porte_fermee", "porte_ouverte"):            # une vraie porte coulissante en acier
        s = pygame.Surface((T, T), pygame.SRCALPHA)
        d.rect(s, (52, 56, 66), (4, 2, 92, 96), border_radius=6)
        d.rect(s, (22, 24, 30), (10, 8, 80, 84), border_radius=4)
        if nom == "porte_fermee":
            d.rect(s, (104, 112, 126), (10, 8, 80, 84), border_radius=4)
            for y in (22, 40, 58, 76):
                d.line(s, (78, 86, 98), (14, y), (86, y), 2)
            for i in range(8):                              # bande de danger en bas du battant
                d.rect(s, (235, 190, 40) if i % 2 == 0 else (30, 30, 34), (10 + i * 10, 84, 10, 8))
            d.rect(s, (30, 32, 38), (60, 38, 22, 30), border_radius=3)
            d.circle(s, (255, 50, 60), (71, 48), 4)
            d.rect(s, (255, 50, 60), (30, 3, 40, 5), border_radius=2)
        else:
            d.rect(s, (104, 112, 126), (10, 8, 16, 84))
            d.rect(s, (30, 130, 90), (26, 8, 64, 84))
            d.rect(s, (90, 240, 170), (34, 14, 48, 72))
            d.rect(s, (60, 255, 140), (30, 3, 40, 5), border_radius=2)
        s = s.convert_alpha()
    else:
        s = pygame.Surface((T, T))
        if nom in ("solA", "solB"):
            s.fill((150, 152, 160) if nom == "solA" else (158, 160, 168))
            d.rect(s, (120, 122, 132), (0, 0, T, T), 1)
        elif nom == "mur":
            s.fill((58, 62, 72))
            d.rect(s, (40, 44, 52), (0, 0, T, T), 3)
            d.line(s, (84, 88, 100), (0, T // 2), (T, T // 2), 2)
        s = s.convert()
    _DEVIL_TUILES[nom] = s
    return s


def _devil_prop_surf(genre, h, w, var):
    """Mobilier vu de dessus (caisse, baril rouillé, chaise, banc, climatiseur abîmé, étagère rouillée), dessiné une seule fois."""
    cle = (genre, h, w, var)
    s = _DEVIL_PROPS.get(cle)
    if s is not None:
        return s
    T, d = TAILLE_CASE, pygame.draw
    W, H = w * T, h * T
    rouille, acier = (150, 70, 30), (74, 78, 88)
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    if genre == "coin":                                     # grosse caisse d'angle (déjà sur l'image ; sert si l'image manque)
        d.rect(s, (46, 48, 56), (6, 6, W - 12, H - 12), border_radius=6)
        for k in range(5):
            d.line(s, (235, 190, 40), (14 + k * 40, H - 14), (14 + k * 40 + 70, 14), 6)
        d.rect(s, (20, 22, 26), (6, 6, W - 12, H - 12), 4, border_radius=6)
    elif genre == "caisse":
        d.rect(s, (0, 0, 0, 80), (12, 14, W - 14, H - 14), border_radius=6)
        d.rect(s, (112, 84, 52), (6, 6, W - 14, H - 14), border_radius=4)
        for i in range(1, 4):
            d.line(s, (82, 60, 36), (8, 6 + i * (H - 14) // 4), (W - 10, 6 + i * (H - 14) // 4), 2)
        d.rect(s, (66, 46, 28), (6, 6, W - 14, H - 14), 4, border_radius=4)
        d.line(s, (66, 46, 28), (10, 10), (W - 12, H - 12), 3)
        d.circle(s, rouille + (140,), (W // 3 + var * 6, H // 2), 13)
        d.circle(s, rouille + (110,), (W // 2 + 12, H // 3), 8)
    elif genre == "baril":
        d.ellipse(s, (0, 0, 0, 90), (14, 16, W - 18, H - 18))
        couleur = [(150, 64, 32), (70, 96, 124), (132, 56, 28), (96, 100, 60)][var]
        d.circle(s, couleur, (W // 2, H // 2), 40)
        d.circle(s, (couleur[0] // 2, couleur[1] // 2, couleur[2] // 2), (W // 2, H // 2), 40, 5)
        d.circle(s, (min(255, couleur[0] + 30), min(255, couleur[1] + 30), min(255, couleur[2] + 30)), (W // 2, H // 2), 26)
        d.circle(s, (couleur[0] // 2, couleur[1] // 2, couleur[2] // 2), (W // 2, H // 2), 26, 3)
        d.circle(s, rouille + (150,), (W // 2 + 14, H // 2 - 12), 9)
        d.circle(s, (30, 30, 34), (W // 2 - 8, H // 2 + 6), 5)
    elif genre == "chaise":
        c = pygame.Surface((W, H), pygame.SRCALPHA)
        d.rect(c, (0, 0, 0, 80), (22, 22, 60, 56), border_radius=8)
        d.rect(c, (70, 80, 112), (20, 28, 58, 52), border_radius=8)
        d.rect(c, (46, 52, 76), (20, 14, 58, 14), border_radius=5)
        for x, y in ((22, 78), (70, 78), (22, 30), (70, 30)):
            d.circle(c, (30, 30, 36), (x, y), 4)
        s = pygame.transform.rotate(c, 90 * var)
    elif genre in ("banc", "etagere"):
        L = max(W, H)
        c = pygame.Surface((L, T), pygame.SRCALPHA)
        d.rect(c, (0, 0, 0, 80), (12, 22, L - 14, 60), border_radius=6)
        if genre == "banc":
            d.rect(c, (128, 96, 62), (8, 24, L - 16, 50), border_radius=5)
            for x in range(8, L - 8, 26):
                d.line(c, (84, 58, 34), (x, 26), (x, 72), 2)
            d.rect(c, (70, 48, 30), (8, 24, L - 16, 50), 3, border_radius=5)
            d.rect(c, acier, (14, 72, 12, 14))
            d.rect(c, acier, (L - 26, 72, 12, 14))
            d.circle(c, rouille + (150,), (L // 2 + 10, 50), 9)
        else:
            d.rect(c, (74, 60, 52), (6, 14, L - 12, 72), border_radius=4)
            for x in range(6, L - 6, 50):
                d.line(c, (130, 66, 32), (x, 14), (x, 86), 4)
            d.line(c, (130, 66, 32), (6, 50), (L - 6, 50), 4)
            for i in range((L // T)):
                d.rect(c, (150, 120, 80), (14 + i * T + (var * 7) % 20, 22 + (i * 17 + var * 9) % 30, 40, 34))
            d.rect(c, (130, 66, 32), (6, 14, L - 12, 72), 4, border_radius=4)
        s = pygame.transform.rotate(c, 90) if h > w else c
    elif genre == "clim":                                   # climatiseur abîmé
        d.rect(s, (0, 0, 0, 90), (14, 16, W - 16, H - 16), border_radius=10)
        d.rect(s, (156, 160, 166), (8, 8, W - 16, H - 16), border_radius=10)
        d.rect(s, (66, 70, 78), (8, 8, W - 16, H - 16), 5, border_radius=10)
        d.circle(s, (40, 44, 52), (W // 2, H // 2), 62)
        d.circle(s, (90, 94, 100), (W // 2, H // 2), 62, 4)
        for k in range(6):
            a = math.radians(60 * k + 17 * var)
            d.line(s, (120, 124, 132), (W // 2, H // 2), (W // 2 + int(56 * math.cos(a)), H // 2 + int(56 * math.sin(a))), 6)
        d.circle(s, (90, 94, 100), (W // 2, H // 2), 11)
        d.polygon(s, (30, 30, 36), [(W - 70, 12), (W - 12, 12), (W - 12, 64), (W - 40, 40)])        # panneau arraché
        d.line(s, (36, 38, 44), (30, 24), (74, 80), 3)                                              # fissure
        d.polygon(s, rouille + (150,), [(20, H - 40), (80, H - 36), (70, H - 14), (22, H - 14)])
        d.rect(s, rouille + (120,), (W // 2 + 20, H - 50, 22, 36))
        d.circle(s, (255, 60, 60), (22, 22), 5)
    s = s.convert_alpha()
    _DEVIL_PROPS[cle] = s
    return s


def _devil_decorer(fond, niveau):
    """Petits détails d'ambiance sur le sol de la salle (taches, huile, rouille, fissures, câbles, papiers), toujours les mêmes pour une mission."""
    rng = random.Random(niveau * 131 + 17)
    T, B = TAILLE_CASE, DEVIL_BORD
    x0, y0, x1, y1 = B * T + 40, B * T + 40, (DEVIL_COLONNES - B) * T - 40, (DEVIL_LIGNES - B) * T - 40
    d = pygame.draw

    def poser(surf, x, y):
        fond.blit(surf, (x - surf.get_width() // 2, y - surf.get_height() // 2))

    for _ in range(16):                                     # taches sombres
        w, h = rng.randint(50, 150), rng.randint(40, 110)
        t = pygame.Surface((w, h), pygame.SRCALPHA)
        d.ellipse(t, (34, 34, 44, rng.randint(28, 60)), (0, 0, w, h))
        poser(t, rng.randint(x0, x1), rng.randint(y0, y1))
    for _ in range(7):                                      # flaques d'huile
        w, h = rng.randint(50, 110), rng.randint(36, 80)
        t = pygame.Surface((w, h), pygame.SRCALPHA)
        d.ellipse(t, (18, 18, 26, 120), (0, 0, w, h))
        d.ellipse(t, (150, 160, 190, 55), (w // 5, h // 5, w // 3, h // 4))
        poser(t, rng.randint(x0, x1), rng.randint(y0, y1))
    for _ in range(12):                                     # rouille
        t = pygame.Surface((90, 70), pygame.SRCALPHA)
        for _k in range(5):
            d.circle(t, (150, 70, 30, rng.randint(40, 90)), (rng.randint(16, 74), rng.randint(14, 56)), rng.randint(6, 16))
        poser(t, rng.randint(x0, x1), rng.randint(y0, y1))
    for _ in range(9):                                      # fissures
        x, y = rng.randint(x0, x1), rng.randint(y0, y1)
        pts = [(x, y)]
        for _k in range(rng.randint(4, 7)):
            x, y = x + rng.randint(-34, 34), y + rng.randint(8, 30) * rng.choice([-1, 1])
            pts.append((x, y))
        d.lines(fond, (60, 62, 72), False, pts, 3)
        d.lines(fond, (176, 178, 188), False, [(px + 2, py + 2) for px, py in pts], 1)
    for _ in range(6):                                      # câbles qui traînent
        x, y = rng.randint(x0, x1), rng.randint(y0, y1)
        pts = [(x, y)]
        for _k in range(6):
            x, y = x + rng.randint(-60, 60), y + rng.randint(-40, 40)
            pts.append((min(x1, max(x0, x)), min(y1, max(y0, y))))
        d.lines(fond, (28, 28, 34), False, pts, 5)
        d.lines(fond, (70, 70, 84), False, pts, 1)
    for _ in range(12):                                     # papiers et débris
        t = pygame.Surface((26, 18), pygame.SRCALPHA)
        d.rect(t, (214, 212, 200, 230), (0, 0, 26, 18))
        d.line(t, (120, 120, 130), (3, 6), (22, 6), 1)
        d.line(t, (120, 120, 130), (3, 11), (16, 11), 1)
        poser(pygame.transform.rotate(t, rng.randint(0, 359)), rng.randint(x0, x1), rng.randint(y0, y1))
    for _ in range(5):                                      # marques de brûlure
        t = pygame.Surface((80, 80), pygame.SRCALPHA)
        for r in (34, 24, 14):
            d.circle(t, (10, 10, 14, 55), (40, 40), r)
        poser(t, rng.randint(x0, x1), rng.randint(y0, y1))
    for _ in range(7):                                      # dalles abîmées
        cx, cy = rng.randrange(B, DEVIL_COLONNES - B), rng.randrange(B, DEVIL_LIGNES - B)
        t = pygame.Surface((T, T), pygame.SRCALPHA)
        d.rect(t, (40, 40, 50, 40), (0, 0, T, T))
        d.line(t, (50, 52, 62, 200), (8, 12), (T - 14, T - 20), 2)
        fond.blit(t, (cx * T, cy * T))


def _devil_fond_pour(w, h):
    """Image de la salle (salle_devil.png, ou .jpg / .jpeg / .webp), étirée exactement sur toute la salle + décor de la mission.
    Retourne None s'il n'y a pas d'image : le jeu dessine alors un décor de secours."""
    if not _DEVIL_FOND["essai"]:
        _DEVIL_FOND["essai"] = True
        for nom in ("salle_devil.png", "salle_devil.jpg", "salle_devil.jpeg", "salle_devil.webp"):
            chemin = _asset(nom)
            if os.path.exists(chemin):
                try:
                    _DEVIL_FOND["img"] = pygame.image.load(chemin).convert()
                    break
                except Exception as e:
                    print(f"⚠️ Image de salle illisible ({nom}) : {e}")
    if _DEVIL_FOND["img"] is None:
        return None
    cle = (DEVIL["niveau_courant"], w, h)
    if _DEVIL_FOND["cle"] != cle:
        try:
            _DEVIL_FOND["cache"] = None                     # libère l'ancienne salle avant d'en préparer une autre
            fond = pygame.transform.smoothscale(_DEVIL_FOND["img"], (w, h))
            _devil_decorer(fond, max(0, DEVIL["niveau_courant"]))
            _DEVIL_FOND["cache"], _DEVIL_FOND["cle"] = fond, cle
        except Exception as e:
            print(f"⚠️ Image de salle inutilisable : {e}")
            _DEVIL_FOND["img"] = _DEVIL_FOND["cache"] = None
            return None
    return _DEVIL_FOND["cache"]


def _devil_dessiner_cle(cx, cy, t_ms):
    y = cy + int(4 * math.sin(t_ms / 260.0))
    c = (255, 215, 60)
    pygame.draw.ellipse(ecran, (30, 30, 40), (cx - 26, cy + 18, 52, 12))
    pygame.draw.circle(ecran, c, (cx - 16, y), 14, 6)
    pygame.draw.rect(ecran, c, (cx - 4, y - 3, 34, 6))
    pygame.draw.rect(ecran, c, (cx + 20, y, 6, 12))
    pygame.draw.rect(ecran, c, (cx + 10, y, 6, 9))
    pygame.draw.circle(ecran, (255, 250, 200), (cx - 16, y), 14, 2)


def devil_dessiner_carte(ox, oy, l0, l1, c0, c1, t_ms):
    """Dessine la salle Devil à la place du labyrinthe du solo. Retourne les halos à tracer par-dessus."""
    T, demi, B = TAILLE_CASE, TAILLE_CASE // 2, DEVIL_BORD
    nl, nc = len(CARTE), len(CARTE[0])
    lueurs = []
    fond = _devil_fond_pour(nc * T, nl * T)
    larg_e, haut_e = ecran.get_size()
    if fond is not None:                                    # image de la salle : on n'en dessine que la partie visible
        vx0, vy0 = max(0, -ox), max(0, -oy)
        vx1, vy1 = min(nc * T, larg_e - ox), min(nl * T, haut_e - oy)
        if vx1 > vx0 and vy1 > vy0:
            ecran.blit(fond, (ox + vx0, oy + vy0), (vx0, vy0, vx1 - vx0, vy1 - vy0))
    for li in range(l0, l1):
        ligne = CARTE[li]
        for ci in range(c0, c1):
            case = ligne[ci]
            rx, ry = ci * T + ox, li * T + oy
            bord = li < B or li >= nl - B or ci < B or ci >= nc - B
            if case == 1:
                if fond is None:                            # décor de secours (sans image)
                    ecran.blit(_devil_tuile("mur" if bord else "solA"), (rx, ry))
                continue                                    # le mobilier est dessiné plus bas
            if case == 3:
                if fond is None:
                    ecran.blit(_devil_tuile("mur"), (rx, ry))
                ecran.blit(_devil_tuile("porte_ouverte" if hack_reussi else "porte_fermee"), (rx, ry))
                lueurs.append((rx + demi, ry + demi, 95, VERT_FLUO if hack_reussi else ROUGE_ALERTE, 0.32 + 0.18 * math.sin(t_ms / 250.0)))
                continue
            if fond is None:
                ecran.blit(_devil_tuile("solA" if (li + ci) % 2 else "solB"), (rx, ry))
            if (li, ci) in DEVIL["effondres"]:
                devil_dessiner_trou(rx, ry)
            elif case == 2 and not hack_reussi:
                _devil_dessiner_cle(rx + demi, ry + demi, t_ms)
                lueurs.append((rx + demi, ry + demi, 110, JAUNE_CYBER, 0.5 + 0.2 * math.sin(t_ms / 300.0)))
    for (r, c, h, w, genre, var) in DEVIL["props"]:         # mobilier : obstacles de la salle
        if genre == "coin" and fond is not None:
            continue
        x, y = c * T + ox, r * T + oy
        if x + w * T < 0 or y + h * T < 0 or x > larg_e or y > haut_e:
            continue
        ecran.blit(_devil_prop_surf(genre, h, w, var), (x, y))
    return lueurs


def devil_dessiner_trou(rx, ry):
    DRAW.rect(ecran, (2, 2, 8), (rx, ry, TAILLE_CASE, TAILLE_CASE))
    DRAW.rect(ecran, (150, 30, 60), (rx + 1, ry + 1, TAILLE_CASE - 2, TAILLE_CASE - 2), 2)
    DRAW.line(ecran, (60, 20, 90), (rx + 12, ry + 16), (rx + TAILLE_CASE - 18, ry + TAILLE_CASE - 12), 2)
    DRAW.line(ecran, (60, 20, 90), (rx + TAILLE_CASE - 14, ry + 12), (rx + 20, ry + TAILLE_CASE - 20), 2)


def devil_dessiner_chute(jx, jy):
    """Le joueur rétrécit, tourne et s'enfonce dans le vide."""
    p = min(1.0, (pygame.time.get_ticks() - DEVIL["chute"]["t0"]) / float(DEVIL_CHUTE_MS))
    k = max(0.06, 1.0 - p)
    if MODE_GRAPHIQUE == "REALISTE":
        w, h = img_joueur_actuel.get_size()
        s = pygame.transform.rotate(pygame.transform.smoothscale(img_joueur_actuel, (max(2, int(w * k)), max(2, int(h * k)))), p * 300)
        ecran.blit(s, (jx - s.get_width() // 2, jy - s.get_height() // 2 + int(p * 36)))
    else:
        taille = max(3, int(TAILLE_PERSO * k))
        DRAW.rect(ecran, VERT_FLUO, (jx - taille // 2, jy - taille // 2 + int(p * 36), taille, taille))


def devil_dessiner_fin():
    cx = LARGEUR // 2
    if partie_gagnee:
        t = pygame.time.get_ticks() - FIN["t0"]
        ecran.blit(obtenir_voile(LARGEUR, HAUTEUR, (4, 12, 14, 170)), (0, 0))
        dessiner_confettis(t)
        y_btn = rect_bouton_suivant.y
        y_haut, y_bas = y_btn - 160, y_btn + 90
        _panneau_fin(VERT_FLUO, y_haut, y_bas, t / 420.0)
        if t < 380:
            return
        dessiner_titre_glitch("DATA SECURED !", police_victoire, cx, y_haut + 18)
        if t >= DELAI_BOUTONS_FIN:
            bouton_neon(rect_bouton_rejouer, BLEU_CYBER, "REJOUE", police_bouton)
            bouton_neon(rect_bouton_suivant, VERT_FLUO, "SUIVANT", police_bouton, plein=True, pulse=True)
    elif partie_perdue:                                     # mort : simple voile rouge, la mission redémarre toute seule
        ecran.blit(obtenir_voile(LARGEUR, HAUTEUR, (22, 0, 6, 130)), (0, 0))


def generer_niveau(niveau):
    if DEVIL["actif"]:
        return devil_generer_niveau(niveau)
    largeur_cellules = min(8 + niveau, 34)
    hauteur_cellules = min(6 + niveau, 22)
    grille = generer_labyrinthe(largeur_cellules, hauteur_cellules)

    depart = (1, 1)
    sortie, distances = cellule_la_plus_eloignee(grille, depart)

    cellules_triees = sorted(distances.items(), key=lambda x: x[1])
    idx_core = max(1, int(len(cellules_triees) * 0.55))
    core = cellules_triees[idx_core][0]

    grille[core[0]][core[1]] = 2
    grille[sortie[0]][sortie[1]] = 3

    est_mission_boss = (niveau + 1) % 5 == 0
    nb_ennemis = 0 if est_mission_boss else min(3 + niveau * 2, 70)
    vitesse = min(2.2 + niveau * 0.10, 7.0)

    cycle = niveau // len(NOMS)
    suffixe = f" [CYCLE {cycle + 1}]" if cycle > 0 else ""
    nom_base = f"MISSION {niveau + 1:02d} : {NOMS[niveau % len(NOMS)]}{suffixe}"
    nom = f"⚠ BOSS ⚠ {nom_base}" if est_mission_boss else nom_base
    couleur = COULEURS[niveau % len(COULEURS)]

    return {
        "carte": grille,
        "couleur_mur": couleur,
        "nom": nom,
        "nb_ennemis": nb_ennemis,
        "vitesse_ennemis": vitesse,
        "depart": depart,
        "est_boss": est_mission_boss,
        "core_cell": core,
        "sortie_cell": sortie
    }


def initialiser_etat_boss(niveau_data, niveau):
    if not niveau_data["est_boss"]:
        return False, False, 0, 0, 0, 0, [], 0
    cycle_boss = (niveau + 1) // 5
    vie_max = min(35 + cycle_boss * 12, 260)
    ligne_core, colonne_core = trouver_position_core(niveau_data["carte"])
    bx = colonne_core * TAILLE_CASE + TAILLE_CASE / 2
    by = ligne_core * TAILLE_CASE + TAILLE_CASE / 2
    return True, False, bx, by, vie_max, vie_max, [], random.randint(60, 90)


def duree_mission_boss(cycle_boss):
    if cycle_boss <= 3:
        return 150 * 60
    elif cycle_boss <= 7:
        return 200 * 60
    else:
        return 300 * 60


niveau_actuel = charger_progression()
niveau_max_atteint = niveau_actuel
niveau_data = generer_niveau(niveau_actuel)
CARTE = niveau_data["carte"]
COULEUR_MUR = niveau_data["couleur_mur"]
liste_ennemis = []
ennemis_restants_a_spawner = niveau_data["nb_ennemis"]
vitesse_ennemis_niveau = niveau_data["vitesse_ennemis"]
delai_min_init, delai_max_init = calcul_delais_spawn(niveau_actuel)
minuteur_spawn = random.randint(delai_min_init, delai_max_init)

boss_actif, boss_vaincu, boss_x, boss_y, boss_vie, boss_vie_max, boules_feu, minuteur_tir_boss = initialiser_etat_boss(niveau_data, niveau_actuel)
boss_angle_precedent = None
boss_surface_cache = None

# POSITIONS DU CORE ET DE LA SORTIE (pour le radar)
pos_core_x = niveau_data["core_cell"][1] * TAILLE_CASE + TAILLE_CASE / 2
pos_core_y = niveau_data["core_cell"][0] * TAILLE_CASE + TAILLE_CASE / 2
pos_sortie_x = niveau_data["sortie_cell"][1] * TAILLE_CASE + TAILLE_CASE / 2
pos_sortie_y = niveau_data["sortie_cell"][0] * TAILLE_CASE + TAILLE_CASE / 2

# PERSO & PROSPECTIVES
joueur_x = niveau_data["depart"][1] * TAILLE_CASE + TAILLE_CASE / 2
joueur_y = niveau_data["depart"][0] * TAILLE_CASE + TAILLE_CASE / 2
joueur_vitesse = 6.5
angle_visée_x, angle_visée_y = 1.0, 0.0
balles = []

jauge_hack = 0.0
hack_reussi = False
partie_gagnee = False
partie_perdue = False
message_defaite = "SYSTÈME CORROMPU"
if niveau_data["est_boss"]:
    temps_restant_frames = duree_mission_boss((niveau_actuel + 1) // 5)
else:
    temps_restant_frames = DUREE_MISSION_FRAMES
plafond_temps_frames = int(temps_restant_frames * 1.65)
liste_potions = []
minuteur_potion = random.randint(300, 600)
ETAT_MENU, ETAT_JEU, ETAT_AIDE, ETAT_PROFIL, ETAT_INFOS, ETAT_NIVEAUX = 0, 1, 2, 3, 4, 5
ETAT_PARAMS = 6
ETAT_BOUTIQUE = 7
ETAT_EDITEUR = 8
ETAT_DEFIS = 9
ETAT_MULTI = 10
ETAT_PARC = 11
etat_actuel = ETAT_MENU
en_pause = False

# TOUCH UI
JOY_CENTRE_X, JOY_CENTRE_Y = 180, HAUTEUR - 180
JOY_RAYON_SOCLE, JOY_RAYON_MANETTE = 85, 35
manette_x, manette_y = JOY_CENTRE_X, JOY_CENTRE_Y
joystick_actif = False
id_touch_joystick = None

# TIR MAINTENU (garder le doigt/clic appuyé pour tirer en continu)
tir_maintenu = False
id_touch_tir = None
CADENCE_TIR_FRAMES = 8  # nombre de frames entre 2 tirs pendant que le bouton est maintenu
minuteur_cadence_tir = 0

BTN_TIR_X, BTN_TIR_Y = LARGEUR - 180, HAUTEUR - 180
BTN_TIR_RAYON = 65
rect_tir_tactile = pygame.Rect(BTN_TIR_X - BTN_TIR_RAYON, BTN_TIR_Y - BTN_TIR_RAYON, BTN_TIR_RAYON * 2, BTN_TIR_RAYON * 2)

# RADAR (aide à la navigation : indique la direction du core et de la sortie)
RADAR_CENTRE_X, RADAR_CENTRE_Y = LARGEUR - 150, 150
RADAR_RAYON = 85
RADAR_PORTEE_MONDE = 900          # portée d'affichage des ennemis/potions sur le radar
RADAR_PORTEE_OBJECTIFS = 3200     # portée virtuelle utilisée pour situer le core/la sortie (toujours affichés, même très loin)

# BOUTON PAUSE (juste au-dessus du radar)
BTN_PAUSE_X, BTN_PAUSE_Y = LARGEUR - 150, 25
BTN_PAUSE_RAYON = 30
rect_bouton_pause = pygame.Rect(BTN_PAUSE_X - BTN_PAUSE_RAYON, BTN_PAUSE_Y - BTN_PAUSE_RAYON, BTN_PAUSE_RAYON * 2, BTN_PAUSE_RAYON * 2)
BTN_VUE_X, BTN_VUE_Y = BTN_PAUSE_X - 80, BTN_PAUSE_Y          # bouton 2D / 3D (change la vue de jeu)
rect_bouton_vue = pygame.Rect(BTN_VUE_X - BTN_PAUSE_RAYON, BTN_VUE_Y - BTN_PAUSE_RAYON, BTN_PAUSE_RAYON * 2, BTN_PAUSE_RAYON * 2)

# ÉCRAN DE SÉLECTION DES MISSIONS (chaîne de niveaux)
NIVEAU_NODE_ESPACEMENT = 160
NIVEAU_NODE_RAYON = 42
NIVEAU_MARGE_GAUCHE = 100
defilement_niveaux = 0.0
glissement_niveaux_actif = False
type_glissement_niveaux = None
dernier_x_glissement_niveaux = 0


def reinitialiser_partie(passer_au_suivant=False, niveau_cible=None):
    global joueur_x, joueur_y, jauge_hack, hack_reussi, partie_gagnee, partie_perdue, niveau_actuel, niveau_max_atteint
    global CARTE, COULEUR_MUR, etat_actuel, liste_ennemis, balles, img_joueur_actuel, niveau_data
    global ennemis_restants_a_spawner, vitesse_ennemis_niveau, minuteur_spawn
    global temps_restant_frames, liste_potions, minuteur_potion, message_defaite, plafond_temps_frames
    global boss_actif, boss_vaincu, boss_x, boss_y, boss_vie, boss_vie_max, boules_feu, minuteur_tir_boss
    global boss_angle_precedent, boss_surface_cache
    global pos_core_x, pos_core_y, pos_sortie_x, pos_sortie_y

    if niveau_cible is not None:
        niveau_actuel = niveau_cible
    elif passer_au_suivant:
        niveau_actuel += 1
        if DEVIL["actif"]:
            if niveau_actuel > DEVIL["max"]:
                DEVIL["max"] = niveau_actuel
            devil_sauvegarder()
        elif niveau_actuel > niveau_max_atteint:
            niveau_max_atteint = niveau_actuel
            sauvegarder_progression(niveau_max_atteint)

    if MP["actif"]:
        random.seed(MP["seed"])          # même labyrinthe pour tous les joueurs de la salle
    niveau_data = generer_niveau(niveau_actuel)
    if MP["actif"]:
        random.seed()
        MP["nb_base"] = niveau_data["nb_ennemis"]
        niveau_data["nb_ennemis"] = 0     # c'est l'hôte qui lance les drones (voir _mp_devenir_hote)
        _mp_reset_partie()
    CARTE = niveau_data["carte"]
    COULEUR_MUR = niveau_data["couleur_mur"]
    liste_ennemis = []
    ennemis_restants_a_spawner = niveau_data["nb_ennemis"]
    vitesse_ennemis_niveau = niveau_data["vitesse_ennemis"]
    delai_min, delai_max = calcul_delais_spawn(niveau_actuel)
    minuteur_spawn = random.randint(delai_min, delai_max)

    pos_core_x = niveau_data["core_cell"][1] * TAILLE_CASE + TAILLE_CASE / 2
    pos_core_y = niveau_data["core_cell"][0] * TAILLE_CASE + TAILLE_CASE / 2
    pos_sortie_x = niveau_data["sortie_cell"][1] * TAILLE_CASE + TAILLE_CASE / 2
    pos_sortie_y = niveau_data["sortie_cell"][0] * TAILLE_CASE + TAILLE_CASE / 2

    boss_actif, boss_vaincu, boss_x, boss_y, boss_vie, boss_vie_max, boules_feu, minuteur_tir_boss = initialiser_etat_boss(niveau_data, niveau_actuel)
    boss_angle_precedent = None
    boss_surface_cache = None

    if niveau_data["est_boss"]:
        temps_restant_frames = duree_mission_boss((niveau_actuel + 1) // 5)
    else:
        temps_restant_frames = DUREE_MISSION_FRAMES
    temps_restant_frames += STATS["chrono"]
    if DEVIL["actif"]:
        temps_restant_frames = 10 ** 9                      # Devil : aucun chrono
    plafond_temps_frames = int(temps_restant_frames * 1.65)
    liste_potions = []
    minuteur_potion = random.randint(300, 600)
    message_defaite = "SYSTÈME CORROMPU"

    joueur_x = niveau_data["depart"][1] * TAILLE_CASE + TAILLE_CASE / 2
    joueur_y = niveau_data["depart"][0] * TAILLE_CASE + TAILLE_CASE / 2
    jauge_hack, hack_reussi, partie_gagnee, partie_perdue = 0.0, False, False, False
    CAM["x"], CAM["y"] = joueur_x, joueur_y
    VUE["ang"], VUE["cam_d"] = _v3_cap_libre(0.0), 1.2
    balles.clear()
    particules_fx.clear()
    ondes_fx.clear()
    ETAT_FX["secousse"] = 0.0
    ETAT_JOUEUR["bouclier"], ETAT_JOUEUR["invuln"] = STATS["bouclier"], 0
    MISSION.update(drones=0, recompense=None, versee=False, duree=max(1, temps_restant_frames), defis_ok=[])
    if MODE_GRAPHIQUE == "REALISTE":
        img_joueur_actuel = img_joueur_droite
    _appliquer_skin()
    _init_pouvoirs()
    if not DEVIL["actif"]:
        _stat("level_start", niveau_actuel)
# 5. SYSTÈME DE PROFIL JOUEUR 
CHEMIN_PROFIL = chemin_donnees("profil_flex.json")
NATIONALITES = ["France", "Belgique", "Suisse", "Canada", "Maroc", "Algérie", "Tunisie",
                "Sénégal", "Côte d'Ivoire", "États-Unis", "Royaume-Uni", "Autre"]


def charger_profil():
    if os.path.exists(CHEMIN_PROFIL):
        try:
            with open(CHEMIN_PROFIL, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Profil illisible : {e}")
    return {"pseudo": "", "nationalite": "France"}


def sauvegarder_profil(donnees_profil):
    try:
        with open(CHEMIN_PROFIL, "w", encoding="utf-8") as f:
            json.dump(donnees_profil, f, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Impossible de sauvegarder le profil : {e}")


def charger_photo_profil():
    for nom_fichier in ["photo_profil.png", "photo_profil.jpg", "photo_profil.jpeg"]:
        if os.path.exists(nom_fichier):
            try:
                taille = 160
                img = pygame.image.load(_asset(nom_fichier)).convert_alpha()
                img = pygame.transform.smoothscale(img, (taille, taille))
                masque = pygame.Surface((taille, taille), pygame.SRCALPHA)
                DRAW.circle(masque, (255, 255, 255, 255), (taille // 2, taille // 2), taille // 2)
                img_ronde = pygame.Surface((taille, taille), pygame.SRCALPHA)
                img_ronde.blit(img, (0, 0))
                img_ronde.blit(masque, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
                return img_ronde
            except Exception as e:
                print(f"⚠️ Erreur chargement photo : {e}")
    return None


def dessiner_icone_personne(surface, centre_x, centre_y, taille, couleur):
    rayon_tete = int(taille * 0.22)
    DRAW.circle(surface, couleur, (centre_x, int(centre_y - taille * 0.14)), rayon_tete)
    rect_corps = pygame.Rect(0, 0, int(taille * 0.58), int(taille * 0.42))
    rect_corps.centerx = centre_x
    rect_corps.top = int(centre_y - taille * 0.14 + rayon_tete * 0.55)
    DRAW.ellipse(surface, couleur, rect_corps)


profil = charger_profil()
photo_profil_surface = charger_photo_profil()
index_nationalite = NATIONALITES.index(profil.get("nationalite", "France")) if profil.get("nationalite") in NATIONALITES else 0
saisie_pseudo_active = False


# 6. EFFETS VISUELS DU MENU (ville cyberpunk de nuit, grille néon, pluie)
HORIZON_Y = int(HAUTEUR * 0.60)
_fond_menu_surface = None
grille_scroll_offset = 0.0
pluie_menu = [[random.uniform(0, LARGEUR + 200), random.uniform(0, HAUTEUR), random.uniform(16, 28), random.randint(14, 30)]
              for _ in range(60)]
particules_menu = [[random.uniform(0, LARGEUR), random.uniform(0, HAUTEUR), random.uniform(0.3, 1.2), random.randint(1, 3)]
                   for _ in range(45)]


def couleur_ciel(y):
    a = (y / float(max(1, HORIZON_Y))) ** 2.2
    return melange((3, 2, 14), (70, 8, 95), a)


def construire_fond_menu():
    """Décor statique pré-rendu une seule fois : ciel, soleil néon, gratte-ciels, enseignes."""
    surf = pygame.Surface((LARGEUR, HAUTEUR))
    alea = random.Random(7)
    for y in range(HORIZON_Y):
        DRAW.line(surf, couleur_ciel(y), (0, y), (LARGEUR, y))

    # soleil néon rayé
    cx_s, rayon_s = int(LARGEUR * 0.74), int(HAUTEUR * 0.20)
    for r in range(rayon_s, 0, -2):
        a = 1 - r / float(rayon_s)
        DRAW.circle(surf, melange((200, 25, 120), (255, 150, 60), a), (cx_s, HORIZON_Y - 5), r)
    for k in range(7):
        y_bande = HORIZON_Y - 10 - k * int(rayon_s / 7.5)
        DRAW.rect(surf, couleur_ciel(y_bande), (cx_s - rayon_s, y_bande, rayon_s * 2, max(2, 9 - k)))

    # sol
    for y in range(HORIZON_Y, HAUTEUR):
        a = min(1.0, (y - HORIZON_Y) / float(max(1, HAUTEUR - HORIZON_Y)) * 1.6)
        DRAW.line(surf, melange((30, 8, 52), (2, 3, 10), a), (0, y), (LARGEUR, y))

    # skyline : 2 couches (lointaine puis proche)
    for couche, (couleur_bat, hmax, lum) in enumerate([((16, 7, 34), 0.30, 0.45), ((7, 5, 18), 0.42, 1.0)]):
        x = -20
        while x < LARGEUR:
            w = alea.randint(50, 130)
            h = int(HAUTEUR * alea.uniform(0.10, hmax))
            top = HORIZON_Y - h
            DRAW.rect(surf, couleur_bat, (x, top, w, h + 4))
            col_ar = alea.choice([BLEU_CYBER, ROSE_SYNTH, VIOLET_CYBER])
            DRAW.line(surf, eclaircir(col_ar, 0.55 * lum), (x, top), (x + w, top), 2)
            for wy in range(top + 12, HORIZON_Y - 8, 20):
                for wx in range(x + 8, x + w - 10, 14):
                    if alea.random() < 0.22:
                        col_f = alea.choice([JAUNE_CYBER, BLEU_CYBER, ROSE_SYNTH, BLANC_NEON])
                        DRAW.rect(surf, eclaircir(col_f, 0.75 * lum), (wx, wy, 6, 9))
            if couche == 1 and alea.random() < 0.28 and h > 90:
                col_e = alea.choice([ROSE_SYNTH, BLEU_CYBER, VERT_FLUO])
                ex_, ey_ = x + w - 14, top + 20
                hh = alea.randint(40, 90)
                DRAW.rect(surf, col_e, (ex_, ey_, 5, hh))
                surf.blit(obtenir_halo(44, col_e, 0.7), (ex_ + 2 - 44, ey_ + hh // 2 - 44),
                          special_flags=pygame.BLEND_RGB_ADD)
            x += w + alea.randint(-10, 12)

    # lueur de l'horizon
    lueur = pygame.Surface((LARGEUR, 90))
    for i in range(90):
        a = (1 - abs(i - 45) / 45.0) ** 3
        DRAW.line(lueur, (int(150 * a), int(40 * a), int(200 * a)), (0, i), (LARGEUR, i))
    surf.blit(lueur, (0, HORIZON_Y - 45), special_flags=pygame.BLEND_RGB_ADD)
    return surf.convert()


def dessiner_fond_menu():
    global _fond_menu_surface, grille_scroll_offset
    if _fond_menu_surface is None:
        _fond_menu_surface = construire_fond_menu()
    ecran.blit(_fond_menu_surface, (0, 0))

    # grille en perspective qui défile vers nous
    cx = LARGEUR // 2
    prof = HAUTEUR - HORIZON_Y
    grille_scroll_offset = (grille_scroll_offset + 0.010) % 1.0
    for k in range(-18, 19, 1 if QUALITE["niveau"] >= 1 else 2):
        DRAW.line(ecran, (110, 20, 150), (cx + k * 12, HORIZON_Y), (cx + k * (LARGEUR // 12), HAUTEUR), 1)
    nb_lignes = 14
    for i in range(nb_lignes):
        z = (i + grille_scroll_offset) / float(nb_lignes)
        y = HORIZON_Y + int(prof * (z ** 2.2))
        DRAW.line(ecran, eclaircir(BLEU_CYBER, 0.15 + 0.6 * z), (0, y), (LARGEUR, y), 1 if z < 0.6 else 2)

    # pluie de néon
    for g in pluie_menu[:(0, 28, 60)[QUALITE["niveau"]]]:
        g[1] += g[2]
        g[0] -= g[2] * 0.15
        if g[1] > HAUTEUR + 30 or g[0] < -60:
            g[1] = random.uniform(-60, -10)
            g[0] = random.uniform(0, LARGEUR + 200)
        DRAW.line(ecran, (70, 120, 175), (int(g[0]), int(g[1])), (int(g[0] + g[3] * 0.15), int(g[1] - g[3])), 1)

    # lucioles lumineuses
    for i, p in enumerate(particules_menu):
        couleur_p = BLEU_CYBER if i % 2 == 0 else ROSE_SYNTH
        p[1] -= p[2]
        if p[1] < -10:
            p[1] = HAUTEUR + 10
            p[0] = random.uniform(0, LARGEUR)
        DRAW.circle(ecran, couleur_p, (int(p[0]), int(p[1])), p[3])
        if p[3] == 3:
            dessiner_halo(p[0], p[1], 16, couleur_p, 0.8, 2)


def dessiner_panneau_neon(x, largeur, couleur, avec_fond=True, alpha=205):
    if avec_fond:
        dessiner_fond_menu()
    ecran.blit(obtenir_voile(largeur, HAUTEUR, (6, 8, 18, alpha)), (x, 0))
    for i in range(10):
        c = eclaircir(couleur, (1 - i / 10.0) ** 2 * (1.0 if i else 1.2))
        DRAW.line(ecran, c, (x - i, 0), (x - i, HAUTEUR))
        DRAW.line(ecran, c, (x + largeur + i, 0), (x + largeur + i, HAUTEUR))


def dessiner_titre_glitch(texte, police, x_centre, y):
    dessiner_halo(x_centre - 90, y + police.get_height() // 2, 150, (0, 90, 150), 0.7, 2)
    dessiner_halo(x_centre + 90, y + police.get_height() // 2, 150, (150, 20, 120), 0.6, 2)
    decalage_glitch = random.randint(-4, 4) if random.random() < 0.06 else 0
    surf_rouge = rendu_texte(police, texte, True, (255, 50, 60))
    surf_bleu = rendu_texte(police, texte, True, (50, 170, 255))
    surf_principal = rendu_texte(police, texte, True, BLANC_NEON)
    largeur_texte = surf_principal.get_width()
    ecran.blit(surf_rouge, (x_centre - largeur_texte // 2 - 3 + decalage_glitch, y))
    ecran.blit(surf_bleu, (x_centre - largeur_texte // 2 + 3 + decalage_glitch, y))
    ecran.blit(surf_principal, (x_centre - largeur_texte // 2 + decalage_glitch, y))


def point_sur_radar(px, py, portee):
    """Convertit une position du monde en un point sur le radar, centré sur le joueur.
    Si le point est hors de portée, il est ramené (clampé) sur le bord du radar
    pour indiquer uniquement la direction."""
    dx, dy = px - joueur_x, py - joueur_y
    if _v3_actif():                      # en 3e personne le radar tourne : le haut = devant le joueur
        _c, _s = math.cos(VUE["ang"] + VUE["cam_off"]), math.sin(VUE["ang"] + VUE["cam_off"])
        dx, dy = -dx * _s + dy * _c, -(dx * _c + dy * _s)
    echelle = RADAR_RAYON / portee
    rx, ry = dx * echelle, dy * echelle
    dist_radar = math.hypot(rx, ry)
    limite = RADAR_RAYON - 9
    if dist_radar > limite:
        rx, ry = rx / dist_radar * limite, ry / dist_radar * limite
    return int(RADAR_CENTRE_X + rx), int(RADAR_CENTRE_Y + ry)


def dessiner_radar():
    # Fond et cadre du radar
    DRAW.circle(ecran, (6, 12, 20), (RADAR_CENTRE_X, RADAR_CENTRE_Y), RADAR_RAYON)
    dessiner_halo(RADAR_CENTRE_X, RADAR_CENTRE_Y, RADAR_RAYON + 30, BLEU_CYBER, 0.35, 2)
    nb_bal = (0, 6, 12)[QUALITE["niveau"]]
    ang_balayage = pygame.time.get_ticks() / 700.0
    if nb_bal == 0:
        DRAW.line(ecran, (0, 150, 110), (RADAR_CENTRE_X, RADAR_CENTRE_Y),
                         (int(RADAR_CENTRE_X + math.cos(ang_balayage) * (RADAR_RAYON - 4)),
                          int(RADAR_CENTRE_Y + math.sin(ang_balayage) * (RADAR_RAYON - 4))), 2)
    for k_bal in range(nb_bal):
        a_bal = ang_balayage - k_bal * (0.72 / nb_bal)
        f_bal = (1 - k_bal / float(nb_bal)) ** 1.5
        DRAW.line(ecran, (0, int(150 * f_bal), int(110 * f_bal)), (RADAR_CENTRE_X, RADAR_CENTRE_Y),
                         (int(RADAR_CENTRE_X + math.cos(a_bal) * (RADAR_RAYON - 4)),
                          int(RADAR_CENTRE_Y + math.sin(a_bal) * (RADAR_RAYON - 4))), 4)
    DRAW.circle(ecran, (0, 60, 80), (RADAR_CENTRE_X, RADAR_CENTRE_Y), int(RADAR_RAYON * 0.5), 1)
    DRAW.line(ecran, (0, 55, 75), (RADAR_CENTRE_X - RADAR_RAYON, RADAR_CENTRE_Y), (RADAR_CENTRE_X + RADAR_RAYON, RADAR_CENTRE_Y), 1)
    DRAW.line(ecran, (0, 55, 75), (RADAR_CENTRE_X, RADAR_CENTRE_Y - RADAR_RAYON), (RADAR_CENTRE_X, RADAR_CENTRE_Y + RADAR_RAYON), 1)
    DRAW.circle(ecran, BLEU_CYBER, (RADAR_CENTRE_X, RADAR_CENTRE_Y), RADAR_RAYON, 3)

    # Le CORE (violet, devient vert une fois hacké, rouge si le boss le garde)
    if boss_actif and not boss_vaincu:
        couleur_core = ROUGE_ALERTE
    elif hack_reussi:
        couleur_core = VERT_FLUO
    else:
        couleur_core = VIOLET_CYBER
    cxr, cyr = point_sur_radar(pos_core_x, pos_core_y, RADAR_PORTEE_OBJECTIFS)
    DRAW.circle(ecran, couleur_core, (cxr, cyr), 7)
    DRAW.circle(ecran, BLANC_NEON, (cxr, cyr), 7, 1)

    # La SORTIE (verte quand elle devient utile, grise sinon)
    couleur_sortie = VERT_FLUO if hack_reussi else (70, 90, 80)
    sxr, syr = point_sur_radar(pos_sortie_x, pos_sortie_y, RADAR_PORTEE_OBJECTIFS)
    DRAW.circle(ecran, couleur_sortie, (sxr, syr), 7)
    DRAW.circle(ecran, BLANC_NEON, (sxr, syr), 7, 1)

    # Boss (repérable même s'il est mobile)
    if boss_actif and not boss_vaincu:
        bxr, byr = point_sur_radar(boss_x, boss_y, RADAR_PORTEE_OBJECTIFS)
        DRAW.circle(ecran, VIOLET_CYBER, (bxr, byr), 5)

    # Ennemis à portée du radar
    for ex in liste_ennemis:
        if math.hypot(ex[0] - joueur_x, ex[1] - joueur_y) <= RADAR_PORTEE_MONDE:
            exr, eyr = point_sur_radar(ex[0], ex[1], RADAR_PORTEE_MONDE)
            DRAW.circle(ecran, ROUGE_ALERTE, (exr, eyr), 3)

    # Potions à portée du radar
    for potion in liste_potions:
        if math.hypot(potion[0] - joueur_x, potion[1] - joueur_y) <= RADAR_PORTEE_MONDE:
            pxr, pyr = point_sur_radar(potion[0], potion[1], RADAR_PORTEE_MONDE)
            DRAW.circle(ecran, JAUNE_CYBER, (pxr, pyr), 3)

    # Le joueur, toujours au centre
    DRAW.circle(ecran, BLANC_NEON, (RADAR_CENTRE_X, RADAR_CENTRE_Y), 5)
    DRAW.circle(ecran, VERT_FLUO, (RADAR_CENTRE_X, RADAR_CENTRE_Y), 5, 2)

    etiquette = rendu_texte(police_petite, "RADAR", True, BLEU_CYBER)
    ecran.blit(etiquette, (RADAR_CENTRE_X - etiquette.get_width() // 2, RADAR_CENTRE_Y + RADAR_RAYON + 6))


police_bouton = pygame.font.SysFont(None, 40)
police_jeu = pygame.font.SysFont(None, 36)
police_petite = pygame.font.SysFont(None, 26)
police_aide = pygame.font.SysFont(None, 30)
police_victoire = pygame.font.SysFont(None, 90)
police_titre = pygame.font.SysFont(None, 80)
clock = pygame.time.Clock()

rect_bouton_jouer = pygame.Rect(LARGEUR // 2 - 150, HAUTEUR // 2 - 60, 300, 55)
rect_bouton_aide = pygame.Rect(LARGEUR // 2 - 150, HAUTEUR // 2 + 20, 300, 55)
rect_bouton_boutique = pygame.Rect(LARGEUR // 2 - 150, HAUTEUR // 2 + 100, 300, 55)
rect_bouton_multi = pygame.Rect(LARGEUR // 2 - 150, HAUTEUR // 2 + 180, 300, 55)
rect_bouton_parc = pygame.Rect(LARGEUR // 2 + 170, HAUTEUR // 2 + 180, 170, 55)
rect_bouton_retour = pygame.Rect(40, 40, 160, 50)   # en haut à gauche : ne cache plus le texte du guide
rect_bouton_rejouer = pygame.Rect(LARGEUR // 2 - 260, HAUTEUR // 2 + 60, 240, 65)
rect_bouton_suivant = pygame.Rect(LARGEUR // 2 + 20, HAUTEUR // 2 + 60, 240, 65)

rect_icone_profil = pygame.Rect(LARGEUR - 110, 30, 70, 70)
rect_icone_infos = pygame.Rect(40, 30, 70, 70)
rect_icone_params = pygame.Rect(130, 30, 70, 70)
rect_icone_classement = pygame.Rect(220, 30, 70, 70)
rect_icone_skins = pygame.Rect(310, 30, 70, 70)
rect_icone_defis = pygame.Rect(400, 30, 70, 70)
rect_icone_devil = pygame.Rect(490, 30, 70, 70)
rect_icone_install = pygame.Rect(580, 30, 70, 70)
# Rangée d'icônes du menu : Infos passe à droite (à côté du Profil) ; à gauche les icônes présentes se serrent sans trou
# (Online : Classement et Skins s'ajoutent ; sur Pygame elles n'existent pas, donc pas de vide)
rect_icone_infos.x = rect_icone_profil.x - 90
for _i, _r in enumerate([rect_icone_params] + ([rect_icone_classement, rect_icone_skins] if IS_WEB else [])
                        + [rect_icone_defis, rect_icone_devil, rect_icone_install]):
    _r.x = 40 + 90 * _i
rect_recharger_photo = pygame.Rect(LARGEUR // 2 - 140, 280, 280, 45)
rect_champ_pseudo = pygame.Rect(LARGEUR // 2 - 220, 350, 440, 60)
rect_fleche_gauche = pygame.Rect(LARGEUR // 2 - 220, 450, 60, 60)
rect_fleche_droite = pygame.Rect(LARGEUR // 2 + 160, 450, 60, 60)
rect_sauvegarder_profil = pygame.Rect(LARGEUR // 2 - 260, HAUTEUR - 220, 240, 65)
rect_retour_profil = pygame.Rect(LARGEUR // 2 + 20, HAUTEUR - 220, 240, 65)

# Boutons spécifiques
rect_bouton_rejouer_defaite = pygame.Rect(LARGEUR // 2 - 260, HAUTEUR // 2 + 60, 240, 65)
rect_bouton_quitter_defaite = pygame.Rect(LARGEUR // 2 + 20, HAUTEUR // 2 + 60, 240, 65)
rect_retour_infos = pygame.Rect(40, 40, 160, 50) # Nouveau bouton retour pour l'écran Infos
rect_retour_niveaux = pygame.Rect(40, 40, 160, 50)

# Menu PAUSE
rect_pause_continuer = pygame.Rect(LARGEUR // 2 - 150, HAUTEUR // 2 - 100, 300, 60)
rect_pause_rejouer = pygame.Rect(LARGEUR // 2 - 150, HAUTEUR // 2 - 20, 300, 60)
rect_pause_params = pygame.Rect(LARGEUR // 2 - 150, HAUTEUR // 2 + 60, 300, 60)
rect_pause_quitter = pygame.Rect(LARGEUR // 2 - 150, HAUTEUR // 2 + 140, 300, 60)

# ==================== PARAMÈTRES ====================
CHEMIN_PARAMS = chemin_donnees("parametres_flex.json")
LOGIQUE = {"t": _time.perf_counter(), "acc": 0.0, "k": 1}   # pas de temps réel de la logique
PAUSE_T = {"t": -1000}
SAUT = {"n": 1}                   # on dessine 1 image sur n (la logique du jeu, elle, tourne à chaque tour)
TMR = {"l": 0.0, "r": 0.0, "f": 0.0}   # temps moyens (ms) : logique / dessin / affichage
CTRL = {"k": 1.0, "dz": 10.0}      # sensibilité (multiplicateur du déplacement du doigt) et zone morte (en pixels)
PAR = {"scroll": 0.0, "drag": False, "id": None, "y": 0.0, "x0": 0.0, "y0": 0.0, "moved": False,
       "origine": ETAT_MENU, "zones": [], "bench": [], "redemarrer": False}


def _liste_pct(debut, fin, pas):
    return [f"{p}%" for p in range(debut, fin + 1, pas)]


# ("SECTION", titre)  ou  (clé, libellé, [options], index par défaut)
PARAM_DEFS = [
    ("SECTION", "GRAPHISMES"),
    ("vue", "Vue de jeu", ["Du dessus", "3e personne"], 0),
    ("qualite3d", "Qualité de la 3D", ["Auto", "Léger", "Moyen", "Max"], 0),
    ("qualite", "Qualité graphique", ["Auto", "Léger", "Équilibré", "Complet"], 0),
    ("resolution", "Résolution (au lancement)", ["Auto", "100%", "75%", "50%"], 0),
    ("saut", "Images dessinées", ["Auto", "Toutes", "1 sur 2", "1 sur 3"], 0),
    ("ombres", "Ombres", ["Non", "Oui"], 1),
    ("dof", "Profondeur de champ", ["Non", "Oui"], 1),
    ("fps", "Afficher les FPS", ["Non", "Oui"], 0),
    ("SECTION", "EFFETS"),
    ("secousse", "Secousse d'écran", ["Non", "Oui"], 1),
    ("particules", "Particules", ["Non", "Oui"], 1),
    ("ville_anim", "Ville animée", ["Non", "Oui"], 1),
    ("SECTION", "COMMANDES"),
    ("sensibilite", "Sensibilité", _liste_pct(50, 150, 10), 5),
    ("zone_morte", "Zone morte", ["0%", "5%", "12%", "20%", "30%"], 2),
    ("ACTION", "Disposition des commandes", "editeur"),
    ("SECTION", "AUDIO"),
    ("vol_musique", "Volume musique", _liste_pct(0, 100, 10), 4),
    ("vol_effets", "Volume effets", _liste_pct(0, 100, 10), 10),
]
PARAM_OPTIONS = {d[0]: d[2] for d in PARAM_DEFS if len(d) == 4}
PARAM_DEFAUT = {d[0]: d[3] for d in PARAM_DEFS if len(d) == 4}
PARAMS = dict(PARAM_DEFAUT)


def dispo_par_defaut():
    """Disposition d'origine : joystick en bas à gauche, bouton TIR en bas à droite (positions en fraction de l'écran)."""
    return {"joy": {"x": 180.0 / LARGEUR, "y": (HAUTEUR - 180.0) / HAUTEUR, "s": 1.0},
            "tir": {"x": (LARGEUR - 180.0) / LARGEUR, "y": (HAUTEUR - 180.0) / HAUTEUR, "s": 1.0}}


DISPO = dispo_par_defaut()
ECHELLE_COMMANDE_MIN, ECHELLE_COMMANDE_MAX = 0.6, 1.8


def charger_parametres():
    if os.path.exists(CHEMIN_PARAMS):
        try:
            with open(CHEMIN_PARAMS, "r", encoding="utf-8") as f:
                donnees = json.load(f)
            for cle, options in PARAM_OPTIONS.items():
                v = donnees.get(cle)
                if isinstance(v, int) and not isinstance(v, bool) and 0 <= v < len(options):
                    PARAMS[cle] = v
            for nom in ("joy", "tir"):                                   # disposition personnalisée des commandes
                d = (donnees.get("dispo") or {}).get(nom)
                if isinstance(d, dict) and all(isinstance(d.get(k), (int, float)) and not isinstance(d.get(k), bool) for k in ("x", "y", "s")):
                    DISPO[nom] = {"x": min(1.0, max(0.0, float(d["x"]))), "y": min(1.0, max(0.0, float(d["y"]))),
                                  "s": min(ECHELLE_COMMANDE_MAX, max(ECHELLE_COMMANDE_MIN, float(d["s"])))}
        except Exception as e:
            print(f"⚠️ Paramètres illisibles : {e}")


def sauvegarder_parametres():
    try:
        with open(CHEMIN_PARAMS, "w", encoding="utf-8") as f:
            json.dump({**PARAMS, **EXTRA, "dispo": DISPO}, f)
    except Exception as e:
        print(f"⚠️ Impossible de sauvegarder les paramètres : {e}")


def basculer_pause():
    """Active/désactive la pause (ignore le 2e événement d'un même toucher : doigt + souris)."""
    global en_pause
    maintenant = pygame.time.get_ticks()
    if maintenant - PAUSE_T["t"] < 350:
        return
    PAUSE_T["t"] = maintenant
    en_pause = not en_pause


def placer_manette(px, py):
    """Place le stick selon le doigt ; la sensibilité agrandit ou réduit le déplacement nécessaire."""
    global manette_x, manette_y
    vx, vy = (px - JOY_CENTRE_X) * CTRL["k"], (py - JOY_CENTRE_Y) * CTRL["k"]
    dist = math.hypot(vx, vy)
    if dist > JOY_RAYON_SOCLE:
        vx, vy = vx / dist * JOY_RAYON_SOCLE, vy / dist * JOY_RAYON_SOCLE
    manette_x, manette_y = JOY_CENTRE_X + vx, JOY_CENTRE_Y + vy


_cache_disques = {}


def _disque(rayon, rgba):
    """Disque translucide mémorisé : pas de recréation pendant qu'on déplace une commande dans l'éditeur."""
    cle = (rayon, rgba)
    if cle not in _cache_disques:
        _cache_disques[cle] = creer_disque_translucide(rayon, rgba)
    return _cache_disques[cle]


def _borner_commande(x, y, rayon):
    """Garde toute la commande à l'intérieur de l'écran."""
    marge = rayon + 6
    return (int(round(max(marge, min(LARGEUR - marge, x)))), int(round(max(marge, min(HAUTEUR - marge, y)))))


def appliquer_controles():
    """Place le joystick et le bouton TIR d'après DISPO (position et taille choisies dans l'éditeur de commandes)."""
    global JOY_CENTRE_X, JOY_CENTRE_Y, JOY_RAYON_SOCLE, JOY_RAYON_MANETTE
    global BTN_TIR_X, BTN_TIR_Y, BTN_TIR_RAYON, rect_tir_tactile
    global manette_x, manette_y, SURF_SOCLE_JOY, SURF_BTN_TIR
    joy, tir = DISPO["joy"], DISPO["tir"]
    JOY_RAYON_SOCLE, JOY_RAYON_MANETTE = int(85 * joy["s"]), int(35 * joy["s"])
    BTN_TIR_RAYON = int(65 * tir["s"])
    JOY_CENTRE_X, JOY_CENTRE_Y = _borner_commande(joy["x"] * LARGEUR, joy["y"] * HAUTEUR, JOY_RAYON_SOCLE)
    BTN_TIR_X, BTN_TIR_Y = _borner_commande(tir["x"] * LARGEUR, tir["y"] * HAUTEUR, BTN_TIR_RAYON)
    rect_tir_tactile = pygame.Rect(BTN_TIR_X - BTN_TIR_RAYON, BTN_TIR_Y - BTN_TIR_RAYON, BTN_TIR_RAYON * 2, BTN_TIR_RAYON * 2)
    manette_x, manette_y = JOY_CENTRE_X, JOY_CENTRE_Y
    SURF_SOCLE_JOY = _disque(JOY_RAYON_SOCLE, (10, 30, 45, 85))
    SURF_BTN_TIR = _disque(BTN_TIR_RAYON, (70, 0, 25, 95))
    CTRL["k"] = 0.5 + 0.1 * PARAMS["sensibilite"]
    CTRL["dz"] = (0.0, 0.05, 0.12, 0.20, 0.30)[PARAMS["zone_morte"]] * JOY_RAYON_SOCLE


def appliquer_audio():
    vm, ve = PARAMS["vol_musique"] / 10.0, PARAMS["vol_effets"] / 10.0
    try:
        if MUSIQUE_ACTIVE:
            pygame.mixer.music.set_volume(vm)
            if vm <= 0:
                pygame.mixer.music.pause()      # musique coupée : le téléphone n'a plus à la décoder
            elif musique_lancee:
                pygame.mixer.music.unpause()
        if SON_ACTIF:
            son_tir.set_volume(0.5 * ve)
            son_explosion.set_volume(0.6 * ve)
            son_echec.set_volume(0.7 * ve)
            son_victoire.set_volume(0.7 * ve)
    except Exception as e:
        print(f"⚠️ Volume : {e}")


def appliquer_parametres(cle=None):
    """Applique les réglages (tous si cle=None, sinon seulement ceux liés à la clé modifiée)."""
    global AUTO_QUALITE, ECHELLE
    AUTO_QUALITE = (PARAMS["qualite"] == 0)
    if cle in (None, "qualite"):
        QUALITE["niveau"] = (1, 0, 1, 2)[PARAMS["qualite"]]
    if cle in (None, "saut"):
        SAUT["n"] = (1, 1, 2, 3)[PARAMS["saut"]]
    if cle in (None, "sensibilite", "zone_morte"):
        appliquer_controles()
    if cle in (None, "vol_musique", "vol_effets"):
        appliquer_audio()


def changer_param(cle, delta):
    options = PARAM_OPTIONS[cle]
    i = PARAMS[cle] + delta
    i = i % len(options) if len(options) <= 4 else max(0, min(len(options) - 1, i))
    if i != PARAMS[cle]:
        PARAMS[cle] = i
        appliquer_parametres(cle)
        if cle == "resolution":
            PAR["redemarrer"] = True
        sauvegarder_parametres()


def reinitialiser_parametres():
    PARAMS.update(PARAM_DEFAUT)
    d = dispo_par_defaut()
    DISPO["joy"], DISPO["tir"] = d["joy"], d["tir"]
    appliquer_parametres()
    sauvegarder_parametres()


def dessiner_icone_engrenage(cx, cy, r, couleur):
    for k in range(8):
        a = k * math.pi / 4
        DRAW.line(ecran, couleur, (cx + math.cos(a) * r * 0.45, cy + math.sin(a) * r * 0.45),
                  (cx + math.cos(a) * r * 0.82, cy + math.sin(a) * r * 0.82), 6)
    DRAW.circle(ecran, couleur, (cx, cy), int(r * 0.52), 4)
    DRAW.circle(ecran, couleur, (cx, cy), int(r * 0.18))


FPS_AFF = {"v": 60.0, "n": 0}


def dessiner_fps():
    FPS_AFF["n"] += 1
    if FPS_AFF["n"] % 10 == 1:
        FPS_AFF["v"] = clock.get_fps()
    v = FPS_AFF["v"]
    col = VERT_FLUO if v >= 52 else (JAUNE_CYBER if v >= 38 else ROUGE_ALERTE)
    rendu = f" (dessin 1/{SAUT['n']})" if SAUT["n"] > 1 else ""
    l1 = rendu_texte(police_petite, f"FPS {int(round(v))}{rendu}   Q{QUALITE['niveau']}   {int(round(ECHELLE * 100))}%", True, col)
    pas = f"   pas x{LOGIQUE['k']}" if LOGIQUE["k"] > 1 else ""
    l2 = rendu_texte(police_petite, f"logique {int(TMR['l'])} ms   dessin {int(TMR['r'])} ms   écran {int(TMR['f'])} ms{pas}", True, (170, 180, 210))
    larg = max(l1.get_width(), l2.get_width()) + 16
    haut = l1.get_height() + l2.get_height() + 8
    ecran.blit(obtenir_voile(larg, haut, (5, 6, 16, 160)), (10, HAUTEUR - haut - 10))
    ecran.blit(l1, (18, HAUTEUR - haut - 7))
    ecran.blit(l2, (18, HAUTEUR - haut - 7 + l1.get_height() + 2))


def adapter_qualite():
    """Mode Auto : si le jeu rame, on allège d'abord les effets, puis on saute des images ; si ça ne suffit pas,
    on note une résolution plus basse pour le PROCHAIN lancement (la résolution ne se change pas en pleine partie)."""
    global frames_total, fps_bas_consecutifs
    frames_total += 1
    if frames_total < 120 or frames_total % 20 != 0:
        return
    if etat_actuel != ETAT_JEU or en_pause or TRANS["actif"]:
        fps_bas_consecutifs = 0
        return
    fps = clock.get_fps()
    peut_effets = AUTO_QUALITE and QUALITE["niveau"] > 0
    peut_saut = PARAMS["saut"] == 0 and SAUT["n"] < 3
    suggerer = PARAMS["resolution"] == 0 and ECHELLE > 0.55 and not EXTRA["suggere"]
    if fps >= 48 or not (peut_effets or peut_saut or suggerer):
        fps_bas_consecutifs = 0
        return
    fps_bas_consecutifs += 1
    if fps_bas_consecutifs < 2:
        return
    fps_bas_consecutifs = 0
    if suggerer and not peut_effets:
        EXTRA["echelle_auto"] = 0.75 if ECHELLE > 0.8 else 0.5
        EXTRA["suggere"] = True
        sauvegarder_parametres()
    for _ in range(2 if fps < 25 else 1):
        if AUTO_QUALITE and QUALITE["niveau"] > 0:
            QUALITE["niveau"] -= 1
        elif PARAMS["saut"] == 0 and SAUT["n"] < 3:
            SAUT["n"] += 1


def lancer_benchmark():
    """Mesure les coûts réels sur CE téléphone et affiche le résultat dans les Paramètres (et dans bench_flex.txt)."""
    def mesurer(f, n):
        t = _time.perf_counter()
        for _ in range(n):
            f()
        return (_time.perf_counter() - t) * 1000.0 / n

    tm, ts = tuile_mur(COULEUR_MUR, 5), tuile_sol(COULEUR_MUR, 0, 3)

    def tuiles():
        for i in range(15):
            for j in range(8):
                ecran.blit(tm if (i + j) % 3 == 0 else ts, (i * 100, j * 90))

    def lueurs():
        for i in range(20):
            dessiner_halo(100 + i * 60, 300, 84, BLEU_CYBER, 0.8, 0)

    def ombres():
        for i in range(20):
            dessiner_ombre(100 + i * 60, 300, 44, 16)

    def calcul():
        s = 0
        for i in range(60000):
            s += i * i
        return s

    ecran.fill((8, 10, 20))
    lueurs()
    ombres()
    tuiles()
    pygame.display.flip()                       # échauffement (création des caches)
    t_fill = mesurer(lambda: ecran.fill((10, 10, 20)), 10)
    t_flip = mesurer(pygame.display.flip, 10)
    t_tuiles = mesurer(tuiles, 5)
    t_lueurs = mesurer(lueurs, 10)
    t_ombres = mesurer(ombres, 10)
    t_calcul = mesurer(calcul, 3)
    total = t_fill + t_flip + t_tuiles + t_lueurs * 0.5 + t_ombres * 0.5 + t_calcul * 0.3
    fps = 1000.0 / max(1.0, total)
    lignes = [
        f"Remplir l'écran : {t_fill:.1f} ms     Afficher (flip) : {t_flip:.1f} ms",
        f"120 tuiles : {t_tuiles:.1f} ms     20 lueurs : {t_lueurs:.1f} ms     20 ombres : {t_ombres:.1f} ms",
        f"Calcul Python : {t_calcul:.1f} ms     Écran : {LARGEUR}x{HAUTEUR}",
        f"Estimation d'une image : {total:.0f} ms  (~{fps:.0f} FPS)",
    ]
    s2 = max(0.25, ECHELLE) ** 2
    est_plein = (t_fill + t_flip + t_tuiles + t_lueurs * 0.5 + t_ombres * 0.5) / s2
    conseil = 1.0 if est_plein <= 16 else (0.75 if est_plein <= 30 else 0.5)
    lignes.append(f"Résolution conseillée : {int(conseil * 100)}%  (redémarre le jeu pour l'appliquer)")
    if PARAMS["resolution"] == 0:
        EXTRA["echelle_auto"] = conseil
        sauvegarder_parametres()
    PAR["bench"] = lignes
    try:
        with open(chemin_donnees("bench_flex.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lignes) + "\n")
    except Exception:
        pass


def traiter_tap_parametres(x, y):
    for rect, genre, cle, delta in PAR["zones"]:
        if rect.collidepoint(x, y):
            if genre == "chg":
                changer_param(cle, delta)
            elif genre == "reset":
                reinitialiser_parametres()
            elif genre == "bench":
                lancer_benchmark()
            elif genre == "action" and cle == "editeur":
                lancer_transition(("etat", ETAT_EDITEUR))
            elif genre == "retour":
                sauvegarder_parametres()
                if PAR["origine"] == ETAT_JEU:
                    lancer_transition(("retour_jeu",), DUREE_CHARGEMENT_RAPIDE)
                else:
                    lancer_transition(("etat", ETAT_MENU))
            return


def dessiner_parametres():
    dessiner_fond_menu()
    pw = min(780, LARGEUR - 40)
    px0 = LARGEUR // 2 - pw // 2
    dessiner_panneau_neon(px0, pw, BLEU_CYBER, False, 215)
    dessiner_titre_glitch("PARAMÈTRES", police_titre, LARGEUR // 2, 50)
    note = None
    if PAR["redemarrer"]:
        note = "Redémarre le jeu pour appliquer la nouvelle résolution"
    elif PARAMS["resolution"] == 0 and EXTRA.get("echelle_auto") not in (None, ECHELLE):
        note = f"Résolution automatique au prochain lancement : {int(EXTRA['echelle_auto'] * 100)}%"
    if note:
        tn_ = rendu_texte(police_petite, note, True, JAUNE_CYBER)
        ecran.blit(tn_, (LARGEUR // 2 - tn_.get_width() // 2, 110))

    y_zone = 130
    nb_sections = sum(1 for d in PARAM_DEFS if len(d) == 2)
    nb_lignes = len(PARAM_DEFS) - nb_sections
    hauteur_contenu = nb_sections * 50 + nb_lignes * 74 + 180 + (len(PAR["bench"]) * 26 + 16 if PAR["bench"] else 0) + 40
    hauteur_visible = HAUTEUR - y_zone - 8
    defil_max = max(0, hauteur_contenu - hauteur_visible)
    PAR["scroll"] = max(-defil_max, min(0, PAR["scroll"]))

    zones = [(rect_retour_infos, "retour", None, 0)]
    couleurs_section = (ROSE_SYNTH, BLEU_CYBER, JAUNE_CYBER, VIOLET_CYBER)
    idx_section = 0
    y = y_zone + 6 + PAR["scroll"]
    ecran.set_clip(pygame.Rect(px0 - 14, y_zone, pw + 28, HAUTEUR - y_zone))
    for defn in PARAM_DEFS:
        if len(defn) == 2:
            col = couleurs_section[idx_section % 4]
            idx_section += 1
            if y_zone - 50 < y < HAUTEUR:
                t = rendu_texte(police_jeu, defn[1], True, col)
                ecran.blit(t, (px0 + 28, int(y + 8)))
                DRAW.line(ecran, eclaircir(col, 0.5), (px0 + 28, int(y + 40)), (px0 + pw - 28, int(y + 40)), 2)
            y += 50
            continue
        if defn[0] == "ACTION":
            if y_zone - 66 < y < HAUTEUR:
                r = pygame.Rect(px0 + 24, int(y), pw - 48, 62)
                DRAW.rect(ecran, (10, 13, 28), r, border_radius=12)
                DRAW.rect(ecran, eclaircir(VIOLET_CYBER, 0.5), r, 2, border_radius=12)
                tl = rendu_texte(police_aide, defn[1], True, BLANC_NEON)
                ecran.blit(tl, (r.x + 18, r.centery - tl.get_height() // 2))
                rb = pygame.Rect(r.right - 232, r.y + 8, 214, 46)
                bouton_neon(rb, VIOLET_CYBER, "MODIFIER", police_petite, plein=True)
                if y_zone + 8 < r.centery < HAUTEUR - 8:
                    zones.append((rb, "action", defn[2], 0))
            y += 74
            continue
        cle, label, options, _defaut = defn
        if y_zone - 66 < y < HAUTEUR:
            r = pygame.Rect(px0 + 24, int(y), pw - 48, 62)
            DRAW.rect(ecran, (10, 13, 28), r, border_radius=12)
            DRAW.rect(ecran, eclaircir(BLEU_CYBER, 0.35), r, 2, border_radius=12)
            tl = rendu_texte(police_aide, label, True, BLANC_NEON)
            ecran.blit(tl, (r.x + 18, r.centery - tl.get_height() // 2))
            lc = min(320, r.width // 2 + 10)
            xc = r.right - 12 - lc
            rg = pygame.Rect(xc, r.y + 8, 46, 46)
            rd = pygame.Rect(xc + lc - 46, r.y + 8, 46, 46)
            for rr, sens in ((rg, -1), (rd, 1)):
                DRAW.rect(ecran, (14, 20, 44), rr, border_radius=10)
                DRAW.rect(ecran, BLEU_CYBER, rr, 2, border_radius=10)
                cx_, cy_ = rr.center
                DRAW.lines(ecran, BLANC_NEON, False,
                           [(cx_ - sens * 6, cy_ - 11), (cx_ + sens * 6, cy_), (cx_ - sens * 6, cy_ + 11)], 4)
            valeur = options[PARAMS[cle]]
            cv = VERT_FLUO if valeur == "Oui" else ((150, 160, 190) if valeur == "Non" else CYAN_NEON)
            tv = rendu_texte(police_aide, valeur, True, cv)
            ecran.blit(tv, (xc + lc // 2 - tv.get_width() // 2, r.centery - tv.get_height() // 2))
            if y_zone + 8 < r.centery < HAUTEUR - 8:
                zones.append((rg, "chg", cle, -1))
                zones.append((rd, "chg", cle, 1))
                zones.append((pygame.Rect(xc + 46, r.y, lc - 92, 62), "chg", cle, 1))
        y += 74
    rr = pygame.Rect(px0 + 60, int(y + 14), pw - 120, 56)
    if y_zone - 60 < y + 14 < HAUTEUR:
        bouton_neon(rr, ROUGE_ALERTE, "RÉTABLIR PAR DÉFAUT", police_bouton)
        if y_zone < rr.centery < HAUTEUR - 8:
            zones.append((rr, "reset", None, 0))
    rb = pygame.Rect(px0 + 60, int(y + 84), pw - 120, 56)
    if y_zone - 60 < y + 84 < HAUTEUR:
        bouton_neon(rb, VIOLET_CYBER, "TEST DE PERFORMANCE", police_bouton)
        if y_zone < rb.centery < HAUTEUR - 8:
            zones.append((rb, "bench", None, 0))
    for k_b, ligne_b in enumerate(PAR["bench"]):
        yb = int(y + 84 + 56 + 14 + k_b * 26)
        if y_zone - 26 < yb < HAUTEUR:
            tb = rendu_texte(police_petite, ligne_b, True, CYAN_NEON if k_b == len(PAR["bench"]) - 1 else BLANC_NEON)
            ecran.blit(tb, (LARGEUR // 2 - tb.get_width() // 2, yb))
    ecran.set_clip(None)
    PAR["zones"] = zones

    if defil_max > 0:
        x_barre, haut_piste = px0 + pw - 9, y_zone + 6
        long_piste = HAUTEUR - y_zone - 22
        long_pouce = max(30, int(long_piste * hauteur_visible / float(hauteur_contenu)))
        y_pouce = haut_piste + int((long_piste - long_pouce) * (-PAR["scroll"]) / float(defil_max))
        DRAW.rect(ecran, (16, 20, 40), (x_barre, haut_piste, 4, long_piste), border_radius=2)
        DRAW.rect(ecran, BLEU_CYBER, (x_barre, y_pouce, 4, long_pouce), border_radius=2)
        if PAR["scroll"] > -6:
            indice = rendu_texte(police_petite, "Glisse pour voir les autres réglages", True, BLEU_CYBER)
            ecran.blit(obtenir_voile(indice.get_width() + 30, 34, (5, 6, 16, 200)), (LARGEUR // 2 - indice.get_width() // 2 - 15, HAUTEUR - 50))
            ecran.blit(indice, (LARGEUR // 2 - indice.get_width() // 2, HAUTEUR - 41))

    bouton_neon(rect_retour_infos, ROUGE_ALERTE, "< RETOUR", police_bouton)


# ==================== BOUTIQUE ET ÉCONOMIE ====================
# Les pièces se gagnent en fin de mission ; la boutique les transforme en bouclier, armes, améliorations et skins de laser.
CHEMIN_BOUTIQUE = chemin_donnees("boutique_flex.json")

# Articles à niveaux : clé, nom, description, prix de chaque niveau, libellé de l'effet pour le niveau 0, 1, 2...
BOUTIQUE_ARTICLES = [
    {"section": "ARMURE"},
    {"cle": "bouclier", "nom": "Bouclier énergétique", "desc": "Absorbe des coups de drone ou de Boss",
     "prix": [150, 400, 900], "effets": ["Aucun", "1 coup", "2 coups", "3 coups"]},
    {"section": "ARMES"},
    {"cle": "cadence", "nom": "Cadence de tir", "desc": "Tire plus vite quand tu maintiens TIR",
     "prix": [100, 250, 500, 900], "effets": ["Normale", "+12%", "+28%", "+50%", "+80%"]},
    {"cle": "degats", "nom": "Puissance anti-Boss", "desc": "Plus de dégâts contre le Boss",
     "prix": [200, 500, 1000], "effets": ["Normale", "+40%", "+80%", "+120%"]},
    {"cle": "perfo", "nom": "Tir perforant", "desc": "Le laser traverse plusieurs drones",
     "prix": [250, 600, 1200], "effets": ["Aucun", "1 drone", "2 drones", "3 drones"]},
    {"section": "AMÉLIORATIONS"},
    {"cle": "hack", "nom": "Hack accéléré", "desc": "Le CORE se pirate plus vite",
     "prix": [150, 400, 800], "effets": ["Normal", "+25%", "+50%", "+80%"]},
    {"cle": "potion", "nom": "Potions prolongées", "desc": "Chaque potion donne plus de temps",
     "prix": [100, 300], "effets": ["+5 s", "+7 s", "+9 s"]},
    {"cle": "chrono", "nom": "Chrono étendu", "desc": "Plus de temps au départ de la mission",
     "prix": [150, 400, 800], "effets": ["+0 s", "+5 s", "+10 s", "+15 s"]},
    {"section": "SKINS DE LASER"},
]
# Skins : identifiant, nom, prix, couleur du laser, couleur de sa traînée
SKINS_LASER = [
    # --- COMMUNS
    ("cyan", "Cyan néon", 0, (0, 235, 255), (0, 80, 150)),
    ("rose", "Rose synthwave", 150, (255, 70, 200), (140, 20, 100)),
    ("acide", "Vert acide", 150, (170, 255, 0), (70, 120, 0)),
    ("rouge", "Rouge alerte", 200, (255, 60, 60), (130, 10, 20)),
    ("blanc", "Blanc glacé", 200, (235, 245, 255), (90, 120, 160)),
    # --- RARES
    ("or", "Or électrique", 350, (255, 205, 50), (140, 90, 0)),
    ("violet", "Violet plasma", 350, (175, 95, 255), (80, 30, 150)),
    ("magenta", "Magenta pulsar", 500, (255, 0, 160), (110, 0, 90)),
    ("azur", "Bleu électrique", 500, (60, 140, 255), (10, 50, 150)),
    ("lave", "Lave en fusion", 700, (255, 120, 20), (150, 30, 0)),
    ("emeraude", "Émeraude toxique", 700, (40, 255, 150), (0, 100, 60)),
    # --- ÉPIQUES
    ("aurore", "Aurore boréale", 1800, (120, 255, 220), (130, 60, 200)),
    ("venin", "Venin radioactif", 2200, (200, 255, 40), (40, 110, 20)),
    ("rubis", "Rubis sang", 2500, (255, 30, 90), (100, 0, 40)),
    ("glace", "Cristal polaire", 3000, (190, 240, 255), (60, 150, 230)),
    # --- LÉGENDAIRES (les deux derniers sont animés)
    ("soleil_noir", "Soleil noir", 5000, (255, 255, 255), (70, 0, 140)),
    ("arcenciel", "Arc-en-ciel", 6500, (255, 0, 0), (120, 0, 0)),
    ("flex_pulse", "Flex Pulse", 8500, (0, 235, 255), (255, 0, 180)),
    # --- EXCLUSIF : jamais en vente, débloqué en terminant tous les défis de 3 semaines
    ("champion", "Champion Flex", 0, (255, 215, 0), (255, 80, 0)),
]
# Rareté de chaque skin : C = commun, R = rare, E = épique, L = légendaire
RARETE_SKIN = {"cyan": "C", "rose": "C", "acide": "C", "rouge": "C", "blanc": "C",
               "or": "R", "violet": "R", "magenta": "R", "azur": "R", "lave": "R", "emeraude": "R",
               "aurore": "E", "venin": "E", "rubis": "E", "glace": "E",
               "soleil_noir": "L", "arcenciel": "L", "flex_pulse": "L", "champion": "L"}
EXCLUSIFS = ("champion",)                      # skins qu'on ne peut pas acheter
RARETES_INFO = {"C": ("COMMUN", (170, 180, 200)), "R": ("RARE", (60, 150, 255)),
                "E": ("ÉPIQUE", (190, 100, 255)), "L": ("LÉGENDAIRE", (255, 200, 50))}
SKINS_ANIMES = ("arcenciel", "flex_pulse")      # couleurs qui changent en continu
ARTICLES_NIVEAUX = {a["cle"]: a for a in BOUTIQUE_ARTICLES if "cle" in a}

DEFIS_VIDE = {"semaine": 0, "liste": [], "progres": {}, "valides": [], "bonus": False, "completes": 0, "serie": 0,
              "diff": 3, "precedents": []}
BOUTIQUE = {"pieces": 0, "niveaux": {}, "skins": ["cyan"], "skin_actif": "cyan", "faits": [], "etoiles": {},
            "defis": dict(DEFIS_VIDE)}
STATS = {"bouclier": 0, "cadence": 8, "degats": 1.0, "perfo": 0, "hack": 1.0, "potion": 0, "chrono": 0}
LASER = {"main": SKINS_LASER[0][3], "trail": SKINS_LASER[0][4]}
MISSION = {"drones": 0, "recompense": None, "versee": False, "duree": 1, "defis_ok": []}      # suivi de la mission en cours
ETAT_JOUEUR = {"bouclier": 0, "invuln": 0}                         # bouclier restant et invulnérabilité (en pas de logique)
BQ = {"scroll": 0.0, "drag": False, "id": None, "y": 0.0, "x0": 0.0, "y0": 0.0, "moved": False,
      "zones": [], "msg": "", "msg_couleur": VERT_FLUO, "msg_t": -10000}


def charger_boutique():
    d, statut = lire_json_signe(CHEMIN_BOUTIQUE)
    if statut == "altere":
        signaler_sauvegarde_alteree()
        return
    if d is None:
        return
    try:
        if isinstance(d.get("pieces"), int) and d["pieces"] >= 0:
            BOUTIQUE["pieces"] = d["pieces"]
        for cle, art in ARTICLES_NIVEAUX.items():
            v = d.get("niveaux", {}).get(cle, 0)
            if isinstance(v, int) and 0 <= v <= len(art["prix"]):
                BOUTIQUE["niveaux"][cle] = v
        ids = [s[0] for s in SKINS_LASER]
        BOUTIQUE["skins"] = [s for s in d.get("skins", []) if s in ids]
        if "cyan" not in BOUTIQUE["skins"]:
            BOUTIQUE["skins"].insert(0, "cyan")
        actif = d.get("skin_actif")
        BOUTIQUE["skin_actif"] = actif if actif in BOUTIQUE["skins"] else "cyan"
        BOUTIQUE["faits"] = [n for n in d.get("faits", []) if isinstance(n, int)]
        BOUTIQUE["etoiles"] = {k: v for k, v in d.get("etoiles", {}).items() if isinstance(v, int) and 1 <= v <= 3}
        BOUTIQUE["defis"] = _defis_depuis_sauvegarde(d.get("defis"))
    except Exception as e:
        print(f"⚠️ Boutique illisible : {e}")
    if statut == "ancien":
        sauvegarder_boutique()            # une ancienne sauvegarde (sans signature) est acceptée une fois, puis signée


def sauvegarder_boutique():
    try:
        ecrire_json_signe(CHEMIN_BOUTIQUE, BOUTIQUE)
    except Exception as e:
        print(f"⚠️ Impossible de sauvegarder la boutique : {e}")


def recalculer_stats():
    """Traduit les niveaux achetés en valeurs de jeu."""
    n = BOUTIQUE["niveaux"]
    STATS["bouclier"] = n.get("bouclier", 0)
    STATS["cadence"] = (8, 7, 6, 5, 4)[n.get("cadence", 0)]
    STATS["degats"] = (1.0, 1.4, 1.8, 2.2)[n.get("degats", 0)]
    STATS["perfo"] = n.get("perfo", 0)
    STATS["hack"] = (1.0, 1.25, 1.5, 1.8)[n.get("hack", 0)]
    STATS["potion"] = (0, 120, 240)[n.get("potion", 0)]
    STATS["chrono"] = (0, 300, 600, 900)[n.get("chrono", 0)]


def couleurs_skin(sid):
    """Couleurs (laser, traînée) d'un skin ; les skins animés changent avec le temps."""
    t = pygame.time.get_ticks() / 1000.0
    if sid == "arcenciel":
        p = (int(127 + 128 * math.sin(t * 2.2)), int(127 + 128 * math.sin(t * 2.2 + 2.094)), int(127 + 128 * math.sin(t * 2.2 + 4.188)))
        return p, (p[0] * 45 // 100, p[1] * 45 // 100, p[2] * 45 // 100)
    if sid == "flex_pulse":
        k = (math.sin(t * 3.0) + 1.0) / 2.0
        a, b = (0, 235, 255), (255, 0, 180)
        p = tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))
        q = tuple(int(b[i] + (a[i] - b[i]) * k) for i in range(3))
        return p, tuple(c * 55 // 100 for c in q)
    for ident, _nom, _prix, principal, traine in SKINS_LASER:
        if ident == sid:
            return principal, traine
    return SKINS_LASER[0][3], SKINS_LASER[0][4]


def appliquer_skin():
    LASER["main"], LASER["trail"] = couleurs_skin(BOUTIQUE["skin_actif"])


def animer_skin():
    """À appeler à chaque image : fait vivre les skins animés (arc-en-ciel, pulse)."""
    if BOUTIQUE["skin_actif"] in SKINS_ANIMES:
        LASER["main"], LASER["trail"] = couleurs_skin(BOUTIQUE["skin_actif"])


def niveau_article(cle):
    return BOUTIQUE["niveaux"].get(cle, 0)


# ---------------------------------------------------------------- dégâts subis et récompenses
def subir_degats(message):
    """Retourne True si le joueur est vaincu ; False si le bouclier (ou l'invulnérabilité) a encaissé le coup."""
    global partie_perdue, message_defaite
    if ETAT_JOUEUR["invuln"] > 0:
        return False
    if message in ("ÉCRASÉ PAR LE BOSS", "BRÛLÉ PAR LE BOSS") and POUV.get("boss_boucliers", 0) > 0:
        POUV["boss_boucliers"] -= 1                 # pouvoir du personnage : absorbe un coup du boss
        ETAT_JOUEUR["invuln"] = 90
        creer_explosion(joueur_x, joueur_y, (120, 220, 255), 18, 6.0, 5.0)
        if SON_ACTIF:
            son_explosion.play()
        return False
    if message == "SYSTÈME CORROMPU" and POUV.get("survie", 0) > 0:
        POUV["survie"] -= 1                         # pouvoir du personnage : survit à un drone de plus
        ETAT_JOUEUR["invuln"] = 45
        creer_explosion(joueur_x, joueur_y, (255, 120, 140), 18, 6.0, 4.0)
        if SON_ACTIF:
            son_explosion.play()
        return False
    if ETAT_JOUEUR["bouclier"] > 0:
        ETAT_JOUEUR["bouclier"] -= 1
        ETAT_JOUEUR["invuln"] = 90
        creer_explosion(joueur_x, joueur_y, LASER["main"], 18, 6.0, 5.0)
        if SON_ACTIF:
            son_explosion.play()
        return False
    partie_perdue = True
    message_defaite = message
    if SON_ACTIF:
        son_echec.play()
    return True


def calculer_recompense(victoire):
    drones = MISSION["drones"]
    mult_or = 1.0 + _cfg().get("or", 0) / 100.0                   # pouvoir « chasseur d'or »
    if not victoire:
        return {"total": int((drones // 3) * mult_or), "base": 0, "temps": 0, "drones": drones, "boss": 0, "reduite": False}
    n = niveau_actuel
    base = 10 + 2 * n
    temps = max(0, temps_restant_frames) // 60 // 6
    bonus_drones = drones // 2
    boss = (60 + 10 * ((n + 1) // 5)) if niveau_data["est_boss"] else 0
    total = base + temps + bonus_drones + boss
    reduite = n in BOUTIQUE["faits"]
    if reduite:
        total //= 4                                  # niveau déjà réussi : gains divisés par 4
    total = max(1, int(total * mult_or))
    return {"total": total, "base": base, "temps": temps, "drones": bonus_drones, "boss": boss, "reduite": reduite}


def accorder_recompense(victoire):
    """Verse les pièces de la mission (une seule fois par partie)."""
    if MISSION["versee"]:
        return
    MISSION["versee"] = True
    if MP["actif"]:                      # multijoueur (étape 1) : aucune pièce ni défi
        MISSION["recompense"] = {"total": 0, "base": 0, "temps": 0, "drones": 0, "boss": 0, "reduite": False}
        return
    r = calculer_recompense(victoire)
    MISSION["recompense"] = r
    BOUTIQUE["pieces"] += r["total"]
    if victoire and niveau_actuel not in BOUTIQUE["faits"]:
        BOUTIQUE["faits"].append(niveau_actuel)
    try:
        defis_evenement(victoire, r)
    except Exception as e:
        print(f"⚠️ Défis : {e}")
    sauvegarder_boutique()


# ---------------------------------------------------------------- achats
def message_boutique(texte, couleur):
    BQ["msg"], BQ["msg_couleur"], BQ["msg_t"] = texte, couleur, pygame.time.get_ticks()


def acheter_niveau(cle):
    art = ARTICLES_NIVEAUX[cle]
    niv = niveau_article(cle)
    if niv >= len(art["prix"]):
        message_boutique("Déjà au niveau maximum", JAUNE_CYBER)
        return
    prix = art["prix"][niv]
    if BOUTIQUE["pieces"] < prix:
        message_boutique(f"Il te manque {prix - BOUTIQUE['pieces']} pièces", ROUGE_ALERTE)
        return
    BOUTIQUE["pieces"] -= prix
    BOUTIQUE["niveaux"][cle] = niv + 1
    recalculer_stats()
    sauvegarder_boutique()
    message_boutique(f"{art['nom']} : niveau {niv + 1} acheté !", VERT_FLUO)


def acheter_ou_equiper_skin(sid):
    for ident, nom, prix, _principal, _traine in SKINS_LASER:
        if ident != sid:
            continue
        if sid not in BOUTIQUE["skins"]:
            if BOUTIQUE["pieces"] < prix:
                message_boutique(f"Il te manque {prix - BOUTIQUE['pieces']} pièces", ROUGE_ALERTE)
                return
            BOUTIQUE["pieces"] -= prix
            BOUTIQUE["skins"].append(sid)
            message_boutique(f"Skin « {nom} » acheté et équipé !", VERT_FLUO)
        else:
            message_boutique(f"Skin « {nom} » équipé", VERT_FLUO)
        BOUTIQUE["skin_actif"] = sid
        appliquer_skin()
        sauvegarder_boutique()
        return


def traiter_tap_boutique(x, y):
    for rect, genre, cle in BQ["zones"]:
        if rect.collidepoint(x, y):
            if genre == "niveau":
                acheter_niveau(cle)
            elif genre == "skin":
                acheter_ou_equiper_skin(cle)
            elif genre == "retour":
                lancer_transition(("etat", ETAT_MENU))
            return


def gerer_liste_tactile(liste, event, etat_cible, action_tap):
    """Défilement au doigt d'un écran à liste ; un simple toucher (sans glisser) appelle action_tap(x, y)."""
    if etat_actuel == etat_cible:
        if event.type == pygame.FINGERDOWN:
            liste.update(drag=True, id=event.finger_id, y=event.y * HAUTEUR, x0=event.x * LARGEUR, y0=event.y * HAUTEUR, moved=False)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not liste["drag"]:
            p = pos_ev(event)
            liste.update(drag=True, id="souris", y=p[1], x0=p[0], y0=p[1], moved=False)
        elif event.type == pygame.FINGERMOTION and liste["drag"] and event.finger_id == liste["id"]:
            y_nouveau = event.y * HAUTEUR
            liste["scroll"] += y_nouveau - liste["y"]
            liste["y"] = y_nouveau
            if abs(y_nouveau - liste["y0"]) > 14:
                liste["moved"] = True
        elif event.type == pygame.MOUSEMOTION and liste["drag"] and liste["id"] == "souris":
            y_nouveau = pos_ev(event)[1]
            liste["scroll"] += y_nouveau - liste["y"]
            liste["y"] = y_nouveau
            if abs(y_nouveau - liste["y0"]) > 14:
                liste["moved"] = True
    if liste["drag"] and ((event.type == pygame.MOUSEBUTTONUP and liste["id"] == "souris") or
                          (event.type == pygame.FINGERUP and event.finger_id == liste["id"])):
        liste["drag"], liste["id"] = False, None
        if not liste["moved"] and etat_actuel == etat_cible and not TRANS["actif"]:
            action_tap(liste["x0"], liste["y0"])



# ==================== DÉFIS HEBDOMADAIRES ====================
# Chaque semaine (du lundi 00:00 UTC au dimanche soir), 4 défis tirés au sort (les mêmes pour tous les joueurs).
# Récompense en pièces à chaque défi réussi + bonus si les 4 sont terminés ; 3 semaines parfaites = skin « Champion Flex ».
DEFIS_NB = 4
DEFIS_BONUS = 250
DEFIS_SEMAINES_CHAMPION = 3
# type : (cible min, cible max, pas, récompense par unité, récompense fixe)
DEFIS_MODELES = {
    "missions":   (4, 8, 1, 15, 0),
    "drones":     (50, 120, 10, 1, 0),
    "boss":       (1, 3, 1, 70, 0),
    "pieces":     (150, 300, 50, 0.5, 0),
    "rapides":    (2, 4, 1, 35, 0),
    "haut_niveau": (5, 15, 1, 4, 60),
    "serie":      (2, 4, 1, 45, 0),
    "total_etoiles": (6, 15, 1, 8, 0),
    "piece_unique": (40, 100, 10, 0.8, 20),
    "drones_mission": (15, 40, 5, 3, 0),
}
DEFIS_UNIQUES = ("haut_niveau", "piece_unique", "drones_mission")      # défis à réussir en une seule mission (objectif = 1)
DEFIS_MAX = {"missions": 15, "drones": 300, "boss": 5, "pieces": 700, "rapides": 8, "serie": 6,
             "total_etoiles": 30, "haut_niveau": 999, "piece_unique": 160, "drones_mission": 90}
DEFIS_DIFF_MAX = 10          # difficulté de 1 à 10 ; elle monte quand le joueur réussit tout, baisse quand il réussit peu


def bonus_defis(d):
    """Le bonus de semaine complète grandit avec la difficulté."""
    return max(150, DEFIS_BONUS + 25 * (d["diff"] - 3))
DEF = {"scroll": 0.0, "drag": False, "id": None, "y": 0.0, "x0": 0.0, "y0": 0.0, "moved": False, "zones": []}


def texte_defi(defi):
    n, k = defi["cible"], defi["type"]
    if k == "missions":
        return f"Remporte {n} missions"
    if k == "drones":
        return f"Détruis {n} drones"
    if k == "boss":
        return "Bats 1 boss" if n == 1 else f"Bats {n} boss"
    if k == "pieces":
        return f"Gagne {n} pièces en missions"
    if k == "rapides":
        return f"Réussis {n} missions avec 40 % du temps restant"
    if k == "haut_niveau":
        return f"Remporte une mission de niveau {n} ou plus"
    if k == "serie":
        return f"Enchaîne {n} victoires d'affilée"
    if k == "total_etoiles":
        return f"Gagne {n} étoiles au total"
    if k == "piece_unique":
        return f"Gagne {n} pièces en une seule mission"
    if k == "drones_mission":
        return f"Détruis {n} drones en une seule mission"
    return "Défi"


def _defis_depuis_sauvegarde(dd):
    """Relit les défis d'une sauvegarde en vérifiant chaque valeur."""
    d = {"semaine": 0, "liste": [], "progres": {}, "valides": [], "bonus": False, "completes": 0, "serie": 0,
         "diff": 3, "precedents": []}
    if not isinstance(dd, dict):
        return d
    try:
        d["semaine"] = max(0, int(dd.get("semaine", 0)))
        for x in dd.get("liste", []):
            if isinstance(x, dict) and x.get("type") in DEFIS_MODELES:
                d["liste"].append({"id": x["type"], "type": x["type"], "cible": max(1, int(x.get("cible", 1))),
                                   "recomp": max(0, int(x.get("recomp", 0)))})
        ids = [x["id"] for x in d["liste"]]
        d["progres"] = {k: max(0, int(v)) for k, v in dict(dd.get("progres", {})).items() if k in ids}
        d["valides"] = [k for k in dd.get("valides", []) if k in ids]
        d["bonus"] = bool(dd.get("bonus", False))
        d["completes"] = max(0, int(dd.get("completes", 0)))
        d["serie"] = max(0, int(dd.get("serie", 0)))
        d["diff"] = max(1, min(DEFIS_DIFF_MAX, int(dd.get("diff", 3))))
        d["precedents"] = [k for k in dd.get("precedents", []) if k in DEFIS_MODELES]
    except Exception:
        return {"semaine": 0, "liste": [], "progres": {}, "valides": [], "bonus": False, "completes": 0, "serie": 0,
                "diff": 3, "precedents": []}
    return d


def semaine_courante():
    """Numéro de la semaine (elle commence le lundi à 00:00 UTC)."""
    jours = int(heure_serveur_s() // 86400)
    return (jours + 3) // 7


def fin_semaine_s(semaine):
    return ((semaine + 1) * 7 - 3) * 86400


def generer_defis(semaine, diff=3, precedents=()):
    """Tire au sort les défis de la semaine. La difficulté (1 à 10) règle les cibles et les récompenses ;
    les types de la semaine précédente ne reviennent pas tout de suite, pour éviter la répétition."""
    rng = random.Random(semaine * 7919 + 13)
    avance = int(globals().get("niveau_max_atteint", 0))
    facteur = 0.75 + 0.15 * (diff - 1)
    types = list(DEFIS_MODELES.keys())
    if avance < 4:                       # pas encore de boss atteignable : pas de défi boss
        types.remove("boss")
    nouveaux = [k for k in types if k not in precedents]
    if len(nouveaux) >= DEFIS_NB:
        types = nouveaux
    rng.shuffle(types)
    liste = []
    for k in types[:DEFIS_NB]:
        lo, hi, pas, par_unite, fixe = DEFIS_MODELES[k]
        n = rng.randrange(lo, hi + 1, pas)
        if k == "haut_niveau":
            n = max(2, min(n + (diff - 3), avance + 1))
        else:
            n = max(1, min(DEFIS_MAX[k], int(round(n * facteur / pas)) * pas))
            if k == "drones_mission":            # jamais plus de drones que les missions déjà débloquées n'en contiennent
                n = min(n, max(5, int(min(70, 3 + 2 * avance) * 0.8) // 5 * 5))
            elif k == "piece_unique":            # jamais plus que ce qu'une mission peut rapporter à ce stade
                n = min(n, 40 if avance < 4 else (100 if avance < 9 else 160))
        recomp = max(10, int((fixe + n * par_unite) * (1 + 0.04 * (diff - 3))))
        liste.append({"id": k, "type": k, "cible": n, "recomp": recomp})
    return liste


def defis_verifier():
    """Retourne les défis de la semaine en cours (en les renouvelant quand une nouvelle semaine commence)."""
    d = BOUTIQUE["defis"]
    sem = max(semaine_courante(), d["semaine"])        # une horloge remise en arrière ne redonne jamais d'anciens défis
    if sem > d["semaine"] or not d["liste"]:
        if d["liste"]:
            faits, total = len(d["valides"]), len(d["liste"])
            if faits >= total:
                d["diff"] = min(DEFIS_DIFF_MAX, d["diff"] + 1)        # tout réussi : la semaine suivante est plus dure
            elif faits <= 1:
                d["diff"] = max(1, d["diff"] - 1)                     # presque rien de réussi : un peu plus facile
            d["precedents"] = [x["type"] for x in d["liste"]]
        d.update(semaine=sem, liste=generer_defis(sem, d["diff"], d["precedents"]), progres={}, valides=[], bonus=False, serie=0)
        sauvegarder_boutique()
    return d


def _valider_defi(d, defi):
    d["valides"].append(defi["id"])
    BOUTIQUE["pieces"] += defi["recomp"]
    MISSION["defis_ok"].append((texte_defi(defi), defi["recomp"]))
    if len(d["valides"]) >= len(d["liste"]) and not d["bonus"]:
        d["bonus"] = True
        d["completes"] += 1
        b = bonus_defis(d)
        BOUTIQUE["pieces"] += b
        MISSION["defis_ok"].append(("BONUS SEMAINE COMPLÈTE", b))
        if d["completes"] >= DEFIS_SEMAINES_CHAMPION and "champion" not in BOUTIQUE["skins"]:
            BOUTIQUE["skins"].append("champion")
            MISSION["defis_ok"].append(("SKIN CHAMPION FLEX DÉBLOQUÉ", 0))


def defis_evenement(victoire, r):
    """Met à jour les défis à la fin d'une mission (r = récompense de la mission)."""
    d = defis_verifier()
    d["serie"] = d["serie"] + 1 if victoire else 0
    for defi in d["liste"]:
        if defi["id"] in d["valides"]:
            continue
        k = defi["type"]
        p = d["progres"].get(defi["id"], 0)
        if k == "missions" and victoire:
            p += 1
        elif k == "drones":
            p += MISSION["drones"]
        elif k == "boss" and victoire and niveau_data["est_boss"]:
            p += 1
        elif k == "pieces":
            p += r["total"]
        elif k == "rapides" and victoire and temps_restant_frames >= 0.4 * MISSION["duree"]:
            p += 1
        elif k == "haut_niveau" and victoire and niveau_actuel + 1 >= defi["cible"]:
            p += 1
        elif k == "serie":
            p = max(p, d["serie"])
        elif k == "total_etoiles" and victoire:
            p += int(FIN.get("etoiles", 0))
        elif k == "piece_unique" and victoire and r["total"] >= defi["cible"]:
            p += 1
        elif k == "drones_mission" and victoire and MISSION["drones"] >= defi["cible"]:
            p += 1
        objectif = 1 if k in DEFIS_UNIQUES else defi["cible"]
        d["progres"][defi["id"]] = min(p, objectif)
        if d["progres"][defi["id"]] >= objectif:
            _valider_defi(d, defi)


def traiter_tap_defis(x, y):
    for rect, genre, _cle in DEF["zones"]:
        if rect.collidepoint(x, y) and genre == "retour":
            lancer_transition(("etat", ETAT_MENU))
            return


def _texte_ajuste(texte, couleur, largeur_max):
    t = rendu_texte(police_aide, texte, True, couleur)
    if t.get_width() > largeur_max:
        t = rendu_texte(police_petite, texte, True, couleur)
    return t


def dessiner_defis():
    d = defis_verifier()
    dessiner_fond_menu()
    pw = min(780, LARGEUR - 40)
    px0 = LARGEUR // 2 - pw // 2
    dessiner_panneau_neon(px0, pw, VERT_FLUO, False, 215)
    dessiner_titre_glitch("DÉFIS", police_titre, LARGEUR // 2, 50)
    dessiner_pieces(LARGEUR - 170, 52)

    y_zone, h_carte, pas = 130, 96, 108
    nb = len(d["liste"])
    hauteur_contenu = 52 + (nb + 2) * pas + 20
    hauteur_visible = HAUTEUR - y_zone - 8
    defil_max = max(0, hauteur_contenu - hauteur_visible)
    DEF["scroll"] = max(-defil_max, min(0, DEF["scroll"]))

    y = y_zone + 6 + DEF["scroll"]
    ecran.set_clip(pygame.Rect(px0 - 14, y_zone, pw + 28, HAUTEUR - y_zone))

    # temps restant avant le renouvellement
    restant = max(0, int(fin_semaine_s(d["semaine"]) - heure_serveur_s()))
    j, h, m = restant // 86400, (restant % 86400) // 3600, (restant % 3600) // 60
    reste_txt = f"{j} j {h} h" if j > 0 else f"{h} h {m} min"
    txt = f"Difficulté {d['diff']}/{DEFIS_DIFF_MAX}   ·   Nouveaux défis dans {reste_txt}"
    t_temps = rendu_texte(police_petite, txt, True, JAUNE_CYBER)
    ecran.blit(t_temps, (LARGEUR // 2 - t_temps.get_width() // 2, int(y + 10)))
    y += 52

    def carte(y_, couleur_bord):
        r = pygame.Rect(px0 + 24, int(y_), pw - 48, h_carte)
        DRAW.rect(ecran, (10, 13, 28), r, border_radius=12)
        DRAW.rect(ecran, couleur_bord, r, 2, border_radius=12)
        return r

    def ligne(r, titre, p, cible, recomp, fait, etiquette_fin):
        col = VERT_FLUO if fait else CYAN_NEON
        largeur_titre = r.w - 36 - 120
        ecran.blit(_texte_ajuste(titre, BLANC_NEON, largeur_titre), (r.x + 18, r.y + 12))
        # récompense à droite
        if recomp:
            t_r = rendu_texte(police_jeu, f"+{recomp}", True, JAUNE_CYBER)
            dessiner_piece(r.right - 24 - t_r.get_width() - 18, r.y + 26, 11)
            ecran.blit(t_r, (r.right - 18 - t_r.get_width(), r.y + 26 - t_r.get_height() // 2))
        # barre de progression
        barre = pygame.Rect(r.x + 18, r.y + 58, r.w - 36 - 110, 16)
        DRAW.rect(ecran, (28, 34, 60), barre, border_radius=8)
        if cible > 0 and p > 0:
            DRAW.rect(ecran, col, (barre.x, barre.y, max(8, int(barre.w * min(1.0, p / float(cible)))), barre.h), border_radius=8)
        DRAW.rect(ecran, eclaircir(col, 0.5), barre, 2, border_radius=8)
        t_p = rendu_texte(police_petite, etiquette_fin if fait else f"{min(p, cible)} / {cible}", True, col)
        ecran.blit(t_p, (r.right - 18 - t_p.get_width(), barre.centery - t_p.get_height() // 2))

    for defi in d["liste"]:
        fait = defi["id"] in d["valides"]
        r = carte(y, VERT_FLUO if fait else eclaircir(BLEU_CYBER, 0.35))
        objectif = 1 if defi["type"] in DEFIS_UNIQUES else defi["cible"]
        ligne(r, texte_defi(defi), d["progres"].get(defi["id"], 0), objectif, defi["recomp"], fait, "FAIT")
        y += pas

    # bonus de la semaine
    r = carte(y, VERT_FLUO if d["bonus"] else JAUNE_CYBER)
    ligne(r, f"BONUS : termine les {nb} défis", len(d["valides"]), nb, bonus_defis(d), d["bonus"], "FAIT")
    y += pas

    # skin exclusif
    possede = "champion" in BOUTIQUE["skins"]
    r = carte(y, VERT_FLUO if possede else (255, 215, 0))
    ligne(r, "Skin exclusif « Champion Flex » : termine tous les défis 3 semaines",
          min(d["completes"], DEFIS_SEMAINES_CHAMPION), DEFIS_SEMAINES_CHAMPION, 0, possede, "DÉBLOQUÉ")
    ecran.set_clip(None)
    DEF["zones"] = [(rect_retour_infos, "retour", None)]
    bouton_neon(rect_retour_infos, ROUGE_ALERTE, "RETOUR", police_bouton)

    if defil_max > 0:
        x_barre, haut_piste = px0 + pw - 9, y_zone + 6
        long_piste = HAUTEUR - y_zone - 22
        long_pouce = max(30, int(long_piste * hauteur_visible / float(hauteur_contenu)))
        y_pouce = haut_piste + int((long_piste - long_pouce) * (-DEF["scroll"]) / float(defil_max))
        DRAW.rect(ecran, (16, 20, 40), (x_barre, haut_piste, 4, long_piste), border_radius=2)
        DRAW.rect(ecran, VERT_FLUO, (x_barre, y_pouce, 4, long_pouce), border_radius=2)


def dessiner_defis_fin(y):
    """Sur l'écran de fin de mission : liste des défis accomplis pendant cette partie."""
    for i, (texte, gain) in enumerate(MISSION["defis_ok"][:4]):
        ligne_txt = f"DÉFI : {texte}" + (f"   +{gain}" if gain else "")
        t = rendu_texte(police_petite, ligne_txt, True, VERT_FLUO)
        ecran.blit(t, (LARGEUR // 2 - t.get_width() // 2, y + i * 24))


# ---------------------------------------------------------------- dessin
def dessiner_piece(cx, cy, r):
    DRAW.circle(ecran, (255, 200, 40), (cx, cy), r)
    DRAW.circle(ecran, (255, 235, 140), (cx, cy), r, 2)
    DRAW.circle(ecran, (185, 125, 10), (cx, cy), max(2, r // 2), 2)


def dessiner_pieces(cx, y):
    """Compteur de pièces centré en cx."""
    t = rendu_texte(police_jeu, f"{BOUTIQUE['pieces']}", True, JAUNE_CYBER)
    largeur = t.get_width() + 62
    rect = pygame.Rect(cx - largeur // 2, y, largeur, 44)
    DRAW.rect(ecran, (8, 10, 20), rect, border_radius=14)
    DRAW.rect(ecran, eclaircir(JAUNE_CYBER, 0.7), rect, 2, border_radius=14)
    dessiner_piece(rect.x + 24, rect.centery, 12)
    ecran.blit(t, (rect.x + 46, rect.centery - t.get_height() // 2))


def dessiner_hud_boutique():
    """En mission : pastilles de bouclier et pièces en banque (sous le texte des drones)."""
    x, y = 40, 108
    for i in range(STATS["bouclier"]):
        centre = (x + 11 + i * 28, y + 11)
        if i < ETAT_JOUEUR["bouclier"]:
            DRAW.circle(ecran, eclaircir(LASER["main"], 0.35), centre, 12)
            DRAW.circle(ecran, LASER["main"], centre, 12, 3)
        else:
            DRAW.circle(ecran, (60, 70, 100), centre, 12, 2)
    x_pieces = x + max(0, STATS["bouclier"]) * 28 + (8 if STATS["bouclier"] else 0)
    dessiner_piece(x_pieces + 11, y + 11, 10)
    t = rendu_texte(police_petite, f"{BOUTIQUE['pieces']}", True, JAUNE_CYBER)
    ecran.blit(t, (x_pieces + 28, y + 11 - t.get_height() // 2))


def _bouton_achat(rect, texte, couleur, actif=True, plein=False):
    """Petit bouton de la boutique (zone tactile gérée par l'appelant)."""
    if actif:
        bouton_neon(rect, couleur, texte, police_petite, plein=plein)
    else:
        DRAW.rect(ecran, (14, 18, 36), rect, border_radius=12)
        DRAW.rect(ecran, (60, 70, 100), rect, 2, border_radius=12)
        t = rendu_texte(police_petite, texte, True, (110, 120, 150))
        ecran.blit(t, (rect.centerx - t.get_width() // 2, rect.centery - t.get_height() // 2))


def dessiner_boutique():
    dessiner_fond_menu()
    pw = min(780, LARGEUR - 40)
    px0 = LARGEUR // 2 - pw // 2
    dessiner_panneau_neon(px0, pw, JAUNE_CYBER, False, 215)
    dessiner_titre_glitch("BOUTIQUE", police_titre, LARGEUR // 2, 50)
    dessiner_pieces(LARGEUR - 170, 52)

    y_zone, h_carte, pas = 130, 92, 104
    nb_sections = sum(1 for a in BOUTIQUE_ARTICLES if "section" in a)
    nb_articles = len(BOUTIQUE_ARTICLES) - nb_sections
    skins_visibles = [sk for sk in SKINS_LASER if sk[0] not in EXCLUSIFS or sk[0] in BOUTIQUE["skins"]]
    hauteur_contenu = nb_sections * 50 + (nb_articles + len(skins_visibles)) * pas + 60
    hauteur_visible = HAUTEUR - y_zone - 8
    defil_max = max(0, hauteur_contenu - hauteur_visible)
    BQ["scroll"] = max(-defil_max, min(0, BQ["scroll"]))

    zones = [(rect_retour_infos, "retour", None)]
    couleurs_section = (ROSE_SYNTH, ROUGE_ALERTE, BLEU_CYBER, VIOLET_CYBER)
    idx_section = 0
    y = y_zone + 6 + BQ["scroll"]
    ecran.set_clip(pygame.Rect(px0 - 14, y_zone, pw + 28, HAUTEUR - y_zone))

    def entete(titre, y_):
        nonlocal idx_section
        col = couleurs_section[idx_section % 4]
        idx_section += 1
        if y_zone - 50 < y_ < HAUTEUR:
            t = rendu_texte(police_jeu, titre, True, col)
            ecran.blit(t, (px0 + 28, int(y_ + 8)))
            DRAW.line(ecran, eclaircir(col, 0.5), (px0 + 28, int(y_ + 40)), (px0 + pw - 28, int(y_ + 40)), 2)

    def carte(y_):
        r = pygame.Rect(px0 + 24, int(y_), pw - 48, h_carte)
        DRAW.rect(ecran, (10, 13, 28), r, border_radius=12)
        DRAW.rect(ecran, eclaircir(BLEU_CYBER, 0.35), r, 2, border_radius=12)
        return r

    def zone_visible(r):
        return y_zone + 8 < r.centery < HAUTEUR - 8

    for art in BOUTIQUE_ARTICLES:
        if "section" in art:
            entete(art["section"], y)
            y += 50
            if art["section"] == "SKINS DE LASER":
                break
            continue
        if y_zone - h_carte < y < HAUTEUR:
            cle = art["cle"]
            niv = niveau_article(cle)
            r = carte(y)
            ecran.blit(rendu_texte(police_aide, art["nom"], True, BLANC_NEON), (r.x + 18, r.y + 10))
            ecran.blit(rendu_texte(police_petite, art["desc"], True, (150, 160, 190)), (r.x + 18, r.y + 40))
            for k in range(len(art["prix"])):                                     # pastilles de niveau
                c = (r.x + 24 + k * 22, r.y + 74)
                if k < niv:
                    DRAW.circle(ecran, JAUNE_CYBER, c, 8)
                else:
                    DRAW.circle(ecran, (60, 70, 100), c, 8, 2)
            ecran.blit(rendu_texte(police_petite, art["effets"][niv], True, CYAN_NEON), (r.x + 24 + len(art["prix"]) * 22 + 6, r.y + 66))
            rb = pygame.Rect(r.right - 218, r.y + 20, 200, 52)
            if niv >= len(art["prix"]):
                _bouton_achat(rb, "NIVEAU MAX", JAUNE_CYBER, actif=False)
            else:
                prix = art["prix"][niv]
                _bouton_achat(rb, f"ACHETER  {prix}", JAUNE_CYBER, actif=BOUTIQUE["pieces"] >= prix, plein=BOUTIQUE["pieces"] >= prix)
                if zone_visible(rb):
                    zones.append((rb, "niveau", cle))
            if niv < len(art["prix"]) and BOUTIQUE["pieces"] < art["prix"][niv] and zone_visible(rb):
                zones.append((rb, "niveau", cle))
        y += pas

    for sid, nom, prix, principal, traine in skins_visibles:
        if y_zone - h_carte < y < HAUTEUR:
            r = carte(y)
            principal, traine = couleurs_skin(sid)
            lib_rar, col_rar = RARETES_INFO[RARETE_SKIN.get(sid, "C")]
            DRAW.rect(ecran, col_rar, r, 2, border_radius=12)
            t_nom = rendu_texte(police_aide, nom, True, BLANC_NEON)
            ecran.blit(t_nom, (r.x + 90, r.y + 12))
            ecran.blit(rendu_texte(police_petite, lib_rar, True, col_rar), (r.x + 90 + t_nom.get_width() + 12, r.y + 18))
            DRAW.line(ecran, traine, (r.x + 24, r.centery + 10), (r.x + 64, r.centery - 10), 9)
            DRAW.line(ecran, principal, (r.x + 30, r.centery + 7), (r.x + 64, r.centery - 10), 5)
            DRAW.circle(ecran, BLANC_NEON, (r.x + 64, r.centery - 10), 4)
            possede = sid in BOUTIQUE["skins"]
            etat_txt = "Équipé" if BOUTIQUE["skin_actif"] == sid else ("Possédé" if possede else f"{prix} pièces")
            ecran.blit(rendu_texte(police_petite, etat_txt, True, VERT_FLUO if possede else JAUNE_CYBER), (r.x + 90, r.y + 50))
            rb = pygame.Rect(r.right - 218, r.y + 20, 200, 52)
            if BOUTIQUE["skin_actif"] == sid:
                _bouton_achat(rb, "ÉQUIPÉ", VERT_FLUO, actif=False)
            elif possede:
                _bouton_achat(rb, "ÉQUIPER", VERT_FLUO)
            else:
                _bouton_achat(rb, f"ACHETER  {prix}", JAUNE_CYBER, actif=BOUTIQUE["pieces"] >= prix, plein=BOUTIQUE["pieces"] >= prix)
            if BOUTIQUE["skin_actif"] != sid and zone_visible(rb):
                zones.append((rb, "skin", sid))
        y += pas
    ecran.set_clip(None)
    BQ["zones"] = zones

    if defil_max > 0:
        x_barre, haut_piste = px0 + pw - 9, y_zone + 6
        long_piste = HAUTEUR - y_zone - 22
        long_pouce = max(30, int(long_piste * hauteur_visible / float(hauteur_contenu)))
        y_pouce = haut_piste + int((long_piste - long_pouce) * (-BQ["scroll"]) / float(defil_max))
        DRAW.rect(ecran, (16, 20, 40), (x_barre, haut_piste, 4, long_piste), border_radius=2)
        DRAW.rect(ecran, JAUNE_CYBER, (x_barre, y_pouce, 4, long_pouce), border_radius=2)

    if BQ["msg"] and pygame.time.get_ticks() - BQ["msg_t"] < 2200:
        tm = rendu_texte(police_aide, BQ["msg"], True, BQ["msg_couleur"])
        ecran.blit(obtenir_voile(tm.get_width() + 40, 44, (5, 6, 16, 235)), (LARGEUR // 2 - tm.get_width() // 2 - 20, HAUTEUR - 66))
        ecran.blit(tm, (LARGEUR // 2 - tm.get_width() // 2, HAUTEUR - 56))

    bouton_neon(rect_retour_infos, ROUGE_ALERTE, "< RETOUR", police_bouton)


def dessiner_filigrane():
    """Bandeau permanent sur une version dont le code a été modifié."""
    t = rendu_texte(police_petite, "VERSION MODIFIÉE · non officielle · version officielle : TikTok @flexplay25", True, ROUGE_ALERTE)
    ecran.blit(obtenir_voile(t.get_width() + 24, 26, (5, 6, 16, 215)), (LARGEUR // 2 - t.get_width() // 2 - 12, 2))
    ecran.blit(t, (LARGEUR // 2 - t.get_width() // 2, 5))


def dessiner_avertissement():
    """Message temporaire (8 s) quand une sauvegarde modifiée à la main a été refusée."""
    if not AVERTISSEMENT["texte"]:
        return
    if AVERTISSEMENT["debut"] is None:
        AVERTISSEMENT["debut"] = _time.time()
    if _time.time() - AVERTISSEMENT["debut"] > 8:
        return
    t = rendu_texte(police_petite, AVERTISSEMENT["texte"], True, JAUNE_CYBER)
    ecran.blit(t, (LARGEUR // 2 - t.get_width() // 2, 88))


# ==================== ÉDITEUR DE COMMANDES ====================
def dessiner_commandes(mx, my, tir_actif):
    """Joystick et bouton TIR. Utilisée par le jeu et par l'éditeur : l'aperçu est donc identique à la réalité."""
    kj, kt = JOY_RAYON_SOCLE / 85.0, BTN_TIR_RAYON / 65.0
    ecran.blit(SURF_SOCLE_JOY, (JOY_CENTRE_X - JOY_RAYON_SOCLE - 6, JOY_CENTRE_Y - JOY_RAYON_SOCLE - 6))
    dessiner_halo(JOY_CENTRE_X, JOY_CENTRE_Y, JOY_RAYON_SOCLE + 25, COULEUR_MUR, 0.28, 2)
    DRAW.circle(ecran, COULEUR_MUR, (JOY_CENTRE_X, JOY_CENTRE_Y), JOY_RAYON_SOCLE, 4)
    DRAW.circle(ecran, eclaircir(COULEUR_MUR, 0.45), (JOY_CENTRE_X, JOY_CENTRE_Y), int(JOY_RAYON_SOCLE * 0.55), 1)
    mx_j, my_j = int(mx), int(my)
    dessiner_halo(mx_j, my_j, int(55 * kj), CYAN_NEON, 0.6)
    DRAW.circle(ecran, (0, 120, 190), (mx_j, my_j), JOY_RAYON_MANETTE)
    DRAW.circle(ecran, CYAN_NEON, (mx_j, my_j), max(2, JOY_RAYON_MANETTE - 4))
    DRAW.circle(ecran, (215, 250, 255), (mx_j - int(8 * kj), my_j - int(9 * kj)), max(2, int(9 * kj)))
    if not DEVIL["actif"]:                                   # Devil : pas de tir
        ecran.blit(SURF_BTN_TIR, (BTN_TIR_X - BTN_TIR_RAYON - 6, BTN_TIR_Y - BTN_TIR_RAYON - 6))
        dessiner_halo(BTN_TIR_X, BTN_TIR_Y, int((85 if tir_actif else 70) * kt), ROUGE_ALERTE, 0.95 if tir_actif else 0.35)
        DRAW.circle(ecran, ROUGE_ALERTE, (BTN_TIR_X, BTN_TIR_Y), BTN_TIR_RAYON, 5)
        tt = rendu_texte(police_bouton, "TIR", True, BLANC_NEON)
        ecran.blit(tt, (BTN_TIR_X - tt.get_width() // 2, BTN_TIR_Y - tt.get_height() // 2))


# ===== POUVOIRS DEBUT
POUVOIRS_SKINS = {
    "recrue": {"survie": 1},
    "sergent_du_desert": {"bouclier": 1, "grenades": 3},
    "rodeur_urbain": {"sprint": 3},
    "fantassin_polaire": {"or": 10},
    "chasseur_de_primes": {"perforant": 1, "munitions": 1},
    "mercenaire_rouge": {"sprint": 5, "grenades": 3, "munitions": 1},
    "tireur_delite": {"perforant": 2, "faufile": 1, "antenne": 1},
    "punk_anarchiste": {"radar": 4, "grenades": 3},
    "pilote_jet": {"fantome": 2, "holo": 1},
    "gladiateur": {"survie": 2},
    "cow_boy_cyber": {"or": 20, "holo": 1, "munitions": 1},
    "colosse_dacier": {"bouclier": 3, "roquettes": 2},
    "cyber_ninja": {"fantome": 4, "faufile": 1, "drone": 1},
    "fantome": {"ralenti": 4, "antenne": 1},
    "samourai_neon": {"sprint": 6, "holo": 1},
    "chevalier_toxique": {"survie": 3, "grenades": 3, "roquettes": 2},
    "commandant_dore": {"bouclier": 2, "or": 30, "munitions": 1},
    "titan_solaire": {"bouclier": 3, "survie": 3, "roquettes": 2, "munitions": 1},
    "seigneur_du_vide": {"fantome": 6, "ralenti": 4, "drone": 1},
    "eclaireur_bronze": {"radar": 3, "faufile": 1, "antenne": 1},
    "eclaireuse": {"sprint": 3, "faufile": 1, "grenades": 3},
    "amazone_des_neiges": {"ralenti": 3, "munitions": 1},
    "pilote_rose": {"fantome": 2, "faufile": 1, "holo": 1},
    "chasseresse_verte": {"perforant": 2, "munitions": 1},
    "alchimiste": {"or": 20, "faufile": 1, "holo": 1},
    "valkyrie": {"fantome": 5},
    "ninja_violette": {"sprint": 6, "faufile": 1, "holo": 1},
    "cyber_chat": {"radar": 6, "faufile": 1, "drone": 1},
    "reine_ecarlate": {"or": 30, "ralenti": 4},
    "deesse_solaire": {"bouclier": 3, "fantome": 5, "drone": 1},
}


# ================================================================ POUVOIRS DES PERSONNAGES
# Chaque personnage (skin) a ses pouvoirs. Tout est regroupé ici ; le reste du jeu n'appelle que quelques fonctions.
ACTIONS_ACTIVES = ("fantome", "sprint", "radar", "ralenti", "grenades", "roquettes")
LIB_ACTION = {"fantome": "PHASE", "sprint": "TURBO", "radar": "RADAR", "ralenti": "TEMPS", "grenades": "GRENADE", "roquettes": "ROQUETTE"}
COUL_ACTION = {"fantome": (120, 255, 230), "sprint": (255, 230, 60), "radar": (255, 200, 60), "ralenti": (110, 170, 255),
               "grenades": (255, 150, 50), "roquettes": (255, 80, 70)}
GRENADE_RAYON, GRENADE_DEGATS_BOSS = 150, 5.0            # dégâts au boss = 5 tirs
ROQUETTE_RAYON, ROQUETTE_DEGATS_BOSS = 130, 30.0         # dégâts au boss = 3 rafales de 10 tirs
POUV = {}
_voile_ralenti = None


def _init_pouvoirs():
    """Prépare les pouvoirs du personnage équipé au début de chaque niveau."""
    cfg = POUVOIRS_SKINS.get(_skin_courant or "", {}) if (IS_WEB and not DEVIL["actif"]) else {}
    slots = [a for a in ACTIONS_ACTIVES if a in cfg][:3]
    POUV.clear()
    POUV.update(cfg=cfg, slots=slots, boss_boucliers=cfg.get("bouclier", 0), survie=cfg.get("survie", 0),
                t_phase=0, t_sprint=0, t_radar=0, t_ralenti=0, utilise=set(), gren=cfg.get("grenades", 0),
                roq=cfg.get("roquettes", 0), cd=0, objets=[], explos=[], contre_mur=False, coince=0,
                sure=(joueur_x, joueur_y), ally_ang=0.0, ally=None, ally_cd=30, erreur=False)


def _cfg():
    return POUV.get("cfg") or {}


def _perfo():
    return STATS["perfo"] + _cfg().get("perforant", 0)


def _cadence():
    c = STATS["cadence"]
    return max(3.0, c / 1.2) if _cfg().get("munitions") else c        # munitions : intervalle de tir divisé par 1,2 (tir 20 % plus rapide)


def _hack():
    return STATS["hack"] * (1.5 if _cfg().get("holo") else 1.0)


def _facteur_vitesse():
    f = 1.0
    if POUV.get("t_sprint", 0) > 0:
        f *= 1.8
    if _cfg().get("faufile") and POUV.get("contre_mur"):
        f *= 1.2
    return f


def _facteur_ennemi(x, y):
    f = 0.45 if POUV.get("t_ralenti", 0) > 0 else 1.0
    if _cfg().get("antenne") and math.hypot(x - joueur_x, y - joueur_y) < 260:
        f *= 0.75
    return f


def _facteur_boule():
    return 0.5 if POUV.get("t_ralenti", 0) > 0 else 1.0


def _esquive_boule(boule):
    """Faufilé : collé à un mur, une boule de feu du boss sur deux rate le joueur."""
    if not (_cfg().get("faufile") and POUV.get("contre_mur")):
        return False
    if len(boule) < 5:
        boule.append(random.random() < 0.5)
    return bool(boule[4])


def _collision_reelle(x, y):
    demi = int(TAILLE_PERSO * (0.35 if _cfg().get("faufile") else 0.5))       # Faufilé : corps 30 % plus fin
    gauche, droite, haut, bas = x - demi, x + demi, y - demi, y + demi
    for cx, cy in [(gauche, haut), (droite, haut), (gauche, bas), (droite, bas)]:
        case_x, case_y = int(cx // TAILLE_CASE), int(cy // TAILLE_CASE)
        if not (0 <= case_x < len(CARTE[0]) and 0 <= case_y < len(CARTE)):
            return True
        if CARTE[case_y][case_x] == 1:
            return True
        if CARTE[case_y][case_x] == 3 and not hack_reussi:
            return True
    return False


def check_collision_murs(x, y):
    if POUV.get("t_phase", 0) > 0:
        for cx, cy in ((x - 4, y - 4), (x + 4, y + 4)):         # en phase : seuls les bords de la carte arrêtent le joueur
            if not (0 <= int(cx // TAILLE_CASE) < len(CARTE[0]) and 0 <= int(cy // TAILLE_CASE) < len(CARTE)):
                return True
        return False
    return _collision_reelle(x, y)


# ---------------------------------------------------------------- cibles, explosions
def _cible_proche(portee, boss_prioritaire=False):
    if boss_prioritaire and boss_actif and not boss_vaincu and math.hypot(boss_x - joueur_x, boss_y - joueur_y) < portee:
        return (boss_x, boss_y)
    meilleur, d_min = None, portee
    for ex in liste_ennemis:
        d = math.hypot(ex[0] - joueur_x, ex[1] - joueur_y)
        if d < d_min:
            meilleur, d_min = (ex[0], ex[1]), d
    if boss_actif and not boss_vaincu:
        d = math.hypot(boss_x - joueur_x, boss_y - joueur_y)
        if d < d_min:
            meilleur = (boss_x, boss_y)
    return meilleur


def _exploser(x, y, rayon, degats_boss, couleur, fort):
    """Vraie explosion : détruit tous les drones dans le rayon et blesse le boss."""
    global boss_vie, boss_vaincu
    for ex in liste_ennemis[:]:
        if math.hypot(ex[0] - x, ex[1] - y) <= rayon:
            liste_ennemis.remove(ex)
            MISSION["drones"] += 1
            creer_explosion(ex[0], ex[1], ROUGE_ALERTE, 22, 7.0, 0.0)
    if boss_actif and not boss_vaincu and math.hypot(boss_x - x, boss_y - y) <= rayon + RAYON_CORPS_BOSS:
        boss_vie = round(boss_vie - degats_boss * STATS["degats"], 1)
        creer_etincelles(boss_x, boss_y, ORANGE_MEC, 12)
        if boss_vie <= 0:
            boss_vie = 0
            boss_vaincu = True
            if SON_ACTIF:
                son_victoire.play()
    creer_explosion(x, y, couleur, 44 if fort else 32, 10.0, 11.0 if fort else 8.0)
    POUV["explos"].append({"x": x, "y": y, "r": rayon, "n": 24, "n0": 24, "c": couleur})
    if SON_ACTIF:
        son_explosion.play()


def _lancer_grenade():
    cible = _cible_proche(430)
    if cible:
        vx, vy = cible[0] - joueur_x, cible[1] - joueur_y
    else:
        vx, vy = angle_visée_x * 220, angle_visée_y * 220
    d = math.hypot(vx, vy) or 1.0
    d_lancer = min(d, 360.0)
    n = 36
    POUV["objets"].append({"t": "gren", "x": joueur_x, "y": joueur_y, "vx": vx / d * d_lancer / n, "vy": vy / d * d_lancer / n, "n": n, "n0": n})


def _lancer_roquette():
    cible = _cible_proche(950, True)
    if cible:
        vx, vy = cible[0] - joueur_x, cible[1] - joueur_y
    else:
        vx, vy = angle_visée_x, angle_visée_y
    d = math.hypot(vx, vy) or 1.0
    POUV["objets"].append({"t": "roq", "x": joueur_x, "y": joueur_y, "vx": vx / d * 12.0, "vy": vy / d * 12.0, "n": 110, "n0": 110})
    creer_etincelles(joueur_x, joueur_y, ORANGE_MEC, 8)


def _activer_pouvoir(action):
    if partie_perdue or partie_gagnee or en_pause or not POUV.get("cfg"):
        return False
    cfg = _cfg()
    if action in ("fantome", "sprint", "radar", "ralenti"):
        if action in POUV["utilise"] or action not in cfg:
            return False
        POUV["utilise"].add(action)
        POUV["t_" + {"fantome": "phase", "sprint": "sprint", "radar": "radar", "ralenti": "ralenti"}[action]] = int(cfg[action] * 60)
        creer_explosion(joueur_x, joueur_y, COUL_ACTION[action], 16, 5.0, 2.0)
        return True
    if POUV["cd"] > 0:
        return False
    if action == "grenades" and POUV["gren"] > 0:
        POUV["gren"] -= 1
        POUV["cd"] = 30
        _lancer_grenade()
        return True
    if action == "roquettes" and POUV["roq"] > 0:
        POUV["roq"] -= 1
        POUV["cd"] = 30
        _lancer_roquette()
        return True
    return False


# ---------------------------------------------------------------- mise à jour (une fois par pas de logique)
def _maj_objets():
    for o in POUV["objets"][:]:
        o["n"] -= 1
        nx, ny = o["x"] + o["vx"], o["y"] + o["vy"]
        cx, cy = int(nx // TAILLE_CASE), int(ny // TAILLE_CASE)
        mur = not (0 <= cx < len(CARTE[0]) and 0 <= cy < len(CARTE)) or CARTE[cy][cx] == 1
        if o["t"] == "gren":
            if mur:
                o["n"] = 0                       # la grenade s'arrête contre le mur et explose
            else:
                o["x"], o["y"] = nx, ny
            if o["n"] <= 0:
                POUV["objets"].remove(o)
                _exploser(o["x"], o["y"], GRENADE_RAYON, GRENADE_DEGATS_BOSS, ORANGE_MEC, False)
        else:
            if not mur:
                o["x"], o["y"] = nx, ny
            touche = mur or o["n"] <= 0
            if not touche:
                for ex in liste_ennemis:
                    if math.hypot(ex[0] - o["x"], ex[1] - o["y"]) < 34:
                        touche = True
                        break
            if not touche and boss_actif and not boss_vaincu and math.hypot(boss_x - o["x"], boss_y - o["y"]) < RAYON_CORPS_BOSS:
                touche = True
            if QUALITE["niveau"] >= 1 and not touche:
                creer_propulsion(o["x"], o["y"], -o["vx"] * 0.4, -o["vy"] * 0.4, ORANGE_MEC)
            if touche:
                POUV["objets"].remove(o)
                _exploser(o["x"], o["y"], ROQUETTE_RAYON, ROQUETTE_DEGATS_BOSS, ROUGE_ALERTE, True)


def _maj_ami():
    if not _cfg().get("drone"):
        return
    POUV["ally_ang"] += 0.05
    ax = joueur_x + math.cos(POUV["ally_ang"]) * 52
    ay = joueur_y + math.sin(POUV["ally_ang"]) * 34 - 34
    POUV["ally"] = (ax, ay)
    POUV["ally_cd"] -= 1
    if POUV["ally_cd"] <= 0:
        meilleur, d_min = None, 420.0
        for ex in liste_ennemis:
            d = math.hypot(ex[0] - ax, ex[1] - ay)
            if d < d_min:
                meilleur, d_min = (ex[0], ex[1]), d
        if boss_actif and not boss_vaincu and math.hypot(boss_x - ax, boss_y - ay) < d_min:
            meilleur = (boss_x, boss_y)
        if meilleur:
            dx_, dy_ = meilleur[0] - ax, meilleur[1] - ay
            d = math.hypot(dx_, dy_) or 1.0
            balles.append([ax, ay, dx_ / d * 13, dy_ / d * 13, 0])
            POUV["ally_cd"] = 28
        else:
            POUV["ally_cd"] = 10


def _maj_pouvoirs():
    """Appelée à chaque pas de logique (1/60 s) pendant une partie."""
    global joueur_x, joueur_y
    if not POUV or not POUV.get("cfg") or POUV.get("erreur"):
        return
    try:
        for cle in ("t_sprint", "t_radar", "t_ralenti", "cd"):
            if POUV[cle] > 0:
                POUV[cle] -= 1
        # phase : si elle se termine alors que le joueur est dans un mur, elle se prolonge jusqu'à ce qu'il en sorte
        if POUV["t_phase"] > 0:
            POUV["t_phase"] -= 1
            if POUV["t_phase"] == 0 and _collision_reelle(joueur_x, joueur_y):
                POUV["t_phase"] = 1
                POUV["coince"] += 1
                if POUV["coince"] > 240:
                    joueur_x, joueur_y = POUV["sure"]
                    POUV["t_phase"], POUV["coince"] = 0, 0
        if not _collision_reelle(joueur_x, joueur_y):
            POUV["sure"] = (joueur_x, joueur_y)
            POUV["coince"] = 0
        if _cfg().get("faufile") and POUV["t_phase"] <= 0:
            POUV["contre_mur"] = any(_collision_reelle(joueur_x + a, joueur_y + b) for a, b in ((6, 0), (-6, 0), (0, 6), (0, -6)))
        else:
            POUV["contre_mur"] = False
        _maj_objets()
        _maj_ami()
    except Exception as e:
        POUV["erreur"] = True
        print("Pouvoirs désactivés (erreur) :", e)


# ---------------------------------------------------------------- dessin
def _boutons_pouvoirs():
    R = 44
    pos = [(BTN_TIR_X - BTN_TIR_RAYON - 62, BTN_TIR_Y + 8), (BTN_TIR_X - 30, BTN_TIR_Y - BTN_TIR_RAYON - 60),
           (BTN_TIR_X - BTN_TIR_RAYON - 150, BTN_TIR_Y + 12)]
    res = []
    for i, a in enumerate(POUV.get("slots", [])[:3]):
        x = min(max(pos[i][0], R + 4), LARGEUR - R - 4)
        y = min(max(pos[i][1], R + 4), HAUTEUR - R - 4)
        res.append((a, int(x), int(y), R))
    return res


def _toucher_pouvoir(x, y):
    """Vrai si le doigt est sur un bouton de pouvoir (et déclenche le pouvoir)."""
    if etat_actuel != ETAT_JEU or not POUV.get("slots"):
        return False
    for a, bx, by, R in _boutons_pouvoirs():
        if math.hypot(x - bx, y - by) <= R + 14:
            _activer_pouvoir(a)
            return True
    return False


def _fleche_bord(sx, sy, couleur):
    cx, cy = LARGEUR / 2, HAUTEUR / 2
    dx_, dy_ = sx - cx, sy - cy
    if dx_ == 0 and dy_ == 0:
        return
    t = min((cx - 40) / max(abs(dx_), 1e-6), (cy - 40) / max(abs(dy_), 1e-6))
    px, py = cx + dx_ * t, cy + dy_ * t
    a = math.atan2(dy_, dx_)
    pts = [(px + math.cos(a) * 16, py + math.sin(a) * 16),
           (px + math.cos(a + 2.5) * 13, py + math.sin(a + 2.5) * 13),
           (px + math.cos(a - 2.5) * 13, py + math.sin(a - 2.5) * 13)]
    DRAW.polygon(ecran, couleur, pts)
    DRAW.polygon(ecran, BLANC_NEON, pts, 2)


def _dessiner_pouvoirs_monde(ox, oy, t_ms):
    """Effets dessinés dans le monde (sous les particules)."""
    if not POUV.get("cfg"):
        return
    jx, jy = int(joueur_x + ox), int(joueur_y + oy)
    if POUV["t_phase"] > 0:
        dessiner_halo(jx, jy, 70, COUL_ACTION["fantome"], 0.7)
        DRAW.circle(ecran, COUL_ACTION["fantome"], (jx, jy), 34 + int(3 * math.sin(t_ms / 90.0)), 2)
    if POUV["t_sprint"] > 0:
        dessiner_halo(jx, jy, 64, COUL_ACTION["sprint"], 0.5)
    if _cfg().get("antenne"):
        rr = 250 + int(10 * math.sin(t_ms / 300.0))
        DRAW.circle(ecran, (30, 110, 140), (jx, jy), rr, 1)
    if POUV["t_radar"] > 0:
        pulse = 4 * math.sin(t_ms / 110.0)
        for ex in liste_ennemis:
            DRAW.circle(ecran, COUL_ACTION["radar"], (int(ex[0] + ox), int(ex[1] + oy)), int(34 + pulse), 2)
        if boss_actif and not boss_vaincu:
            DRAW.circle(ecran, COUL_ACTION["radar"], (int(boss_x + ox), int(boss_y + oy)), int(RAYON_CORPS_BOSS + 14 + pulse), 3)
    for o in POUV["objets"]:
        sx, sy = int(o["x"] + ox), int(o["y"] + oy)
        if o["t"] == "gren":
            prog = 1.0 - o["n"] / float(o["n0"])
            haut = math.sin(math.pi * prog) * 46
            DRAW.circle(ecran, (20, 20, 28), (sx, sy + 4), 8)
            DRAW.circle(ecran, (90, 110, 60), (sx, int(sy - haut)), 9)
            DRAW.circle(ecran, (200, 220, 140), (sx - 2, int(sy - haut - 2)), 3)
        else:
            dessiner_halo(sx, sy, 40, ORANGE_MEC, 0.9)
            DRAW.line(ecran, ORANGE_MEC, (int(sx - o["vx"] * 2.4), int(sy - o["vy"] * 2.4)), (sx, sy), 7)
            DRAW.circle(ecran, BLANC_NEON, (sx, sy), 6)
    for e in POUV["explos"][:]:
        e["n"] -= 1
        if e["n"] <= 0:
            POUV["explos"].remove(e)
            continue
        prog = 1.0 - e["n"] / float(e["n0"])
        r = int(e["r"] * (0.25 + 0.75 * prog))
        ex_, ey_ = int(e["x"] + ox), int(e["y"] + oy)
        dessiner_halo(ex_, ey_, int(e["r"] * (1.1 - 0.4 * prog)), e["c"], 0.9 * (1.0 - prog))
        DRAW.circle(ecran, e["c"], (ex_, ey_), r, max(2, int(7 * (1.0 - prog))))
    if POUV.get("ally"):
        ax, ay = int(POUV["ally"][0] + ox), int(POUV["ally"][1] + oy)
        dessiner_halo(ax, ay, 26, CYAN_NEON, 0.6)
        for dx_, dy_ in ((-9, -9), (9, -9), (-9, 9), (9, 9)):
            DRAW.circle(ecran, (150, 200, 230), (ax + dx_, ay + dy_), 5)
        DRAW.circle(ecran, (30, 40, 58), (ax, ay), 7)
        DRAW.circle(ecran, CYAN_NEON, (ax + 2, ay), 3)


def _dessiner_pouvoirs_hud(ox, oy, t_ms):
    """Boutons, alertes et indications à l'écran."""
    global _voile_ralenti
    if not POUV.get("cfg"):
        return
    if POUV["t_ralenti"] > 0:
        if _voile_ralenti is None:
            _voile_ralenti = pygame.Surface((LARGEUR, HAUTEUR), pygame.SRCALPHA)
            _voile_ralenti.fill((60, 120, 220, 34))
        ecran.blit(_voile_ralenti, (0, 0))
    # flèches vers les drones hors de l'écran (radar : tous ; écran holographique : ceux qui approchent)
    if POUV["t_radar"] > 0 or _cfg().get("holo"):
        for ex in liste_ennemis:
            sx, sy = ex[0] + ox, ex[1] + oy
            hors = sx < 24 or sx > LARGEUR - 24 or sy < 24 or sy > HAUTEUR - 24
            if hors and (POUV["t_radar"] > 0 or math.hypot(ex[0] - joueur_x, ex[1] - joueur_y) < 1100):
                _fleche_bord(sx, sy, ROUGE_ALERTE)
        if POUV["t_radar"] > 0 and boss_actif and not boss_vaincu:
            sx, sy = boss_x + ox, boss_y + oy
            if sx < 24 or sx > LARGEUR - 24 or sy < 24 or sy > HAUTEUR - 24:
                _fleche_bord(sx, sy, VIOLET_CYBER)
    # boutons
    for a, bx, by, R in _boutons_pouvoirs():
        col = COUL_ACTION[a]
        if a in ("grenades", "roquettes"):
            n = POUV["gren"] if a == "grenades" else POUV["roq"]
            pret, actif, bas = n > 0, False, "x%d" % n
        else:
            cle = {"fantome": "t_phase", "sprint": "t_sprint", "radar": "t_radar", "ralenti": "t_ralenti"}[a]
            actif = POUV[cle] > 0
            pret = (a not in POUV["utilise"])
            bas = ("%ds" % (POUV[cle] // 60 + 1)) if actif else ("PRÊT" if pret else "UTILISÉ")
        c_ring = col if (pret or actif) else (90, 90, 100)
        dessiner_halo(bx, by, int(R * 1.5), c_ring, 0.55 if actif else (0.35 if pret else 0.1))
        DRAW.circle(ecran, (8, 10, 24), (bx, by), R)
        if actif:
            DRAW.circle(ecran, eclaircir(col, 0.1), (bx, by), R - 5)
        DRAW.circle(ecran, c_ring, (bx, by), R, 4)
        t1 = rendu_texte(police_petite, LIB_ACTION[a], True, NOIR_ESPACE if actif else c_ring)
        t2 = rendu_texte(police_petite, bas, True, NOIR_ESPACE if actif else BLANC_NEON)
        ecran.blit(t1, (bx - t1.get_width() // 2, by - t1.get_height() - 1))
        ecran.blit(t2, (bx - t2.get_width() // 2, by + 2))
    # indications des protections et talents
    lignes = []
    if POUV["boss_boucliers"] > 0:
        lignes.append(("BOUCLIER BOSS x%d" % POUV["boss_boucliers"], (120, 220, 255)))
    if POUV["survie"] > 0:
        lignes.append(("PEAU D'ACIER x%d" % POUV["survie"], (255, 120, 140)))
    if POUV["contre_mur"]:
        lignes.append(("COLLÉ AU MUR  +20 %", (120, 255, 170)))
    if POUV["t_phase"] <= 0 and POUV.get("coince", 0) > 0:
        lignes.append(("SORS DU MUR !", ROUGE_ALERTE))
    for i, (txt, c) in enumerate(lignes):
        ecran.blit(rendu_texte(police_petite, txt, True, c), (40, 92 + i * 24))

# ===== POUVOIRS FIN


# ===== ENTREES DEBUT
# ================================================================ CLAVIER, SOURIS ET MANETTE
# La page web (controls.js) lit le clavier et les manettes et publie leur état ; le jeu le lit ici une fois par image.
# Dans les menus : un curseur (stick gauche = libre, croix directionnelle / flèches = saute de bouton en bouton),
# Croix (A) / Entrée = choisir, Rond (B) / Échap = retour. En partie : déplacement, visée, tir et pouvoirs.
import json as _json_in

IN = {"d": None, "n0": None, "a0": None, "src": "", "edges": [0] * 9, "post": [], "up": None,
      "souris_x": 0.0, "souris_y": 0.0, "souris_ok": False, "souris_tir": False, "cle": None}
CUR = {"x": 0.0, "y": 0.0, "vis": False}
_IN_ZERO = (0, 0)


def _modal_actif():
    """Vrai quand une fenêtre web (SKINS, classement...) est ouverte par-dessus le jeu."""
    if not IS_WEB:
        return False
    try:
        return bool(getattr(_pfs.window, "flexModal", False))
    except Exception:
        return False


def _in_lire():
    if not IS_WEB:
        return None
    try:
        txt = str(_pfs.window.flexInJ)
        if not txt or txt[0] != "{":
            return None
        return _json_in.loads(txt)
    except Exception:
        return None


def _in_contexte():
    """'jeu' en partie, 'ui' sur un écran de menu / pause / fin de partie, '' sinon."""
    if IN["d"] is None or _modal_actif() or TRANS["actif"] or saisie_pseudo_active:
        return ""
    if etat_actuel == ETAT_JEU:
        return "ui" if (en_pause or partie_gagnee or partie_perdue) else "jeu"
    if etat_actuel == ETAT_PARC:
        return "jeu"
    return "ui"


def _in_rects(*noms):
    sortie = []
    for n in noms:
        r = globals().get(n)
        if r is not None:
            sortie.append((r.centerx, r.centery))
    return sortie


def _in_cibles():
    """Boutons que la croix directionnelle peut atteindre sur l'écran actuel (centre de chaque bouton)."""
    e = etat_actuel
    if e == ETAT_JEU:
        if partie_perdue:
            return _in_rects("rect_bouton_rejouer_defaite", "rect_bouton_quitter_defaite")
        if partie_gagnee:
            return _in_rects("rect_bouton_rejouer", "rect_bouton_suivant")
        if en_pause:
            return _in_rects("rect_pause_continuer", "rect_pause_rejouer", "rect_pause_params", "rect_pause_quitter")
        return []
    if e == ETAT_MENU:
        noms = ["rect_bouton_jouer", "rect_bouton_aide", "rect_bouton_boutique", "rect_icone_profil", "rect_icone_infos", "rect_icone_params", "rect_icone_defis", "rect_icone_devil"]
        if IS_WEB:
            noms += ["rect_bouton_multi", "rect_icone_classement", "rect_icone_skins"]
            if _inst_visible:
                noms.append("rect_icone_install")
        return _in_rects(*noms)
    if e == ETAT_NIVEAUX:
        pts = _in_rects("rect_retour_niveaux")
        for idx in range(0, _niv_max() + 1):
            x = NIVEAU_MARGE_GAUCHE + idx * NIVEAU_NODE_ESPACEMENT + defilement_niveaux
            if -NIVEAU_NODE_RAYON <= x <= LARGEUR + NIVEAU_NODE_RAYON:
                pts.append((x, HAUTEUR // 2 + int(60 * math.sin(idx * 0.9))))
        return pts
    if e == ETAT_AIDE:
        return _in_rects("rect_bouton_retour")
    if e == ETAT_INFOS:
        return _in_rects("rect_retour_infos")
    if e == ETAT_PROFIL:
        return _in_rects("rect_champ_pseudo", "rect_fleche_gauche", "rect_fleche_droite", "rect_recharger_photo", "rect_sauvegarder_profil", "rect_retour_profil")
    if e == ETAT_PARAMS:
        return [(z[0].centerx, z[0].centery) for z in PAR["zones"] if 0 <= z[0].centery <= HAUTEUR]
    if e == ETAT_BOUTIQUE:
        return [(z[0].centerx, z[0].centery) for z in BQ["zones"] if 0 <= z[0].centery <= HAUTEUR]
    if e == ETAT_DEFIS:
        return _in_rects("rect_retour_infos")
    return []


def _in_vers(cibles, x, y, dx, dy):
    """Bouton le plus proche dans la direction demandée (même principe que dans les fenêtres web)."""
    meilleur, score = None, 1e12
    for cx, cy in cibles:
        ddx, ddy = cx - x, cy - y
        if abs(ddx) < 3 and abs(ddy) < 3:
            continue
        prim = ddx * dx + ddy * dy
        if prim < 4:
            continue
        perp = abs(ddx * dy - ddy * dx)
        s = prim + 2.2 * perp
        if s < score:
            meilleur, score = (cx, cy), s
    return meilleur


def _in_retour_pos():
    """Position du bouton « retour » de l'écran actuel (None s'il n'y en a pas)."""
    e = etat_actuel
    if e == ETAT_JEU:
        if partie_perdue or partie_gagnee:
            return None
        return (rect_pause_continuer.centerx, rect_pause_continuer.centery) if en_pause else None
    if e == ETAT_NIVEAUX:
        return rect_retour_niveaux.center
    if e == ETAT_AIDE:
        return rect_bouton_retour.center
    if e == ETAT_INFOS:
        return rect_retour_infos.center
    if e == ETAT_PROFIL:
        return rect_retour_profil.center
    if e == ETAT_BOUTIQUE:
        for z in BQ["zones"]:
            if len(z) > 1 and z[1] == "retour":
                return z[0].center
        return rect_bouton_retour.center
    if e == ETAT_PARAMS:
        for z in PAR["zones"]:
            if "retour" in [str(v) for v in z[1:3]]:
                return z[0].center
        return rect_bouton_retour.center
    if e == ETAT_EDITEUR:
        return rect_bouton_retour.center
    if e == ETAT_DEFIS:
        return rect_retour_infos.center
    return None


def _in_pos_brute(x, y):
    """Position à donner à un clic simulé pour que le jeu la lise comme (x, y)."""
    sonde = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (100.0, 100.0), "button": 1})
    k = pos_ev(sonde)[0] / 100.0 or 1.0
    return (x / k, y / k)


def _in_clic(x, y):
    """Simule un clic (appui maintenant, relâchement à l'image suivante)."""
    p = _in_pos_brute(x, y)
    IN["post"].append(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": p, "button": 1, "synth": True}))
    IN["up"] = p


def _in_cle_contexte():
    return (etat_actuel, bool(en_pause), bool(partie_gagnee), bool(partie_perdue), TRANS["actif"] and 1 or 0)


def _in_frame():
    """À appeler une fois par image, avant la lecture des événements."""
    global defilement_niveaux
    d = _in_lire()
    IN["d"] = d
    IN["post"] = []
    if IN["up"] is not None:                                   # relâchement du clic simulé de l'image précédente
        IN["post"].append(pygame.event.Event(pygame.MOUSEBUTTONUP, {"pos": IN["up"], "button": 1, "synth": True}))
        IN["up"] = None
    ed = [0] * 9
    if d:
        n = d.get("n") or [0] * 9
        if IN["n0"] is None:
            IN["n0"] = list(n)
            IN["a0"] = d.get("a", 0)
        for i in range(9):
            ed[i] = max(0, n[i] - IN["n0"][i])
        IN["n0"] = list(n)
        if d.get("a", 0) != IN["a0"]:                          # une touche ou la manette vient de servir
            IN["a0"] = d.get("a", 0)
            if d.get("s"):
                IN["src"] = d["s"]
    IN["edges"] = ed
    ctx = _in_contexte()
    CUR["vis"] = ctx == "ui" and IN["src"] in ("pad", "key")
    if not d or ctx == "":
        return
    ok, bk, ps, p1, p2, hu, hd, hl, hr = ed
    if ctx == "jeu":
        if etat_actuel == ETAT_PARC:                              # parc / arène : pas de pause ni de pouvoirs
            return
        if ps or bk:
            basculer_pause()
        slots = POUV.get("slots") or []
        if p1 and len(slots) >= 1:
            _activer_pouvoir(slots[0])
        if p2 and len(slots) >= 2:
            _activer_pouvoir(slots[1])
        return
    # ----- écrans de menu, pause, fin de partie : curseur -----
    cles = _in_cle_contexte()
    cibles = _in_cibles()
    if IN["src"] not in ("pad", "key"):
        return
    if IN["cle"] != cles:                                      # nouvel écran (ou premier appui) : le curseur se pose sur un bouton
        IN["cle"] = cles
        if cibles:
            pt = cibles[-1] if (etat_actuel == ETAT_JEU and partie_gagnee) else cibles[0]
            CUR["x"], CUR["y"] = float(pt[0]), float(pt[1])
        elif CUR["x"] == 0.0 and CUR["y"] == 0.0:
            CUR["x"], CUR["y"] = LARGEUR / 2.0, HAUTEUR / 2.0
    sx, sy = d.get("sx", 0) or 0, d.get("sy", 0) or 0
    if sx or sy:                                               # stick gauche : curseur libre
        CUR["x"] = min(max(CUR["x"] + sx * 17.0, 0.0), float(LARGEUR))
        CUR["y"] = min(max(CUR["y"] + sy * 17.0, 0.0), float(HAUTEUR))
    for nb, (ddx, ddy) in ((hu, (0, -1)), (hd, (0, 1)), (hl, (-1, 0)), (hr, (1, 0))):
        for _ in range(min(nb, 3)):                            # croix directionnelle / flèches : bouton suivant
            cible = _in_vers(cibles, CUR["x"], CUR["y"], ddx, ddy) if cibles else None
            if cible is None and etat_actuel == ETAT_NIVEAUX and ddx != 0:
                defilement_niveaux = min(0, defilement_niveaux - ddx * NIVEAU_NODE_ESPACEMENT)   # niveaux : fait défiler la carte
                cibles = _in_cibles()
                continue
            if cible is None:
                cible = (min(max(CUR["x"] + ddx * 90.0, 0.0), float(LARGEUR)), min(max(CUR["y"] + ddy * 90.0, 0.0), float(HAUTEUR)))
            CUR["x"], CUR["y"] = float(cible[0]), float(cible[1])
            if etat_actuel == ETAT_NIVEAUX and (CUR["x"] > LARGEUR - 140 or CUR["x"] < 140) and ddx != 0:
                decal = LARGEUR / 2.0 - CUR["x"]
                defilement_niveaux = min(0, defilement_niveaux + decal)
                CUR["x"] = LARGEUR / 2.0
    if etat_actuel == ETAT_AIDE and sy:                       # écran d'aide : le stick fait défiler le texte
        AIDE["scroll"] -= sy * 14
    if etat_actuel == ETAT_DEFIS and sy:                      # écran des défis : idem
        DEF["scroll"] -= sy * 14
    if ok:
        _in_clic(CUR["x"], CUR["y"])
    if bk or ps:
        pos = _in_retour_pos()
        if pos is not None:
            _in_clic(pos[0], pos[1])


def _in_evenements():
    """Clics simulés à ajouter aux événements de cette image."""
    sortie = IN["post"]
    IN["post"] = []
    return sortie


def _in_deplacement():
    """Direction demandée au clavier / à la manette en partie : (x, y) entre -1 et 1, ou None."""
    d = IN["d"]
    if not d or _in_contexte() != "jeu":
        return None
    mx, my = d.get("mx", 0) or 0, d.get("my", 0) or 0
    n = math.hypot(mx, my)
    if n < 0.05:
        return None
    if n > 1.0:
        mx, my = mx / n, my / n
    return (mx, my)


def _in_visee():
    """Direction de visée choisie par le joueur (stick droit ou souris), ou None pour la visée automatique."""
    if _v3_actif():
        return _v3_viser()
    d = IN["d"]
    if not d or _in_contexte() != "jeu":
        return None
    ax, ay = d.get("ax", 0) or 0, d.get("ay", 0) or 0
    n = math.hypot(ax, ay)
    if n > 0.05:
        return (ax / n, ay / n)
    if IN["src"] == "mouse" and IN["souris_ok"]:
        px = joueur_x - CAM["x"] + LARGEUR // 2
        py = joueur_y - CAM["y"] + HAUTEUR // 2
        vx, vy = IN["souris_x"] - px, IN["souris_y"] - py
        n = math.hypot(vx, vy)
        if n > 14:
            return (vx / n, vy / n)
    return None


def _in_tir():
    """Vrai tant que le joueur tire (R2, Espace ou clic de souris)."""
    d = IN["d"]
    if _in_contexte() != "jeu":
        return False
    return bool((d and d.get("f")) or IN["souris_tir"])


def _in_masquer_tactile():
    """Cache les boutons tactiles quand on joue au clavier, à la souris ou à la manette."""
    return IN["src"] in ("pad", "key", "mouse") and IN["d"] is not None


def _dessiner_curseur():
    """Curseur de menu pour le clavier et la manette."""
    if not CUR["vis"]:
        return
    x, y = int(CUR["x"]), int(CUR["y"])
    dessiner_halo(x, y, 46, (255, 214, 70), 0.55)
    DRAW.circle(ecran, (255, 214, 70), (x, y), 24, 4)
    DRAW.circle(ecran, (255, 255, 255), (x, y), 5)
# ===== ENTREES FIN


GRILLES_EDITEUR = (0, 32, 64, 96)      # 0 = pas de grille
ED = {"mode": "deplacer", "grille": 0, "drag": False, "id": None, "cible": None, "bouton": None, "bouge": False,
      "x0": 0.0, "y0": 0.0, "x": 0.0, "y": 0.0, "orig": None, "selection": None, "zones": []}


def centre_commande(nom):
    """(x, y, rayon) actuels d'une commande : 'joy' ou 'tir'."""
    if nom == "joy":
        return JOY_CENTRE_X, JOY_CENTRE_Y, JOY_RAYON_SOCLE
    return BTN_TIR_X, BTN_TIR_Y, BTN_TIR_RAYON


def _en_conflit(nom):
    """Vrai si la commande chevauche l'autre commande, le bouton pause ou le radar."""
    cx, cy, r = centre_commande(nom)
    ax, ay, ar = centre_commande("tir" if nom == "joy" else "joy")
    for zx, zy, zr in ((ax, ay, ar), (BTN_PAUSE_X, BTN_PAUSE_Y, BTN_PAUSE_RAYON), (RADAR_CENTRE_X, RADAR_CENTRE_Y, RADAR_RAYON)):
        if math.hypot(cx - zx, cy - zy) < r + zr - 4:
            return True
    return False


def _magnetiser(v):
    g = GRILLES_EDITEUR[ED["grille"]]
    return round(v / float(g)) * g if g else v


def _debut_toucher(identifiant, x, y):
    ED.update(drag=True, id=identifiant, x0=x, y0=y, x=x, y=y, bouge=False, cible=None, bouton=None, orig=None)
    for rect, action in ED["zones"]:                         # d'abord les boutons du panneau
        if rect.collidepoint(x, y):
            ED["bouton"] = (rect, action)
            return
    meilleure, dist_min = None, 10 ** 9                         # sinon : la commande touchée (la plus proche du doigt)
    for nom in ("tir", "joy"):
        cx, cy, r = centre_commande(nom)
        d = math.hypot(x - cx, y - cy)
        if d <= r + 30 and d < dist_min:
            meilleure, dist_min = nom, d
    if meilleure:
        cx, cy, _r = centre_commande(meilleure)
        ED["cible"], ED["selection"] = meilleure, meilleure
        ED["orig"] = (cx, cy, DISPO[meilleure]["s"])


def _mouvement_toucher(x, y):
    ED["x"], ED["y"] = x, y
    if math.hypot(x - ED["x0"], y - ED["y0"]) > 8:
        ED["bouge"] = True
    nom = ED["cible"]
    if not nom or not ED["bouge"]:
        return
    ox, oy, os_ = ED["orig"]
    if ED["mode"] == "deplacer":
        nx, ny = _magnetiser(ox + (x - ED["x0"])), _magnetiser(oy + (y - ED["y0"]))
        s = DISPO[nom]["s"]
    else:                                                       # redimensionner : plus le doigt s'éloigne du centre, plus c'est grand
        nx, ny = ox, oy
        d0, d = math.hypot(ED["x0"] - ox, ED["y0"] - oy), math.hypot(x - ox, y - oy)
        s = round((os_ + (d - d0) / 150.0) * 20) / 20.0
        s = max(ECHELLE_COMMANDE_MIN, min(ECHELLE_COMMANDE_MAX, s))
    rayon = int((85 if nom == "joy" else 65) * s)
    cx, cy = _borner_commande(nx, ny, rayon)
    DISPO[nom] = {"x": cx / float(LARGEUR), "y": cy / float(HAUTEUR), "s": s}
    appliquer_controles()


def _action_editeur(action):
    if action in ("deplacer", "taille"):
        ED["mode"] = action
    elif action == "grille":
        ED["grille"] = (ED["grille"] + 1) % len(GRILLES_EDITEUR)
    elif action == "inverser":                                  # miroir gauche/droite (mode gaucher)
        for nom in ("joy", "tir"):
            DISPO[nom]["x"] = 1.0 - DISPO[nom]["x"]
        appliquer_controles()
        sauvegarder_parametres()
    elif action == "reset":
        d = dispo_par_defaut()
        DISPO["joy"], DISPO["tir"] = d["joy"], d["tir"]
        appliquer_controles()
        sauvegarder_parametres()
    elif action == "retour":
        sauvegarder_parametres()
        lancer_transition(("etat", ETAT_PARAMS))


def _fin_toucher():
    ED["drag"], ED["id"] = False, None
    if ED["bouton"]:
        rect, action = ED["bouton"]
        if rect.collidepoint(ED["x"], ED["y"]) and not TRANS["actif"]:
            _action_editeur(action)
    elif ED["cible"] and ED["bouge"]:
        sauvegarder_parametres()


def gerer_editeur(event):
    """Événements tactiles de l'éditeur de commandes (doigt et souris ; le 2e événement d'un même toucher est ignoré)."""
    if etat_actuel == ETAT_EDITEUR and not TRANS["actif"]:
        if event.type == pygame.FINGERDOWN:
            _debut_toucher(event.finger_id, event.x * LARGEUR, event.y * HAUTEUR)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not ED["drag"]:
            p = pos_ev(event)
            _debut_toucher("souris", p[0], p[1])
        elif event.type == pygame.FINGERMOTION and ED["drag"] and event.finger_id == ED["id"]:
            _mouvement_toucher(event.x * LARGEUR, event.y * HAUTEUR)
        elif event.type == pygame.MOUSEMOTION and ED["drag"] and ED["id"] == "souris":
            p = pos_ev(event)
            _mouvement_toucher(p[0], p[1])
    if ED["drag"] and ((event.type == pygame.MOUSEBUTTONUP and ED["id"] == "souris") or
                       (event.type == pygame.FINGERUP and event.finger_id == ED["id"])):
        _fin_toucher()


def dessiner_editeur():
    # Aperçu : le sol du jeu, l'interface (pause, radar, chrono) et les vraies commandes, aux positions réelles
    T = TAILLE_CASE
    for j in range(HAUTEUR // T + 1):
        for i in range(LARGEUR // T + 1):
            mur = (i * 7 + j * 13) % 6 == 0 and 0 < i < LARGEUR // T
            ecran.blit(tuile_mur(COULEUR_MUR, 0) if mur else tuile_sol(COULEUR_MUR, (i + j) % 2, 0), (i * T, j * T))
    ecran.blit(obtenir_voile(LARGEUR, HAUTEUR, (4, 5, 14, 110)), (0, 0))
    g = GRILLES_EDITEUR[ED["grille"]]
    if g:
        for x in range(0, LARGEUR, g):
            DRAW.line(ecran, (40, 60, 95), (x, 0), (x, HAUTEUR), 1)
        for y in range(0, HAUTEUR, g):
            DRAW.line(ecran, (40, 60, 95), (0, y), (LARGEUR, y), 1)

    DRAW.circle(ecran, (6, 12, 20), (RADAR_CENTRE_X, RADAR_CENTRE_Y), RADAR_RAYON)
    DRAW.circle(ecran, BLEU_CYBER, (RADAR_CENTRE_X, RADAR_CENTRE_Y), RADAR_RAYON, 3)
    tr_ = rendu_texte(police_petite, "RADAR", True, BLEU_CYBER)
    ecran.blit(tr_, (RADAR_CENTRE_X - tr_.get_width() // 2, RADAR_CENTRE_Y + RADAR_RAYON + 6))
    DRAW.circle(ecran, (10, 10, 20), (BTN_PAUSE_X, BTN_PAUSE_Y), BTN_PAUSE_RAYON)
    DRAW.circle(ecran, BLEU_CYBER, (BTN_PAUSE_X, BTN_PAUSE_Y), BTN_PAUSE_RAYON, 3)
    DRAW.rect(ecran, BLEU_CYBER, (BTN_PAUSE_X - 9, BTN_PAUSE_Y - 10, 6, 20))
    DRAW.rect(ecran, BLEU_CYBER, (BTN_PAUSE_X + 3, BTN_PAUSE_Y - 10, 6, 20))
    chrono = pygame.Rect(LARGEUR // 2 - 130, 96, 260, 44)
    DRAW.rect(ecran, (8, 10, 20), chrono, border_radius=14)
    DRAW.rect(ecran, VERT_FLUO, chrono, 2, border_radius=14)
    tc_ = rendu_texte(police_bouton, "TEMPS : 125s", True, VERT_FLUO)
    ecran.blit(tc_, (chrono.centerx - tc_.get_width() // 2, chrono.centery - tc_.get_height() // 2))

    dessiner_commandes(JOY_CENTRE_X, JOY_CENTRE_Y, False)

    for nom in ("joy", "tir"):                                  # commande sélectionnée : cercle jaune + taille ; conflit : rouge
        cx, cy, r = centre_commande(nom)
        conflit = _en_conflit(nom)
        if ED["selection"] == nom or conflit:
            col = ROUGE_ALERTE if conflit else JAUNE_CYBER
            DRAW.circle(ecran, col, (cx, cy), r + 14, 3)
            texte = f"{int(DISPO[nom]['s'] * 100)} %" + ("  ·  chevauche l'interface" if conflit else "")
            tl = rendu_texte(police_petite, texte, True, col)
            ecran.blit(obtenir_voile(tl.get_width() + 16, 26, (5, 6, 16, 200)), (int(cx - tl.get_width() // 2 - 8), int(cy - r - 46)))
            ecran.blit(tl, (int(cx - tl.get_width() // 2), int(cy - r - 42)))

    ecran.blit(obtenir_voile(250, 392, (4, 5, 14, 205)), (8, 14))     # panneau de boutons (à gauche, comme sur PPSSPP)
    g_txt = "GRILLE : OFF" if not g else f"GRILLE : {g}"
    boutons = [("deplacer", "DÉPLACER", BLEU_CYBER, ED["mode"] == "deplacer"),
               ("taille", "REDIMENSIONNER", BLEU_CYBER, ED["mode"] == "taille"),
               ("grille", g_txt, VIOLET_CYBER, bool(g)),
               ("inverser", "INVERSER G/D", JAUNE_CYBER, False),
               ("reset", "RÉTABLIR", ROUGE_ALERTE, False),
               ("retour", "RETOUR", VERT_FLUO, False)]
    zones = []
    for k, (action, texte, couleur, actif) in enumerate(boutons):
        rect = pygame.Rect(24, 28 + k * 62, 220, 50)
        bouton_neon(rect, couleur, texte, police_petite, plein=actif)
        zones.append((rect, action))
    ED["zones"] = zones
    aide = "Touche une commande, puis glisse" if ED["mode"] == "deplacer" else "Touche une commande, puis glisse pour agrandir / réduire"
    ta = rendu_texte(police_petite, aide, True, (170, 180, 210))
    ecran.blit(obtenir_voile(ta.get_width() + 24, 30, (5, 6, 16, 190)), (LARGEUR // 2 - ta.get_width() // 2 - 12, HAUTEUR - 44))
    ecran.blit(ta, (LARGEUR // 2 - ta.get_width() // 2, HAUTEUR - 40))


# ==================== ÉCRANS DE FIN DE MISSION ====================
FIN = {"t0": 0, "etoiles": 0, "record": False, "conseil": ""}
DELAI_BOUTONS_FIN = 1100          # les boutons n'apparaissent (et ne réagissent) qu'après l'animation : pas d'appui accidentel
CONSEILS_DEFAITE = [
    "Reste en mouvement : les drones foncent tout droit sur toi.",
    "Maintiens TIR : le laser vise tout seul le drone le plus proche.",
    "Les potions jaunes ajoutent du temps au chrono.",
    "Le Boss lance des boules de feu : esquive-les, puis tire.",
    "Reste dans la zone violette jusqu'à 100% pour pirater le CORE.",
]
CONSEIL_BOUCLIER = "Passe par la BOUTIQUE : le bouclier encaisse des coups à ta place."
_alea_confettis = random.Random(11)
CONFETTIS = [(_alea_confettis.random(), _alea_confettis.uniform(0.10, 0.28), _alea_confettis.uniform(0, 6.28),
              _alea_confettis.choice([VERT_FLUO, JAUNE_CYBER, ROSE_SYNTH, CYAN_NEON, VIOLET_CYBER]), _alea_confettis.randint(7, 12))
             for _ in range(40)]


def fin_pret():
    return pygame.time.get_ticks() - FIN["t0"] >= DELAI_BOUTONS_FIN


# ==================== PUBLICITÉ (version web uniquement) ====================
# La pub s'affiche seulement sur l'écran de fin de mission (le jeu est à l'arrêt), jamais en pleine partie.
PUB_TOUS_LES_N = 3            # une pub toutes les 3 fins de mission
PUB_ESPACEMENT_MS = 180000    # et au moins 3 minutes entre deux pubs
PUB_ATTENTE_MS = 1000         # on laisse 1 seconde au joueur pour voir son résultat avant la pub
PUB = {"fins": 0, "attente": None, "derniere": -10 ** 9}


def pubs_autorisees():
    """Plus tard : False pour les joueurs qui ont acheté « RETIRER LES PUBS »."""
    try:
        return not BOUTIQUE.get("pubs_retirees", False)
    except Exception:
        return True


def planifier_pub():
    """Appelée une fois à chaque fin de mission : décide si une pub sera montrée sur cet écran de fin."""
    PUB["attente"] = None
    if not IS_WEB or not pubs_autorisees():
        return
    PUB["fins"] += 1
    maintenant = pygame.time.get_ticks()
    if PUB["fins"] % PUB_TOUS_LES_N == 0 and maintenant - PUB["derniere"] >= PUB_ESPACEMENT_MS:
        PUB["attente"] = maintenant


def verifier_pub():
    """Appelée à chaque image tant que l'écran de fin est affiché : lance la pub une seule fois."""
    if PUB["attente"] is None or TRANS["actif"]:
        return
    if pygame.time.get_ticks() - PUB["attente"] < PUB_ATTENTE_MS:
        return
    PUB["attente"] = None
    PUB["derniere"] = pygame.time.get_ticks()
    try:
        import platform as _pfpub
        _pfpub.window.flexPub()
    except Exception:
        pass


def demarrer_ecran_fin(victoire):
    """Appelé une seule fois quand la mission se termine : prépare étoiles, record ou conseil."""
    FIN["t0"] = pygame.time.get_ticks()
    FIN["record"] = False
    _stat("level_win" if victoire else "level_lose", niveau_actuel)
    planifier_pub()
    if victoire:
        _install_rappel_victoire()
    if victoire:
        ratio = max(0, temps_restant_frames) / float(MISSION["duree"])
        etoiles = 3 if ratio >= 0.45 else (2 if ratio >= 0.20 else 1)
        cle = str(niveau_actuel)
        ancien = BOUTIQUE["etoiles"].get(cle, 0)
        FIN["record"] = 0 < ancien < etoiles
        if etoiles > ancien and not MP["actif"]:
            BOUTIQUE["etoiles"][cle] = etoiles
        FIN["etoiles"] = etoiles
    else:
        choix = list(CONSEILS_DEFAITE)
        if STATS["bouclier"] == 0:
            choix += [CONSEIL_BOUCLIER] * 3
        FIN["conseil"] = random.choice(choix)


def _avancement(t, debut, duree):
    return max(0.0, min(1.0, (t - debut) / float(duree)))


def dessiner_etoile(cx, cy, r, couleur, plein=True):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr))
    if plein:
        DRAW.polygon(ecran, couleur, pts)
        DRAW.polygon(ecran, (255, 245, 170), pts, 2)
    else:
        DRAW.polygon(ecran, (70, 80, 110), pts, 3)


def dessiner_confettis(t):
    nb = 40 if QUALITE["niveau"] >= 1 else 16
    for x0, vit, phase, couleur, taille in CONFETTIS[:nb]:
        y = (t * vit + phase * 200) % (HAUTEUR + 60) - 30
        x = x0 * LARGEUR + 28 * math.sin(t / 380.0 + phase)
        DRAW.rect(ecran, couleur, (int(x), int(y), taille, taille // 2 + 2))


def dessiner_parasites():
    """Lignes rouges qui sautent : effet de signal corrompu."""
    for _ in range(8 if QUALITE["niveau"] >= 1 else 4):
        y = random.randint(0, HAUTEUR)
        x = random.randint(0, LARGEUR - 100)
        DRAW.line(ecran, (random.randint(120, 255), 0, random.randint(20, 60)), (x, y), (x + random.randint(80, 420), y), random.randint(1, 3))


def _panneau_fin(couleur, y_haut, y_bas, avancement):
    """Panneau central qui s'ouvre en hauteur, avec un contour néon."""
    largeur = min(780, LARGEUR - 60)
    h = int((y_bas - y_haut) * lisser(avancement))
    if h < 8:
        return
    rect = pygame.Rect(LARGEUR // 2 - largeur // 2, (y_haut + y_bas) // 2 - h // 2, largeur, h)
    DRAW.rect(ecran, (7, 9, 20), rect, border_radius=min(18, h // 2))
    for i in range(5, 0, -1):
        DRAW.rect(ecran, eclaircir(couleur, (1 - i / 6.0) * 0.55), rect.inflate(i * 4, i * 4), 3, border_radius=min(18 + i * 2, (h + i * 4) // 2))
    DRAW.rect(ecran, couleur, rect, 3, border_radius=min(18, h // 2))


def dessiner_ecran_victoire():
    verifier_pub()
    t = pygame.time.get_ticks() - FIN["t0"]
    cx = LARGEUR // 2
    ecran.blit(obtenir_voile(LARGEUR, HAUTEUR, (4, 12, 14, 170)), (0, 0))
    dessiner_confettis(t)
    y_btn = rect_bouton_suivant.y
    y_haut, y_bas = y_btn - 312, y_btn + 90
    _panneau_fin(VERT_FLUO, y_haut, y_bas, t / 420.0)
    if t < 380:
        return
    dessiner_titre_glitch("DATA SECURED !", police_victoire, cx, y_haut + 18)

    for i in range(3):                                           # étoiles qui apparaissent une à une
        p = _avancement(t, 560 + i * 220, 300)
        centre = (cx + (i - 1) * 92, y_haut + 138)
        if i >= FIN["etoiles"]:
            if p > 0:
                dessiner_etoile(centre[0], centre[1], 30, None, plein=False)
        elif p > 0:
            echelle = p * (1.0 + 0.3 * math.sin(p * math.pi))
            dessiner_etoile(centre[0], centre[1], max(2, int(34 * echelle)), JAUNE_CYBER)
    if FIN["record"] and t > 1300 and (t // 300) % 2 == 0:
        tr = rendu_texte(police_petite, "NOUVEAU RECORD !", True, JAUNE_CYBER)
        ecran.blit(tr, (cx - tr.get_width() // 2, y_haut + 184))

    r = MISSION["recompense"]
    if r and t > 900:
        valeur = int(r["total"] * lisser(_avancement(t, 900, 900)))      # le total « monte » comme un compteur
        t1 = rendu_texte(police_jeu, f"+{valeur} PIÈCES", True, JAUNE_CYBER)
        dessiner_piece(cx - t1.get_width() // 2 - 24, y_haut + 218, 12)
        ecran.blit(t1, (cx - t1.get_width() // 2, y_haut + 206))
        morceaux = [f"Mission {r['base']}", f"Temps {r['temps']}", f"Drones {r['drones']}"]
        if r["boss"]:
            morceaux.append(f"Boss {r['boss']}")
        t2 = rendu_texte(police_petite, "   ·   ".join(morceaux), True, (170, 180, 210))
        ecran.blit(t2, (cx - t2.get_width() // 2, y_haut + 242))
        if r["reduite"]:
            t3 = rendu_texte(police_petite, "Mission déjà réussie : gains réduits des trois quarts", True, JAUNE_CYBER)
            ecran.blit(t3, (cx - t3.get_width() // 2, y_haut + 266))
    if t >= DELAI_BOUTONS_FIN:
        bouton_neon(rect_bouton_rejouer, BLEU_CYBER, "REJOUE", police_bouton)
        bouton_neon(rect_bouton_suivant, VERT_FLUO, "SUIVANT", police_bouton, plein=True, pulse=True)
        dessiner_defis_fin(rect_bouton_suivant.bottom + 16)


def dessiner_ecran_defaite():
    verifier_pub()
    t = pygame.time.get_ticks() - FIN["t0"]
    cx = LARGEUR // 2
    ecran.blit(obtenir_voile(LARGEUR, HAUTEUR, (22, 0, 6, 190)), (0, 0))
    if (t // 90) % 3:
        dessiner_parasites()
    y_btn = rect_bouton_rejouer_defaite.y
    y_haut, y_bas = y_btn - 300, y_btn + 90
    _panneau_fin(ROUGE_ALERTE, y_haut, y_bas, t / 420.0)
    if t < 380:
        return
    dessiner_titre_glitch(message_defaite, police_victoire, cx, y_haut + 20)
    ts = rendu_texte(police_jeu, "MISSION ÉCHOUÉE", True, ROSE_SYNTH)
    ecran.blit(ts, (cx - ts.get_width() // 2, y_haut + 112))
    if t > 600:
        stats = rendu_texte(police_petite, f"Drones détruits : {MISSION['drones']}   ·   Hack : {int(jauge_hack)}%", True, (170, 180, 210))
        ecran.blit(stats, (cx - stats.get_width() // 2, y_haut + 152))
    r = MISSION["recompense"]
    if r and r["total"] > 0 and t > 800:
        t1 = rendu_texte(police_aide, f"+{r['total']} pièces récupérées", True, JAUNE_CYBER)
        dessiner_piece(cx - t1.get_width() // 2 - 24, y_haut + 196, 11)
        ecran.blit(t1, (cx - t1.get_width() // 2, y_haut + 184))
    if t > 1000 and FIN["conseil"]:
        tc = rendu_texte(police_petite, FIN["conseil"], True, BLEU_CYBER)
        ecran.blit(tc, (cx - tc.get_width() // 2, y_haut + 232))
    if t >= DELAI_BOUTONS_FIN:
        bouton_neon(rect_bouton_rejouer_defaite, BLEU_CYBER, "REJOUER", police_bouton)
        bouton_neon(rect_bouton_quitter_defaite, ROUGE_ALERTE, "QUITTER", police_bouton)
        dessiner_defis_fin(rect_bouton_quitter_defaite.bottom + 16)


# ==================== ÉCRAN DE DÉMARRAGE ====================
def _tache_vide():
    pass


def _tache_ville():
    global _tuile_ville
    if _tuile_ville is None:
        _tuile_ville = construire_tuile_ville()
    if PARAMS["dof"]:
        obtenir_tuile_ville_floue()


def _tache_menu():
    global _fond_menu_surface
    if _fond_menu_surface is None:
        _fond_menu_surface = construire_fond_menu()


def _tache_lueurs():
    for rayon in (24, 30, 36, 42, 56, 84, 110):
        for couleur in (BLEU_CYBER, ROSE_SYNTH, VIOLET_CYBER, ROUGE_ALERTE, JAUNE_CYBER, VERT_FLUO, CYAN_NEON, ORANGE_MEC):
            obtenir_halo(rayon, couleur, 0.8)


def _tache_labyrinthe():
    for masque in range(16):
        tuile_mur(COULEUR_MUR, masque)
        for variante in (0, 1):
            tuile_sol(COULEUR_MUR, variante, masque)


def _tache_textes():
    for texte in ("COMMENCER", "GUIDE TACTIQUE", "BOUTIQUE"):
        rendu_texte(police_bouton, texte, True, NOIR_ESPACE)
        rendu_texte(police_bouton, texte, True, ROSE_SYNTH)
    for texte in ("MODE INFINI", "DATA SECURED !", "MISSION ÉCHOUÉE"):
        rendu_texte(police_jeu, texte, True, ROSE_SYNTH)


ETAPES_DEMARRAGE = [
    ("Initialisation du système", _tache_vide),
    ("Génération de la ville futuriste", _tache_ville),
    ("Calibrage du décor du menu", _tache_menu),
    ("Compilation des lueurs néon", _tache_lueurs),
    ("Préparation du labyrinthe", _tache_labyrinthe),
    ("Synchronisation du profil et de la boutique", _tache_textes),
    ("Connexion au réseau neuronal", _tache_vide),
]
DUREE_ETAPE_DEMARRAGE = 430        # ms par étape (≈ 3 s au total) ; chaque étape fait un vrai préchargement


def dessiner_grille_demarrage(t_ms, horizon):
    cx = LARGEUR // 2
    for k in range(-16, 17):
        DRAW.line(ecran, (90, 20, 130), (cx + k * 10, horizon), (cx + k * (LARGEUR // 11), HAUTEUR), 1)
    decal = (t_ms / 1400.0) % 1.0
    for i in range(12):
        z = (i + decal) / 12.0
        y = horizon + int((HAUTEUR - horizon) * z ** 2.2)
        DRAW.line(ecran, eclaircir(BLEU_CYBER, 0.12 + 0.55 * z), (0, y), (LARGEUR, y), 1 if z < 0.6 else 2)


async def ecran_de_demarrage():
    """Logo FlexPlay, titre du jeu et barre de chargement pendant que les décors sont réellement préparés."""
    n = len(ETAPES_DEMARRAGE)
    t_debut = pygame.time.get_ticks()
    derniere = -1
    t_pret = None
    cx = LARGEUR // 2
    horizon = int(HAUTEUR * 0.60)
    bw = min(520, LARGEUR - 120)
    bx, by = cx - bw // 2, HAUTEUR - 70
    while True:
        await asyncio.sleep(0)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                EXTRA["_essai"] = 0
                sauvegarder_parametres()
                pygame.quit()
                sys.exit()
        t = pygame.time.get_ticks() - t_debut
        etape = min(n - 1, int(t / DUREE_ETAPE_DEMARRAGE))
        if derniere < etape:                       # une nouvelle étape commence : on fait son vrai travail
            derniere = etape
            ETAPES_DEMARRAGE[etape][1]()
        fini = t >= n * DUREE_ETAPE_DEMARRAGE
        if fini and t_pret is None:
            t_pret = t
        avancement = min(1.0, t / float(n * DUREE_ETAPE_DEMARRAGE))

        ecran.fill((4, 5, 14))
        dessiner_halo(cx, horizon, 260, (110, 30, 170), 0.55)
        dessiner_grille_demarrage(t, horizon)
        dessiner_titre_glitch("FLEXPLAY", police_titre, cx, int(HAUTEUR * 0.10))
        ts = rendu_texte(police_petite, "présente", True, BLEU_CYBER)
        ecran.blit(ts, (cx - ts.get_width() // 2, int(HAUTEUR * 0.10) + 78))
        if t > 900:
            dessiner_titre_glitch("FLEX CYBERPUNK", police_titre, cx, int(HAUTEUR * 0.33))
        if t > 1300:
            tm = rendu_texte(police_jeu, "MODE INFINI", True, ROSE_SYNTH)
            ecran.blit(tm, (cx - tm.get_width() // 2, int(HAUTEUR * 0.33) + 84))

        message = "Système prêt" if fini else ETAPES_DEMARRAGE[etape][0] + "..."
        tx = rendu_texte(police_aide, message, True, VERT_FLUO if fini else BLANC_NEON)
        ecran.blit(tx, (cx - tx.get_width() // 2, by - 44))
        DRAW.rect(ecran, (16, 20, 40), (bx, by, bw, 12), border_radius=6)
        rempli = int(bw * avancement)
        if rempli > 4:
            DRAW.rect(ecran, BLEU_CYBER, (bx, by, rempli, 12), border_radius=min(6, rempli // 2))
            DRAW.rect(ecran, (170, 235, 255), (bx + 2, by + 2, max(2, rempli - 4), 3), border_radius=1)
            dessiner_halo(bx + rempli, by + 6, 34, BLEU_CYBER, 0.8)
        DRAW.rect(ecran, eclaircir(BLEU_CYBER, 0.55), (bx, by, bw, 12), 2, border_radius=6)
        pct = rendu_texte(police_petite, f"{int(avancement * 100)}%", True, BLEU_CYBER)
        ecran.blit(pct, (cx - pct.get_width() // 2, by + 18))
        cr = rendu_texte(police_petite, "© 2026 FlexPlay", True, (150, 160, 195))
        ecran.blit(cr, (LARGEUR - cr.get_width() - 24, HAUTEUR - 30))

        if VERSION_MODIFIEE:
            dessiner_filigrane()
        if t_pret is not None and t - t_pret > 350:          # fermeture du rideau, puis le menu s'ouvre derrière
            dessiner_rideau(int((LARGEUR // 2 + 2) * lisser((t - t_pret - 350) / 400.0)))
            if t - t_pret > 750:
                break
        pygame.display.flip()
        clock.tick(60)

    DEMARRAGE["actif"] = False
    TRANS.update(actif=True, phase=2, t0=pygame.time.get_ticks(), duree=0.0, cible=None)
    LOGIQUE["t"] = _time.perf_counter()


# 7. ASSETS D'EFFETS PRÉ-CALCULÉS
def creer_disque_translucide(rayon, couleur_rgba):
    s = pygame.Surface((rayon * 2 + 12, rayon * 2 + 12), pygame.SRCALPHA)
    DRAW.circle(s, couleur_rgba, (rayon + 6, rayon + 6), rayon)
    return s


def construire_vignette():
    """Assombrit doucement les bords de l'écran (calculée une seule fois, appliquée en multiplication)."""
    pw, ph = max(2, LARGEUR // 10), max(2, HAUTEUR // 10)
    petite = pygame.Surface((pw, ph))
    for y in range(ph):
        for x in range(pw):
            nx = (x / float(pw - 1) - 0.5) * 2
            ny = (y / float(ph - 1) - 0.5) * 2
            d = math.sqrt(nx * nx * 0.8 + ny * ny)
            f = 1.0 - 0.65 * max(0.0, min(1.0, (d - 0.55) / 0.75)) ** 1.6
            petite.set_at((x, y), (int(255 * f), int(255 * f), int(255 * min(1.0, f * 1.05))))
    return pygame.transform.smoothscale(petite, (LARGEUR, HAUTEUR)).convert()


SURF_SOCLE_JOY = creer_disque_translucide(JOY_RAYON_SOCLE, (10, 30, 45, 85))
SURF_BTN_TIR = creer_disque_translucide(BTN_TIR_RAYON, (70, 0, 25, 95))
VIGNETTE = None


def obtenir_vignette():
    global VIGNETTE
    if VIGNETTE is None:
        VIGNETTE = construire_vignette()
    return VIGNETTE


charger_parametres()
appliquer_parametres()
charger_boutique()
recalculer_stats()
appliquer_skin()
# ===== VUE 3E PERSONNE DEBUT
# ================================================================ VUE 3E PERSONNE (pseudo-3D)
# La logique du jeu reste 100 % 2D (positions en pixels). Seule la caméra change : ici on convertit
# les positions en « cases » (1 case = TAILLE_CASE pixels) et on dessine le labyrinthe en perspective.
VUE = {"ang": 0.0, "cam_d": 1.7, "surf": None, "dim": None, "carte": None, "faces": {}, "t_bascule": 0,
       "qa_i": 0, "ema": 16.0, "cool": 120, "scale_ok": True, "tmp": None,
       "perso_cle": None, "perso_hd": None, "perso_def": None, "perso_cache": {}, "face": 1, "flux": {}, "flux_cle": None,
       "lean": 0.0, "img": {}, "marche": 0.0, "coul": {}, "dos": {}, "dos_cache": {}, "mv": 0.0, "vise": 0.0,
       "look_id": None, "look_x": 0.0, "look_y": 0.0, "pitch": 0.0,
       "kick": 0.0, "nb": 0, "dust": [], "cos_prev": 1.0, "t_prev": 0,
       "cam_off": 0.0, "look_n": 0, "atlas": {}, "cadres": {}, "tours": {}}
V3_STYLES = ((60, 85), (35, 80), (35, 55))     # selon la mission : part de murs « métal néon », puis « briques », le reste « circuits »
V3_NEAR, V3_CAMZ, V3_MUR_H, V3_PORTEE, V3_CAM_D_MAX = 0.12, 0.85, 1.35, 8.0, 2.0
V3_JAMBES = (0.60, 0.66, 0.50, 0.76)  # (début des jambes, fin du haut du corps, séparation gauche/droite, genou) en fraction de l'image
V3_BOTTES = 0.2125                    # écart des bottes par rapport au centre, en fraction de la largeur de l'image
V3_CANON = (0.181, 0.152, 0.206)      # (fin du canon en x, haut, bas) en fraction de l'image de base : la partie du fusil qui se raccourcit au tir
V3_ATLAS_N = 5                        # nombre de vues dans soldat_<skin>.png : dos, dos 3/4, 3/4, profil, face (les vues tournées vers la gauche sont des miroirs)
V3_ATLAS_BOUCHES = ((0.145, 0.198), (0.88, 0.169), (0.979, 0.191), (0.817, 0.185), (0.554, 0.304))     # bout du canon de chaque vue (fraction de la case)
V3_ATLAS_SEMELLES = 0.9867            # hauteur des semelles dans la case (fraction)
V3_SENS_REGARD = 0.005                # radians par pixel quand on fait glisser le doigt pour tourner la caméra
V3_QA = (1.0, 0.85, 0.72, 0.6, 0.5, 0.42, 0.35)      # échelles de résolution de la 3D : la vue baisse toute seule si le téléphone peine
V3_VIT_TOURNER = 0.05          # radians par pas de logique (1/60 s) quand le joystick est poussé à fond sur le côté
V3_FOND = (11, 16, 38)

_v3_rng = random.Random(7)
V3_VILLE = []
for _k in range(36):
    _a = _k * (2 * math.pi / 36) + _v3_rng.uniform(-0.05, 0.05)
    _fen = [(_v3_rng.uniform(0.15, 0.75), _v3_rng.uniform(0.1, 0.85), _v3_rng.randrange(3)) for _ in range(4)]
    V3_VILLE.append((_a, _v3_rng.uniform(0.07, 0.14), _v3_rng.uniform(0.10, 0.34), _fen))


def _v3_actif():
    return PARAMS.get("vue", 0) == 1 and not MP["actif"] and not DEVIL["actif"]      # multijoueur : vue du dessus uniquement


def _v3_mix(a, b, k):
    return (int(a[0] + (b[0] - a[0]) * k), int(a[1] + (b[1] - a[1]) * k), int(a[2] + (b[2] - a[2]) * k))


def _v3_mur(i, j):
    if j < 0 or i < 0 or j >= len(CARTE) or i >= len(CARTE[0]):
        return True
    return CARTE[j][i] == 1


def _v3_bloque(x, y, r):
    for j in range(int(math.floor(y - r)), int(math.floor(y + r)) + 1):
        for i in range(int(math.floor(x - r)), int(math.floor(x + r)) + 1):
            if _v3_mur(i, j):
                nx = min(max(x, i), i + 1)
                ny = min(max(y, j), j + 1)
                if (x - nx) ** 2 + (y - ny) ** 2 < r * r:
                    return True
    return False


def _v3_cap_libre(base):
    """Cap (radians) le plus proche de `base` où il y a de la place devant le joueur (évite de démarrer face à un mur)."""
    px, py = joueur_x / TAILLE_CASE, joueur_y / TAILLE_CASE
    for k in (0, 1, -1, 2, -2, 3, -3, 4):
        a = base + k * math.pi / 4
        if not _v3_bloque(px + math.cos(a) * 1.2, py + math.sin(a) * 1.2, 0.2):
            return a
    return base


def _v3_perso_hd():
    """Image du VRAI personnage (skin équipé) en grande taille, pour la 3D. Mise en cache ; None si indisponible."""
    cle = _skin_courant or ""
    if VUE["perso_cle"] == cle:
        return VUE["perso_hd"]
    img = None
    try:
        if cle in SKIN_IDS:
            planche = _planche_skins
            if planche is None:
                planche = pygame.image.load(_asset("skins_sheet.png")).convert_alpha()
            i = SKIN_IDS.index(cle)
            img = planche.subsurface(pygame.Rect((i % 6) * 160, (i // 6) * 160, 160, 160)).copy()
        else:
            if VUE["perso_def"] is None:
                VUE["perso_def"] = pygame.transform.smoothscale(pygame.image.load(_asset("perso-removebg-preview.png")).convert_alpha(), (160, 160))
            img = VUE["perso_def"]
    except Exception as e:
        print("[3D] image du personnage introuvable :", e, "| dossier courant :", os.getcwd())
        img = None
    VUE["perso_cle"], VUE["perso_hd"] = cle, img
    VUE["perso_cache"].clear()
    return img


def _v3_perso_taille(taille, miroir):
    """Le personnage à la taille voulue (par paliers de 8 px, en cache) : évite de redimensionner l'image à chaque image."""
    hd = _v3_perso_hd()
    if hd is None:
        return None
    t = min(240, max(16, (taille // 8) * 8))
    cle = (t, miroir)
    img = VUE["perso_cache"].get(cle)
    if img is None:
        if len(VUE["perso_cache"]) > 14:
            VUE["perso_cache"].clear()
        img = pygame.transform.smoothscale(hd, (t, t))
        if miroir < 0:
            img = pygame.transform.flip(img, True, False)
        VUE["perso_cache"][cle] = img
    return img


def _v3_image(nom):
    """Charge une image du jeu une seule fois (None si introuvable)."""
    if nom not in VUE["img"]:
        try:
            VUE["img"][nom] = pygame.image.load(_asset(nom)).convert_alpha()
        except Exception as e:
            print("[3D] image introuvable :", nom, "|", e)
            VUE["img"][nom] = None
    return VUE["img"][nom]


def _v3_plat(cle, src, largeur, ratio, angle, pas=6):
    """Image vue du dessus, tournée de `angle` degrés puis écrasée (`ratio`) comme si on la voyait en perspective.
    Mise en cache par paliers de taille et d'angle : on ne redimensionne pas l'image à chaque image."""
    if src is None or largeur < 6:
        return None
    lb = max(6, (int(largeur) // 6) * 6)
    ab = int(round(angle / pas)) * pas
    k = (cle, lb, ab, ratio)
    img = VUE["perso_cache"].get(k)
    if img is None:
        if len(VUE["perso_cache"]) > 90:
            VUE["perso_cache"].clear()
        base = src if ab % 360 == 0 else pygame.transform.rotate(src, ab)
        f = lb / float(src.get_width())
        img = pygame.transform.smoothscale(base, (max(2, int(base.get_width() * f)), max(2, int(base.get_height() * f * ratio))))
        VUE["perso_cache"][k] = img
    return img


def _v3_style(grp):
    """Style d'un pan de mur (0 = métal et néon, 1 = briques néon, 2 = circuits lumineux), identique sur 3 cases de suite."""
    h = (grp[0] * 73856093 ^ grp[1] * 19349663 ^ grp[2] * 83492791) & 0xFFFF
    r = h % 100
    th = V3_STYLES[niveau_actuel % 3]
    return 0 if r < th[0] else (1 if r < th[1] else 2)


def _v3_decor(rs, style, detail, fog, cm, fa, ra, fb, rb, t0, t1, half, hor, focal, seed):
    """Décor d'un mur, dessiné avec quelques lignes en perspective (très léger, sans textures lourdes)."""
    if t1 - t0 < 0.03:
        return
    H = V3_MUR_H

    def P(u, z):
        u = t0 if u < t0 else (t1 if u > t1 else u)
        sc = focal / (fa + (fb - fa) * u)
        return (int(half + (ra + (rb - ra) * u) * sc), int(hor + (V3_CAMZ - z) * sc))

    def col(c):
        return _v3_mix(c, V3_FOND, fog)

    def bande(u0, u1, z0, z1, c):
        pygame.draw.polygon(rs, c, [P(u0, z1), P(u1, z1), P(u1, z0), P(u0, z0)])

    neon = col(_v3_mix(cm, (255, 255, 255), 0.3))
    rose = col((255, 43, 214))
    sombre = col((8, 12, 26))
    if style == 0:                                   # métal et néon
        bande(0, 1, H - 0.11, H - 0.05, neon)
        bande(0, 1, 0.05, 0.10, neon)
        if detail >= 1:
            sm = col(_v3_mix(V3_FOND, cm, 0.12))
            pygame.draw.line(rs, sm, P(0.5, 0.10), P(0.5, H - 0.11), 1)
            pygame.draw.line(rs, sm, P(0, 0.58), P(1, 0.58), 1)
            if detail >= 2:
                pygame.draw.line(rs, sm, P(0, 0.30), P(1, 0.30), 1)
                for (ru, rz) in ((0.06, 0.2), (0.94, 0.2), (0.06, 1.0), (0.94, 1.0)):
                    pygame.draw.circle(rs, col(_v3_mix(V3_FOND, cm, 0.5)), P(ru, rz), 2)
            m = seed % 3
            if m == 0:                               # écran allumé
                cadre = [P(0.28, 0.95), P(0.72, 0.95), P(0.72, 0.55), P(0.28, 0.55)]
                pygame.draw.polygon(rs, sombre, cadre)
                pygame.draw.polygon(rs, rose if seed & 4 else neon, cadre, 1)
                if detail >= 2:
                    pygame.draw.line(rs, rose if seed & 4 else neon, P(0.34, 0.82), P(0.66, 0.82), 1)
                    pygame.draw.line(rs, rose if seed & 4 else neon, P(0.34, 0.70), P(0.56, 0.70), 1)
            elif m == 1:                             # grille d'aération
                for k in range(4):
                    bande(0.2, 0.8, 0.35 + k * 0.1, 0.39 + k * 0.1, sombre)
            else:                                    # tube néon
                pygame.draw.line(rs, rose if seed & 8 else neon, P(0.15, 0.72), P(0.85, 0.72), 2)
    elif style == 1:                                 # briques néon
        mort = col((34, 12, 36))
        for r in range(1, 5):
            pygame.draw.line(rs, mort, P(0, r * 0.27), P(1, r * 0.27), 1)
        if detail >= 1:
            for r in range(5):
                for u in ((0.5,) if r % 2 == 0 else (0.25, 0.75)):
                    pygame.draw.line(rs, mort, P(u, r * 0.27), P(u, r * 0.27 + 0.27), 1)
            if seed % 4 == 0:                        # une brique éclairée
                pygame.draw.polygon(rs, rose, [P(0.5, 0.81), P(1, 0.81), P(1, 0.54), P(0.5, 0.54)], 1)
            if seed % 5 == 1 and detail >= 2:        # enseigne lumineuse
                cadre = [P(0.25, 0.9), P(0.75, 0.9), P(0.75, 0.6), P(0.25, 0.6)]
                pygame.draw.polygon(rs, sombre, cadre)
                pygame.draw.polygon(rs, neon, cadre, 1)
                pygame.draw.line(rs, neon, P(0.32, 0.8), P(0.68, 0.8), 2)
                pygame.draw.line(rs, rose, P(0.32, 0.68), P(0.55, 0.68), 2)
        bande(0, 1, H - 0.05, H - 0.02, col(_v3_mix(V3_FOND, cm, 0.5)))
    else:                                            # circuits lumineux
        mir = seed & 1

        def U(u):
            return 1.0 - u if mir else u
        pygame.draw.lines(rs, neon, False, [P(U(u), z) for (u, z) in ((0, 0.30), (0.35, 0.30), (0.5, 0.5), (1, 0.5))], 1)
        pygame.draw.lines(rs, rose, False, [P(U(u), z) for (u, z) in ((0, 0.92), (0.25, 0.92), (0.4, 0.74), (0.8, 0.74), (0.9, 0.94), (1, 0.94))], 1)
        if detail >= 1:
            pygame.draw.lines(rs, neon, False, [P(U(u), z) for (u, z) in ((0.6, 0.05), (0.6, 0.2), (0.82, 0.32))], 1)
            for (u, z, c) in ((0.35, 0.30, neon), (0.8, 0.74, rose), (0.5, 0.5, neon)):
                pygame.draw.circle(rs, c, P(U(u), z), 2)
        if detail >= 2:
            chip = [P(U(0.1), 0.6), P(U(0.3), 0.6), P(U(0.3), 0.42), P(U(0.1), 0.42)]
            pygame.draw.polygon(rs, sombre, chip)
            pygame.draw.polygon(rs, neon, chip, 1)
        bande(0, 1, H - 0.05, H - 0.02, col(_v3_mix(V3_FOND, cm, 0.5)))


def _v3_coul_perso(hd, cle):
    """Couleurs du personnage (uniforme, sac, casque, arme, halo) mesurées sur son image : chaque skin a donc ses propres couleurs."""
    c = VUE["coul"].get(cle)
    if c is None:
        c = {"uni": (62, 78, 70), "sac": (95, 88, 60), "casque": (40, 42, 46), "arme": (130, 78, 40), "halo": None}
        try:
            w, h = hd.get_size()

            def moy(x0, x1, y0, y1):
                tot, n = [0, 0, 0], 0
                for iy in range(7):
                    for ix in range(7):
                        p = hd.get_at((int(w * (x0 + (x1 - x0) * ix / 6.0)), int(h * (y0 + (y1 - y0) * iy / 6.0))))
                        if p[3] > 200:
                            tot[0] += p[0]; tot[1] += p[1]; tot[2] += p[2]; n += 1
                return (tot[0] // n, tot[1] // n, tot[2] // n) if n else None
            for (nom, zone) in (("uni", (0.50, 0.76, 0.22, 0.48)), ("sac", (0.05, 0.30, 0.15, 0.45)),
                                ("casque", (0.38, 0.52, 0.50, 0.70)), ("arme", (0.40, 0.90, 0.70, 0.80))):
                m = moy(*zone)
                if m:
                    c[nom] = m
            # halo lumineux : pixels semi-transparents (bord des skins brillants)
            tot, n = [0, 0, 0], 0
            for iy in range(20):
                for ix in range(20):
                    p = hd.get_at((int(w * ix / 20.0), int(h * iy / 20.0)))
                    if 30 < p[3] < 200 and max(p[0], p[1], p[2]) - min(p[0], p[1], p[2]) > 60:
                        tot[0] += p[0]; tot[1] += p[1]; tot[2] += p[2]; n += 1
            if n >= 6:
                c["halo"] = (tot[0] // n, tot[1] // n, tot[2] // n)
            for nom, f in (("uni", 1.55), ("sac", 1.45), ("casque", 1.6), ("arme", 1.25)):
                c[nom] = tuple(min(255, int(v * f) + 14) for v in c[nom])
        except Exception:
            pass
        VUE["coul"][cle] = c
    return c


def _v3_soldat(rs, sx, yb, s, c, phase, accent):
    """Soldat debout vu de dos, dessiné avec les couleurs du skin (uniforme, sac, casque, arme, halo). Les jambes avancent à tour de rôle."""
    X = int(sx)
    noir = _v3_mix((16, 16, 26), c["halo"] or accent, 0.5)           # contour lumineux : le soldat reste lisible sur le sol sombre
    bottes = (14, 14, 20)

    def R(x0, y0, x1, y1, col, bord=True):
        if bord:
            pygame.draw.rect(rs, noir, (int(x0) - 1, int(y0) - 1, int(x1 - x0) + 3, int(y1 - y0) + 3))
        pygame.draw.rect(rs, col, (int(x0), int(y0), max(1, int(x1 - x0)), max(1, int(y1 - y0))))

    if c["halo"]:
        pygame.draw.ellipse(rs, _v3_mix(V3_FOND, c["halo"], 0.55), (int(sx - 0.32 * s), int(yb - 0.92 * s), int(0.64 * s), int(0.95 * s)), 2)
    bob = abs(math.sin(phase)) * 0.015 * s
    # jambes
    for (k, sgn) in ((-1, 1), (1, -1)):
        lev = max(0.0, math.sin(phase) * sgn) * 0.05 * s
        x = sx + k * 0.065 * s
        R(x - 0.045 * s, yb - 0.38 * s - bob, x + 0.045 * s, yb - 0.03 * s - lev, _v3_mix(c["uni"], noir, 0.35))
        R(x - 0.05 * s, yb - 0.075 * s - lev, x + 0.05 * s, yb - 0.02 * s - lev, bottes, False)
    # sac à dos et torse
    h0 = yb - 0.40 * s - bob
    pygame.draw.polygon(rs, noir, [(int(sx - 0.165 * s), int(h0)), (int(sx + 0.165 * s), int(h0)), (int(sx + 0.20 * s), int(h0 - 0.28 * s)), (int(sx - 0.20 * s), int(h0 - 0.28 * s))])
    pygame.draw.polygon(rs, c["uni"], [(int(sx - 0.15 * s), int(h0 - 0.01 * s)), (int(sx + 0.15 * s), int(h0 - 0.01 * s)), (int(sx + 0.185 * s), int(h0 - 0.27 * s)), (int(sx - 0.185 * s), int(h0 - 0.27 * s))])
    R(sx - 0.115 * s, h0 - 0.255 * s, sx + 0.115 * s, h0 - 0.045 * s, c["sac"])
    pygame.draw.line(rs, _v3_mix(c["sac"], noir, 0.5), (X, int(h0 - 0.25 * s)), (X, int(h0 - 0.05 * s)), 1)
    # bras
    for k in (-1, 1):
        x = sx + k * 0.205 * s
        R(x - 0.032 * s, h0 - 0.27 * s, x + 0.032 * s, h0 - 0.06 * s, c["uni"])
        R(x - 0.036 * s, h0 - 0.075 * s, x + 0.036 * s, h0 - 0.03 * s, noir, False)
    # arme tenue à droite, pointée vers l'avant
    R(sx + 0.205 * s - 0.018 * s, h0 - 0.23 * s, sx + 0.205 * s + 0.018 * s, h0 - 0.02 * s, c["arme"])
    # casque
    ty = h0 - 0.28 * s - 0.075 * s
    pygame.draw.circle(rs, noir, (X, int(ty)), max(2, int(0.105 * s)))
    pygame.draw.circle(rs, c["casque"], (X, int(ty)), max(1, int(0.092 * s)))
    pygame.draw.circle(rs, _v3_mix(c["casque"], (255, 255, 255), 0.22), (int(sx - 0.03 * s), int(ty - 0.04 * s)), max(1, int(0.022 * s)))


def _v3_dos(cle):
    """Image du personnage vu de dos : dos_<skin>.png, sinon dos_defaut.png. Renvoie (image, exacte, nom du fichier) ; (None, False, "") si aucun."""
    k = cle or "defaut"
    if k not in VUE["dos"]:
        trouve = (None, False, "")
        for nom in ("dos_" + k + ".png", "dos_defaut.png"):
            try:
                trouve = (pygame.image.load(_asset(nom)).convert_alpha(), nom == "dos_" + k + ".png", nom)
                break
            except Exception:
                continue
        if trouve[0] is None:
            print("[3D] image du personnage de dos introuvable (dos_defaut.png) | dossier courant :", os.getcwd())
        VUE["dos"][k] = trouve
    return VUE["dos"][k]


def _v3_dos_tir(cle):
    """Image du personnage en train de tirer (arme pointée devant) : dos_<skin>_tir.png, sinon dos_defaut_tir.png. None si absente."""
    k = (cle or "defaut") + "_tir"
    if k not in VUE["dos"]:
        r = None
        for nom in ("dos_" + k + ".png", "dos_defaut_tir.png"):
            try:
                r = pygame.image.load(_asset(nom)).convert_alpha()
                break
            except Exception:
                continue
        VUE["dos"][k] = (r, True, "")
    return VUE["dos"][k][0]


def _v3_calques(cle, hauteur, tir):
    """Découpe le personnage en pièces à la bonne hauteur (en cache) : haut du corps, cuisse et tibia+botte de chaque jambe,
    canon du fusil (image de base), silhouette (pour l'ombre sur les murs). On les fait bouger comme un squelette."""
    hb = max(12, (int(hauteur) // 6) * 6)
    k = (cle or "defaut", hb, tir)
    c = VUE["dos_cache"].get(k)
    if c is None:
        if len(VUE["dos_cache"]) > 10:
            VUE["dos_cache"].clear()
        if tir:
            src, defaut = _v3_dos_tir(cle), False
        else:
            src, _ex, nom = _v3_dos(cle)
            defaut = (nom == "dos_defaut.png")
        img = pygame.transform.smoothscale(src, (max(4, int(src.get_width() * hb / float(src.get_height()))), hb))
        w, h = img.get_size()
        ys, yc, cx, yk = int(V3_JAMBES[0] * h), int(V3_JAMBES[1] * h), int(V3_JAMBES[2] * w), int(V3_JAMBES[3] * h)

        def morceau(x0, x1, y0, y1):
            return img.subsurface(pygame.Rect(x0, y0, x1 - x0, y1 - y0)).copy()
        haut = img.copy()
        haut.fill((0, 0, 0, 0), pygame.Rect(0, yc, w, h - yc))
        c = {"dim": (w, h), "ys": ys, "yk": yk, "cx": cx, "rot": {}, "canon": None, "geom": None, "sil": None,
             "cg": morceau(0, cx, ys, yk + 2), "tg": morceau(0, cx, yk, h),
             "cd": morceau(cx, w, ys, yk + 2), "td": morceau(cx, w, yk, h)}
        if defaut and not tir:
            xb, ya, yb2 = int(V3_CANON[0] * w), int(V3_CANON[1] * h), int(V3_CANON[2] * h)
            r = pygame.Rect(0, ya, xb, yb2 - ya)
            c["canon"] = img.subsurface(r).copy()
            haut.fill((0, 0, 0, 0), r)
            c["geom"] = (xb, ya, yb2 - ya)
        c["haut"] = haut
        try:
            sil = img.copy()
            sil.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)       # même forme, tout en noir
            c["sil"] = sil
        except Exception:
            c["sil"] = None
        VUE["dos_cache"][k] = c
    return c


def _v3_tourner(surf, ang, pivot):
    """Tourne une pièce de `ang` degrés autour d'un point (le bassin, par exemple). Renvoie (image, décalage x, décalage y)."""
    rot = pygame.transform.rotate(surf, ang)
    w, h = surf.get_size()
    vx, vy = w / 2.0 - pivot[0], h / 2.0 - pivot[1]
    a = math.radians(ang)
    nx = vx * math.cos(a) + vy * math.sin(a)
    ny = -vx * math.sin(a) + vy * math.cos(a)
    rw, rh = rot.get_size()
    return rot, pivot[0] + nx - rw / 2.0, pivot[1] + ny - rh / 2.0


def _v3_atlas(cle):
    """Les vues du soldat sous tous les angles : soldat_<skin>.png, sinon soldat_defaut.png. Renvoie (image, exacte) ou None."""
    k = cle or "defaut"
    if k not in VUE["atlas"]:
        r = None
        for nom in (("soldat_" + k + ".png"), "soldat_defaut.png"):
            try:
                r = (pygame.image.load(_asset(nom)).convert_alpha(), nom == "soldat_" + k + ".png")
                break
            except Exception:
                continue
        VUE["atlas"][k] = r
    return VUE["atlas"][k]


def _v3_cadre(cle, atlas, vue, miroir, hauteur):
    """Une vue du soldat à la bonne hauteur (par paliers de 6 px), éventuellement en miroir. Mise en cache."""
    hb = max(12, (int(hauteur) // 6) * 6)
    k = (cle or "defaut", vue, miroir, hb)
    c = VUE["cadres"].get(k)
    if c is None:
        if len(VUE["cadres"]) > 24:
            VUE["cadres"].clear()
            VUE["tours"].clear()
        img = atlas[0]
        cw = img.get_width() // V3_ATLAS_N
        cell = img.subsurface(pygame.Rect(vue * cw, 0, cw, img.get_height()))
        c = pygame.transform.smoothscale(cell, (max(4, int(cw * hb / float(img.get_height()))), hb))
        if miroir:
            c = pygame.transform.flip(c, True, False)
        VUE["cadres"][k] = c
    return c


def _v3_flux():
    """Distance (en cases, par les couloirs) depuis la case du joueur. Recalculé seulement quand le joueur change de case."""
    ci, cj = int(joueur_x // TAILLE_CASE), int(joueur_y // TAILLE_CASE)
    cle = (id(CARTE), ci, cj)
    if VUE["flux_cle"] == cle:
        return VUE["flux"]
    dist = {(ci, cj): 0}
    file = [(ci, cj)]
    t = 0
    while t < len(file):
        i, j = file[t]
        t += 1
        d = dist[(i, j)] + 1
        for (a, b) in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if (a, b) not in dist and not _v3_mur(a, b):
                dist[(a, b)] = d
                file.append((a, b))
    VUE["flux"], VUE["flux_cle"] = dist, cle
    return dist


def _v3_cap_ennemi(ex):
    """3e personne : le drone suit les couloirs (il ne traverse plus les murs). Renvoie son cap, ou None pour l'ancien comportement."""
    flux = _v3_flux()
    ci, cj = int(ex[0] // TAILLE_CASE), int(ex[1] // TAILLE_CASE)
    if (ci, cj) not in flux:                       # drone coincé dans un mur : on le replace sur la case libre la plus proche
        for r in range(1, 9):
            proches = [(ci + k, cj + m) for k in range(-r, r + 1) for m in range(-r, r + 1) if (ci + k, cj + m) in flux]
            if proches:
                ci, cj = min(proches, key=lambda c: (c[0] - ci) ** 2 + (c[1] - cj) ** 2)
                ex[0], ex[1] = ci * TAILLE_CASE + TAILLE_CASE / 2, cj * TAILLE_CASE + TAILLE_CASE / 2
                break
        else:
            return None
    d = flux[(ci, cj)]
    if d == 0:                                     # même case que le joueur : tout droit
        return math.atan2(joueur_y - ex[1], joueur_x - ex[0]) + random.uniform(-0.08, 0.08)
    meilleur = None
    for (a, b) in ((ci + 1, cj), (ci - 1, cj), (ci, cj + 1), (ci, cj - 1)):
        if flux.get((a, b), 9999) < d:
            meilleur = (a, b)
            break
    if meilleur is None:
        return None
    tx, ty = meilleur[0] * TAILLE_CASE + TAILLE_CASE / 2, meilleur[1] * TAILLE_CASE + TAILLE_CASE / 2
    return math.atan2(ty - ex[1], tx - ex[0]) + random.uniform(-0.03, 0.03)


def _v3_spawn_ennemi():
    """3e personne : les drones apparaissent loin dans le labyrinthe (par les couloirs) et arrivent en se montrant, jamais « BOOM » devant le joueur."""
    flux = _v3_flux()
    loin = [c for c, d in flux.items() if 9 <= d <= 18]            # assez loin pour qu'on les voie venir, assez près pour qu'ils arrivent
    if not loin:
        plus = [d for d in flux.values() if d >= 9]
        if plus:
            dmin = min(plus)
            loin = [c for c, d in flux.items() if dmin <= d <= dmin + 3]
        elif len(flux) >= 2:
            dmax = max(flux.values())
            loin = [c for c, d in flux.items() if d >= max(3, dmax - 1)]
        else:
            return None
    i, j = random.choice(loin)
    return i * TAILLE_CASE + TAILLE_CASE / 2, j * TAILLE_CASE + TAILLE_CASE / 2


def _v3_regarder(dx, dy):
    """Glisser le doigt : tourner la caméra (gauche/droite) et l'incliner un peu (haut/bas), comme dans un jeu en monde ouvert.
    Le personnage regarde et tire là où la caméra regarde."""
    VUE["cam_off"] = (VUE["cam_off"] + dx * V3_SENS_REGARD + math.pi) % (2 * math.pi) - math.pi
    VUE["look_n"] = 90
    VUE["pitch"] = max(-0.10, min(0.10, VUE["pitch"] - dy * 0.0004))


def basculer_vue():
    """Bouton 2D/3D : passe de la vue du dessus à la vue 3e personne (et inversement). Ignore le 2e événement d'un même toucher."""
    if MP["actif"] or DEVIL["actif"]:    # multijoueur et Devil : la vue du dessus reste imposée
        return
    now = pygame.time.get_ticks()
    if now - VUE["t_bascule"] < 450:
        return
    VUE["t_bascule"] = now
    PARAMS["vue"] = 0 if _v3_actif() else 1
    VUE["look_id"] = None
    if _v3_actif():
        VUE["ang"] = _v3_cap_libre(math.atan2(angle_visée_y, angle_visée_x))
        VUE["cam_d"] = 1.2
        VUE["cam_off"] = 0.0
    sauvegarder_parametres()


def _v3_controle(im):
    """Commandes en 3e personne : le joystick avance/recule (haut/bas) et tourne (gauche/droite). Renvoie dx, dy, visée x, visée y."""
    sx = sy = 0.0
    if joystick_actif:
        vx, vy = manette_x - JOY_CENTRE_X, manette_y - JOY_CENTRE_Y
        d = math.hypot(vx, vy)
        if d > CTRL["dz"]:
            sx, sy = vx / d, vy / d
    if im is not None:
        sx, sy = im
    VUE["ang"] += sx * V3_VIT_TOURNER
    if VUE["look_n"] > 0:
        VUE["look_n"] -= 1
    elif abs(sy) > 0.12 and VUE["look_id"] is None:
        VUE["cam_off"] *= 0.94                                  # en avançant, la caméra revient derrière le soldat
    VUE["lean"] += (sx * 20.0 - VUE["lean"]) * 0.25
    VUE["mv"] += ((1.0 if abs(sy) > 0.12 else 0.0) - VUE["mv"]) * 0.2
    VUE["marche_av"] = VUE["marche"]
    if abs(sy) > 0.12:
        VUE["marche"] += 0.22 * (-sy)
    if sx > 0.25:
        VUE["face"] = 1
    elif sx < -0.25:
        VUE["face"] = -1
    a = VUE["ang"]
    c, s = math.cos(a), math.sin(a)
    f = -sy
    v = joueur_vitesse * _facteur_vitesse()
    if f > 0.12:
        return c * f * v, s * f * v, c, s
    if f < -0.12:
        return c * f * v * 0.6, s * f * v * 0.6, c, s
    return 0, 0, c, s


def _v3_apres_deplacement(x0, y0, dx, dy):
    """Appelée juste après le déplacement réel : les jambes ne marchent plus sur place contre un mur,
    et ralentissent quand le soldat glisse le long d'un mur (la marche suit le vrai déplacement)."""
    voulu = math.hypot(dx, dy)
    if voulu <= 0.0:
        return
    reel = math.hypot(joueur_x - x0, joueur_y - y0)
    k = min(1.0, reel / voulu)
    if k >= 0.98:
        return
    av = VUE.get("marche_av", VUE["marche"])
    VUE["marche"] = av + (VUE["marche"] - av) * k
    VUE["mv"] *= 0.4 + 0.6 * k


def _v3_viser():
    """Visée en 3e personne : tout droit devant, avec une petite aide si un drone ou le boss est presque dans l'axe."""
    a = VUE["ang"]
    hx, hy = math.cos(a), math.sin(a)
    cibles = [(e[0], e[1]) for e in liste_ennemis]
    if boss_actif and not boss_vaincu:
        cibles.append((boss_x, boss_y))
    meilleur, dmin = None, 900.0
    for (x, y) in cibles:
        vx, vy = x - joueur_x, y - joueur_y
        d = math.hypot(vx, vy)
        if d < 8 or d > dmin:
            continue
        if (vx * hx + vy * hy) / d > 0.94:          # environ 20 degrés de chaque côté
            meilleur, dmin = (vx / d, vy / d), d
    return meilleur if meilleur else (hx, hy)


def _v3_preparer_faces():
    """Liste, pour chaque case de mur, les faces visibles (côtés donnant sur un couloir). Refait à chaque nouveau niveau."""
    if VUE["carte"] is CARTE:
        return
    faces = {}
    for j, ligne in enumerate(CARTE):
        for i, val in enumerate(ligne):
            if val != 1:
                continue
            f = []
            if not _v3_mur(i, j - 1):
                f.append((i, j, i + 1, j, 0, 0, -1))
            if not _v3_mur(i, j + 1):
                f.append((i, j + 1, i + 1, j + 1, 0, 0, 1))
            if not _v3_mur(i - 1, j):
                f.append((i, j, i, j + 1, 1, -1, 0))
            if not _v3_mur(i + 1, j):
                f.append((i + 1, j, i + 1, j + 1, 1, 1, 0))
            if f:
                faces[(i, j)] = f
    VUE["faces"] = faces
    VUE["carte"] = CARTE


def _v3_couvert(iv, a, b):
    """Vrai si les colonnes [a, b) de l'écran sont déjà entièrement couvertes par des murs plus proches."""
    for (x, y) in iv:
        if x <= a and y >= b:
            return True
        if x > a:
            break
    return False


def _v3_marquer(iv, a, b):
    nouveau, place = [], False
    for (x, y) in iv:
        if y < a:
            nouveau.append((x, y))
        elif x > b:
            if not place:
                nouveau.append((a, b))
                place = True
            nouveau.append((x, y))
        else:
            a, b = min(a, x), max(b, y)
    if not place:
        nouveau.append((a, b))
    iv[:] = nouveau


def _v3_clip(f1, r1, f2, r2):
    if f1 < V3_NEAR and f2 < V3_NEAR:
        return None
    if f1 < V3_NEAR:
        t = (V3_NEAR - f1) / (f2 - f1)
        r1 = r1 + (r2 - r1) * t
        f1 = V3_NEAR
    elif f2 < V3_NEAR:
        t = (V3_NEAR - f2) / (f1 - f2)
        r2 = r2 + (r1 - r2) * t
        f2 = V3_NEAR
    return f1, r1, f2, r2


def dessiner_vue_3d(t_ms):
    """Dessine tout le monde du jeu en 3e personne (à la place de la vue du dessus). Le HUD est dessiné ensuite comme d'habitude."""
    _v3_preparer_faces()
    animer_skin()
    EW, EH = ecran.get_size()
    t_debut = _time.perf_counter()
    niv = min(2, max(0, QUALITE["niveau"]))
    mode3d = PARAMS.get("qualite3d", 0)
    q = ((0.34, 0.42, 0.5)[niv] * V3_QA[VUE["qa_i"]]) if mode3d == 0 else (0.3, 0.42, 0.55)[mode3d - 1]
    RW, RH = max(160, int(EW * q)), max(90, int(EH * q))
    if VUE["dim"] != (RW, RH):
        VUE["surf"] = pygame.Surface((RW, RH))
        try:
            VUE["surf"] = VUE["surf"].convert()
        except Exception:
            pass
        VUE["dim"] = (RW, RH)
    rs = VUE["surf"]
    focal = min(RW * 0.8, RH * 1.25)
    sec = ETAT_FX["secousse"]
    tremble = random.uniform(-sec, sec) * q * 0.5 if sec > 0 else 0.0
    if VUE["look_id"] is None:
        VUE["pitch"] *= 0.94
    hor = int(RH * (0.36 + VUE["pitch"]) + tremble)
    half = RW * 0.5 + (random.uniform(-sec, sec) * q * 0.5 if sec > 0 else 0.0)

    px, py = joueur_x / TAILLE_CASE, joueur_y / TAILLE_CASE
    ang = VUE["ang"] + VUE["cam_off"]                       # cap de la caméra : celui du soldat + ce qu'on a tourné au doigt
    dirx, diry = math.cos(ang), math.sin(ang)
    cible = V3_CAM_D_MAX
    for pas_cam in range(1, 18):                      # on recule pas à pas et on s'arrête avant le premier mur (même très fin)
        dd = pas_cam * 0.1
        if dd > V3_CAM_D_MAX:
            break
        if _v3_bloque(px - dirx * dd, py - diry * dd, 0.14):
            cible = dd - 0.1
            break
    cible = max(0.35, cible)
    if cible < VUE["cam_d"]:
        VUE["cam_d"] = cible
    else:
        VUE["cam_d"] += (cible - VUE["cam_d"]) * 0.2
    cam_d = VUE["cam_d"]
    camx, camy = px - dirx * cam_d, py - diry * cam_d

    cm = tuple(COULEUR_MUR[:3])
    c_ciel = _v3_mix((16, 8, 34), cm, 0.14)
    c_ville = _v3_mix(c_ciel, cm, 0.28)
    c_base = ((_v3_mix(V3_FOND, cm, 0.34), _v3_mix(V3_FOND, cm, 0.24)),
              (_v3_mix(V3_FOND, (150, 45, 95), 0.5), _v3_mix(V3_FOND, (150, 45, 95), 0.38)),
              (_v3_mix(V3_FOND, cm, 0.17), _v3_mix(V3_FOND, cm, 0.11)))
    c_grille = _v3_mix(V3_FOND, cm, 0.38)
    c_fen = (cm, VIOLET_CYBER, JAUNE_CYBER)

    # ciel + ville au loin (défile quand on tourne)
    rs.fill(c_ciel)
    for (a, w, h, fen) in V3_VILLE:
        dxa = ((a - ang + math.pi) % (2 * math.pi)) - math.pi
        if abs(dxa) > 1.3:
            continue
        bx = half + dxa * focal
        bw = w * focal
        bh = h * RH
        rect = (int(bx - bw / 2), int(hor - bh), int(bw), int(bh) + 1)
        pygame.draw.rect(rs, c_ville, rect)
        for (ox_, oy_, ic) in fen:
            pygame.draw.rect(rs, c_fen[ic], (int(rect[0] + ox_ * rect[2]), int(rect[1] + oy_ * rect[3]),
                                             max(1, int(RW * 0.006)), max(1, int(RW * 0.006))))
    pygame.draw.rect(rs, V3_FOND, (0, hor, RW, RH - hor))
    pygame.draw.line(rs, _v3_mix(c_ciel, cm, 0.7), (0, hor), (RW, hor), 1)

    # grille au sol
    R = (-1, 5, 5)[niv]
    ix, iy = int(camx), int(camy)
    for k in range(-R, R + 1):
        for (x1, y1, x2, y2) in ((ix + k, iy - R, ix + k, iy + R), (ix - R, iy + k, ix + R, iy + k)):
            ax, ay = x1 - camx, y1 - camy
            bx2, by2 = x2 - camx, y2 - camy
            c = _v3_clip(ax * dirx + ay * diry, -ax * diry + ay * dirx, bx2 * dirx + by2 * diry, -bx2 * diry + by2 * dirx)
            if c is None:
                continue
            f1, r1, f2, r2 = c
            s1, s2 = focal / f1, focal / f2
            pygame.draw.line(rs, c_grille, (int(half + r1 * s1), int(hor + V3_CAMZ * s1)),
                             (int(half + r2 * s2), int(hor + V3_CAMZ * s2)), 1)

    # murs + objets, triés du plus loin au plus proche
    items = []
    murs = []
    maxd2 = V3_PORTEE * V3_PORTEE
    faces = VUE["faces"]
    ci, cj = int(camx), int(camy)
    Rf = int(V3_PORTEE) + 1
    for j in range(cj - Rf, cj + Rf + 1):
        for i in range(ci - Rf, ci + Rf + 1):
            fl = faces.get((i, j))
            if not fl:
                continue
            for (x1, y1, x2, y2, o, nx, ny) in fl:
                mx = (x1 + x2) * 0.5 - camx
                my = (y1 + y2) * 0.5 - camy
                d2 = mx * mx + my * my
                if d2 > maxd2 or (-mx) * nx + (-my) * ny <= 0:
                    continue
                murs.append((d2, x1, y1, x2, y2, o))

    def ajouter(genre, x, y, extra=None, portee2=maxd2):
        xc, yc = x / TAILLE_CASE, y / TAILLE_CASE
        d2 = (xc - camx) ** 2 + (yc - camy) ** 2
        if d2 <= portee2:
            items.append((d2, 1, (genre, xc, yc, extra)))

    if not partie_perdue and (ETAT_JOUEUR["invuln"] <= 0 or (t_ms // 90) % 2 == 0):
        ajouter(0, joueur_x, joueur_y, None, 1e9)
    for e in liste_ennemis:
        ajouter(1, e[0], e[1])
    if boss_actif and not boss_vaincu:
        ajouter(2, boss_x, boss_y, None, 400.0)
    for b in boules_feu:
        ajouter(3, b[0], b[1], (b[2], b[3]))
    for b in balles:
        ajouter(4, b[0], b[1], (b[2], b[3]))
    for p in liste_potions:
        ajouter(5, p[0], p[1])
    ajouter(6, pos_core_x, pos_core_y, "core")
    ajouter(6, pos_sortie_x, pos_sortie_y, "sortie")
    for o in ondes_fx:
        ajouter(7, o[0], o[1], o)
    for p in particules_fx[:40]:
        ajouter(8, p[0], p[1], p)
    if POUV.get("cfg"):
        for o in POUV["objets"]:
            ajouter(9, o["x"], o["y"], o)
        for e in POUV["explos"][:]:
            e["n"] -= 1
            if e["n"] <= 0:
                POUV["explos"].remove(e)
                continue
            ajouter(10, e["x"], e["y"], e)
        if POUV.get("ally"):
            ajouter(11, POUV["ally"][0], POUV["ally"][1])
    # murs : du plus proche au plus loin ; on ignore ceux qui sont entièrement cachés derrière un mur plus proche
    murs.sort()
    couv = []
    for (d2, x1, y1, x2, y2, o) in murs:
        ax, ay = x1 - camx, y1 - camy
        bx2, by2 = x2 - camx, y2 - camy
        fa, ra = ax * dirx + ay * diry, -ax * diry + ay * dirx
        fb, rb = bx2 * dirx + by2 * diry, -bx2 * diry + by2 * dirx
        c = _v3_clip(fa, ra, fb, rb)
        if c is None:
            continue
        f1, r1, f2, r2 = c
        s1, s2 = focal / f1, focal / f2
        X1, X2 = half + r1 * s1, half + r2 * s2
        xa, xb = max(0, int(min(X1, X2))), min(RW, int(max(X1, X2)) + 1)
        if xb <= xa or _v3_couvert(couv, xa, xb):
            continue
        _v3_marquer(couv, xa, xb)
        poly = [(int(X1), int(hor - (V3_MUR_H - V3_CAMZ) * s1)), (int(X2), int(hor - (V3_MUR_H - V3_CAMZ) * s2)),
                (int(X2), int(hor + V3_CAMZ * s2)), (int(X1), int(hor + V3_CAMZ * s1))]
        un = (V3_NEAR - fa) / (fb - fa) if fb != fa else 0.0
        t0 = 0.0 if fa >= V3_NEAR else un
        t1 = 1.0 if fb >= V3_NEAR else un
        items.append((d2, 0, (poly, o, fa, ra, fb, rb, t0, t1, x1, y1, x2, y2)))
        if len(couv) == 1 and couv[0][0] <= 0 and couv[0][1] >= RW:
            break
    items.sort(key=lambda it: -it[0])

    c_laser, c_traine = LASER["main"], LASER["trail"]
    for (d2, genre_item, data) in items:
        if genre_item == 0:
            poly, o, fa, ra, fb, rb, t0, t1, wx1, wy1, wx2, wy2 = data
            k = min(1.0, math.sqrt(d2) / V3_PORTEE) * 0.85
            style = _v3_style((int(min(wx1, wx2)) // 3, int(min(wy1, wy2)) // 3, o))
            pygame.draw.polygon(rs, _v3_mix(c_base[style][o], V3_FOND, k), poly)
            detail = 2 if d2 < 16.0 else (1 if d2 < 40.0 else 0)
            if niv == 0 and detail > 1:
                detail = 1
            seed = (int(wx1) * 7349 + int(wy1) * 1931 + o * 17 + int(wx2) * 13) & 0xFFFF
            _v3_decor(rs, style, detail, k, cm, fa, ra, fb, rb, t0, t1, half, hor, focal, seed)
            if d2 < 20.0:
                pygame.draw.polygon(rs, _v3_mix(cm, V3_FOND, k), poly, 1)
            continue

        genre, x, y, extra = data
        ax, ay = x - camx, y - camy
        f = ax * dirx + ay * diry
        if f < 0.25:
            continue
        r = -ax * diry + ay * dirx
        if genre == 0 and f < 1.9:
            f = 1.9                                  # le personnage reste bien visible même si la caméra est collée à un mur
        s = focal / f
        sx = half + r * s
        if sx < -RW * 0.4 or sx > RW * 1.4:
            continue
        yb = hor + V3_CAMZ * s
        isx = int(sx)

        if genre == 0:      # le joueur, vu de dos
            w = 0.17 * s
            cle_sk = _skin_courant or ""
            dos, exact, _nom = _v3_dos(cle_sk)
            hd = _v3_perso_hd()
            tir_on = bool(tir_maintenu or _in_tir())
            VUE["vise"] += ((1.0 if tir_on else 0.0) - VUE["vise"]) * (0.35 if tir_on else 0.07)
            aim = dos is not None and VUE["vise"] > 0.5 and _v3_dos_tir(cle_sk) is not None     # image « en train de tirer », si elle existe
            atlas = _v3_atlas(cle_sk)
            exact_a = bool(atlas[1]) if atlas else False
            cal = None
            if dos is not None and atlas is None:
                try:
                    cal = _v3_calques(cle_sk, 0.95 * s, aim)
                except Exception as e:                   # sécurité : si l'animation échoue, on revient au soldat dessiné par le code
                    print("[3D] animation du personnage indisponible :", e)
                    VUE["dos"][cle_sk or "defaut"] = (None, False, "")
            if atlas is not None:                        # les VRAIES vues du soldat : on voit son bon côté selon l'angle de la caméra
                try:
                    phi = (-VUE["cam_off"] + math.pi) % (2 * math.pi) - math.pi            # cap du soldat par rapport à la caméra (0 = de dos)
                    ap = abs(phi)
                    droite = phi >= 0.0
                    fr = 0 if ap < 0.30 else (1 if ap < 0.82 else (2 if ap < 1.31 else (3 if ap < 2.36 else 4)))
                    if fr == 0 and VUE["vise"] > 0.5:         # de dos, au tir : il tourne un peu les épaules pour montrer le fusil pointé devant
                        fr, droite = 1, VUE["face"] >= 0
                    miroir = (not droite) and fr != 0
                    img = _v3_cadre(cle_sk, atlas, fr, miroir, 0.96 * s)
                    cw_, ch_ = img.get_size()
                    mv, ph = VUE["mv"], VUE["marche"]
                    cs, sn = math.cos(ph), math.sin(ph)
                    ts = t_ms / 1000.0
                    nbb = len(balles)
                    if nbb > VUE["nb"]:
                        VUE["kick"] = 1.0                      # nouveau projectile : le soldat tire
                    VUE["nb"] = nbb
                    kick = VUE["kick"]
                    VUE["kick"] *= 0.86
                    bob = ((0.5 - 0.5 * math.cos(2 * ph)) * 0.020 * s * mv) + math.sin(ts * 2.3) * 0.004 * s * (1.0 - mv)      # rebond à chaque pas, respiration à l'arrêt
                    sway = cs * 0.012 * s * mv
                    roll = -2.4 * cs * mv + VUE["lean"] * 0.10
                    dirf = (1 if droite else -1) if fr != 0 else 0
                    ix = int(sx - cw_ / 2 + sway - dirf * 0.030 * s * kick)                  # recul au tir : en arrière par rapport à la direction du fusil
                    iy = int(yb + 0.02 * s - V3_ATLAS_SEMELLES * ch_ - bob + (0.02 * s * kick if fr in (0, 4) else 0.0))
                    # --- ombres
                    for (r_, f_) in ((1.0, 0.30), (0.78, 0.5), (0.55, 0.72)):
                        pygame.draw.ellipse(rs, _v3_mix(V3_FOND, (3, 5, 12), f_), (int(sx - 0.30 * s * r_), int(yb - 0.045 * s * r_), int(0.60 * s * r_), max(2, int(0.13 * s * r_))))
                    tmur = None
                    for pas_m in range(2, 11):
                        tm = pas_m * 0.15
                        if _v3_bloque(px + dirx * tm, py + diry * tm, 0.1):
                            tmur = tm
                            break
                    if tmur is not None:                        # ombre sur le mur derrière lui : il ne « colle » plus au mur
                        ks = ("sil", cle_sk or "defaut", fr, miroir, int(0.96 * s) // 6)
                        sil = VUE["cadres"].get(ks)
                        if sil is None:
                            try:
                                sil = img.copy()
                                sil.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
                            except Exception:
                                sil = False
                            VUE["cadres"][ks] = sil
                        if sil:
                            try:
                                sil.set_alpha(int(140 * (1.0 - tmur / 1.55)))
                                rs.blit(sil, (ix + int(0.05 * s), iy - int(0.015 * s)))
                            except Exception:
                                pass
                    # --- le soldat, légèrement balancé quand il marche
                    ar = max(-4, min(4, int(round(roll))))
                    surf, ox, oy = img, 0.0, 0.0
                    if ar != 0:
                        kt = (cle_sk or "defaut", fr, miroir, int(0.96 * s) // 6, ar)
                        kc = VUE["tours"].get(kt)
                        if kc is None:
                            if len(VUE["tours"]) > 30:
                                VUE["tours"].clear()
                            kc = _v3_tourner(img, float(ar), (cw_ / 2.0, V3_ATLAS_SEMELLES * ch_))
                            VUE["tours"][kt] = kc
                        surf, ox, oy = kc
                    if not exact_a:                              # skin sans vues propres : aura de la couleur du skin autour du soldat de base
                        aura = (_v3_coul_perso(hd, VUE["perso_cle"])["halo"] if hd is not None else None) or c_laser
                        pygame.draw.ellipse(rs, _v3_mix(V3_FOND, aura, 0.7), (isx - int(0.36 * s), iy + int(0.03 * s), int(0.72 * s), int(0.95 * s)), 2)
                    rs.blit(surf, (int(ix + ox), int(iy + oy)))
                    fx_, fy_ = V3_ATLAS_BOUCHES[fr]
                    if miroir:
                        fx_ = 1.0 - fx_
                    bout = (ix + int(fx_ * cw_), iy + int(fy_ * ch_))
                    # --- poussière des pas
                    cprev = VUE["cos_prev"]
                    if mv > 0.4 and ((cprev > 0.0 >= cs) or (cprev < 0.0 <= cs)):
                        for _ in range(4):
                            VUE["dust"].append([random.choice((-0.11, 0.11)), 0.0, random.uniform(-0.25, 0.25), random.uniform(-0.45, -0.15), 1.0])
                    VUE["cos_prev"] = cs
                    for pd in VUE["dust"][:]:
                        pd[0] += pd[2] * 0.04
                        pd[1] += pd[3] * 0.04
                        pd[3] += 0.03
                        pd[4] -= 0.06
                        if pd[4] <= 0.0:
                            VUE["dust"].remove(pd)
                            continue
                        pygame.draw.circle(rs, _v3_mix(V3_FOND, (120, 130, 150), 0.55 * pd[4]), (int(sx + pd[0] * s), int(yb + pd[1] * s)), max(1, int(0.022 * s * (1.4 - pd[4]))))
                except Exception as e:                   # sécurité : si les vues échouent, on revient à l'animation de repli
                    print("[3D] vues du soldat indisponibles :", e)
                    VUE["atlas"][cle_sk or "defaut"] = None
                    bout = (isx, int(yb - 0.5 * s))
            elif cal is not None:                        # (repli) soldat de dos découpé en squelette
                C = cal
                cw, ch = C["dim"]
                ys, yk, cxm = C["ys"], C["yk"], C["cx"]
                ix = int(sx - cw / 2)
                iy = int(yb - ch + 0.02 * s)                                           # les semelles touchent le sol
                mv, ph = VUE["mv"], VUE["marche"]
                cs, sn = math.cos(ph), math.sin(ph)
                ts = t_ms / 1000.0
                # tir : à chaque nouveau projectile, le corps recule
                nbb = len(balles)
                if nbb > VUE["nb"]:
                    VUE["kick"] = 1.0
                VUE["nb"] = nbb
                kick = VUE["kick"]
                VUE["kick"] *= 0.86
                # --- le corps : rebond (2 fois par cycle), transfert du poids, roulis, respiration à l'arrêt, recul au tir
                bob = ((0.5 - 0.5 * math.cos(2 * ph)) * 0.016 * s * mv) + math.sin(ts * 2.3) * 0.0035 * s * (1.0 - mv)
                sway = cs * 0.013 * s * mv
                roll = -2.4 * cs * mv + VUE["lean"] * 0.10 + kick * 2.2 + math.sin(ts * 1.7) * 0.5 * (1.0 - mv)
                hy0 = iy - bob + 0.028 * s * kick
                bobh = bob * 0.6
                # --- ombres
                for (r_, f_) in ((1.0, 0.30), (0.78, 0.5), (0.55, 0.72)):
                    pygame.draw.ellipse(rs, _v3_mix(V3_FOND, (3, 5, 12), f_), (int(sx - 0.30 * s * r_), int(yb - 0.045 * s * r_), int(0.60 * s * r_), max(2, int(0.13 * s * r_))))
                # ombre du personnage sur le mur devant lui (lui donne du relief quand il est près d'un mur)
                tmur = None
                for pas_m in range(2, 11):
                    tm = pas_m * 0.15
                    if _v3_bloque(px + dirx * tm, py + diry * tm, 0.1):
                        tmur = tm
                        break
                if tmur is not None and C["sil"] is not None:
                    try:
                        C["sil"].set_alpha(int(140 * (1.0 - tmur / 1.55)))
                        rs.blit(C["sil"], (ix + int(0.05 * s), iy - int(0.015 * s)))
                    except Exception:
                        pass
                # --- les jambes : cuisse + tibia/botte ; la jambe en l'air se plie, l'autre reste plantée au sol
                for (cote, sgn) in (("g", 1), ("d", -1)):
                    cj = cs * sgn
                    z = sn * sgn
                    lev = max(0.0, cj) ** 0.8
                    D = (0.055 * z + 0.080 * lev) * s * mv                              # la botte monte à l'écran (loin devant ou levée)
                    Dn = max(-0.045 * s, D) - bobh
                    x0 = ix + (0 if cote == "g" else cxm) + int((-1 if cote == "g" else 1) * 0.012 * s * lev * mv)
                    ytop = int(iy + ys - bobh)
                    cu0, ti0 = C["c" + cote], C["t" + cote]
                    hc = max(4, int(cu0.get_height() - 0.3 * Dn))
                    ht = max(4, int(ti0.get_height() - 0.7 * Dn))
                    rs.blit(pygame.transform.scale(cu0, (cu0.get_width(), hc)), (x0, ytop))
                    rs.blit(pygame.transform.scale(ti0, (ti0.get_width(), ht)), (x0, ytop + hc - 2))
                    # ombre sous la botte : plus petite et plus claire quand elle est levée
                    bx = int(sx + (-1 if cote == "g" else 1) * V3_BOTTES * cw)
                    fb = max(0.35, 1.0 - 0.6 * lev * mv)
                    pygame.draw.ellipse(rs, _v3_mix(V3_FOND, (3, 5, 12), 0.88 * fb + 0.1), (bx - int(0.085 * s * fb), int(yb - 0.015 * s), int(0.17 * s * fb), max(2, int(0.045 * s * fb))))
                    # poussière quand le pied se pose
                    cprev = VUE["cos_prev"] * sgn
                    if mv > 0.4 and cprev > 0.0 >= cj:
                        for _ in range(4):
                            VUE["dust"].append([(bx - sx) / s, 0.0, random.uniform(-0.25, 0.25), random.uniform(-0.45, -0.15), 1.0])
                VUE["cos_prev"] = cs
                # --- le haut du corps (tourné autour du bassin), puis le fusil
                haut = C["haut"]
                pivot = (cw / 2.0, 0.62 * ch)
                ar = round(roll * 2.0) / 2.0
                ar = max(-9.0, min(9.0, ar))
                if abs(ar) >= 0.5:
                    kc = C["rot"].get(ar)
                    if kc is None:
                        if len(C["rot"]) > 40:
                            C["rot"].clear()
                        kc = _v3_tourner(haut, ar, pivot)
                        C["rot"][ar] = kc
                    surf, ox, oy = kc
                else:
                    surf, ox, oy = haut, 0.0, 0.0
                hx, hy = int(ix + sway + ox), int(hy0 + oy)
                rs.blit(surf, (hx, hy))
                bout = (hx + int(cw * 0.02), hy + int(ch * 0.2))
                if C["canon"] is not None:               # le canon se raccourcit quand il tire : l'arme se tourne vers l'avant
                    xb, ya, chh = C["geom"]
                    f = 1.0 - 0.78 * VUE["vise"]
                    cc = C["canon"] if f > 0.98 else pygame.transform.scale(C["canon"], (max(2, int(xb * f)), chh))
                    cox = xb - cc.get_width()
                    if abs(ar) >= 0.5:
                        cc, ox2, oy2 = _v3_tourner(cc, ar, (pivot[0] - cox, pivot[1] - ya))
                    else:
                        ox2, oy2 = 0.0, 0.0
                    rs.blit(cc, (int(ix + sway + cox + ox2), int(hy0 + ya + oy2)))
                    a_ = math.radians(ar)
                    vx_, vy_ = (cox + 2) - pivot[0], (ya + chh / 2.0) - pivot[1]
                    bout = (int(ix + sway + pivot[0] + vx_ * math.cos(a_) + vy_ * math.sin(a_)),
                            int(hy0 + pivot[1] - vx_ * math.sin(a_) + vy_ * math.cos(a_)))
                elif aim:
                    bout = (isx, hy + int(ch * 0.22))
                if not exact and not aim:                # skin sans image propre : aura de la couleur du skin autour du soldat de base
                    aura = (_v3_coul_perso(hd, VUE["perso_cle"])["halo"] if hd is not None else None) or c_laser
                    pygame.draw.ellipse(rs, _v3_mix(V3_FOND, aura, 0.7), (isx - int(0.36 * s), iy + int(0.03 * s), int(0.72 * s), int(0.95 * s)), 2)
                # --- poussière des pas
                for pd in VUE["dust"][:]:
                    pd[0] += pd[2] * 0.04
                    pd[1] += pd[3] * 0.04
                    pd[3] += 0.03
                    pd[4] -= 0.06
                    if pd[4] <= 0.0:
                        VUE["dust"].remove(pd)
                        continue
                    pygame.draw.circle(rs, _v3_mix(V3_FOND, (120, 130, 150), 0.55 * pd[4]), (int(sx + pd[0] * s), int(yb + pd[1] * s)), max(1, int(0.022 * s * (1.4 - pd[4]))))
            elif hd is not None:
                pygame.draw.ellipse(rs, (5, 8, 20), (int(sx - 0.22 * s), int(yb - 0.03 * s), int(0.44 * s), max(2, int(0.08 * s))))
                _v3_soldat(rs, sx, yb, s, _v3_coul_perso(hd, VUE["perso_cle"]), VUE["marche"], c_laser)
                bout = (isx, int(yb - 0.5 * s))
            else:
                pygame.draw.ellipse(rs, (5, 8, 20), (int(sx - 0.22 * s), int(yb - 0.03 * s), int(0.44 * s), max(2, int(0.08 * s))))
                pygame.draw.polygon(rs, BLEU_CYBER, [(int(sx - w), int(yb)), (int(sx + w), int(yb)),
                                                     (int(sx + w * 0.75), int(yb - 0.5 * s)), (int(sx - w * 0.75), int(yb - 0.5 * s))])
                pygame.draw.line(rs, c_laser, (isx, int(yb - 0.46 * s)), (isx, int(yb - 0.06 * s)), max(1, int(0.03 * s)))
                pygame.draw.circle(rs, BLANC_NEON, (isx, int(yb - 0.62 * s)), max(2, int(0.11 * s)))
                pygame.draw.rect(rs, c_laser, (int(sx + w * 0.75), int(yb - 0.52 * s), max(2, int(0.05 * s)), max(2, int(0.28 * s))))
                bout = (isx, int(yb - 0.5 * s))
            if (tir_maintenu or _in_tir()) and ((t_ms // 80) % 2 == 0 or VUE["kick"] > 0.4):
                pygame.draw.circle(rs, c_laser, bout, max(2, int((0.05 + 0.05 * VUE["kick"]) * s)))
                pygame.draw.circle(rs, BLANC_NEON, bout, max(1, int((0.03 + 0.035 * VUE["kick"]) * s)))
            if ETAT_JOUEUR["bouclier"] > 0:
                pygame.draw.circle(rs, c_laser, (isx, int(yb - 0.34 * s)), max(3, int(0.55 * s)), 2)
            if POUV.get("t_phase", 0) > 0:
                pygame.draw.circle(rs, COUL_ACTION["fantome"], (isx, int(yb - 0.34 * s)), max(3, int(0.5 * s)), 2)
        elif genre == 1:    # drone
            cyy = hor + (V3_CAMZ - (0.55 + math.sin(t_ms / 200.0 + x * 3) * 0.04)) * s
            rad = max(2, int(0.2 * s))
            pygame.draw.ellipse(rs, (5, 8, 20), (int(sx - 0.2 * s), int(yb - 0.03 * s), int(0.4 * s), max(2, int(0.07 * s))))
            spr = _v3_plat("drone", _v3_image("drone__23_-removebg-preview.png"), 0.5 * s, 0.6, 0)
            if spr is not None:
                rs.blit(spr, (isx - spr.get_width() // 2, int(cyy - spr.get_height() / 2)))
                pygame.draw.circle(rs, ROUGE_ALERTE, (isx, int(cyy)), max(1, int(0.045 * s)))      # voyant rouge : on repère les ennemis
            else:
                pygame.draw.circle(rs, ROUGE_ALERTE, (isx, int(cyy)), rad)
                pygame.draw.line(rs, (255, 179, 192), (int(sx - 0.34 * s), int(cyy - 0.2 * s)), (int(sx + 0.34 * s), int(cyy - 0.2 * s)), max(1, int(0.04 * s)))
                pygame.draw.circle(rs, CYAN_NEON, (isx, int(cyy)), max(1, rad // 3))
        elif genre == 2:    # boss
            cyy = int(hor + (V3_CAMZ - 0.85) * s)
            rad = max(4, int(0.85 * s))
            pulse = 0.65 + 0.35 * math.sin(t_ms / 260.0)
            coul = ROUGE_ALERTE if boss_vie < boss_vie_max * 0.3 else VIOLET_CYBER
            pygame.draw.ellipse(rs, (5, 8, 20), (int(sx - 0.8 * s), int(yb - 0.05 * s), int(1.6 * s), max(2, int(0.14 * s))))
            vbx, vby = joueur_x / TAILLE_CASE - x, joueur_y / TAILLE_CASE - y
            cap = math.degrees(math.atan2(vbx * dirx + vby * diry, -vbx * diry + vby * dirx)) + 90        # le dragon regarde vers le joueur
            spr = _v3_plat("boss", _v3_image("boss.png"), min(2.0 * s, RW * 0.8), 0.7, cap, 8)
            if spr is not None:
                if boss_vie < boss_vie_max * 0.3:
                    pygame.draw.ellipse(rs, ROUGE_ALERTE, (isx - spr.get_width() // 2, cyy - spr.get_height() // 2, spr.get_width(), spr.get_height()), 2)
                rs.blit(spr, (isx - spr.get_width() // 2, cyy - spr.get_height() // 2))
            else:
                pygame.draw.circle(rs, _v3_mix(V3_FOND, coul, 0.55), (isx, cyy), rad)
                pygame.draw.circle(rs, _v3_mix(coul, BLANC_NEON, pulse * 0.5), (isx, cyy), rad, max(2, int(0.06 * s)))
                pygame.draw.circle(rs, ROUGE_ALERTE, (isx, cyy), max(2, int(0.28 * s)))
                pygame.draw.circle(rs, BLANC_NEON, (isx, cyy), max(1, int(0.1 * s)))
        elif genre == 3:    # boule de feu du boss
            cyy = int(hor + (V3_CAMZ - 0.5) * s)
            pygame.draw.circle(rs, ORANGE_MEC, (isx, cyy), max(2, int((0.18 + 0.03 * math.sin(t_ms / 90.0)) * s)))
            pygame.draw.circle(rs, JAUNE_CYBER, (isx, cyy), max(1, int(0.09 * s)))
        elif genre == 4:    # laser du joueur
            cyy = int(hor + (V3_CAMZ - 0.55) * s)
            xa, ya = x - extra[0] * 0.025, y - extra[1] * 0.025
            fa = (xa - camx) * dirx + (ya - camy) * diry
            if fa > 0.2:
                ra = -(xa - camx) * diry + (ya - camy) * dirx
                sa = focal / fa
                pygame.draw.line(rs, c_traine, (int(half + ra * sa), int(hor + (V3_CAMZ - 0.55) * sa)), (isx, cyy), max(2, int(0.06 * s)))
            pygame.draw.circle(rs, c_laser, (isx, cyy), max(1, int(0.05 * s)))
        elif genre == 5:    # potion de temps
            cyy = int(hor + (V3_CAMZ - (0.38 + 0.05 * math.sin(t_ms / 250.0))) * s)
            pygame.draw.circle(rs, JAUNE_CYBER, (isx, cyy), max(2, int(0.2 * s)))
            pygame.draw.circle(rs, V3_FOND, (isx, cyy), max(1, int(0.11 * s)))
        elif genre == 6:    # faisceau du core / de la sortie (visible au-dessus des murs)
            if extra == "core":
                coul = ROUGE_ALERTE if (boss_actif and not boss_vaincu) else (VERT_FLUO if hack_reussi else VIOLET_CYBER)
            else:
                coul = VERT_FLUO if hack_reussi else ROUGE_ALERTE
            p = 0.55 + 0.45 * math.sin(t_ms / 300.0)
            wb = max(2, int((0.16 + 0.05 * p) * s))
            haut = int(hor - (2.4 - V3_CAMZ) * s)
            pygame.draw.rect(rs, _v3_mix(V3_FOND, coul, 0.35 + 0.25 * p), (isx - wb, haut, wb * 2, int(yb) - haut))
            pygame.draw.rect(rs, coul, (isx - max(1, wb // 4), haut, max(2, wb // 2), int(yb) - haut))
            pygame.draw.ellipse(rs, coul, (int(sx - 0.45 * s), int(yb - 0.08 * s), int(0.9 * s), max(2, int(0.16 * s))), 2)
        elif genre == 7:    # onde de choc
            a = extra[5] / float(extra[6])
            pygame.draw.circle(rs, _v3_mix(V3_FOND, extra[4], a), (isx, int(hor + (V3_CAMZ - 0.4) * s)),
                               max(2, int(extra[2] / TAILLE_CASE * s)), max(1, int(3 * a)))
        elif genre == 8:    # particule
            a = extra[4] / float(extra[5])
            pygame.draw.circle(rs, _v3_mix(V3_FOND, extra[6], a), (isx, int(hor + (V3_CAMZ - 0.45) * s)), max(1, int(extra[7] * 0.015 * s * (0.5 + a))))
        elif genre == 9:    # grenade / roquette
            cyy = int(hor + (V3_CAMZ - 0.45) * s)
            if extra["t"] == "gren":
                prog = 1.0 - extra["n"] / float(extra["n0"])
                cyy = int(hor + (V3_CAMZ - (0.2 + math.sin(math.pi * prog) * 0.9)) * s)
                pygame.draw.circle(rs, (90, 110, 60), (isx, cyy), max(2, int(0.1 * s)))
            else:
                pygame.draw.circle(rs, ORANGE_MEC, (isx, cyy), max(2, int(0.12 * s)))
                pygame.draw.circle(rs, BLANC_NEON, (isx, cyy), max(1, int(0.05 * s)))
        elif genre == 10:   # explosion de pouvoir
            prog = 1.0 - extra["n"] / float(extra["n0"])
            pygame.draw.circle(rs, _v3_mix(V3_FOND, extra["c"], 1.0 - prog * 0.6), (isx, int(hor + (V3_CAMZ - 0.4) * s)),
                               max(2, int(extra["r"] / TAILLE_CASE * (0.25 + 0.75 * prog) * s)), max(2, int(0.08 * s * (1.0 - prog))))
        elif genre == 11:   # drone allié
            cyy = int(hor + (V3_CAMZ - 0.6) * s)
            pygame.draw.circle(rs, (30, 40, 58), (isx, cyy), max(2, int(0.13 * s)))
            pygame.draw.circle(rs, CYAN_NEON, (isx, cyy), max(1, int(0.06 * s)))
            pygame.draw.line(rs, (150, 200, 230), (int(sx - 0.22 * s), int(cyy - 0.1 * s)), (int(sx + 0.22 * s), int(cyy - 0.1 * s)), max(1, int(0.03 * s)))

    if VUE["scale_ok"]:
        try:
            pygame.transform.scale(rs, (EW, EH), ecran)
        except Exception:
            VUE["scale_ok"] = False
    if not VUE["scale_ok"]:
        if VUE["tmp"] is None or VUE["tmp"].get_size() != (EW, EH):
            VUE["tmp"] = pygame.Surface((EW, EH))
            try:
                VUE["tmp"] = VUE["tmp"].convert()
            except Exception:
                pass
        pygame.transform.scale(rs, (EW, EH), VUE["tmp"])
        ecran.blit(VUE["tmp"], (0, 0))

    # auto-réglage : si le dessin 3D est trop lent, la résolution baisse (et remonte si le téléphone suit)
    VUE["ema"] += ((_time.perf_counter() - t_debut) * 1000.0 - VUE["ema"]) * 0.12
    VUE["cool"] -= 1
    if VUE["cool"] <= 0 and mode3d == 0:
        if VUE["ema"] > 17.0 and VUE["qa_i"] < len(V3_QA) - 1:
            VUE["qa_i"] += 1
            VUE["cool"], VUE["ema"] = 40, 14.0
        elif VUE["ema"] < 8.0 and VUE["qa_i"] > 0:
            VUE["qa_i"] -= 1
            VUE["cool"], VUE["ema"] = 150, 12.0
# ===== VUE 3E PERSONNE FIN


async def main():
    global DRAW, ECHELLE, _cache_boss, _cache_drones, _cible, _dt_logique, _echelle_active, _ecoule, _ecran_reel, _k_logique, _maintenant, _pas, _tm0, _tm1, _tm2, _tm3, ang, ang_drone, ang_orbite, ang_q, angle_affichage_boss, angle_arrondi_boss, angle_boss, angle_visée_x, angle_visée_y, astuce, b, bh, boss_angle_precedent, boss_fx_faite, boss_surface_cache, boss_vaincu, boss_vie, boss_x, boss_y, boule, bw, bx, bx0, bx_e, bx_ecran, by, by0, by_e, by_ecran, case, cbx, cby, centre_avatar, cfx, cfy, ci, cible, clic_detecte, clic_x, clic_y, clignote, col_sortie, colonne_max, colonne_min, core_accessible, couleur_aura_boss, couleur_bordure, couleur_ligne, couleur_lueur_core, couleur_node, couleur_timer, curseur, cx, cy, d, d_boss, d_rep, db, decal_x, decal_y, defil_max, defilement_niveaux, delai_max, delai_min, demi, dernier_x_glissement_niveaux, dir_x, dir_y, dist, dist_dir, dist_min, drone_rot, dx, dy, ecran, en_pause, ennemis_restants_a_spawner, espacement_infos, est_boss_node, etat_actuel, event, ex, ex_spawn, ey_spawn, fps_bas_consecutifs, frames_total, fx_ecran, fy_ecran, glissement_niveaux_actif, gris_credit, hack_reussi, haut_piste, hauteur_contenu, hauteur_visible, id_touch_joystick, id_touch_tir, idx, idx_max_affiche, idx_max_clic, idx_min_affiche, idx_min_clic, img_joueur_actuel, index_nationalite, indication_niveaux, indice, info_drones, jauge_hack, joueur_x, joueur_y, joystick_actif, jx_e, jy_e, k_cadre, k_seg, k_traine, largeur_barre_boss, largeur_rempli, largeur_v, lc, lg, li, ligne_max, ligne_min, lignes, lignes_infos, lint, long_piste, long_pouce, lr, lueurs, lx, ly, manette_x, manette_y, masque, message_defaite, minuteur_cadence_tir, minuteur_potion, minuteur_spawn, minuteur_tir_boss, mort_fx_faite, ms, musique_lancee, nb_colonnes_carte, nb_lignes_carte, niveau_max_atteint, niveau_sauvegarde_affichage, ombres_actives, ox, oy, p_core, p_sortie, panneau_largeur, panneau_x, partie_gagnee, partie_perdue, pas, photo_profil_surface, points_chemin, police_l, police_texte, potion, pulsation, pulsation_feu, pulsation_node, pulse_boss, px_ecran, px_potion, py_ecran, py_potion, r_bouclier, ratio_vie_boss, rayon_affiche, rect_timer, rx, ry, saisie_pseudo_active, sec, secondes_restantes, surf_nat, surf_pseudo, t_ms, tag, tag_boss, tb, temps_restant_frames, texte_ligne, texte_node, texte_pseudo, texte_timer, th_hack, ti, ti_icone, til, tir_maintenu, tirer_balle, tl, tn, tp, tp5, txt_vie_boss, type_glissement_niveaux, victoire_fx_faite, vitesse_deplacement_boss, vx, vy, x_actuel_glissement, x_barre, x_barre_boss, x_node, x_node_clic, x_v, xk, y_depart_infos, y_node, y_node_clic, y_nouveau, y_pouce, y_zone, yy
    await ecran_de_demarrage()
    await ecran_connexion()
    _cache_drones = {}
    _cache_boss = {}
    frames_total = 0
    fps_bas_consecutifs = 0
    mort_fx_faite = False
    victoire_fx_faite = False
    boss_fx_faite = False

    # LOOP
    while True:
        await asyncio.sleep(0)
        _tm0 = _time.perf_counter()
        dx, dy = 0, 0
        clic_detecte, tirer_balle = False, False
        clic_x, clic_y = 0, 0
        _in_frame()

        for event in list(pygame.event.get()) + _in_evenements():
            if TRANS["actif"] and event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN, pygame.MOUSEMOTION,
                                                  pygame.FINGERMOTION, pygame.TEXTINPUT, pygame.KEYDOWN):
                continue
            if etat_actuel == ETAT_PARC and ARENE["actif"]:
                arene_evenement(event)
            if event.type == pygame.FINGERDOWN:
                IN["src"] = "touch"
                IN["t_doigt"] = pygame.time.get_ticks()
            elif event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN) and not getattr(event, "synth", False):
                # une vraie souris (les touchers génèrent aussi des événements de souris : on les ignore)
                if not getattr(event, "touch", False) and pygame.time.get_ticks() - IN.get("t_doigt", -9999) > 1500:
                    IN["src"] = "mouse"
                    IN["souris_ok"] = True
                    IN["souris_x"], IN["souris_y"] = pos_ev(event)
            _calibrer_souris(event)
            if event.type == pygame.QUIT:
                EXTRA["_essai"] = 0
                sauvegarder_parametres()
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_v and etat_actuel == ETAT_JEU and not partie_gagnee and not partie_perdue:
                basculer_vue()                               # touche V : vue du dessus <-> 3e personne
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3 and etat_actuel == ETAT_JEU and _v3_actif() and not en_pause:
                VUE["look_id"] = "souris"                    # PC : clic droit maintenu + déplacement = tourner la caméra
                VUE["look_x"], VUE["look_y"] = pos_ev(event)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
                if VUE["look_id"] == "souris":
                    VUE["look_id"] = None
            elif event.type == pygame.MOUSEMOTION and VUE["look_id"] == "souris":
                _lx, _ly = pos_ev(event)
                _v3_regarder(_lx - VUE["look_x"], _ly - VUE["look_y"])
                VUE["look_x"], VUE["look_y"] = _lx, _ly
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                clic_detecte = True
                clic_x, clic_y = pos_ev(event)
                if etat_actuel == ETAT_JEU and rect_bouton_pause.collidepoint(clic_x, clic_y) and not partie_gagnee and not partie_perdue:
                    basculer_pause()
                elif etat_actuel == ETAT_JEU and not partie_gagnee and not partie_perdue and rect_bouton_vue.collidepoint(clic_x, clic_y):
                    basculer_vue()
                elif etat_actuel == ETAT_JEU and not en_pause and not partie_gagnee and not partie_perdue and _toucher_pouvoir(clic_x, clic_y):
                    pass
                elif etat_actuel == ETAT_JEU and not en_pause and rect_tir_tactile.collidepoint(clic_x, clic_y):
                    tirer_balle = True
                    tir_maintenu = True
                    minuteur_cadence_tir = 0
                elif etat_actuel == ETAT_JEU and not en_pause and not partie_gagnee and not partie_perdue and IN["src"] == "mouse" and not getattr(event, "synth", False):
                    tirer_balle = True                       # PC : le clic gauche tire (la visée suit la souris)
                    tir_maintenu = True
                    IN["souris_tir"] = True
                    minuteur_cadence_tir = 0
                elif etat_actuel == ETAT_NIVEAUX:
                    glissement_niveaux_actif = True
                    type_glissement_niveaux = "souris"
                    dernier_x_glissement_niveaux = clic_x
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                tir_maintenu = False
                IN["souris_tir"] = False
                if type_glissement_niveaux == "souris":
                    glissement_niveaux_actif = False
                    type_glissement_niveaux = None
            elif event.type == pygame.MOUSEMOTION and glissement_niveaux_actif and type_glissement_niveaux == "souris":
                defilement_niveaux += pos_ev(event)[0] - dernier_x_glissement_niveaux
                defilement_niveaux = min(0, defilement_niveaux)
                dernier_x_glissement_niveaux = pos_ev(event)[0]
            elif event.type == pygame.FINGERDOWN:
                clic_detecte = True
                clic_x, clic_y = event.x * LARGEUR, event.y * HAUTEUR
                if etat_actuel == ETAT_JEU and not partie_gagnee and not partie_perdue:
                    if rect_bouton_pause.collidepoint(clic_x, clic_y):
                        basculer_pause()
                    elif rect_bouton_vue.collidepoint(clic_x, clic_y):
                        basculer_vue()
                    elif not en_pause and _toucher_pouvoir(clic_x, clic_y):
                        pass
                    elif not en_pause and rect_tir_tactile.collidepoint(clic_x, clic_y):
                        tirer_balle = True
                        tir_maintenu = True
                        id_touch_tir = event.finger_id
                        minuteur_cadence_tir = 0
                    elif not en_pause and math.hypot(clic_x - JOY_CENTRE_X, clic_y - JOY_CENTRE_Y) <= JOY_RAYON_SOCLE + 40:
                        joystick_actif, id_touch_joystick = True, event.finger_id
                        placer_manette(clic_x, clic_y)
                    elif not en_pause and _v3_actif() and VUE["look_id"] is None:        # 3e personne : un doigt posé ailleurs fait tourner la caméra
                        VUE["look_id"], VUE["look_x"], VUE["look_y"] = event.finger_id, clic_x, clic_y
                elif etat_actuel == ETAT_NIVEAUX:
                    glissement_niveaux_actif = True
                    type_glissement_niveaux = event.finger_id
                    dernier_x_glissement_niveaux = clic_x
                elif etat_actuel == ETAT_PARC and math.hypot(clic_x - JOY_CENTRE_X, clic_y - JOY_CENTRE_Y) <= JOY_RAYON_SOCLE + 40:
                    joystick_actif, id_touch_joystick = True, event.finger_id
                    placer_manette(clic_x, clic_y)

            elif event.type == pygame.TEXTINPUT and saisie_pseudo_active:
                if len(profil["pseudo"]) < 14:
                    profil["pseudo"] += event.text
            elif event.type == pygame.KEYDOWN and saisie_pseudo_active:
                if event.key == pygame.K_BACKSPACE:
                    profil["pseudo"] = profil["pseudo"][:-1]
                elif event.key == pygame.K_RETURN:
                    saisie_pseudo_active = False
                    pygame.key.stop_text_input()

            if partie_gagnee and clic_detecte and fin_pret():
                if rect_bouton_rejouer.collidepoint(clic_x, clic_y):
                    lancer_transition(("rejouer",), DUREE_CHARGEMENT_RAPIDE)
                elif rect_bouton_suivant.collidepoint(clic_x, clic_y):
                    lancer_transition(("suivant",), DUREE_CHARGEMENT_RAPIDE)

            if partie_perdue and clic_detecte and fin_pret():
                if rect_bouton_rejouer_defaite.collidepoint(clic_x, clic_y):
                    lancer_transition(("rejouer",), DUREE_CHARGEMENT_RAPIDE)
                elif rect_bouton_quitter_defaite.collidepoint(clic_x, clic_y):
                    lancer_transition(("quitter_partie",))

            if en_pause and clic_detecte:
                if rect_pause_continuer.collidepoint(clic_x, clic_y):
                    en_pause = False
                elif rect_pause_rejouer.collidepoint(clic_x, clic_y):
                    lancer_transition(("rejouer",), DUREE_CHARGEMENT_RAPIDE)
                elif rect_pause_params.collidepoint(clic_x, clic_y):
                    lancer_transition(("params", ETAT_JEU), DUREE_CHARGEMENT_RAPIDE)
                elif rect_pause_quitter.collidepoint(clic_x, clic_y):
                    lancer_transition(("quitter_partie",))

            if event.type == pygame.FINGERMOTION and joystick_actif and event.finger_id == id_touch_joystick:
                placer_manette(event.x * LARGEUR, event.y * HAUTEUR)

            if event.type == pygame.FINGERMOTION and VUE["look_id"] is not None and event.finger_id == VUE["look_id"]:
                _lx, _ly = event.x * LARGEUR, event.y * HAUTEUR
                _v3_regarder(_lx - VUE["look_x"], _ly - VUE["look_y"])
                VUE["look_x"], VUE["look_y"] = _lx, _ly

            if event.type == pygame.FINGERMOTION and glissement_niveaux_actif and event.finger_id == type_glissement_niveaux:
                x_actuel_glissement = event.x * LARGEUR
                defilement_niveaux += x_actuel_glissement - dernier_x_glissement_niveaux
                defilement_niveaux = min(0, defilement_niveaux)
                dernier_x_glissement_niveaux = x_actuel_glissement

            if event.type == pygame.FINGERUP and VUE["look_id"] is not None and event.finger_id == VUE["look_id"]:
                VUE["look_id"] = None

            if event.type == pygame.FINGERUP and joystick_actif and event.finger_id == id_touch_joystick:
                joystick_actif, id_touch_joystick = False, None
                manette_x, manette_y = JOY_CENTRE_X, JOY_CENTRE_Y

            if event.type == pygame.FINGERUP and glissement_niveaux_actif and event.finger_id == type_glissement_niveaux:
                glissement_niveaux_actif = False
                type_glissement_niveaux = None

            if event.type == pygame.FINGERUP and event.finger_id == id_touch_tir:
                tir_maintenu = False
                id_touch_tir = None

            # Guide tactique : on fait défiler le texte en glissant le doigt vers le haut / le bas
            if etat_actuel == ETAT_AIDE:
                if event.type == pygame.FINGERDOWN:
                    AIDE["drag"], AIDE["id"], AIDE["y"] = True, event.finger_id, event.y * HAUTEUR
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not AIDE["drag"]:
                    AIDE["drag"], AIDE["id"], AIDE["y"] = True, "souris", pos_ev(event)[1]
                elif event.type == pygame.FINGERMOTION and AIDE["drag"] and event.finger_id == AIDE["id"]:
                    y_nouveau = event.y * HAUTEUR
                    AIDE["scroll"] += y_nouveau - AIDE["y"]
                    AIDE["y"] = y_nouveau
                elif event.type == pygame.MOUSEMOTION and AIDE["drag"] and AIDE["id"] == "souris":
                    AIDE["scroll"] += pos_ev(event)[1] - AIDE["y"]
                    AIDE["y"] = pos_ev(event)[1]
            if (event.type == pygame.MOUSEBUTTONUP and AIDE["id"] == "souris") or \
                    (event.type == pygame.FINGERUP and event.finger_id == AIDE["id"]):
                AIDE["drag"], AIDE["id"] = False, None

            # Écrans à liste (Paramètres, Boutique) : glisser = défiler, toucher = agir
            gerer_liste_tactile(PAR, event, ETAT_PARAMS, traiter_tap_parametres)
            gerer_liste_tactile(BQ, event, ETAT_BOUTIQUE, traiter_tap_boutique)
            gerer_liste_tactile(DEF, event, ETAT_DEFIS, traiter_tap_defis)
            gerer_editeur(event)

        # --- Nombre de pas de logique à effectuer ce tour (temps réel)
        _maintenant = _time.perf_counter()
        _dt_logique = min(0.25, _maintenant - LOGIQUE["t"])
        LOGIQUE["t"] = _maintenant
        _k_logique = 1
        if etat_actuel == ETAT_JEU and not en_pause and not partie_gagnee and not partie_perdue and not TRANS["actif"]:
            LOGIQUE["acc"] += _dt_logique
            _k_logique = max(1, min(4, int(round(LOGIQUE["acc"] / 0.016667))))
            LOGIQUE["acc"] -= _k_logique * 0.016667
            if abs(LOGIQUE["acc"]) > 0.05:
                LOGIQUE["acc"] = 0.0
        else:
            LOGIQUE["acc"] = 0.0
        LOGIQUE["k"] = _k_logique

        # --- Transition en cours : le rideau se ferme, l'action est appliquée derrière l'écran de chargement, puis il s'ouvre
        if TRANS["actif"]:
            _ecoule = pygame.time.get_ticks() - TRANS["t0"]
            if TRANS["phase"] == 0 and _ecoule >= DUREE_COUVRIR * 1000.0:
                TRANS["phase"], TRANS["t0"] = 1, pygame.time.get_ticks()
                _cible = TRANS["cible"]
                TRANS["cible"] = None
                if _cible is not None:
                    if _cible[0] in ("commencer", "parc", "arene", "multi", "niveau"):
                        DEVIL["actif"] = False               # on quitte le mode Devil
                    if DEVIL["musique"] and _cible[0] not in ("rejouer", "suivant", "devil_niveau", "params", "retour_jeu"):
                        devil_musique(False)                 # on quitte les missions : la musique normale revient
                    if _cible[0] == "etat":
                        etat_actuel = _cible[1]
                        if etat_actuel == ETAT_AIDE:
                            AIDE["scroll"], AIDE["drag"], AIDE["id"] = 0.0, False, None
                        elif etat_actuel == ETAT_BOUTIQUE:
                            BQ.update(scroll=0.0, drag=False, id=None, msg="")
                        elif etat_actuel == ETAT_DEFIS:
                            DEF.update(scroll=0.0, drag=False, id=None)
                        elif etat_actuel == ETAT_EDITEUR:
                            ED.update(drag=False, id=None, cible=None, bouton=None, selection=None, mode="deplacer")
                    elif _cible[0] == "parc":
                        parc_demarrer()
                        etat_actuel = ETAT_PARC
                    elif _cible[0] == "arene":
                        arene_demarrer()
                        etat_actuel = ETAT_PARC
                    elif _cible[0] == "multi":
                        mp_chercher_salle()
                        etat_actuel = ETAT_MULTI
                    elif _cible[0] == "params":
                        PAR["origine"], PAR["scroll"], PAR["drag"], PAR["id"] = _cible[1], 0.0, False, None
                        etat_actuel = ETAT_PARAMS
                    elif _cible[0] == "retour_jeu":
                        etat_actuel = ETAT_JEU
                    elif _cible[0] == "commencer":
                        niveau_max_atteint = charger_progression()
                        defilement_niveaux = min(0, LARGEUR / 2 - NIVEAU_MARGE_GAUCHE - niveau_max_atteint * NIVEAU_NODE_ESPACEMENT)
                        etat_actuel = ETAT_NIVEAUX
                    elif _cible[0] == "niveau":
                        reinitialiser_partie(False, niveau_cible=_cible[1])
                        etat_actuel = ETAT_JEU
                        en_pause = False
                        if MUSIQUE_ACTIVE and not musique_lancee:
                            pygame.mixer.music.play(-1)
                            musique_lancee = True
                            appliquer_audio()
                    elif _cible[0] == "devil":
                        devil_ouvrir()
                        defilement_niveaux = min(0, LARGEUR / 2 - NIVEAU_MARGE_GAUCHE - DEVIL["max"] * NIVEAU_NODE_ESPACEMENT)
                        etat_actuel = ETAT_NIVEAUX
                    elif _cible[0] == "devil_niveau":
                        devil_lancer(_cible[1])
                        etat_actuel = ETAT_JEU
                        en_pause = False
                        if MUSIQUE_ACTIVE and not musique_lancee:
                            pygame.mixer.music.play(-1)
                            musique_lancee = True
                            appliquer_audio()
                    elif _cible[0] == "quitter_partie":
                        mp_quitter()
                        reinitialiser_partie(False)
                        DEVIL["actif"] = False
                        etat_actuel = ETAT_MENU
                        en_pause = False
                    elif _cible[0] == "rejouer":
                        reinitialiser_partie(False)
                        en_pause = False
                    elif _cible[0] == "suivant":
                        reinitialiser_partie(not MP["actif"])
                        en_pause = False
            elif TRANS["phase"] == 1 and _ecoule >= TRANS["duree"]:
                TRANS["phase"], TRANS["t0"] = 2, pygame.time.get_ticks()
            elif TRANS["phase"] == 2 and _ecoule >= DUREE_REVELER * 1000.0:
                TRANS["actif"] = False

        if etat_actuel == ETAT_MENU and clic_detecte:
            if rect_bouton_jouer.collidepoint(clic_x, clic_y):
                lancer_transition(("commencer",))
            elif rect_bouton_aide.collidepoint(clic_x, clic_y):
                lancer_transition(("etat", ETAT_AIDE))
            elif rect_bouton_boutique.collidepoint(clic_x, clic_y):
                lancer_transition(("etat", ETAT_BOUTIQUE))
            elif IS_WEB and rect_bouton_multi.collidepoint(clic_x, clic_y):
                lancer_transition(("multi",))
            elif rect_bouton_parc.collidepoint(clic_x, clic_y):
                lancer_transition(("parc",))
            elif rect_icone_profil.collidepoint(clic_x, clic_y):
                lancer_transition(("etat", ETAT_PROFIL))
            elif rect_icone_infos.collidepoint(clic_x, clic_y):
                lancer_transition(("etat", ETAT_INFOS))
            elif rect_icone_defis.collidepoint(clic_x, clic_y):
                lancer_transition(("etat", ETAT_DEFIS))
            elif IS_WEB and rect_icone_classement.collidepoint(clic_x, clic_y):
                _ouvrir_classement()
            elif IS_WEB and rect_icone_skins.collidepoint(clic_x, clic_y):
                _ouvrir_skins()
            elif IS_WEB and _inst_visible and rect_icone_install.collidepoint(clic_x, clic_y):
                _ouvrir_install()
            elif rect_icone_devil.collidepoint(clic_x, clic_y):
                lancer_transition(("devil",))
            elif rect_icone_params.collidepoint(clic_x, clic_y):
                lancer_transition(("params", ETAT_MENU))
        elif etat_actuel == ETAT_NIVEAUX and clic_detecte:
            if rect_retour_niveaux.collidepoint(clic_x, clic_y):
                lancer_transition(("etat", ETAT_MENU))
            else:
                idx_min_clic = max(0, int((-defilement_niveaux - 150) / NIVEAU_NODE_ESPACEMENT))
                idx_max_clic = min(_niv_max() + 30, int((LARGEUR - defilement_niveaux + 150) / NIVEAU_NODE_ESPACEMENT))
                for idx in range(idx_min_clic, idx_max_clic + 1):
                    if idx > _niv_max():
                        continue
                    x_node_clic = NIVEAU_MARGE_GAUCHE + idx * NIVEAU_NODE_ESPACEMENT + defilement_niveaux
                    y_node_clic = HAUTEUR // 2 + int(60 * math.sin(idx * 0.9))
                    if math.hypot(clic_x - x_node_clic, clic_y - y_node_clic) <= NIVEAU_NODE_RAYON + 10:
                        lancer_transition(("devil_niveau" if DEVIL["actif"] else "niveau", idx))
                        break
        elif etat_actuel == ETAT_MULTI and clic_detecte and rect_retour_niveaux.collidepoint(clic_x, clic_y):
            mp_quitter()
            lancer_transition(("etat", ETAT_MENU))
        elif etat_actuel == ETAT_AIDE and clic_detecte and rect_bouton_retour.collidepoint(clic_x, clic_y):
            lancer_transition(("etat", ETAT_MENU))
        elif etat_actuel == ETAT_INFOS and clic_detecte and rect_retour_infos.collidepoint(clic_x, clic_y):
            lancer_transition(("etat", ETAT_MENU))
        elif etat_actuel == ETAT_PROFIL and clic_detecte:
            if rect_champ_pseudo.collidepoint(clic_x, clic_y):
                saisie_pseudo_active = True
                pygame.key.start_text_input()
            elif rect_fleche_gauche.collidepoint(clic_x, clic_y):
                index_nationalite = (index_nationalite - 1) % len(NATIONALITES)
                saisie_pseudo_active = False
                pygame.key.stop_text_input()
            elif rect_fleche_droite.collidepoint(clic_x, clic_y):
                index_nationalite = (index_nationalite + 1) % len(NATIONALITES)
                saisie_pseudo_active = False
                pygame.key.stop_text_input()
            elif rect_recharger_photo.collidepoint(clic_x, clic_y):
                photo_profil_surface = charger_photo_profil()
                saisie_pseudo_active = False
                pygame.key.stop_text_input()
            elif rect_sauvegarder_profil.collidepoint(clic_x, clic_y):
                profil["nationalite"] = NATIONALITES[index_nationalite]
                sauvegarder_profil(profil)
                saisie_pseudo_active = False
                pygame.key.stop_text_input()
            elif rect_retour_profil.collidepoint(clic_x, clic_y):
                saisie_pseudo_active = False
                pygame.key.stop_text_input()
                lancer_transition(("etat", ETAT_MENU))
            else:
                saisie_pseudo_active = False
                pygame.key.stop_text_input()
        elif etat_actuel == ETAT_JEU and not partie_gagnee and not partie_perdue and not en_pause and not TRANS["actif"]:
            # Chaque tour de boucle fait autant de pas de logique (1/60 s) que de temps réellement écoulé : la vitesse du jeu reste normale
            for _pas in range(_k_logique):
                if _pas > 0 and (partie_perdue or partie_gagnee):
                    break
                temps_restant_frames -= 1
                _maj_pouvoirs()
                if ETAT_JOUEUR["invuln"] > 0:
                    ETAT_JOUEUR["invuln"] -= 1
                if temps_restant_frames <= 0:
                    partie_perdue = True
                    message_defaite = "TEMPS ÉCOULÉ"
                    if SON_ACTIF:
                        son_echec.play()

                if niveau_actuel >= NIVEAU_APPARITION_POTIONS and not DEVIL["actif"]:
                    minuteur_potion -= 1
                    if minuteur_potion <= 0 and len(liste_potions) < 3:
                        px_potion, py_potion = position_spawn_potion(CARTE)
                        liste_potions.append([px_potion, py_potion])
                        minuteur_potion = random.randint(300, 600)

                for potion in liste_potions[:]:
                    if math.hypot(joueur_x - potion[0], joueur_y - potion[1]) < (TAILLE_PERSO / 2 + 25):
                        liste_potions.remove(potion)
                        temps_restant_frames = min(temps_restant_frames + BONUS_POTION_FRAMES + STATS["potion"], plafond_temps_frames)

                if ennemis_restants_a_spawner > 0 and not _mp_client():
                    minuteur_spawn -= 1
                    if minuteur_spawn <= 0:
                        ex_spawn, ey_spawn = (_v3_spawn_ennemi() if _v3_actif() else None) or position_spawn_ennemi(CARTE)
                        liste_ennemis.append([ex_spawn, ey_spawn, vitesse_ennemis_niveau, _mp_id()])
                        ennemis_restants_a_spawner -= 1
                        delai_min, delai_max = calcul_delais_spawn(niveau_actuel)
                        minuteur_spawn = random.randint(delai_min, delai_max)

                if joystick_actif and not _v3_actif():
                    vx, vy = manette_x - JOY_CENTRE_X, manette_y - JOY_CENTRE_Y
                    dist = math.hypot(vx, vy)
                    if dist > CTRL["dz"]:
                        dx, dy = (vx / dist) * joueur_vitesse * _facteur_vitesse(), (vy / dist) * joueur_vitesse * _facteur_vitesse()
                        angle_visée_x, angle_visée_y = vx / dist, vy / dist

                        if MODE_GRAPHIQUE == "REALISTE":
                            if vx < -15:
                                img_joueur_actuel = img_joueur_gauche
                            elif vx > 15:
                                img_joueur_actuel = img_joueur_droite

                _im = _in_deplacement()
                if _im is not None and not _v3_actif():      # clavier (ZQSD / WASD / flèches) ou stick gauche
                    dx, dy = _im[0] * joueur_vitesse * _facteur_vitesse(), _im[1] * joueur_vitesse * _facteur_vitesse()
                    angle_visée_x, angle_visée_y = _im[0], _im[1]
                    if MODE_GRAPHIQUE == "REALISTE":
                        if _im[0] < -0.2:
                            img_joueur_actuel = img_joueur_gauche
                        elif _im[0] > 0.2:
                            img_joueur_actuel = img_joueur_droite

                if DEVIL["actif"] and DEVIL["chute"] is not None:
                    dx, dy = 0, 0                          # Devil : le joueur tombe dans le vide
                _v3_x0, _v3_y0 = joueur_x, joueur_y
                if _v3_actif():
                    dx, dy, angle_visée_x, angle_visée_y = _v3_controle(_im)
                if dx != 0 and not check_collision_murs(joueur_x + dx, joueur_y):
                    joueur_x += dx
                if dy != 0 and not check_collision_murs(joueur_x, joueur_y + dy):
                    joueur_y += dy
                if _v3_actif():
                    _v3_apres_deplacement(_v3_x0, _v3_y0, dx, dy)
                if (dx != 0 or dy != 0) and QUALITE["niveau"] >= 1:
                    creer_propulsion(joueur_x, joueur_y, dx, dy, BLEU_CYBER)

                if tir_maintenu or _in_tir():
                    if minuteur_cadence_tir <= 0:
                        tirer_balle = True
                        minuteur_cadence_tir = _cadence()
                    else:
                        minuteur_cadence_tir -= 1

                if tirer_balle and not DEVIL["actif"]:
                    if SON_ACTIF:
                        son_tir.play()
                    cible, dist_min = None, 900
                    for ex in liste_ennemis:
                        d = math.hypot(ex[0] - joueur_x, ex[1] - joueur_y)
                        if d < dist_min:
                            dist_min, cible = d, ex
                    if boss_actif and not boss_vaincu:
                        d_boss = math.hypot(boss_x - joueur_x, boss_y - joueur_y)
                        if d_boss < dist_min:
                            dist_min, cible = d_boss, [boss_x, boss_y]
                    _vm = _in_visee()
                    if _vm is not None:
                        balles.append([joueur_x, joueur_y, _vm[0] * 13, _vm[1] * 13, _perfo()])
                    elif cible:
                        bx, by = cible[0] - joueur_x, cible[1] - joueur_y
                        db = math.hypot(bx, by)
                        balles.append([joueur_x, joueur_y, (bx / db) * 13, (by / db) * 13, _perfo()])
                    else:
                        balles.append([joueur_x, joueur_y, angle_visée_x * 13, angle_visée_y * 13, _perfo()])
                    if MP["actif"] and balles:
                        _mp_tir_local(balles[-1])

                # CORRECTION DE LA FUITE DE MÉMOIRE DES BALLES
                for b in balles[:]:
                    b[0] += b[2]
                    b[1] += b[3]
                    cbx, cby = int(b[0] // TAILLE_CASE), int(b[1] // TAILLE_CASE)
                    # Suppression si hors de la carte OU si ça touche un mur
                    if not (0 <= cbx < len(CARTE[0]) and 0 <= cby < len(CARTE)):
                        balles.remove(b)
                    elif CARTE[cby][cbx] == 1:
                        creer_etincelles(b[0], b[1], LASER["main"], 5)
                        balles.remove(b)

                for ex in liste_ennemis[:]:
                    if not _mp_client():                              # en multijoueur, seul l'hôte déplace les drones
                        ang = _v3_cap_ennemi(ex) if _v3_actif() else None
                        if ang is None:
                            _cx, _cy = _mp_cible(ex[0], ex[1])
                            ang = math.atan2(_cy - ex[1], _cx - ex[0]) + random.uniform(-0.08, 0.08)
                        _fe = _facteur_ennemi(ex[0], ex[1])
                        ex[0] += math.cos(ang) * ex[2] * _fe
                        ex[1] += math.sin(ang) * ex[2] * _fe
                        if QUALITE["niveau"] >= 1 and len(liste_ennemis) <= 8 and random.random() < 0.3:
                            creer_propulsion(ex[0], ex[1], math.cos(ang) * ex[2], math.sin(ang) * ex[2], ROUGE_ALERTE)
                    for b in balles[:]:
                        if math.hypot(ex[0] - b[0], ex[1] - b[1]) < 28:
                            if ex in liste_ennemis:
                                liste_ennemis.remove(ex)
                                _mp_tuer(ex)
                                MISSION["drones"] += 1
                                creer_explosion(ex[0], ex[1], ROUGE_ALERTE, 24, 7.0, 3.0)
                                if SON_ACTIF:
                                    son_explosion.play()
                            if b in balles:
                                if b[4] > 0:
                                    b[4] -= 1          # tir perforant : le laser continue sa route
                                else:
                                    balles.remove(b)
                    if not partie_perdue and math.hypot(joueur_x - ex[0], joueur_y - ex[1]) < (TAILLE_PERSO / 2 + 16):
                        if not subir_degats("SYSTÈME CORROMPU") and ex in liste_ennemis:
                            liste_ennemis.remove(ex)          # le choc détruit le drone
                            _mp_tuer(ex)
                            MISSION["drones"] += 1
                            creer_explosion(ex[0], ex[1], ROUGE_ALERTE, 24, 7.0, 3.0)

                if boss_actif and not boss_vaincu and not partie_perdue and not partie_gagnee:
                    angle_boss = math.atan2(joueur_y - boss_y, joueur_x - boss_x) + random.uniform(-0.05, 0.05)
                    vitesse_deplacement_boss = 1.6 * _facteur_ennemi(boss_x, boss_y)
                    boss_x += math.cos(angle_boss) * vitesse_deplacement_boss
                    boss_y += math.sin(angle_boss) * vitesse_deplacement_boss

                    for b in balles[:]:
                        if math.hypot(boss_x - b[0], boss_y - b[1]) < RAYON_CORPS_BOSS:
                            boss_vie -= STATS["degats"]
                            creer_etincelles(b[0], b[1], ORANGE_MEC, 7)
                            if b in balles:
                                balles.remove(b)
                            if boss_vie <= 0:
                                boss_vie = 0
                                boss_vaincu = True
                                if SON_ACTIF:
                                    son_victoire.play()

                    minuteur_tir_boss -= 0.5 if POUV.get("t_ralenti", 0) > 0 else 1
                    if minuteur_tir_boss <= 0 and not boss_vaincu:
                        dir_x, dir_y = joueur_x - boss_x, joueur_y - boss_y
                        dist_dir = math.hypot(dir_x, dir_y)
                        if dist_dir > 0:
                            boules_feu.append([boss_x, boss_y, (dir_x / dist_dir) * 5.5, (dir_y / dist_dir) * 5.5])
                        minuteur_tir_boss = random.randint(60, 90)

                    if not partie_perdue and math.hypot(joueur_x - boss_x, joueur_y - boss_y) < (TAILLE_PERSO / 2 + RAYON_CORPS_BOSS):
                        if not subir_degats("ÉCRASÉ PAR LE BOSS"):
                            d_rep = max(1.0, math.hypot(boss_x - joueur_x, boss_y - joueur_y))
                            boss_x += (boss_x - joueur_x) / d_rep * 170          # le bouclier repousse le Boss
                            boss_y += (boss_y - joueur_y) / d_rep * 170

                for boule in boules_feu[:]:
                    boule[0] += boule[2] * _facteur_boule()
                    boule[1] += boule[3] * _facteur_boule()
                    cfx, cfy = int(boule[0] // TAILLE_CASE), int(boule[1] // TAILLE_CASE)
                    if not (0 <= cfx < len(CARTE[0]) and 0 <= cfy < len(CARTE)):
                        boules_feu.remove(boule)
                        continue
                    if CARTE[cfy][cfx] == 1:
                        boules_feu.remove(boule)
                        continue
                    if not partie_perdue and math.hypot(joueur_x - boule[0], joueur_y - boule[1]) < (TAILLE_PERSO / 2 + 14):
                        if _esquive_boule(boule):
                            continue                          # Faufilé : la boule de feu rate le joueur
                        subir_degats("BRÛLÉ PAR LE BOSS")
                        boules_feu.remove(boule)

                cx, cy = int(joueur_x // TAILLE_CASE), int(joueur_y // TAILLE_CASE)
                if DEVIL["actif"]:
                    devil_pas(cx, cy)
                elif 0 <= cx < len(CARTE[0]) and 0 <= cy < len(CARTE):
                    core_accessible = (not boss_actif) or boss_vaincu
                    if CARTE[cy][cx] == 2 and not hack_reussi and core_accessible:
                        jauge_hack = min(jauge_hack + 0.7 * _hack(), 100.0)
                        if jauge_hack >= 100.0:
                            hack_reussi = True
                    elif not hack_reussi:
                        jauge_hack = max(jauge_hack - 0.3, 0.0)
                    if CARTE[cy][cx] == 3 and hack_reussi and not partie_gagnee:
                        partie_gagnee = True
                        if SON_ACTIF:
                            son_victoire.play()
                tirer_balle = False          # un appui ne tire qu'une seule fois, même s'il y a plusieurs pas

        if MP["actif"] or MP["etat"] == "recherche":
            _mp_tick()
        _tm1 = _time.perf_counter()
        if etat_actuel == ETAT_JEU:
            if DEVIL["actif"]:
                devil_hook()
            if partie_perdue and not mort_fx_faite:
                mort_fx_faite = True
                if DEVIL["actif"]:
                    devil_mort()
                else:
                    creer_explosion(joueur_x, joueur_y, ROUGE_ALERTE, 46, 9.0, 12.0)
                    demarrer_ecran_fin(False)
                    accorder_recompense(False)
            elif not partie_perdue:
                mort_fx_faite = False
            if partie_gagnee and not victoire_fx_faite:
                creer_explosion(joueur_x, joueur_y, VERT_FLUO, 50, 8.0, 4.0)
                victoire_fx_faite = True
                if DEVIL["actif"]:
                    devil_victoire()
                else:
                    demarrer_ecran_fin(True)
                    accorder_recompense(True)
            elif not partie_gagnee:
                victoire_fx_faite = False
            if boss_actif and boss_vaincu and not boss_fx_faite:
                creer_explosion(boss_x, boss_y, VIOLET_CYBER, 90, 12.0, 14.0)
                creer_explosion(boss_x, boss_y, ORANGE_MEC, 60, 8.0, 0.0)
                boss_fx_faite = True
            elif not boss_vaincu:
                boss_fx_faite = False

        # Mises à jour qui doivent avoir lieu à CHAQUE tour (même si on saute le dessin) : particules et caméra
        if etat_actuel == ETAT_JEU:
            if not en_pause:
                mettre_a_jour_fx()
            if abs(CAM["x"] - joueur_x) > 700 or abs(CAM["y"] - joueur_y) > 700:
                CAM["x"], CAM["y"] = joueur_x, joueur_y
            elif not en_pause:
                CAM["x"] += (joueur_x - CAM["x"]) * 0.2
                CAM["y"] += (joueur_y - CAM["y"]) * 0.2

        # Saut d'images : on ne dessine qu'une image sur n, le jeu garde ainsi sa vitesse normale
        if (SAUT["n"] > 1 and etat_actuel == ETAT_JEU and not en_pause and not TRANS["actif"]
                and not partie_gagnee and not partie_perdue and frames_total % SAUT["n"] != 0):
            clock.tick(60)
            adapter_qualite()
            continue

        ecran.fill(NOIR_ESPACE)
        largeur_v = 500
        x_v = (LARGEUR - largeur_v) // 2

        if etat_actuel == ETAT_MENU:
            dessiner_fond_menu()
            dessiner_panneau_neon(x_v, largeur_v, BLEU_CYBER, False, 150)

            dessiner_titre_glitch("FLEX CYBERPUNK", police_titre, LARGEUR // 2, HAUTEUR // 4)
            ti = rendu_texte(police_jeu, "MODE INFINI", True, ROSE_SYNTH)
            ecran.blit(ti, (LARGEUR // 2 - ti.get_width() // 2, HAUTEUR // 4 + 90))

            niveau_sauvegarde_affichage = niveau_max_atteint
            if niveau_sauvegarde_affichage > 0:
                tp = rendu_texte(police_petite, f"Reprise à la MISSION {niveau_sauvegarde_affichage + 1:02d}", True, BLEU_CYBER)
                ecran.blit(tp, (LARGEUR // 2 - tp.get_width() // 2, HAUTEUR // 4 + 125))

            bouton_neon(rect_bouton_jouer, ROSE_SYNTH, "COMMENCER", police_bouton, plein=True, pulse=True)
            bouton_neon(rect_bouton_aide, BLEU_CYBER, "GUIDE TACTIQUE", police_bouton)
            bouton_neon(rect_bouton_boutique, JAUNE_CYBER, "BOUTIQUE", police_bouton)
            if IS_WEB:
                bouton_neon(rect_bouton_multi, VERT_FLUO, "MULTIJOUEUR", police_bouton)
            bouton_neon(rect_bouton_parc, CYAN_NEON, "PARC", police_bouton)
            dessiner_pieces(LARGEUR // 2, 36)
            dessiner_avertissement()
            dessiner_marque(HAUTEUR - 84)

            dessiner_halo(rect_icone_profil.centerx, rect_icone_profil.centery, 60, VERT_FLUO, 0.45, 2)
            DRAW.circle(ecran, GRIS_HACKER, rect_icone_profil.center, 35)
            DRAW.circle(ecran, VERT_FLUO, rect_icone_profil.center, 35, 3)
            dessiner_icone_personne(ecran, rect_icone_profil.centerx, rect_icone_profil.centery, 52, VERT_FLUO)
            if profil.get("pseudo"):
                tag = rendu_texte(police_petite, profil["pseudo"], True, VERT_FLUO)
                ecran.blit(tag, (rect_icone_profil.centerx - tag.get_width() // 2, rect_icone_profil.bottom + 6))

            dessiner_halo(rect_icone_infos.centerx, rect_icone_infos.centery, 60, BLEU_CYBER, 0.45, 2)
            DRAW.circle(ecran, GRIS_HACKER, rect_icone_infos.center, 35)
            DRAW.circle(ecran, BLEU_CYBER, rect_icone_infos.center, 35, 3)
            ti_icone = rendu_texte(police_titre, "i", True, BLEU_CYBER)
            ecran.blit(ti_icone, (rect_icone_infos.centerx - ti_icone.get_width() // 2, rect_icone_infos.centery - ti_icone.get_height() // 2 - 4))

            dessiner_halo(rect_icone_params.centerx, rect_icone_params.centery, 60, VIOLET_CYBER, 0.45, 2)
            DRAW.circle(ecran, GRIS_HACKER, rect_icone_params.center, 35)
            DRAW.circle(ecran, VIOLET_CYBER, rect_icone_params.center, 35, 3)
            dessiner_icone_engrenage(rect_icone_params.centerx, rect_icone_params.centery, 27, VIOLET_CYBER)

            cx_d, cy_d = rect_icone_defis.center
            dessiner_halo(cx_d, cy_d, 60, VERT_FLUO, 0.45, 2)
            DRAW.circle(ecran, GRIS_HACKER, (cx_d, cy_d), 35)
            DRAW.circle(ecran, VERT_FLUO, (cx_d, cy_d), 35, 3)
            DRAW.circle(ecran, VERT_FLUO, (cx_d, cy_d), 21, 3)
            DRAW.circle(ecran, VERT_FLUO, (cx_d, cy_d), 7)
            _dd = defis_verifier()
            _reste = len(_dd["liste"]) - len(_dd["valides"])
            if _reste > 0:                                                       # pastille : défis restants
                DRAW.circle(ecran, ROSE_SYNTH, (cx_d + 27, cy_d - 27), 12)
                _tp = rendu_texte(police_petite, str(_reste), True, BLANC_NEON)
                ecran.blit(_tp, (cx_d + 27 - _tp.get_width() // 2, cy_d - 27 - _tp.get_height() // 2))
            t_de = rendu_texte(police_petite, "DÉFIS", True, VERT_FLUO)
            ecran.blit(t_de, (cx_d - t_de.get_width() // 2, rect_icone_defis.bottom + 6))

            cx_v, cy_v = rect_icone_devil.center                                 # extension : mode DEVIL
            dessiner_halo(cx_v, cy_v, 60, ROSE_SYNTH, 0.45, 2)
            DRAW.circle(ecran, GRIS_HACKER, (cx_v, cy_v), 35)
            DRAW.circle(ecran, ROSE_SYNTH, (cx_v, cy_v), 35, 3)
            DRAW.polygon(ecran, ROSE_SYNTH, [(cx_v - 25, cy_v - 12), (cx_v - 30, cy_v - 38), (cx_v - 8, cy_v - 25)])
            DRAW.polygon(ecran, ROSE_SYNTH, [(cx_v + 25, cy_v - 12), (cx_v + 30, cy_v - 38), (cx_v + 8, cy_v - 25)])
            DRAW.circle(ecran, ROSE_SYNTH, (cx_v - 10, cy_v - 4), 4)
            DRAW.circle(ecran, ROSE_SYNTH, (cx_v + 10, cy_v - 4), 4)
            pygame.draw.arc(ecran, ROSE_SYNTH, (cx_v - 14, cy_v - 4, 28, 20), math.pi + 0.35, 2 * math.pi - 0.35, 3)
            t_dv = rendu_texte(police_petite, "DEVIL", True, ROSE_SYNTH)
            ecran.blit(t_dv, (cx_v - t_dv.get_width() // 2, rect_icone_devil.bottom + 6))

            if IS_WEB:
                cx_t, cy_t = rect_icone_classement.center
                dessiner_halo(cx_t, cy_t, 60, JAUNE_CYBER, 0.45, 2)
                DRAW.circle(ecran, GRIS_HACKER, (cx_t, cy_t), 35)
                DRAW.circle(ecran, JAUNE_CYBER, (cx_t, cy_t), 35, 3)
                DRAW.circle(ecran, JAUNE_CYBER, (cx_t - 15, cy_t - 6), 7, 3)
                DRAW.circle(ecran, JAUNE_CYBER, (cx_t + 15, cy_t - 6), 7, 3)
                DRAW.polygon(ecran, JAUNE_CYBER, [(cx_t - 13, cy_t - 15), (cx_t + 13, cy_t - 15), (cx_t + 9, cy_t + 2), (cx_t + 4, cy_t + 7), (cx_t - 4, cy_t + 7), (cx_t - 9, cy_t + 2)])
                DRAW.rect(ecran, JAUNE_CYBER, (cx_t - 3, cy_t + 7, 6, 7))
                DRAW.rect(ecran, JAUNE_CYBER, (cx_t - 11, cy_t + 14, 22, 5))
                t_top = rendu_texte(police_petite, "TOP 10", True, JAUNE_CYBER)
                ecran.blit(t_top, (cx_t - t_top.get_width() // 2, rect_icone_classement.bottom + 6))
                cx_s, cy_s = rect_icone_skins.center
                dessiner_halo(cx_s, cy_s, 60, CYAN_NEON, 0.45, 2)
                DRAW.circle(ecran, GRIS_HACKER, (cx_s, cy_s), 35)
                DRAW.circle(ecran, CYAN_NEON, (cx_s, cy_s), 35, 3)
                DRAW.circle(ecran, CYAN_NEON, (cx_s, cy_s - 8), 9)
                DRAW.ellipse(ecran, CYAN_NEON, (cx_s - 16, cy_s + 3, 32, 22))
                t_sk = rendu_texte(police_petite, "SKINS", True, CYAN_NEON)
                ecran.blit(t_sk, (cx_s - t_sk.get_width() // 2, rect_icone_skins.bottom + 6))
                if _install_visible():
                    cx_i, cy_i = rect_icone_install.center
                    VERT_INSTALL = (120, 255, 170)
                    dessiner_halo(cx_i, cy_i, 60, VERT_INSTALL, 0.5, 2)
                    DRAW.circle(ecran, GRIS_HACKER, (cx_i, cy_i), 35)
                    DRAW.circle(ecran, VERT_INSTALL, (cx_i, cy_i), 35, 3)
                    DRAW.rect(ecran, VERT_INSTALL, (cx_i - 5, cy_i - 18, 10, 18))
                    DRAW.polygon(ecran, VERT_INSTALL, [(cx_i - 14, cy_i), (cx_i + 14, cy_i), (cx_i, cy_i + 14)])
                    DRAW.rect(ecran, VERT_INSTALL, (cx_i - 17, cy_i + 19, 34, 5))
                    t_in = rendu_texte(police_petite, "INSTALLER", True, VERT_INSTALL)
                    ecran.blit(t_in, (cx_i - t_in.get_width() // 2, rect_icone_install.bottom + 6))

        elif etat_actuel == ETAT_NIVEAUX:
            dessiner_fond_menu()
            _nm = _niv_max()
            dessiner_titre_glitch("MISSIONS", police_titre, LARGEUR // 2, 50)

            idx_min_affiche = max(0, int((-defilement_niveaux - 150) / NIVEAU_NODE_ESPACEMENT))
            idx_max_affiche = min(_nm + 30, int((LARGEUR - defilement_niveaux + 150) / NIVEAU_NODE_ESPACEMENT))

            points_chemin = []
            for idx in range(idx_min_affiche, idx_max_affiche + 1):
                x_node = int(NIVEAU_MARGE_GAUCHE + idx * NIVEAU_NODE_ESPACEMENT + defilement_niveaux)
                y_node = HAUTEUR // 2 + int(60 * math.sin(idx * 0.9))
                points_chemin.append((x_node, y_node))
            if len(points_chemin) >= 2:
                DRAW.lines(ecran, (0, 40, 60), False, points_chemin, 12)
                DRAW.lines(ecran, (0, 90, 130), False, points_chemin, 6)
                DRAW.lines(ecran, (80, 200, 255), False, points_chemin, 2)

            for idx in range(idx_min_affiche, idx_max_affiche + 1):
                x_node = int(NIVEAU_MARGE_GAUCHE + idx * NIVEAU_NODE_ESPACEMENT + defilement_niveaux)
                y_node = HAUTEUR // 2 + int(60 * math.sin(idx * 0.9))
                est_boss_node = (idx + 1) % 5 == 0 and not DEVIL["actif"]
                pulsation_node = 0

                if idx < _nm:
                    couleur_node = VERT_FLUO
                elif idx == _nm:
                    pulsation_node = 4 * math.sin(pygame.time.get_ticks() / 200)
                    couleur_node = VIOLET_CYBER if est_boss_node else BLEU_CYBER
                else:
                    couleur_node = GRIS_HACKER

                rayon_affiche = NIVEAU_NODE_RAYON + int(pulsation_node)
                if idx <= _nm:
                    dessiner_halo(x_node, y_node, 65, couleur_node, 0.6)
                DRAW.circle(ecran, (8, 8, 16), (x_node, y_node), rayon_affiche)
                DRAW.circle(ecran, couleur_node, (x_node, y_node), rayon_affiche, 5 if idx == _nm else 4)

                if idx > _nm:
                    DRAW.rect(ecran, GRIS_HACKER, (x_node - 13, y_node - 4, 26, 22), border_radius=4)
                    DRAW.arc(ecran, GRIS_HACKER, (x_node - 11, y_node - 24, 22, 26), 3.4, 6.0, 3)
                else:
                    if idx < _nm:
                        DRAW.lines(ecran, NOIR_ESPACE, False, [
                            (x_node - 13, y_node),
                            (x_node - 3, y_node + 10),
                            (x_node + 15, y_node - 13)
                        ], 5)
                    else:
                        texte_node = rendu_texte(police_bouton, str(idx + 1), True, BLANC_NEON)
                        ecran.blit(texte_node, (x_node - texte_node.get_width() // 2, y_node - texte_node.get_height() // 2))
                    if est_boss_node:
                        tag_boss = rendu_texte(police_petite, "BOSS", True, ROUGE_ALERTE)
                        ecran.blit(tag_boss, (x_node - tag_boss.get_width() // 2, y_node + NIVEAU_NODE_RAYON + 10))

            indication_niveaux = rendu_texte(police_petite, "Glisse pour naviguer  •  Touche une mission débloquée pour jouer", True, BLEU_CYBER)
            ecran.blit(indication_niveaux, (LARGEUR // 2 - indication_niveaux.get_width() // 2, HAUTEUR - 112))
            dessiner_marque(HAUTEUR - 84)

            bouton_neon(rect_retour_niveaux, ROUGE_ALERTE, "< RETOUR", police_bouton)

        elif etat_actuel == ETAT_AIDE:
            dessiner_panneau_neon(x_v, largeur_v, BLEU_CYBER)
            dessiner_titre_glitch("GUIDE TACTIQUE", police_titre, LARGEUR // 2, 50)

            gris_credit = (170, 180, 210)
            lignes = [
                ("CONTRÔLES", ROSE_SYNTH),
                ("Manette gauche : déplacement", BLANC_NEON),
                ("Bouton TIR : laser avec autolock sur le", BLANC_NEON),
                ("drone (ou boss) le plus proche", BLANC_NEON),
                ("", BLANC_NEON),
                ("OBJECTIF DE CHAQUE MISSION", ROSE_SYNTH),
                ("1. Rejoins la zone violette (CORE)", BLANC_NEON),
                ("2. Reste dedans jusqu'à 100% de hack", BLANC_NEON),
                ("3. Fonce vers la sortie (zone verte)", BLANC_NEON),
                ("", BLANC_NEON),
                ("DANGERS À ÉVITER", ROUGE_ALERTE),
                ("Drones ennemis : 1 seul contact = échec", BLANC_NEON),
                ("Chrono : 130s par mission (plus sur boss)", BLANC_NEON),
                ("Temps écoulé avant la sortie = échec", BLANC_NEON),
                ("", BLANC_NEON),
                ("BONUS", JAUNE_CYBER),
                ("Potions jaunes +5s, dès la mission 9", BLANC_NEON),
                ("", BLANC_NEON),
                ("BOSS", ROUGE_ALERTE),
                ("Toutes les 5 missions, sans drones", BLANC_NEON),
                ("Le CORE reste verrouillé tant qu'il est en vie", BLANC_NEON),
                ("Tire sans arrêt et esquive ses boules de feu", BLANC_NEON),
                ("", BLANC_NEON),
                ("MODE INFINI : la difficulté augmente sans", VIOLET_CYBER),
                ("fin, les missions n'ont pas de limite !", VIOLET_CYBER),
                ("", BLANC_NEON),
                ("---", BLANC_NEON),
                ("", BLANC_NEON),
                ("FLEX CYBERPUNK", ROSE_SYNTH),
                ("", BLANC_NEON),
                ("Un jeu créé et développé par FlexPlay.", BLANC_NEON),
                ("", BLANC_NEON),
                ("Toute modification ou redistribution doit", gris_credit),
                ("conserver les crédits du créateur original.", gris_credit),
                ("", BLANC_NEON),
            ]
            y_zone, pas = 130, 32
            hauteur_contenu = len(lignes) * pas + 20
            hauteur_visible = HAUTEUR - y_zone - 10
            defil_max = max(0, hauteur_contenu - hauteur_visible)
            AIDE["scroll"] = max(-defil_max, min(0, AIDE["scroll"]))

            ecran.set_clip(pygame.Rect(x_v - 14, y_zone, largeur_v + 28, HAUTEUR - y_zone))
            for idx, (texte_ligne, couleur_ligne) in enumerate(lignes):
                yy = int(y_zone + 8 + idx * pas + AIDE["scroll"])
                if yy < y_zone - 40 or yy > HAUTEUR:
                    continue
                if texte_ligne == "---":
                    DRAW.line(ecran, eclaircir(BLEU_CYBER, 0.35), (x_v + 40, yy + 14), (x_v + largeur_v - 40, yy + 14), 5)
                    DRAW.line(ecran, BLEU_CYBER, (x_v + 40, yy + 14), (x_v + largeur_v - 40, yy + 14), 2)
                elif texte_ligne:
                    police_l = police_jeu if texte_ligne == "FLEX CYBERPUNK" else police_aide
                    tl = rendu_texte(police_l, texte_ligne, True, couleur_ligne)
                    ecran.blit(tl, (LARGEUR // 2 - tl.get_width() // 2, yy))
            ecran.set_clip(None)

            if defil_max > 0:
                x_barre, haut_piste = x_v + largeur_v - 9, y_zone + 6
                long_piste = HAUTEUR - y_zone - 22
                long_pouce = max(30, int(long_piste * hauteur_visible / float(hauteur_contenu)))
                y_pouce = haut_piste + int((long_piste - long_pouce) * (-AIDE["scroll"]) / float(defil_max))
                DRAW.rect(ecran, (16, 20, 40), (x_barre, haut_piste, 4, long_piste), border_radius=2)
                DRAW.rect(ecran, BLEU_CYBER, (x_barre, y_pouce, 4, long_pouce), border_radius=2)
                if AIDE["scroll"] > -6:
                    indice = rendu_texte(police_petite, "Glisse pour voir la suite", True, BLEU_CYBER)
                    ecran.blit(obtenir_voile(280, 34, (5, 6, 16, 200)), (LARGEUR // 2 - 140, HAUTEUR - 50))
                    ecran.blit(indice, (LARGEUR // 2 - indice.get_width() // 2, HAUTEUR - 41))

            bouton_neon(rect_bouton_retour, ROUGE_ALERTE, "< RETOUR", police_bouton)

        elif etat_actuel == ETAT_INFOS:
            dessiner_fond_menu()
        
            panneau_largeur = 520
            panneau_x = (LARGEUR - panneau_largeur) // 2
        
            ecran.blit(obtenir_voile(panneau_largeur, HAUTEUR, (10, 10, 20, 220)), (panneau_x, 0))
        
            DRAW.line(ecran, BLEU_CYBER, (panneau_x, 0), (panneau_x, HAUTEUR), 3)
            DRAW.line(ecran, BLEU_CYBER, (panneau_x + panneau_largeur, 0), (panneau_x + panneau_largeur, HAUTEUR), 3)
        
            dessiner_titre_glitch("INFORMATIONS", police_titre, LARGEUR // 2, 50)
        
            lignes_infos = [
                ("DÉVELOPPEUR ET CRÉATEUR", VERT_FLUO),
                ("FLEXPLAY", BLANC_NEON),
                ("", BLANC_NEON),
                ("CONNAISSANCES", BLEU_CYBER),
                ("ZZED GAMING23", BLANC_NEON),
                ("GLOD'S", BLANC_NEON),
                ("GAMEPLAY PSP", BLANC_NEON),
                ("ROMULUS GAMES", BLANC_NEON),
                ("BENI TUBE", BLANC_NEON),
                ("ISHAQ GAMER", VERT_FLUO),
                ("BADLEX PRO GAMING", BLANC_NEON),
                ("GAMER REPUBLIC", BLANC_NEON),
                ("BEN GAMING23", BLANC_NEON),
                ("GAMEHUB XD", BLANC_NEON),
                ("JHONS GAMING", BLANC_NEON),
                ("DARK GAMES", BLANC_NEON),
            ]
        
            y_depart_infos = 135
            espacement_infos = min(32, max(22, (HAUTEUR - 135 - 110) // max(1, len(lignes_infos) - 1)))
            for idx, (texte_ligne, couleur_ligne) in enumerate(lignes_infos):
                if texte_ligne:
                    police_texte = police_jeu if couleur_ligne in [VERT_FLUO, BLEU_CYBER] else police_petite
                    til = rendu_texte(police_texte, texte_ligne, True, couleur_ligne)
                    ecran.blit(til, (LARGEUR // 2 - til.get_width() // 2, y_depart_infos + idx * espacement_infos))

            dessiner_marque(HAUTEUR - 84)
            bouton_neon(rect_retour_infos, ROUGE_ALERTE, "< RETOUR", police_bouton)

        elif etat_actuel == ETAT_PROFIL:
            dessiner_panneau_neon(x_v, largeur_v, BLEU_CYBER)
            dessiner_titre_glitch("MON PROFIL", police_titre, LARGEUR // 2, 60)

            centre_avatar = (LARGEUR // 2, 190)
            if photo_profil_surface:
                ecran.blit(photo_profil_surface, (centre_avatar[0] - 80, centre_avatar[1] - 80))
                DRAW.circle(ecran, VERT_FLUO, centre_avatar, 80, 3)
            else:
                DRAW.circle(ecran, NOIR_ESPACE, centre_avatar, 80)
                DRAW.circle(ecran, VERT_FLUO, centre_avatar, 80, 3)
                dessiner_icone_personne(ecran, centre_avatar[0], centre_avatar[1], 110, VERT_FLUO)

            astuce = rendu_texte(police_petite, "Depose 'photo_profil.png' dans le dossier du jeu", True, BLANC_NEON)
            ecran.blit(astuce, (LARGEUR // 2 - astuce.get_width() // 2, centre_avatar[1] + 90))

            bouton_neon(rect_recharger_photo, BLEU_CYBER, "RECHARGER LA PHOTO", police_petite)

            DRAW.rect(ecran, NOIR_ESPACE, rect_champ_pseudo, border_radius=8)
            couleur_bordure = VERT_FLUO if saisie_pseudo_active else BLEU_CYBER
            DRAW.rect(ecran, couleur_bordure, rect_champ_pseudo, border_radius=8, width=3)
            curseur = "|" if (saisie_pseudo_active and (pygame.time.get_ticks() // 500) % 2 == 0) else ""
            texte_pseudo = profil["pseudo"] if (profil["pseudo"] or saisie_pseudo_active) else "Toucher pour saisir un pseudo"
            surf_pseudo = rendu_texte(police_jeu, texte_pseudo + curseur, True, BLANC_NEON)
            ecran.blit(surf_pseudo, (rect_champ_pseudo.x + 15, rect_champ_pseudo.centery - surf_pseudo.get_height() // 2))

            bouton_neon(rect_fleche_gauche, BLEU_CYBER, "<", police_bouton)
            bouton_neon(rect_fleche_droite, BLEU_CYBER, ">", police_bouton)
            surf_nat = rendu_texte(police_jeu, NATIONALITES[index_nationalite], True, VERT_FLUO)
            ecran.blit(surf_nat, (LARGEUR // 2 - surf_nat.get_width() // 2, rect_fleche_gauche.centery - surf_nat.get_height() // 2))

            bouton_neon(rect_sauvegarder_profil, ROSE_SYNTH, "ENREGISTRER", police_bouton, plein=True, pulse=True)
            bouton_neon(rect_retour_profil, ROUGE_ALERTE, "RETOUR", police_bouton)
            dessiner_marque(HAUTEUR - 84)

        elif etat_actuel == ETAT_EDITEUR:
            dessiner_editeur()

        elif etat_actuel == ETAT_BOUTIQUE:
            dessiner_boutique()

        elif etat_actuel == ETAT_DEFIS:
            dessiner_defis()

        elif etat_actuel == ETAT_MULTI:
            dessiner_multi_attente()

        elif etat_actuel == ETAT_PARC:
            jouer_parc()

        elif etat_actuel == ETAT_PARAMS:
            dessiner_parametres()

        elif etat_actuel == ETAT_JEU:
            t_ms = pygame.time.get_ticks()
            sec = ETAT_FX["secousse"]
            decal_x = random.uniform(-sec, sec) if sec > 0 else 0.0
            decal_y = random.uniform(-sec, sec) if sec > 0 else 0.0
            ox = int(LARGEUR // 2 - CAM["x"] + decal_x)
            oy = int(HAUTEUR // 2 - CAM["y"] + decal_y)

            _echelle_active = False
            if _echelle_active:
                _ecran_reel = ecran
                ecran = obtenir_cible_monde()
                DRAW = _DESSIN_ECHELLE
            if _v3_actif():
                dessiner_vue_3d(t_ms)
            else:
                if DEVIL["actif"]:
                    ecran.fill((7, 3, 14))
                else:
                    dessiner_fond_ville(ox, oy, t_ms, (ox, oy, len(CARTE[0]) * TAILLE_CASE, len(CARTE) * TAILLE_CASE))
                    dessiner_cadre_carte(ox, oy, 0)
                nb_lignes_carte, nb_colonnes_carte = len(CARTE), len(CARTE[0])
                colonne_min = max(0, int((-ox) // TAILLE_CASE) - 1)
                colonne_max = min(nb_colonnes_carte, int((LARGEUR - ox) // TAILLE_CASE) + 2)
                ligne_min = max(0, int((-oy) // TAILLE_CASE) - 1)
                ligne_max = min(nb_lignes_carte, int((HAUTEUR - oy) // TAILLE_CASE) + 2)

                lueurs = []
                demi = TAILLE_CASE // 2
                ombres_actives = bool(PARAMS["ombres"]) and QUALITE["niveau"] >= 1
                if DEVIL["actif"]:
                    lueurs += devil_dessiner_carte(ox, oy, ligne_min, ligne_max, colonne_min, colonne_max, t_ms)
                else:
                    for li in range(ligne_min, ligne_max):
                        lg = CARTE[li]
                        for ci in range(colonne_min, colonne_max):
                            case = lg[ci]
                            rx, ry = ci * TAILLE_CASE + ox, li * TAILLE_CASE + oy
                            if case == 1:
                                masque = 0
                                if li > 0 and CARTE[li - 1][ci] != 1:
                                    masque |= 1
                                if li < nb_lignes_carte - 1 and CARTE[li + 1][ci] != 1:
                                    masque |= 2
                                if ci > 0 and lg[ci - 1] != 1:
                                    masque |= 4
                                if ci < nb_colonnes_carte - 1 and lg[ci + 1] != 1:
                                    masque |= 8
                                ecran.blit(tuile_mur(COULEUR_MUR, masque), (rx, ry))
                                continue
    
                            ms = 0
                            if ombres_actives:
                                if li > 0 and CARTE[li - 1][ci] == 1:
                                    ms |= 1
                                if li < nb_lignes_carte - 1 and CARTE[li + 1][ci] == 1:
                                    ms |= 2
                                if ci > 0 and lg[ci - 1] == 1:
                                    ms |= 4
                                if ci < nb_colonnes_carte - 1 and lg[ci + 1] == 1:
                                    ms |= 8
                            ecran.blit(tuile_sol(COULEUR_MUR, (li + ci) % 2, ms), (rx, ry))
                            if case == 2:
                                if boss_actif and not boss_vaincu:
                                    p_core = 0.6 + 0.4 * math.sin(t_ms / 180.0)
                                    DRAW.rect(ecran, eclaircir(ROUGE_ALERTE, p_core), (rx + 3, ry + 3, TAILLE_CASE - 6, TAILLE_CASE - 6), 5)
                                    DRAW.line(ecran, eclaircir(ROUGE_ALERTE, 0.35), (rx + 12, ry + 12), (rx + TAILLE_CASE - 12, ry + TAILLE_CASE - 12), 3)
                                    DRAW.line(ecran, eclaircir(ROUGE_ALERTE, 0.35), (rx + TAILLE_CASE - 12, ry + 12), (rx + 12, ry + TAILLE_CASE - 12), 3)
                                    lueurs.append((rx + demi, ry + demi, 110, ROUGE_ALERTE, 0.55 * p_core))
                                else:
                                    if MODE_GRAPHIQUE == "REALISTE":
                                        ecran.blit(img_core, (rx, ry))
                                    else:
                                        DRAW.rect(ecran, VIOLET_CYBER, (rx, ry, TAILLE_CASE, TAILLE_CASE))
                                    couleur_lueur_core = VERT_FLUO if hack_reussi else VIOLET_CYBER
                                    lueurs.append((rx + demi, ry + demi, 120, couleur_lueur_core, 0.5 + 0.2 * math.sin(t_ms / 300.0)))
                            elif case == 3:
                                col_sortie = VERT_FLUO if hack_reussi else ROUGE_ALERTE
                                p_sortie = 0.55 + 0.45 * math.sin(t_ms / (200.0 if hack_reussi else 350.0))
                                DRAW.rect(ecran, melange(NOIR_ESPACE, col_sortie, 0.18), (rx + 4, ry + 4, TAILLE_CASE - 8, TAILLE_CASE - 8))
                                for k_cadre in range(3):
                                    DRAW.rect(ecran, eclaircir(col_sortie, max(0.0, p_sortie - k_cadre * 0.2)),
                                                     (rx + 4 + k_cadre * 8, ry + 4 + k_cadre * 8,
                                                      TAILLE_CASE - 8 - k_cadre * 16, TAILLE_CASE - 8 - k_cadre * 16), 3)
                                lueurs.append((rx + demi, ry + demi, 100, col_sortie, 0.35 + 0.35 * p_sortie))

                if not DEVIL["actif"]:
                    dessiner_cadre_carte(ox, oy, 1)
                if ombres_actives:
                    if not partie_perdue:
                        dessiner_ombre(joueur_x + ox + 5, joueur_y + oy + 16, TAILLE_PERSO + 14, 22)
                    for ex in liste_ennemis:
                        dessiner_ombre(ex[0] + ox + 4, ex[1] + oy + 18, 44, 16)
                    if boss_actif and not boss_vaincu:
                        dessiner_ombre(boss_x + ox + 10, boss_y + oy + int(TAILLE_BOSS * 0.38), int(TAILLE_BOSS * 0.8), int(TAILLE_BOSS * 0.26))
                if not partie_perdue:
                    lueurs.append((joueur_x + ox, joueur_y + oy, 120, BLEU_CYBER, 0.38))
                for lx, ly, lr, lc, lint in lueurs:
                    dessiner_halo(lx, ly, lr if QUALITE["niveau"] >= 2 else int(lr * 0.7), lc, lint)

                animer_skin()
                for b in balles:
                    bx_e, by_e = int(b[0] + ox), int(b[1] + oy)
                    DRAW.line(ecran, LASER["trail"], (int(bx_e - b[2] * 3.2), int(by_e - b[3] * 3.2)), (bx_e, by_e), 9)
                    DRAW.line(ecran, LASER["main"], (int(bx_e - b[2] * 2.0), int(by_e - b[3] * 2.0)), (bx_e, by_e), 5)
                    DRAW.circle(ecran, BLANC_NEON, (bx_e, by_e), 4)
                    dessiner_halo(bx_e, by_e, 24, LASER["main"], 0.95, 0)

                _dessiner_pouvoirs_monde(ox, oy, t_ms)

                for potion in liste_potions:
                    px_ecran, py_ecran = int(potion[0] + ox), int(potion[1] + oy)
                    pulsation = 3 * math.sin(pygame.time.get_ticks() / 150)
                    dessiner_halo(px_ecran, py_ecran, 36, JAUNE_CYBER, 0.85)
                    ang_orbite = pygame.time.get_ticks() / 380.0
                    DRAW.circle(ecran, BLANC_NEON, (int(px_ecran + math.cos(ang_orbite) * 27), int(py_ecran + math.sin(ang_orbite) * 27)), 3)
                    DRAW.circle(ecran, JAUNE_CYBER, (px_ecran, py_ecran), int(18 + pulsation))
                    DRAW.circle(ecran, NOIR_ESPACE, (px_ecran, py_ecran), int(11 + pulsation))
                    tp5 = rendu_texte(police_petite, "+5", True, JAUNE_CYBER)
                    ecran.blit(tp5, (px_ecran - tp5.get_width() // 2, py_ecran - tp5.get_height() // 2))

                for ex in liste_ennemis:
                    if len(liste_ennemis) <= 10:
                        dessiner_halo(ex[0] + ox, ex[1] + oy, 30, ROUGE_ALERTE, 0.75)
                    if MODE_GRAPHIQUE == "REALISTE":
                        ang_drone = math.degrees(math.atan2(-(joueur_y - ex[1]), joueur_x - ex[0])) - 90
                        ang_q = int(round(ang_drone / 6.0)) * 6
                        drone_rot = _cache_drones.get(ang_q)
                        if drone_rot is None:
                            drone_rot = pygame.transform.rotate(img_drone, ang_q)
                            _cache_drones[ang_q] = drone_rot
                        ecran.blit(drone_rot, (int(ex[0] + ox - drone_rot.get_width() // 2), int(ex[1] + oy - drone_rot.get_height() // 2)))
                    else:
                        DRAW.circle(ecran, ROUGE_ALERTE, (int(ex[0] + ox), int(ex[1] + oy)), 16)

                if boss_actif and not boss_vaincu:
                    bx_ecran, by_ecran = int(boss_x + ox), int(boss_y + oy)
                    pulse_boss = 0.65 + 0.35 * math.sin(t_ms / 260.0)
                    couleur_aura_boss = ROUGE_ALERTE if boss_vie < boss_vie_max * 0.3 else VIOLET_CYBER
                    dessiner_halo(bx_ecran, by_ecran, 160 if QUALITE["niveau"] >= 2 else 110, couleur_aura_boss, 0.75 * pulse_boss)
                    if BOSS_IMAGE_DISPONIBLE:
                        angle_affichage_boss = math.degrees(math.atan2(-(joueur_y - boss_y), joueur_x - boss_x)) - 90
                        angle_arrondi_boss = round(angle_affichage_boss / 6) * 6
                        if boss_surface_cache is None or angle_arrondi_boss != boss_angle_precedent:
                            boss_surface_cache = _cache_boss.get(angle_arrondi_boss)
                            if boss_surface_cache is None:
                                if len(_cache_boss) >= 40:
                                    _cache_boss.pop(next(iter(_cache_boss)))
                                boss_surface_cache = pygame.transform.rotate(img_boss, angle_arrondi_boss)
                                _cache_boss[angle_arrondi_boss] = boss_surface_cache
                            boss_angle_precedent = angle_arrondi_boss
                        ecran.blit(boss_surface_cache, (bx_ecran - boss_surface_cache.get_width() // 2, by_ecran - boss_surface_cache.get_height() // 2))
                    else:
                        DRAW.circle(ecran, VIOLET_CYBER, (bx_ecran, by_ecran), int(TAILLE_BOSS / 2))
                        tb = rendu_texte(police_bouton, "BOSS", True, BLANC_NEON)
                        ecran.blit(tb, (bx_ecran - tb.get_width() // 2, by_ecran - tb.get_height() // 2))

                for boule in boules_feu:
                    fx_ecran, fy_ecran = int(boule[0] + ox), int(boule[1] + oy)
                    for k_traine in (3, 2, 1):
                        DRAW.circle(ecran, eclaircir(ORANGE_MEC, 0.22 * (4 - k_traine)),
                                           (int(fx_ecran - boule[2] * k_traine * 2.4), int(fy_ecran - boule[3] * k_traine * 2.4)),
                                           5 + (4 - k_traine) * 3)
                    dessiner_halo(fx_ecran, fy_ecran, 42, ORANGE_MEC, 1.0)
                    pulsation_feu = 3 * math.sin(pygame.time.get_ticks() / 90)
                    DRAW.circle(ecran, ORANGE_MEC, (fx_ecran, fy_ecran), int(16 + pulsation_feu))
                    DRAW.circle(ecran, JAUNE_CYBER, (fx_ecran, fy_ecran), int(9 + pulsation_feu))

                if MP["actif"]:
                    _mp_dessiner_autres(ox, oy)
                if not partie_perdue:
                    jx_e, jy_e = int(joueur_x + ox), int(joueur_y + oy) + int(3 * math.sin(t_ms / 230.0))
                    if DEVIL["chute"] is not None:
                        devil_dessiner_chute(jx_e, jy_e)
                    elif ETAT_JOUEUR["invuln"] <= 0 or (t_ms // 90) % 2 == 0:          # clignote après un coup encaissé
                        if MODE_GRAPHIQUE == "REALISTE":
                            if POUV.get("t_phase", 0) > 0:
                                img_joueur_actuel.set_alpha(120)                  # phase : le joueur devient transparent
                            ecran.blit(img_joueur_actuel, (jx_e - img_joueur_actuel.get_width() // 2, jy_e - img_joueur_actuel.get_height() // 2))
                            img_joueur_actuel.set_alpha(255)
                        else:
                            DRAW.rect(ecran, VERT_FLUO, (jx_e - TAILLE_PERSO // 2, jy_e - TAILLE_PERSO // 2, TAILLE_PERSO, TAILLE_PERSO))
                    if ETAT_JOUEUR["bouclier"] > 0:
                        r_bouclier = 36 + int(2 * math.sin(t_ms / 160.0))
                        DRAW.circle(ecran, eclaircir(LASER["main"], 0.4), (jx_e, jy_e), r_bouclier + 3, 3)
                        DRAW.circle(ecran, LASER["main"], (jx_e, jy_e), r_bouclier, 2)
                        dessiner_halo(jx_e, jy_e, 56, LASER["main"], 0.55)

                dessiner_fx(ox, oy)
                if QUALITE["niveau"] >= 2:
                    ecran.blit(obtenir_vignette(), (0, 0), special_flags=pygame.BLEND_RGB_MULT)
            if _echelle_active:
                ecran = _ecran_reel
                DRAW = pygame.draw
                try:
                    pygame.transform.scale(_cible_monde.surf, _ecran_reel.get_size(), _ecran_reel)
                except Exception as _err:
                    print("⚠️ Résolution réduite impossible, retour à 100% :", _err)
                    ECHELLE = 1.0
                    PARAMS["resolution"] = 1

            tn = rendu_texte(police_jeu, niveau_data["nom"], True, COULEUR_MUR)
            ecran.blit(tn, (40, 40))

            dessiner_radar()

            if not partie_gagnee and not partie_perdue:
                dessiner_halo(BTN_PAUSE_X, BTN_PAUSE_Y, 52, BLEU_CYBER, 0.5, 2)
                DRAW.circle(ecran, (10, 10, 20), (BTN_PAUSE_X, BTN_PAUSE_Y), BTN_PAUSE_RAYON)
                DRAW.circle(ecran, BLEU_CYBER, (BTN_PAUSE_X, BTN_PAUSE_Y), BTN_PAUSE_RAYON, 3)
                if en_pause:
                    DRAW.polygon(ecran, BLEU_CYBER, [
                        (BTN_PAUSE_X - 8, BTN_PAUSE_Y - 12),
                        (BTN_PAUSE_X - 8, BTN_PAUSE_Y + 12),
                        (BTN_PAUSE_X + 12, BTN_PAUSE_Y)
                    ])
                else:
                    DRAW.rect(ecran, BLEU_CYBER, (BTN_PAUSE_X - 11, BTN_PAUSE_Y - 12, 7, 24))
                    DRAW.rect(ecran, BLEU_CYBER, (BTN_PAUSE_X + 4, BTN_PAUSE_Y - 12, 7, 24))

            if not partie_gagnee and not partie_perdue and not DEVIL["actif"]:
                dessiner_halo(BTN_VUE_X, BTN_VUE_Y, 52, BLEU_CYBER, 0.5, 2)
                DRAW.circle(ecran, (10, 10, 20), (BTN_VUE_X, BTN_VUE_Y), BTN_PAUSE_RAYON)
                DRAW.circle(ecran, BLEU_CYBER, (BTN_VUE_X, BTN_VUE_Y), BTN_PAUSE_RAYON, 3)
                t_vue = rendu_texte(police_petite, "2D" if _v3_actif() else "3D", True, BLEU_CYBER)
                ecran.blit(t_vue, (BTN_VUE_X - t_vue.get_width() // 2, BTN_VUE_Y - t_vue.get_height() // 2))

            if boss_actif and not boss_vaincu:
                info_drones = rendu_texte(police_petite, "BOSS ACTIF : TIRE SANS ARRÊT ET ESQUIVE LE FEU", True, ROUGE_ALERTE)
            elif boss_actif and boss_vaincu:
                info_drones = rendu_texte(police_petite, "BOSS VAINCU : REJOINS LE CORE POUR HACKER", True, VERT_FLUO)
            else:
                info_drones = rendu_texte(police_petite, 
                    f"DRONES ACTIFS : {len(liste_ennemis)}   EN APPROCHE : {ennemis_restants_a_spawner}", True, ROUGE_ALERTE)
            if not DEVIL["actif"]:                                   # Devil : pas de drones
                ecran.blit(info_drones, (40, 80))
            dessiner_hud_boutique()

            if not DEVIL["actif"]:                                   # Devil : pas de chrono
                secondes_restantes = max(0, temps_restant_frames // 60)
                couleur_timer = ROUGE_ALERTE if secondes_restantes <= 10 else VERT_FLUO
                texte_timer = rendu_texte(police_bouton, f"TEMPS : {secondes_restantes:02d}s", True, couleur_timer)
                rect_timer = texte_timer.get_rect(topleft=(LARGEUR // 2 - texte_timer.get_width() // 2, 100)).inflate(44, 14)
                DRAW.rect(ecran, (8, 10, 20), rect_timer, border_radius=14)
                clignote = 1.0 if secondes_restantes > 10 else 0.6 + 0.4 * math.sin(t_ms / 110.0)
                DRAW.rect(ecran, eclaircir(couleur_timer, clignote), rect_timer, width=2, border_radius=14)
                ecran.blit(texte_timer, (LARGEUR // 2 - texte_timer.get_width() // 2, 100))
            if jauge_hack > 0 and not hack_reussi:
                bx0, by0, bw, bh = LARGEUR // 2 - 175, 45, 350, 30
                largeur_rempli = int(jauge_hack * 3.5)
                DRAW.rect(ecran, (10, 10, 22), (bx0, by0, bw, bh), border_radius=6)
                if largeur_rempli > 8:
                    DRAW.rect(ecran, VIOLET_CYBER, (bx0, by0, largeur_rempli, bh), border_radius=6)
                    DRAW.rect(ecran, (225, 120, 255), (bx0 + 3, by0 + 3, largeur_rempli - 6, bh // 3), border_radius=4)
                dessiner_halo(bx0 + largeur_rempli, by0 + bh // 2, 40, VIOLET_CYBER, 0.7, 2)
                DRAW.rect(ecran, BLEU_CYBER, (bx0, by0, bw, bh), width=2, border_radius=6)
                th_hack = rendu_texte(police_petite, f"HACK {int(jauge_hack)}%", True, BLANC_NEON)
                ecran.blit(th_hack, (LARGEUR // 2 - th_hack.get_width() // 2, by0 + bh // 2 - th_hack.get_height() // 2))

            if boss_actif and not boss_vaincu:
                largeur_barre_boss = 460
                x_barre_boss = LARGEUR // 2 - largeur_barre_boss // 2
                DRAW.rect(ecran, GRIS_HACKER, (x_barre_boss, 140, largeur_barre_boss, 28), border_radius=6)
                ratio_vie_boss = max(0.0, boss_vie / boss_vie_max)
                DRAW.rect(ecran, ROUGE_ALERTE, (x_barre_boss, 140, int(largeur_barre_boss * ratio_vie_boss), 28), border_radius=6)
                if ratio_vie_boss > 0.03:
                    DRAW.rect(ecran, (255, 120, 150), (x_barre_boss + 3, 143, max(1, int(largeur_barre_boss * ratio_vie_boss) - 6), 8), border_radius=4)
                    dessiner_halo(x_barre_boss + int(largeur_barre_boss * ratio_vie_boss), 154, 40, ROUGE_ALERTE, 0.7, 2)
                for k_seg in range(1, 10):
                    xk = x_barre_boss + largeur_barre_boss * k_seg // 10
                    DRAW.line(ecran, (20, 0, 10), (xk, 142), (xk, 166), 2)
                DRAW.rect(ecran, BLANC_NEON, (x_barre_boss, 140, largeur_barre_boss, 28), width=2, border_radius=6)
                txt_vie_boss = rendu_texte(police_petite, f"BOSS {boss_vie}/{boss_vie_max}", True, BLANC_NEON)
                ecran.blit(txt_vie_boss, (LARGEUR // 2 - txt_vie_boss.get_width() // 2, 144))

            if not _in_masquer_tactile():
                dessiner_commandes(manette_x, manette_y, tir_maintenu)
            _dessiner_pouvoirs_hud(ox, oy, t_ms)

            if DEVIL["actif"]:
                devil_dessiner_fin()
            elif partie_gagnee:
                dessiner_ecran_victoire()
            elif partie_perdue:
                dessiner_ecran_defaite()

        if etat_actuel == ETAT_JEU and en_pause and not partie_gagnee and not partie_perdue:
            ecran.blit(obtenir_voile(LARGEUR, HAUTEUR, (5, 5, 10, 205)), (0, 0))

            dessiner_titre_glitch("PAUSE", police_titre, LARGEUR // 2, HAUTEUR // 2 - 230)

            bouton_neon(rect_pause_continuer, BLEU_CYBER, "CONTINUER", police_bouton)
            bouton_neon(rect_pause_rejouer, VERT_FLUO, "REJOUER", police_bouton)
            bouton_neon(rect_pause_params, VIOLET_CYBER, "PARAMÈTRES", police_bouton)
            bouton_neon(rect_pause_quitter, ROUGE_ALERTE, "QUITTER", police_bouton)

        if TRANS["actif"]:
            dessiner_transition()

        _tm2 = _time.perf_counter()
        if VERSION_MODIFIEE:
            dessiner_filigrane()
        if PARAMS["fps"]:
            dessiner_fps()

        _dessiner_curseur()
        pygame.display.flip()
        _tm3 = _time.perf_counter()
        TMR["l"] += ((_tm1 - _tm0) * 1000.0 - TMR["l"]) * 0.1
        TMR["r"] += ((_tm2 - _tm1) * 1000.0 - TMR["r"]) * 0.1
        TMR["f"] += ((_tm3 - _tm2) * 1000.0 - TMR["f"]) * 0.1
        clock.tick(60)
        adapter_qualite()
        if EXTRA["_essai"] and pygame.time.get_ticks() > 6000:
            EXTRA["_essai"] = 0          # le démarrage a tenu : la résolution réduite est validée
            sauvegarder_parametres()


asyncio.run(main())
