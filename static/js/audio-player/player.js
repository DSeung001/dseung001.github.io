/*! mp3 audio player shortcode — native <audio> driven custom controls */
(function () {
  "use strict";

  var allAudioEls = [];

  function loadCSS() {
    if (document.querySelector('link[data-audio-player-css]')) return;
    var link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "/js/audio-player/player.css";
    link.setAttribute("data-audio-player-css", "1");
    document.head.appendChild(link);
  }

  function formatTime(sec) {
    sec = Number(sec);
    if (!isFinite(sec) || sec < 0) sec = 0;
    var total = Math.floor(sec);
    var m = Math.floor(total / 60);
    var s = total % 60;
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  function pauseOthers(audioEl) {
    allAudioEls.forEach(function (el) {
      if (el !== audioEl && !el.paused) el.pause();
    });
  }

  function mount(root) {
    var audioEl = root.querySelector("[data-audio-el]");
    if (!audioEl) return;
    audioEl.removeAttribute("controls");
    allAudioEls.push(audioEl);

    var controls = document.createElement("div");
    controls.className = "audio-player__controls";

    var playBtn = document.createElement("button");
    playBtn.type = "button";
    playBtn.className = "audio-player__play";
    playBtn.setAttribute("aria-label", "재생");
    playBtn.title = "재생";
    playBtn.innerHTML =
      '<svg class="audio-player__icon audio-player__icon--play" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">' +
      '<path d="M8 5v14l11-7z"></path>' +
      "</svg>" +
      '<svg class="audio-player__icon audio-player__icon--pause" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">' +
      '<rect x="6" y="5" width="4" height="14" rx="1"></rect>' +
      '<rect x="14" y="5" width="4" height="14" rx="1"></rect>' +
      "</svg>";

    var scrub = document.createElement("input");
    scrub.type = "range";
    scrub.className = "audio-player__scrub";
    scrub.min = "0";
    scrub.max = "0";
    scrub.value = "0";
    scrub.step = "0.1";
    scrub.setAttribute("aria-label", "재생 위치");

    var timeEl = document.createElement("span");
    timeEl.className = "audio-player__time";
    timeEl.textContent = "0:00 / 0:00";

    controls.appendChild(playBtn);
    controls.appendChild(scrub);
    controls.appendChild(timeEl);
    root.appendChild(controls);

    var scrubbing = false;

    function syncPlayUi() {
      var playing = !audioEl.paused && !audioEl.ended;
      playBtn.classList.toggle("is-playing", playing);
      playBtn.setAttribute("aria-label", playing ? "일시정지" : "재생");
      playBtn.title = playing ? "일시정지" : "재생";
    }

    function syncTime() {
      if (scrubbing) return;
      var duration = isFinite(audioEl.duration) ? audioEl.duration : 0;
      scrub.max = String(duration);
      scrub.value = String(audioEl.currentTime);
      timeEl.textContent =
        formatTime(audioEl.currentTime) + " / " + formatTime(duration);
    }

    playBtn.addEventListener("click", function () {
      if (audioEl.paused) {
        pauseOthers(audioEl);
        audioEl.play();
      } else {
        audioEl.pause();
      }
    });

    audioEl.addEventListener("play", function () {
      pauseOthers(audioEl);
      syncPlayUi();
    });
    audioEl.addEventListener("pause", syncPlayUi);
    audioEl.addEventListener("ended", syncPlayUi);
    audioEl.addEventListener("loadedmetadata", syncTime);
    audioEl.addEventListener("timeupdate", syncTime);

    scrub.addEventListener("pointerdown", function () {
      scrubbing = true;
    });
    scrub.addEventListener("input", function () {
      timeEl.textContent =
        formatTime(Number(scrub.value)) + " / " + formatTime(audioEl.duration);
    });
    function commitScrub() {
      scrubbing = false;
      audioEl.currentTime = Number(scrub.value);
    }
    scrub.addEventListener("change", commitScrub);
    scrub.addEventListener("pointerup", commitScrub);
    scrub.addEventListener("pointercancel", function () {
      scrubbing = false;
    });

    syncPlayUi();
    syncTime();
  }

  function initAll() {
    loadCSS();
    document.querySelectorAll("[data-audio-player]").forEach(function (el) {
      if (el.getAttribute("data-audio-ready")) return;
      el.setAttribute("data-audio-ready", "1");
      mount(el);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAll);
  } else {
    initAll();
  }
})();
