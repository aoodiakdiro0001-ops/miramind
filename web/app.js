/* MIRA Mind PWA — local-first, RTL, zero dependencies (works on older browsers).
   Data lives in IndexedDB on this device only. No network calls except SW shell. */
"use strict";

/* ── صغير: أدوات ───────────────────────────────────────────────────── */
var $ = function (id) { return document.getElementById(id); };
var AR_MOODS = ["", "سعيد", "هادئ", "فضولي", "متحمس", "متعب", "حزين قليلاً", "غاضب قليلاً", "مشتت"];
var AR_DAYS = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"];

function toast(msg) {
  var t = $("toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toast._h);
  toast._h = setTimeout(function () { t.classList.add("hidden"); }, 2600);
}
function esc(s) {
  return String(s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
  });
}
function dayName(ts) {
  var d = new Date(ts * 1000);
  var today = new Date();
  var isToday = d.toDateString() === today.toDateString();
  return (isToday ? "اليوم · " : AR_DAYS[d.getDay()] + " · ") +
    d.getDate() + "/" + (d.getMonth() + 1);
}

/* ── IndexedDB محلي ────────────────────────────────────────────────── */
var DB = {
  db: null,
  open: function () {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open("miramind", 1);
      req.onupgradeneeded = function (e) {
        var db = e.target.result;
        db.createObjectStore("profile");
        var entries = db.createObjectStore("entries", { keyPath: "id", autoIncrement: true });
        entries.createIndex("ts", "ts");
      };
      req.onsuccess = function (e) { DB.db = e.target.result; resolve(); };
      req.onerror = function () { reject(req.error); };
    });
  },
  tx: function (store, mode, fn) {
    return new Promise(function (resolve, reject) {
      var t = DB.db.transaction(store, mode);
      var s = t.objectStore(store);
      var out = fn(s);
      t.oncomplete = function () { resolve(out.result !== undefined ? out.result : null); };
      t.onerror = function () { reject(t.error); };
    });
  },
  setProfile: function (p) { return DB.tx("profile", "readwrite", function (s) { return s.put(p, "me"); }); },
  getProfile: function () { return DB.tx("profile", "readonly", function (s) { return s.get("me"); }); },
  addEntry: function (e) { return DB.tx("entries", "readwrite", function (s) { return s.add(e); }); },
  allEntries: function () {
    return new Promise(function (resolve, reject) {
      var t = DB.db.transaction("entries", "readonly");
      var all = t.objectStore("entries").getAll();
      t.oncomplete = function () { resolve((all.result || []).sort(function (a, b) { return b.ts - a.ts; })); };
      t.onerror = function () { reject(t.error); };
    });
  },
  clear: function () {
    return Promise.all([
      DB.tx("profile", "readwrite", function (s) { return s.clear(); }),
      DB.tx("entries", "readwrite", function (s) { return s.clear(); })
    ]);
  }
};

