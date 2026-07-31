/*! Chantrace traffic map — rank heat + replay + cursor tooltip */
(function () {
  "use strict";

  var COLOR_IDLE = "#9aa3ad";
  var COLOR_OK = "#2f9e8a";
  var TIP_OFFSET = 14;
  var BASE_INTERVAL_MS = 80;
  var TARGET_FRAMES = 200;
  var SPEED_MULT = [0.5, 1, 2];
  var SPEED_LABEL = ["0.5x", "1x", "2x"];
  // light blue → teal → yellow → orange → rust
  var HEAT_STOPS = [
    [125, 211, 252],
    [45, 212, 191],
    [250, 204, 21],
    [249, 115, 22],
    [153, 27, 27],
  ];

  function fmtNS(ns) {
    ns = Number(ns) || 0;
    if (ns === 0) return "0";
    var ms = ns / 1e6;
    if (ms >= 1) return ns + "ns (" + ms.toFixed(2) + "ms)";
    if (ms >= 0.001) return ns + "ns (" + (ms * 1000).toFixed(2) + "µs)";
    return ns + "ns";
  }

  function fmtShort(ns) {
    ns = Number(ns) || 0;
    if (ns === 0) return "";
    var ms = ns / 1e6;
    if (ms >= 10) return Math.round(ms) + "ms";
    if (ms >= 1) return ms.toFixed(1) + "ms";
    if (ms >= 0.001) return Math.round(ms * 1000) + "µs";
    return ns + "ns";
  }

  function loadCSS() {
    if (document.querySelector('link[data-chan-replay-css]')) return;
    var link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "/js/chan-replay/player.css";
    link.setAttribute("data-chan-replay-css", "1");
    document.head.appendChild(link);
  }

  function accumulate(events, endIdx) {
    var chans = {};
    var last = events.length - 1;
    if (endIdx == null || endIdx > last) endIdx = last;
    if (endIdx < 0) return chans;
    var i;
    for (i = 0; i <= endIdx; i++) {
      var ev = events[i];
      var c = chans[ev.id];
      if (!c) {
        c = {
          id: ev.id,
          cap: ev.cap || 0,
          q: 0,
          created: false,
          ops: 0,
          blockedSum: 0,
          blockedMax: 0,
          blockedCount: 0,
        };
        chans[ev.id] = c;
      }
      if (ev.kind === "create") {
        c.created = true;
        c.cap = ev.cap || 0;
      } else if (ev.kind === "send" || ev.kind === "recv") {
        c.ops++;
        c.q = ev.q || 0;
        if (ev.cap != null) c.cap = ev.cap;
        c.blockedSum += ev.blocked_ns || 0;
        if ((ev.blocked_ns || 0) > c.blockedMax) c.blockedMax = ev.blocked_ns;
        if ((ev.blocked_ns || 0) > 0) c.blockedCount++;
      }
    }
    return chans;
  }

  // Average-rank percentile for blocked_max>0 in the current window.
  function blockedRankT(chans, ids) {
    var items = [];
    var i;
    for (i = 0; i < ids.length; i++) {
      var c = chans[ids[i]];
      if (c && c.blockedMax > 0) items.push({ id: ids[i], v: c.blockedMax });
    }
    items.sort(function (a, b) {
      return a.v - b.v;
    });
    var ranks = {};
    i = 0;
    while (i < items.length) {
      var j = i;
      while (j < items.length && items[j].v === items[i].v) j++;
      var avg = (i + j - 1) / 2;
      var t = items.length === 1 ? 1 : avg / (items.length - 1);
      var k;
      for (k = i; k < j; k++) ranks[items[k].id] = t;
      i = j;
    }
    return ranks;
  }

  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  function heatColor(t) {
    t = Math.max(0, Math.min(1, t));
    var n = HEAT_STOPS.length - 1;
    var x = t * n;
    var i = Math.min(n - 1, Math.floor(x));
    var f = x - i;
    var a = HEAT_STOPS[i];
    var b = HEAT_STOPS[i + 1];
    return (
      "rgb(" +
      Math.round(lerp(a[0], b[0], f)) +
      "," +
      Math.round(lerp(a[1], b[1], f)) +
      "," +
      Math.round(lerp(a[2], b[2], f)) +
      ")"
    );
  }

  function channelColor(c, rankT) {
    if (!c || !c.created || c.ops === 0) return COLOR_IDLE;
    if (c.blockedMax === 0) return COLOR_OK;
    var t = rankT[c.id];
    if (t == null) t = 0;
    return heatColor(t);
  }

  function heatBarCSS() {
    return (
      "linear-gradient(90deg," +
      heatColor(0) +
      "," +
      heatColor(0.25) +
      "," +
      heatColor(0.5) +
      "," +
      heatColor(0.75) +
      "," +
      heatColor(1) +
      ")"
    );
  }

  function Mount(root) {
    this.root = root;
    this.url = root.getAttribute("data-json");
    this.data = null;
    this.chans = {};
    this.ids = [];
    this.rankT = {};
    this.idx = 0;
    this.playing = false;
    this.timer = null;
    this.speedIdx = 1;
    this.hoverId = null;
    this.flashId = null;
    this.lastClientX = 0;
    this.lastClientY = 0;
    this.pointerInSvg = false;
    loadCSS();
    this.root.innerHTML = '<p class="chan-replay__meta">맵 로딩 중…</p>';
    var self = this;
    fetch(this.url)
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        self.data = data;
        var finalChans = accumulate(data.events || []);
        self.ids = Object.keys(finalChans)
          .map(Number)
          .sort(function (a, b) {
            return a - b;
          });
        self.idx = 0;
        self.renderShell();
        self.buildMapSkeleton();
        self.bindMap();
        self.bindControls();
        self.render();
        self.hideTip();
      })
      .catch(function (err) {
        self.root.innerHTML =
          '<p class="chan-replay__err">맵 로드 실패: ' +
          String(err.message || err) +
          "</p>";
      });
  }

  Mount.prototype.activeId = function () {
    return this.hoverId;
  };

  Mount.prototype.playInterval = function () {
    return Math.max(20, Math.round(BASE_INTERVAL_MS / SPEED_MULT[this.speedIdx]));
  };

  Mount.prototype.playStride = function () {
    var n = (this.data.events || []).length;
    return Math.max(1, Math.ceil(n / TARGET_FRAMES));
  };

  Mount.prototype.renderShell = function () {
    var meta = (this.data && this.data.meta) || {};
    var last = Math.max(0, (this.data.events || []).length - 1);
    this.root.innerHTML =
      '<div class="chan-replay__title">chantrace traffic map</div>' +
      '<p class="chan-replay__meta" data-meta></p>' +
      '<div class="chan-replay__controls">' +
      '<button type="button" data-act="play">Play</button>' +
      '<button type="button" data-act="reset">Reset</button>' +
      '<button type="button" data-act="end">End</button>' +
      '<button type="button" data-act="speed">Speed: 1x</button>' +
      '<span class="chan-replay__step" data-step>step 0 / ' +
      last +
      "</span>" +
      '<input class="chan-replay__scrub" type="range" min="0" max="' +
      last +
      '" value="0" data-scrub aria-label="이벤트 위치" />' +
      "</div>" +
      '<div class="chan-replay__legend" data-legend></div>' +
      '<p class="chan-replay__hint">Play로 누적을 재생합니다(기본 약 15–20초). 색은 같은 시점 채널 간 blocked_max 순위입니다. 원에 마우스를 올리면 상세가 뜹니다.</p>' +
      '<div class="chan-replay__svg-wrap" data-svg></div>' +
      '<div class="chan-replay__tip" data-tip hidden role="tooltip"></div>';

    this.root.querySelector("[data-meta]").textContent =
      "channels=" +
      (meta.channels || this.ids.length) +
      " · messages=" +
      (meta.messages || 0) +
      " · blocked_events=" +
      (meta.blocked_events || 0) +
      " · blocked_sum=" +
      fmtNS(meta.blocked_sum_ns || 0) +
      " · blocked_max=" +
      fmtNS(meta.blocked_max_ns || 0);

    this.root.querySelector("[data-legend]").innerHTML =
      '<span class="chan-replay__legend-item"><span class="chan-replay__swatch" style="background:' +
      COLOR_IDLE +
      '"></span>미사용</span>' +
      '<span class="chan-replay__legend-item"><span class="chan-replay__swatch" style="background:' +
      COLOR_OK +
      '"></span>park 없음</span>' +
      '<span class="chan-replay__legend-item chan-replay__legend-heat">' +
      '<span class="chan-replay__heatbar" style="background:' +
      heatBarCSS() +
      '"></span>' +
      "<span>blocked_max 낮음 → 높음 (순위)</span></span>";
  };

  Mount.prototype.bindControls = function () {
    var self = this;
    var play = this.root.querySelector('[data-act="play"]');
    var reset = this.root.querySelector('[data-act="reset"]');
    var end = this.root.querySelector('[data-act="end"]');
    var speed = this.root.querySelector('[data-act="speed"]');
    var scrub = this.root.querySelector("[data-scrub]");
    if (play) {
      play.onclick = function () {
        self.togglePlay();
      };
    }
    if (reset) {
      reset.onclick = function () {
        self.stopPlay();
        self.idx = 0;
        self.render();
      };
    }
    if (end) {
      end.onclick = function () {
        self.stopPlay();
        self.idx = Math.max(0, self.data.events.length - 1);
        self.render();
      };
    }
    if (speed) {
      speed.onclick = function () {
        var was = self.playing;
        self.stopPlay();
        self.speedIdx = (self.speedIdx + 1) % SPEED_MULT.length;
        speed.textContent = "Speed: " + SPEED_LABEL[self.speedIdx];
        if (was) self.togglePlay();
      };
    }
    if (scrub) {
      scrub.oninput = function () {
        self.stopPlay();
        self.idx = Number(scrub.value);
        self.render();
      };
    }
  };

  Mount.prototype.togglePlay = function () {
    if (this.playing) {
      this.stopPlay();
      return;
    }
    if (this.idx >= this.data.events.length - 1) this.idx = 0;
    this.playing = true;
    var btn = this.root.querySelector('[data-act="play"]');
    if (btn) {
      btn.textContent = "Pause";
      btn.classList.add("is-active");
    }
    var self = this;
    var stride = this.playStride();
    this.timer = setInterval(function () {
      if (self.idx >= self.data.events.length - 1) {
        self.stopPlay();
        return;
      }
      self.idx = Math.min(self.data.events.length - 1, self.idx + stride);
      self.render();
    }, this.playInterval());
  };

  Mount.prototype.stopPlay = function () {
    this.playing = false;
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    var btn = this.root.querySelector('[data-act="play"]');
    if (btn) {
      btn.textContent = "Play";
      btn.classList.remove("is-active");
    }
  };

  Mount.prototype.buildMapSkeleton = function () {
    var wrap = this.root.querySelector("[data-svg]");
    if (!wrap) return;
    var ids = this.ids;
    var n = ids.length || 1;
    var cols = Math.max(2, Math.ceil(Math.sqrt(n)) * 2);
    var cell = 52;
    var pad = 12;
    var width = pad * 2 + cols * cell;
    var rows = Math.ceil(n / cols) || 1;
    var height = pad * 2 + rows * cell;

    var nodes = ids
      .map(function (id, i) {
        var x = pad + (i % cols) * cell + cell / 2;
        var y = pad + Math.floor(i / cols) * cell + cell / 2 - 4;
        var r = 13;
        return (
          '<g data-cid="' +
          id +
          '" aria-label="C' +
          id +
          '">' +
          '<circle cx="' +
          x +
          '" cy="' +
          y +
          '" r="' +
          r +
          '" fill="' +
          COLOR_IDLE +
          '" stroke="#fff" stroke-width="1"/>' +
          '<text class="chan-replay__id" x="' +
          x +
          '" y="' +
          (y + 3.5) +
          '" text-anchor="middle" font-size="8" font-weight="600" fill="#fff" pointer-events="none">' +
          id +
          "</text>" +
          '<text class="chan-replay__time" data-time x="' +
          x +
          '" y="' +
          (y + r + 11) +
          '" text-anchor="middle" font-size="8" fill="#555" pointer-events="none"></text>' +
          "</g>"
        );
      })
      .join("");

    wrap.innerHTML =
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' +
      width +
      " " +
      height +
      '" role="img" aria-label="채널 blocked_max 히트맵">' +
      nodes +
      "</svg>";
  };

  Mount.prototype.currentFlashId = function () {
    var ev = this.data.events[this.idx];
    if (!ev) return null;
    if (
      (ev.kind === "send" || ev.kind === "recv") &&
      (ev.blocked_ns || 0) > 0
    ) {
      return ev.id;
    }
    return null;
  };

  Mount.prototype.render = function () {
    this.chans = accumulate(this.data.events || [], this.idx);
    this.rankT = blockedRankT(this.chans, this.ids);
    this.flashId = this.currentFlashId();
    var scrub = this.root.querySelector("[data-scrub]");
    var step = this.root.querySelector("[data-step]");
    if (scrub) scrub.value = String(this.idx);
    if (step) {
      step.textContent =
        "step " + this.idx + " / " + (this.data.events.length - 1);
    }
    this.updateFills();
    this.updateSelection();
    // 툴팁은 포인터가 SVG 안에 있을 때만 유지/갱신
    if (!this.pointerInSvg) {
      this.hideTip();
      return;
    }
    var tipId = this.activeId();
    if (tipId != null) {
      this.showTip(tipId);
    } else if (this.flashId != null) {
      this.showTip(this.flashId);
    } else {
      this.hideTip();
    }
  };

  Mount.prototype.updateFills = function () {
    var wrap = this.root.querySelector("[data-svg]");
    if (!wrap) return;
    var self = this;
    wrap.querySelectorAll("[data-cid]").forEach(function (g) {
      var id = Number(g.getAttribute("data-cid"));
      var circle = g.querySelector("circle");
      var timeEl = g.querySelector("[data-time]");
      var c = self.chans[id];
      if (circle) {
        circle.setAttribute("fill", channelColor(c, self.rankT));
      }
      if (timeEl) {
        timeEl.textContent =
          c && c.blockedMax > 0 ? fmtShort(c.blockedMax) : "";
      }
    });
  };

  Mount.prototype.updateSelection = function () {
    var active = this.activeId();
    var flash = this.flashId;
    var wrap = this.root.querySelector("[data-svg]");
    if (!wrap) return;
    wrap.querySelectorAll("[data-cid]").forEach(function (g) {
      var id = Number(g.getAttribute("data-cid"));
      var circle = g.querySelector("circle");
      if (!circle) return;
      var on = active === id;
      var isFlash = flash === id;
      if (on) {
        circle.setAttribute("stroke", "#111");
        circle.setAttribute("stroke-width", "2.5");
        circle.classList.remove("is-flash");
      } else if (isFlash) {
        circle.setAttribute("stroke", "#7c2d12");
        circle.setAttribute("stroke-width", "3");
        circle.classList.add("is-flash");
      } else {
        circle.setAttribute("stroke", "#fff");
        circle.setAttribute("stroke-width", "1");
        circle.classList.remove("is-flash");
      }
    });
  };

  Mount.prototype.placeTip = function (clientX, clientY) {
    var tip = this.root.querySelector("[data-tip]");
    if (!tip || tip.hidden) return;
    if (clientX != null) this.lastClientX = clientX;
    if (clientY != null) this.lastClientY = clientY;
    if (!this.lastClientX && !this.lastClientY) {
      var wrap = this.root.querySelector("[data-svg]");
      var g =
        wrap &&
        wrap.querySelector(
          '[data-cid="' + (this.activeId() || this.flashId) + '"]'
        );
      var circle = g && g.querySelector("circle");
      if (circle) {
        var rect = circle.getBoundingClientRect();
        this.lastClientX = rect.right;
        this.lastClientY = rect.top;
      }
    }

    var vw = window.innerWidth;
    var vh = window.innerHeight;
    // 커서가 뷰포트 밖이면 호버창 숨김
    if (
      this.lastClientX < 0 ||
      this.lastClientY < 0 ||
      this.lastClientX > vw ||
      this.lastClientY > vh
    ) {
      this.hideTip();
      return;
    }

    var rootRect = this.root.getBoundingClientRect();
    var x = this.lastClientX - rootRect.left + TIP_OFFSET;
    var y = this.lastClientY - rootRect.top + TIP_OFFSET;
    tip.style.left = "0px";
    tip.style.top = "0px";
    tip.style.visibility = "hidden";
    tip.hidden = false;
    var tw = tip.offsetWidth;
    var th = tip.offsetHeight;
    tip.style.visibility = "";

    // 가능하면 맵 루트 안에 두고, 그래도 뷰포트를 벗어나면 숨김
    var maxX = this.root.clientWidth - tw - 4;
    var maxY = this.root.clientHeight - th - 4;
    if (x > maxX) x = this.lastClientX - rootRect.left - tw - TIP_OFFSET;
    if (y > maxY) y = this.lastClientY - rootRect.top - th - TIP_OFFSET;
    x = Math.max(4, x);
    y = Math.max(4, y);
    tip.style.left = x + "px";
    tip.style.top = y + "px";

    var tipRect = tip.getBoundingClientRect();
    var fullyOutside =
      tipRect.right < 0 ||
      tipRect.bottom < 0 ||
      tipRect.left > vw ||
      tipRect.top > vh;
    var mostlyOutside =
      tipRect.left < 0 ||
      tipRect.top < 0 ||
      tipRect.right > vw ||
      tipRect.bottom > vh;
    if (fullyOutside || mostlyOutside) {
      this.hideTip();
    }
  };

  Mount.prototype.hideTip = function () {
    var tip = this.root.querySelector("[data-tip]");
    if (!tip) return;
    tip.hidden = true;
    tip.innerHTML = "";
  };

  Mount.prototype.showTip = function (id, clientX, clientY) {
    var tip = this.root.querySelector("[data-tip]");
    if (!tip || id == null || !this.chans[id]) {
      this.hideTip();
      return;
    }
    var c = this.chans[id];
    var flash = this.flashId === id;
    tip.innerHTML =
      '<div class="chan-replay__tip-title">C' +
      c.id +
      (flash ? " (park)" : "") +
      "</div>" +
      '<div class="chan-replay__tip-row"><span>cap/q</span><b>' +
      c.q +
      "/" +
      c.cap +
      "</b></div>" +
      '<div class="chan-replay__tip-row"><span>max</span><b>' +
      fmtNS(c.blockedMax) +
      "</b></div>" +
      '<div class="chan-replay__tip-row"><span>sum</span><b>' +
      fmtNS(c.blockedSum) +
      "</b></div>" +
      '<div class="chan-replay__tip-row"><span>count</span><b>' +
      c.blockedCount +
      "</b></div>" +
      '<div class="chan-replay__tip-row"><span>ops</span><b>' +
      c.ops +
      "</b></div>";
    tip.hidden = false;
    this.placeTip(
      clientX != null ? clientX : this.lastClientX,
      clientY != null ? clientY : this.lastClientY
    );
  };

  Mount.prototype.bindMap = function () {
    var wrap = this.root.querySelector("[data-svg]");
    if (!wrap || wrap.getAttribute("data-bound")) return;
    wrap.setAttribute("data-bound", "1");
    var self = this;

    function cidFromEvent(e) {
      var g = e.target.closest("[data-cid]");
      return g ? Number(g.getAttribute("data-cid")) : null;
    }

    function leaveSvg() {
      self.pointerInSvg = false;
      self.hoverId = null;
      self.updateSelection();
      self.hideTip();
    }

    wrap.addEventListener("pointerenter", function () {
      self.pointerInSvg = true;
    });
    wrap.addEventListener("pointerleave", leaveSvg);

    wrap.addEventListener("pointerover", function (e) {
      self.pointerInSvg = true;
      var id = cidFromEvent(e);
      if (id == null) return;
      self.hoverId = id;
      self.updateSelection();
      self.showTip(id, e.clientX, e.clientY);
    });
    wrap.addEventListener("pointermove", function (e) {
      self.pointerInSvg = true;
      var id = cidFromEvent(e);
      if (id == null) {
        self.hoverId = null;
        self.updateSelection();
        self.hideTip();
        return;
      }
      if (self.hoverId !== id) {
        self.hoverId = id;
        self.updateSelection();
        self.showTip(id, e.clientX, e.clientY);
      } else {
        self.placeTip(e.clientX, e.clientY);
      }
    });
    window.addEventListener(
      "scroll",
      function () {
        if (!self.pointerInSvg) {
          self.hideTip();
          return;
        }
        var tip = self.root.querySelector("[data-tip]");
        if (tip && !tip.hidden) self.placeTip();
      },
      true
    );
    window.addEventListener("resize", function () {
      if (!self.pointerInSvg) {
        self.hideTip();
        return;
      }
      var tip = self.root.querySelector("[data-tip]");
      if (tip && !tip.hidden) self.placeTip();
    });
  };

  function initAll() {
    document.querySelectorAll("[data-chan-replay]").forEach(function (el) {
      if (el.getAttribute("data-chan-replay-ready")) return;
      el.setAttribute("data-chan-replay-ready", "1");
      new Mount(el);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAll);
  } else {
    initAll();
  }
})();
