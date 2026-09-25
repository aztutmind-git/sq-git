
window.SyllabusQuestPerformanceThemes = {
  themes: {
    mountain:{title:"Mountain Journey",subtitle:"Climb through your learning journey.",icon:"🏔️"},
    space:{title:"Space Mission",subtitle:"Explore and unlock new learning worlds.",icon:"🚀"},
    ocean:{title:"Ocean Journey",subtitle:"Dive deeper as your understanding grows.",icon:"🐠"},
    garden:{title:"Learning Garden",subtitle:"Grow your knowledge one stage at a time.",icon:"🌱"},
    race:{title:"Learning Race",subtitle:"Build momentum through every level.",icon:"🏎️"},
    classic:{title:"Classic Journey",subtitle:"A clean, focused learning journey.",icon:"⭐"}
  },
  getTheme(){
    return localStorage.getItem("selectedTheme") || localStorage.getItem("theme") || "classic";
  },
  render(container, score){
    const key=this.getTheme();
    const t=this.themes[key] || this.themes.classic;
    const pct=Math.max(0,Math.min(100,Number(score)||0));
    container.className="performance-theme-shell "+key;
    container.innerHTML=`<div class="performance-theme-decoration">${t.icon}</div>
      <div class="theme-title">${t.title}</div>
      <div class="theme-subtitle">${t.subtitle}</div>
      <div class="performance-theme-progress"><span style="width:${pct}%"></span></div>
      <div style="margin-top:10px;font-weight:700">${pct.toFixed(0)}% journey progress</div>`;
  }
};