/* ── قياسات الرسم (موضوعية — داخل المتصفح) ─────────────────────────── */
function hex(r, g, b) {
  return "#" + [r, g, b].map(function (v) {
    var s = Math.max(0, Math.min(255, Math.round(v))).toString(16);
    return s.length < 2 ? "0" + s : s;
  }).join("");
}
function colorName(r, g, b) {
  var mx = Math.max(r, g, b), mn = Math.min(r, g, b), v = mx / 255;
  if (v > 0.9 && mx - mn < 12) return "أبيض";
  if (v < 0.25) return "أسود";
  if (mx - mn < 14) return "رمادي/بيج";
  var h = 0;
  var d = mx - mn;
  if (mx === r) h = 60 * (((g - b) / d) % 6);
  else if (mx === g) h = 60 * ((b - r) / d + 2);
  else h = 60 * ((r - g) / d + 4);
  if (h < 15 || h >= 345) return "أحمر";
  if (h < 45) return "برتقالي";
  if (h < 70) return "أصفر";
  if (h < 160) return "أخضر";
  if (h < 250) return "أزرق";
  if (h < 300) return "بنفسجي";
  return "وردي/زهري";
}
function drawingMetrics(srcCanvas) {
  var S = 64;
  var small = document.createElement("canvas");
  small.width = S; small.height = S;
  small.getContext("2d").drawImage(srcCanvas, 0, 0, S, S);
  var px = small.getContext("2d").getImageData(0, 0, S, S).data;
  var n = S * S, i, r, g, b, k;
  var buckets = {}, maxKey = null, maxCt = 0;
  var hues = {}, satSum = 0, brightSum = 0;
  for (i = 0; i < n; i++) {
    r = px[i * 4]; g = px[i * 4 + 1]; b = px[i * 4 + 2];
    k = (r >> 5) + "," + (g >> 5) + "," + (b >> 5);
    buckets[k] = (buckets[k] || 0) + 1;
    if (buckets[k] > maxCt) { maxCt = buckets[k]; maxKey = k; }
    var mx = Math.max(r, g, b), mn = Math.min(r, g, b);
    brightSum += mx / 255;
    satSum += (mx ? (mx - mn) / mx : 0);
  }
  /* palette top colours with names */
  var top = Object.keys(buckets).map(function (key) {
    var p = key.split(",");
    return { key: key, ct: buckets[key] };
  }).sort(function (a, b) { return b.ct - a.ct; }).slice(0, 6);
  var palette = top.map(function (t) {
    var p = t.key.split(",").map(function (x) { return +x; });
    var R = p[0] * 32 + 16, G = p[1] * 32 + 16, B = p[2] * 32 + 16;
    return { rgb: hex(R, G, B), name: colorName(R, G, B), share: t.ct / n };
  });
  /* ink = pixels away from background bucket */
  var ink = 0, thirds = [0, 0, 0];
  for (i = 0; i < n; i++) {
    r = px[i * 4]; g = px[i * 4 + 1]; b = px[i * 4 + 2];
    k = (r >> 5) + "," + (g >> 5) + "," + (b >> 5);
    if (k !== maxKey) {
      ink++;
      var band = Math.min(2, Math.floor(i / (n / 3)));
      thirds[band]++;
    }
  }
  var inkTotal = thirds[0] + thirds[1] + thirds[2] || 1;
  /* stroke density: colour jumps along sampled mid rows of the full-size canvas */
  var dense = 0, samples = 0;
  [0.33, 0.55].forEach(function (fy) {
    var y = Math.floor(srcCanvas.height * fy);
    var row = srcCanvas.getContext("2d").getImageData(0, y, srcCanvas.width, 1).data;
    var step = Math.max(1, Math.floor(srcCanvas.width / 200));
    for (var x = step; x < srcCanvas.width; x += step) {
      var a = (x - step) * 4, c = x * 4;
      var dd = Math.abs(row[c] - row[a]) + Math.abs(row[c + 1] - row[a + 1]) + Math.abs(row[c + 2] - row[a + 2]);
      if (dd > 90) dense++;
      samples++;
    }
  });
  return {
    width: srcCanvas.width, height: srcCanvas.height,
    brightness: +(brightSum / n).toFixed(3),
    colorfulness: +(satSum / n).toFixed(3),
    ink_coverage: +(ink / n).toFixed(3),
    ink_thirds: thirds.map(function (t) { return +(t / inkTotal).toFixed(3); }),
    stroke_density: +(dense / Math.max(1, samples)).toFixed(3),
    palette: palette
  };
}

/* ── تأملات احتمالية + بنك النصائح (نفس لغة المحرك) ────────────────── */
function drawingReflections(m) {
  var refl = [], pal = m.palette || [], warm = 0, cool = 0, i;
  for (i = 0; i < Math.min(4, pal.length); i++) {
    var c = pal[i];
    if (c.name === "أحمر" || c.name === "برتقالي" || c.name === "أصفر") warm += c.share;
    if (c.name === "أزرق" || c.name === "أخضر") cool += c.share;
  }
  if (warm > 0.5) refl.push("الألوان الدافئة (أحمر/برتقالي/أصفر) مسيطرة — أحياناً تعكس حماساً وطاقة وأحياناً انفعالاً لطيفاً.");
  if (cool > 0.5) refl.push("الألوان الباردة (أزرق/أخضر) مسيطرة — غالباً تعكس هدوءاً أو تركيزاً لدى بعض الأطفال.");
  var ink = m.ink_coverage || 0;
  if (ink > 0.45) refl.push("تغطية حبر مرتفعة على الصفحة — قد تعكس انشغالاً شديداً بالنشاط وثقة في الحركة.");
  else if (ink < 0.08) refl.push("تغطية حبر خفيفة — قد تكون مرحلة استكشاف (ملاحظة القلم أو الرقبة) أو مزاج صامت اليوم.");
  var t3 = m.ink_thirds || [];
  if (t3[2] > 0.55) refl.push("تركّز الحبر في الثلث السفلي — بعض المربين يربطون ذلك بالأرضية والأمان؛ يُقرأ مع رسومات قادمة لا وحده.");
  var st = m.stroke_density || 0;
  if (st > 0.35) refl.push("كثافة خطوط عالية — حركة قلم نشطة (طاقة أو تركيز).");
  else if (st > 0 && st < 0.08) refl.push("خطوط متباعدة — ربما يتدرب على التحكم بالقلم.");
  if (!refl.length) refl.push("رسومات اليوم بألوان متوازنة — سجّلها وراقب النمط عبر أسبوع.");
  refl.push("🎓 الرسمة الواحدة لا تُقرأ وحدها — اسأل طفلك عن رسمته فكلماته أهم من تفسيراتنا.");
  return refl;
}
function moodFamily(mood) {
  if (mood === "سعيد" || mood === "هادئ" || mood === "فضولي" || mood === "متحمس") return "positive";
  if (mood === "متعب" || mood === "مشتت") return "low_energy";
  return "co_regulate";
}
var TIPS = {
  "positive-1-2": ["أطع وقتاً في اللعب الحر على الأرض معه — الاهتمام المشترك أقوى معزز في هذه المرحلة.", "سمّى المشاعر بصوتك: «أنت سعيد! تلعب بفرح» — يبني مفردات عاطفية مبكراً.", "العب معه لعبة حركة (كرات/مطاردة لطيفة) لتفريغ الطاقة الإيجابية بأمان."],
  "positive-2-4": ["حوّل حماسه إلى لعبة أدوار قصيرة (مطعم، طبيب) — يغذي اللغة والتعاطف.", "اقترح «لوحة الفضول»: يرسم ما أعجبه اليوم ويشرحه لك.", "خمس دقائق لعب مشترك بارتياح كامل أفضل من ساعة مشتتة."],
  "positive-4-7": ["أطلق «مشروع أسبوع» صغير (بناء مجسم، قصة) — يكافئ المثابرة.", "اسأله عن رسمته: «مَن هذا؟ وماذا يفعل؟» — تنمية السرد والثقة.", "نشاط بدني قصير (رقص 5 دقائق) بعد الجلوس الطويل."],
  "low_energy-1-2": ["نوم ووجبات بأوقات ثابتة — التعب عند الصغار سببه غالباً النوم أو الجوع.", "الأنشطة المهدئة أفضل في الرهج (كتب قماشية، هز لطيف).", "تقليل التحفيز قبل النوم بنصف ساعة (إضاءة خفيفة، صوت هادئ)."],
  "low_energy-2-4": ["جرب «زاوية الهدوء»: وسادة + كتاب + دبدوب.", "افحص الأساسيات أولاً: نوم كافٍ، ماء، وجبات منتظمة قبل البحث عن سبب سلوكي.", "أنشطة حسّية خفيفة (عجين، ماء) تعيد شحنه دون إثارة."],
  "low_energy-4-7": ["حوار قصير قبل النوم: «ما أصعب لحظة اليوم؟ وأجملها؟».", "قلّل الشاشات وخصّص نوم 10–11 ساعة لهذه المرحلة.", "قد يكون مللاً لا تعباً — اقترح نشاطاً واحداً محفزاً فقط."],
  "co_regulate-1-2": ["احضنه ولا تُطِل الكلام — التنظيم المشترك يبدأ من هدوئك الجسدي.", "انقل انتباهه بهدوء إلى شيء ملموس (ضوء، ماء).", "لاحظ ما قبل الحدث مباشرة (جوع/نوم) — النمط يظهر بعد أيام."],
  "co_regulate-2-4": ["سمّ شعوره أولاً: «أرى أنك غاضب لأن المكعب انهار» — التسمية تخفض الحدة.", "«نفس الفيل»: شهيق 3 / زفير 3 — لعبة لا عقاب.", "حدّ بهدوء ووفّر بديلاً: «الغضب مسموح، الضرب لا — اضرب به الوسادة»."],
  "co_regulate-4-7": ["اصنعا «صندوق الهدوء» معاً (ورق تلوين، كتب) — يختار مكوناته.", "جرّب التسمية الكاملة: تنهيدة عميقة… قل ما تشعر… ماذا نحتاج؟", "راجع الأوقيات — مشاجرات العشاء غالباً جوع وليست سلوكاً."]
};
var GENERIC_TIPS = ["روتين ثابت (نوم/أكل/لعب) يقلل الانفعالات ويزيد الشعور بالأمان.", "10 دقائق لعب مشترك بلا هاتف يومياً أقوى معزز عاطفي عملياً.", "إن استمر الملاحظة أسبوعين أو شدت قلقك — استشر أخصائياً؛ هذا حكمة الوالدين لا فشل."];
function pickTips(mood, ageMonths) {
  var band = ageMonths >= 48 ? "4-7" : (ageMonths >= 24 ? "2-4" : "1-2");
  var bank = TIPS[moodFamily(mood) + "-" + band] || GENERIC_TIPS;
  return bank.concat(GENERIC_TIPS).slice(0, 3);
}

/* ── التقرير الأسبوعي ─────────────────────────────────────────────── */
function weeklyReport(entries, child, ageMonths) {
  var week = entries.filter(function (e) {
    return (Date.now() / 1000 - e.ts) < 8 * 86400;
  }).sort(function (a, b) { return a.ts - b.ts; });
  if (!week.length) return "لا يوجد تسجيلات هذا الأسبوع بعد.\nسجّل اليوم بإذن الله يومياً وأرسل الرسومات — النمط يبني التقرير.";

  var counts = {}, energies = [], drawings = [], actCt = {}, i;
  for (i = 0; i < week.length; i++) {
    var e = week[i];
    if (e.mood) counts[e.mood] = (counts[e.mood] || 0) + 1;
    if (e.energy) energies.push(e.energy);
    if (e.drawing) drawings.push(e.drawing);
    (e.acts || []).forEach(function (a) { if (a) actCt[a] = (actCt[a] || 0) + 1; });
  }
  var moodStr = Object.keys(counts).map(function (k) { return k + " ×" + counts[k]; }).join(" · ");
  var avgE = energies.length ? Math.round(energies.reduce(function (s, v) { return s + v; }, 0) / energies.length * 10) / 10 : "—";
  var topActs = Object.keys(actCt).sort(function (a, b) { return actCt[b] - actCt[a]; }).slice(0, 3)
    .map(function (a) { return a + " ×" + actCt[a]; }).join(" · ") || "—";
  var peak = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; })[0] || null;

  var line = "──────────────";
  var txt = "📊 تقرير MIRA الأسبوعي — " + child + "\n" + line + "\n";
  txt += "سُجّل " + week.length + (week.length > 2 ? " أيام" : " يوم") + " مع " +
    (drawings.length === 0 ? "بلا رسومات" : drawings.length + (drawings.length > 2 ? " رسمات" : " رسمة")) + ".\n";
  txt += "🧷 المزاج المُسجَّل: " + (moodStr || "—") + "\n⚡ متوسط الطاقة: " + avgE + " / 5\n";
  txt += "🎨 أبرز الأنشطة: " + topActs + "\n";
  if (drawings.length) {
    txt += "\n🔍 تأملات الرسومات (احتمالات لا حقائق):\n";
    var seen = {};
    drawings.slice(-3).forEach(function (d) {
      (d.reflections || []).forEach(function (r) {
        if (!seen[r]) { txt += " • " + r + "\n"; seen[r] = 1; }
      });
      if (d.metrics && d.metrics.palette && d.metrics.palette.length >= 2) {
        var cols = d.metrics.palette.slice(0, 3)
          .map(function (c) { return c.name; }).join("، ");
        if (!seen[cols]) { txt += " 🌈 ألوان: " + cols + "\n"; seen[cols] = 1; }
      }
    });
  }
  txt += "\n💡 ثلاث نصائح لهذا الأسبوع:\n";
  pickTips(peak || "سعيد", ageMonths).forEach(function (t, idx) { txt += " " + (idx + 1) + ". " + t + "\n"; });
  txt += "\n" + line + "\n⚠️ أداة استرشادية تعليمية — لا تشخيص ولا بديل عن المختص. عند أي قلق دائم راجع أخصائياً.";
  return txt;
}

/* ── الرسم: التقاط + تحليل ────────────────────────────────────────── */
function loadImageToCanvas(file, cb) {
  var reader = new FileReader();
  reader.onload = function (ev) {
    var img = new Image();
    img.onload = function () { cb(img, ev.target.result); };
    img.src = ev.target.result;
  };
  reader.readAsDataURL(file);
}
function handleDrawing(file) {
  loadImageToCanvas(file, function (img, dataUrl) {
    var canvas = document.createElement("canvas");
    canvas.width = Math.min(900, img.width);
    canvas.height = Math.round(img.height * canvas.width / img.width);
    canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
    var metrics = drawingMetrics(canvas);
    var refl = drawingReflections(metrics);
    /* thumb صغير للعرض (يُضغط داخل البيانات المحلية) */
    var tCanvas = document.createElement("canvas");
    tCanvas.width = 320; tCanvas.height = Math.round(canvas.height * 320 / canvas.width);
    tCanvas.getContext("2d").drawImage(canvas, 0, 0, tCanvas.width, tCanvas.height);
    var thumb = tCanvas.toDataURL("image/jpeg", 0.7);

    DB.getProfile().then(function (p) {
      if (!p) { toast("سجّل الطفل أولاً من تبويب «الطفل» 👶"); return; }
      var entry = { ts: Math.floor(Date.now() / 1000), mood: null, energy: null, acts: [], type: "drawing", drawing: { thumb: thumb, metrics: metrics, reflections: refl } };
      DB.addEntry(entry).then(function () {
        showPreview(canvas, metrics, refl);
        refreshLists();
        toast("تم حفظ الرسمة محلياً 🎨");
      });
    });
  });
}
function showPreview(canvas, m, refl) {
  var pv = $("previewImg");
  pv.src = canvas.toDataURL("image/jpeg", 0.85);
  pv.classList.remove("hidden");
  var cols = (m.palette || []).slice(0, 4).map(function (c) {
    return '<span class="chip"><i style="background:' + c.rgb + '"></i>' + esc(c.name) + " " + Math.round(c.share * 100) + "%</span>";
  }).join(" ");
  var html = "<table class=\"metrics\">" +
    "<tr><td>📐 الأبعاد</td><td>" + m.width + "×" + m.height + "</td></tr>" +
    "<tr><td>✏️ تغطية الحبر</td><td>" + (m.ink_coverage * 100).toFixed(0) + "%</td></tr>" +
    "<tr><td>📊 كثافة الخط</td><td>" + m.stroke_density + "</td></tr>" +
    "<tr><td>🔆 السطوع / الغِنى</td><td>" + m.brightness + " / " + m.colorfulness + "</td></tr></table>" +
    "<div class='chips'>" + cols + "</div>" +
    "<h3>🔍 قراءة استرشادية:</h3><ul>" + refl.map(function (r) { return "<li>" + esc(r) + "</li>"; }).join("") + "</ul>" +
    "<p class='hint'>قد يعكس/تُقرأ مع نمط الرسومات عبر الأيام — ليست حقائق ولا تشخيصاً.</p>";
  var box = $("metricsOut");
  box.innerHTML = html;
  box.classList.remove("hidden");
}

/* ── واجهات: طفل / يوم / قوائم / تقرير ────────────────────────────── */
function refreshChildUI() {
  DB.getProfile().then(function (p) {
    if (p) {
      $("childForm").classList.add("hidden");
      $("childCard").classList.remove("hidden");
      var y = Math.floor(p.ageMonths / 12), mo = p.ageMonths % 12;
      $("childShown").textContent = esc(p.name) + " — " + p.ageMonths + " شهراً" + (y ? " (" + y + " " + (y === 1 ? "سنة" : "سنوات") + (mo !== "" && mo ? " " : "") + (mo ? " و" + mo + " شهر" : "") + ")" : "");
    } else {
      $("childForm").classList.remove("hidden");
      $("childCard").classList.add("hidden");
    }
  });
}
function refreshLists() {
  DB.allEntries().then(function (all) {
    /* اليوم: آخر 5 سجلات نوع نوعية موجة */
    var recent = all.filter(function (e) { return !e.drawing; }).slice(0, 5);
    $("recentList").innerHTML = recent.length ? recent.map(function (e) {
      var acts = (e.acts || []).join("، ");
      return "<div class='row'><b>" + esc(e.mood || "—") + "</b><span>⚡ " + (e.energy || "—") + " · " + esc(acts || "بلا أنشطة مسجلة") + " · <time>" + dayName(e.ts) + "</time></span></div>";
    }).join("") : "<p class='hint'>لا سجلات بعد — ابدأ من الأعلى.</p>";
    /* الرسمة: كل الرسومات */
    var dr = all.filter(function (e) { return e.drawing; }).slice(0, 12);
    $("drawingList").innerHTML = dr.length ? dr.map(function (e) {
      return "<div class='row drawing'><img src='" + e.drawing.thumb + "' alt=''><span>📐 تغطية " +
        Math.round((e.drawing.metrics.ink_coverage || 0) * 100) + "% · " + dayName(e.ts) +
        "<time>" + esc((e.drawing.metrics.palette || []).map(function (c) { return c.name; }).slice(0, 3).join("، ")) + "</time></span></div>";
    }).join("") : "<p class='hint'>لا رسومات بعد — أرسل صورة أول رسمة 🎨</p>";
  });
}
function buildReport() {
  DB.getProfile().then(function (p) {
    if (!p) { toast("سجّل الطفل أولاً 👶"); return; }
    DB.allEntries().then(function (entries) {
      var txt = weeklyReport(entries, p.name, p.ageMonths);
      var pre = document.createElement("pre");
      pre.textContent = txt;
      $("reportBody").innerHTML = "";
      $("reportBody").appendChild(pre);
      $("reportBody").classList.remove("hidden");
      report.last = txt;
    });
  });
}

/* ── تهيئة الصفحة ─────────────────────────────────────────────────── */
function initNav() {
  var bar = document.querySelectorAll(".tabbar button");
  Array.prototype.forEach.call(bar, function (btn) {
    btn.addEventListener("click", function () {
      document.querySelectorAll(".tab").forEach(function (s) { s.classList.remove("active"); });
      document.querySelectorAll(".tabbar button").forEach(function (b) { b.classList.remove("on"); });
      $("tab-" + btn.dataset.tab).classList.add("active");
      btn.classList.add("on");
      window.scrollTo(0, 0);
    });
  });
}
function initChild() {
  $("saveChild").addEventListener("click", function () {
    var name = $("childName").value.trim();
    var age = parseInt($("childAge").value, 10);
    if (!name || !age || age < 1 || age > 84) { toast("أدخل الاسم والعمر (1–84 شهراً)"); return; }
    DB.setProfile({ name: name, ageMonths: age, createdAt: Math.floor(Date.now() / 1000) })
      .then(function () { refreshChildUI(); toast("تم حفظ ملف الطفل ✓"); });
  });
  $("editChild").addEventListener("click", function () {
    DB.getProfile().then(function (p) {
      $("childName").value = p ? p.name : "";
      $("childAge").value = p ? p.ageMonths : "";
      $("childForm").classList.remove("hidden");
      $("childCard").classList.add("hidden");
    });
  });
}
function initDay() {
  var mg = $("moodGrid");
  /* نظرية التربية الإيجابية: لا نعرض «غاضب/حزين» بشكل سلبي — بل بلغة القول «قليلاً» */
  var labels = ["", "😄 سعيد", "😌 هادئ", "🤔 فضولي", "🤩 متحمس", "😴 متعب", "🥺 حزين قليلاً", "😤 غاضب قليلاً", "🌀 مشتت"];
  labels.forEach(function (lab, i) {
    if (!lab) return;
    var b = document.createElement("button");
    b.className = "mood"; b.textContent = lab; b.dataset.v = i;
    b.addEventListener("click", function () {
      mg.querySelectorAll(".mood").forEach(function (x) { x.classList.remove("on"); });
      b.classList.add("on"); mg.dataset.choice = i;
    });
    mg.appendChild(b);
  });
  var er = $("energyRow");
  for (var i = 1; i <= 5; i++) {
    (function (v) {
      var b = document.createElement("button");
      b.className = "en"; b.textContent = v;
      b.addEventListener("click", function () {
        er.querySelectorAll(".en").forEach(function (x) { x.classList.remove("on"); });
        b.classList.add("on"); er.dataset.choice = v;
      });
      er.appendChild(b);
    })(i);
  }
  $("saveDay").addEventListener("click", function () {
    DB.getProfile().then(function (p) {
      if (!p) { toast("سجّل الطفل أولاً 👶"); return; }
      var mi = +mg.dataset.choice, ei = +er.dataset.choice;
      if (!mi) { toast("اختر المزاج أولاً 😄"); return; }
      if (!ei) { toast("اختر الطاقة أولاً ⚡"); return; }
      var acts = ($("dayActs").value || "").split(/[،,؛;]/).map(function (s) { return s.trim(); }).filter(Boolean).slice(0, 8);
      var entry = { ts: Math.floor(Date.now() / 1000), mood: AR_MOODS[mi], energy: ei, acts: acts, type: "day" };
      DB.addEntry(entry).then(function () {
        toast("سُجّل يوم اليوم ✓ — النمط عبر الأيام هو المهم");
        $("dayActs").value = "";
        mg.dataset.choice = er.dataset.choice = "";
        mg.querySelectorAll(".mood").forEach(function (x) { x.classList.remove("on"); });
        er.querySelectorAll(".en").forEach(function (x) { x.classList.remove("on"); });
        refreshLists();
      });
    });
  });
}
function initDrawing() {
  $("photoInput").addEventListener("change", function (ev) {
    if (ev.target.files && ev.target.files[0]) handleDrawing(ev.target.files[0]);
    this.value = "";
  });
}
function initReport() {
  $("buildReport").addEventListener("click", buildReport);
  $("shareReport").addEventListener("click", function () {
    if (!report.last) { buildReport(); setTimeout(function () { report.share(); }, 400); return; }
    report.share();
  });
}
var report = { last: "", share: function () {
  var me = this;
  if (!me.last) return;
  if (navigator.share) {
    navigator.share({ title: "تقرير MIRA الأسبوعي", text: me.last }).catch(function () {});
  } else if (navigator.clipboard) {
    navigator.clipboard.writeText(me.last).then(function () { toast("نُسخ التقرير 📋"); });
  } else { toast("استخدم أزرار النسخ اليدوية"); }
} };
function initPrivacy() {
  $("exportBtn").addEventListener("click", function () {
    Promise.all([DB.getProfile(), DB.allEntries()]).then(function (res) {
      var blob = new Blob([JSON.stringify({ profile: res[0], entries: res[1], exported: new Date().toISOString(), app: "MIRA Mind PWA v1" }, null, 1)], { type: "application/json" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "miramind-backup-" + new Date().toISOString().slice(0, 10) + ".json";
      a.click();
      URL.revokeObjectURL(a.href);
      toast("صدّرنا نسخة احتياطية ⇩ (لأجلك فقط)");
    });
  });
  $("importBtn").addEventListener("click", function () { $("importFile").click(); });
  $("importFile").addEventListener("change", function (ev) {
    var f = ev.target.files && ev.target.files[0];
    if (!f) return;
    var r = new FileReader();
    r.onload = function (e2) {
      try {
        var data = JSON.parse(e2.target.result);
        var chain = Promise.resolve();
        if (data.profile) chain = chain.then(function () { return DB.setProfile(data.profile); });
        (data.entries || []).forEach(function (en) {
          chain = chain.then(function () {
            /* امسح المُعرّف القديم فتعيد here IndexedDB تسميته */
            var copy = { ts: en.ts, mood: en.mood, energy: en.energy, acts: en.acts || (en.acts ? [] : []), type: en.type };
            if (en.drawing) copy.drawing = en.drawing;
            return DB.addEntry(copy);
          });
        });
        chain.then(function () { toast("استوردنا السجلات ✓"); refreshChildUI(); refreshLists(); });
      } catch (err) { toast("ملف غير صالح"); }
    };
    r.readAsText(f);
    this.value = "";
  });
  $("wipeBtn").addEventListener("click", function () {
    if (confirm("سيُمسح كل ملف الطفل والسجلات والرسومات من هذا الجهاز نهائياً. أكمل؟")) {
      DB.clear().then(function () {
        toast("تم المسح الكامل 🗑️");
        refreshChildUI(); refreshLists();
        $("metricsOut").classList.add("hidden");
        $("previewImg").classList.add("hidden");
        $("reportBody").innerHTML = "<p class='hint'>اضغط للبناء بعد توفر سجلات.</p>";
      });
    }
  });
}
function initSW() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(function () {});
  }
}

/* ── boot ─────────────────────────────────────────────────────────── */
DB.open().then(function () {
  initNav(); initChild(); initDay(); initDrawing(); initReport(); initPrivacy();
  refreshChildUI(); refreshLists(); initSW();
}).catch(function (e) {
  toast("تعذر فتح قاعدة البيانات المحلية: " + e);
});
