import re

with open('dashboard/gui/receptor_profile.html', 'r', encoding='utf-8') as f:
    html = f.read()

new_css = """
/* ATUALIZAÇÃO DO CABEÇALHO */
.receptor-header {
  display: flex;
  gap: var(--s4);
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-md);
  padding: var(--s4) var(--s5);
  margin-bottom: var(--s5);
  transition: opacity 0.2s, transform 0.2s;
}

.receptor-identity {
  display: flex;
  align-items: flex-start;
  gap: var(--s3);
  flex-shrink: 0;
  width: 280px;
}

#hdr-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 8px;
  font-size: 18px;
  font-weight: bold;
  flex-shrink: 0;
  transition: all 0.3s;
}

#hdr-name {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}

#hdr-uuid {
  font-size: 11px;
  color: var(--text-muted);
  font-family: monospace;
  word-break: break-all;
  margin-top: 2px;
}

#hdr-badge {
  display: inline-block;
  border: 1.5px solid #50C878;
  color: #50C878;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.5px;
  margin-top: 8px;
  text-transform: uppercase;
}

.kpi-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  flex: 1;
}

.new-kpi-card {
  background: var(--bg-elevated);
  border-radius: 8px;
  padding: 12px 16px;
  min-width: 120px;
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.new-kpi-label {
  font-size: 10px;
  color: var(--text-muted);
  letter-spacing: 0.8px;
  text-transform: uppercase;
  margin-bottom: 4px;
}

.new-kpi-val {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

.new-kpi-sub {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}

/* RESPONSIVIDADE HEADER */
@media (max-width: 1279px) {
  .new-kpi-card { min-width: 30%; } /* queues in 2 rows */
}
@media (max-width: 959px) { /* 768 - 959 */
  .receptor-identity { width: 220px; }
  #hdr-logo { width: 44px; height: 44px; font-size: 14px; }
  #hdr-name { font-size: 18px; max-width: 160px; }
  .new-kpi-card { min-width: 45%; } /* queues in 3 rows */
}
@media (max-width: 767px) {
  .receptor-header { flex-direction: column; }
  .receptor-identity { width: 100%; max-width: none; }
  #hdr-name { max-width: none; }
}

/* Skeleton Loading */
.skeleton { position: relative; overflow: hidden; background-color: var(--bg-elevated); }
.skeleton::after {
  content: "";
  position: absolute; top: 0; right: 0; bottom: 0; left: 0;
  transform: translateX(-100%);
  background-image: linear-gradient(90deg, rgba(255,255,255, 0) 0, rgba(255,255,255, 0.05) 20%, rgba(255,255,255, 0.05) 60%, rgba(255,255,255, 0));
  animation: shimmer 1.5s infinite;
}
@keyframes shimmer { 100% { transform: translateX(100%); } }
"""

dom_block = """
<!-- ATUALIZAÇÃO DO CABEÇALHO -->
  <div class="receptor-header" id="dynamic-header" style="opacity:0; transform:translateY(-4px);">
    <div class="receptor-identity">
      <div id="hdr-logo">--</div>
      <div>
        <div id="hdr-name">Instituição</div>
        <div id="hdr-uuid">uuid-xyz</div>
        <div id="hdr-badge">ARQUÉTIPO</div>
      </div>
    </div>
    <div class="kpi-strip">
      <div class="new-kpi-card"><div class="new-kpi-label">TOTAL REQUISIÇÕES</div><div class="new-kpi-val" id="kpi-req-v">-</div><div class="new-kpi-sub" id="kpi-req-s">-</div></div>
      <div class="new-kpi-card"><div class="new-kpi-label">CONSENTIMENTOS</div><div class="new-kpi-val" id="kpi-con-v">-</div><div class="new-kpi-sub" id="kpi-con-s">-</div></div>
      <div class="new-kpi-card"><div class="new-kpi-label">INTENSIDADE 30D</div><div class="new-kpi-val" id="kpi-int-v">-</div><div class="new-kpi-sub" id="kpi-int-s">-</div></div>
      <div class="new-kpi-card"><div class="new-kpi-label">TAXA DE ERRO</div><div class="new-kpi-val" id="kpi-err-v">-</div><div class="new-kpi-sub" id="kpi-err-s">-</div></div>
      <div class="new-kpi-card"><div class="new-kpi-label">TRANSMISSORES</div><div class="new-kpi-val" id="kpi-tx-v">-</div><div class="new-kpi-sub" id="kpi-tx-s">-</div></div>
      <div class="new-kpi-card"><div class="new-kpi-label">RANKING VOLUME</div><div class="new-kpi-val" id="kpi-vol-v">-</div><div class="new-kpi-sub" id="kpi-vol-s">-</div></div>
    </div>
  </div>
"""

js_block = """
function getTierColor(t) {
  if(t==="green") return "#50C878";
  if(t==="warning") return "#F5A623";
  if(t==="error") return "#E05252";
  if(t==="gold") return "#F5A623";
  return "var(--text-primary)";
}

function loadSkeleton() {
  document.getElementById('dynamic-header').style.opacity = '1';
  document.getElementById('dynamic-header').style.transform = 'translateY(0)';
  document.getElementById('hdr-logo').className = 'skeleton';
  document.getElementById('hdr-logo').textContent = '';
  document.getElementById('hdr-logo').style.background = 'var(--bg-elevated)';
  document.getElementById('hdr-name').className = 'skeleton';
  document.getElementById('hdr-name').style.color = 'transparent';
  document.getElementById('hdr-uuid').className = 'skeleton';
  document.getElementById('hdr-uuid').style.color = 'transparent';
  document.getElementById('hdr-badge').style.opacity = '0';
  
  const vals = document.querySelectorAll('.new-kpi-val');
  const subs = document.querySelectorAll('.new-kpi-sub');
  vals.forEach(e => { e.className = 'new-kpi-val skeleton'; e.style.color = 'transparent'; e.textContent = '0000'; });
  subs.forEach(e => { e.className = 'new-kpi-sub skeleton'; e.style.color = 'transparent'; e.textContent = 'Loading txt'; });
}

function setKpi(id, txtVal, txtSub, tCol) {
   const ve = document.getElementById(id+'-v');
   const se = document.getElementById(id+'-s');
   ve.textContent = txtVal;
   ve.style.color = tCol;
   ve.className = 'new-kpi-val';
   se.textContent = txtSub;
   se.className = 'new-kpi-sub';
   if (txtSub.includes('+')) se.style.color = '#50C878';
   else se.style.color = 'var(--text-muted)';
}

function renderHeader(headerObj) {
    if (!headerObj.header) return;
    const h = headerObj.header;
    const inst = headerObj.institution;
    
    // Logo
    const lg = document.getElementById('hdr-logo');
    lg.className = '';
    lg.textContent = h.avatar.initials;
    lg.style.background = h.avatar.background_color;
    lg.style.color = h.avatar.text_color;
    
    const nm = document.getElementById('hdr-name');
    nm.className = '';
    nm.style.color = 'var(--text-primary)';
    nm.textContent = inst.label;
    nm.title = inst.label;
    
    const ud = document.getElementById('hdr-uuid');
    ud.className = '';
    ud.style.color = 'var(--text-muted)';
    ud.textContent = inst.id;
    
    const bg = document.getElementById('hdr-badge');
    bg.style.opacity = '1';
    bg.textContent = h.archetype || inst.archetype;
    
    // KPIs
    const kp = h.kpis;
    setKpi('kpi-req', kp.total_requests.formatted, kp.total_requests.subtitle, 'var(--text-primary)');
    setKpi('kpi-con', kp.consents.formatted, kp.consents.subtitle, 'var(--text-primary)');
    setKpi('kpi-int', kp.intensity_30d.formatted, kp.intensity_30d.subtitle, kp.intensity_30d.above_median ? '#50C878' : 'var(--text-primary)');
    setKpi('kpi-err', kp.error_rate.formatted, kp.error_rate.subtitle, getTierColor(kp.error_rate.color_tier));
    setKpi('kpi-tx', kp.transmitters.formatted, kp.transmitters.subtitle, getTierColor(kp.transmitters.color_tier));
    setKpi('kpi-vol', kp.volume_rank.formatted, kp.volume_rank.subtitle, getTierColor(kp.volume_rank.color_tier));
    
    const headArea = document.getElementById('dynamic-header');
    headArea.style.opacity = '0';
    headArea.style.transform = 'translateY(-4px)';
    setTimeout(() => {
        headArea.style.opacity = '1';
        headArea.style.transform = 'translateY(0)';
    }, 50);
}
"""

if '</style>' in html:
    html = html.replace('</style>', new_css + '\n</style>')

# Replace the HTML block
start_tag = '<div class="receptor-header">'
end_tag = '<!-- STRATEGIC MAP + TORNADO -->'
start_idx = html.find(start_tag)
end_idx = html.find(end_tag)

if start_idx != -1 and end_idx != -1:
    html = html[:start_idx] + dom_block + '\n  ' + html[end_idx:]

# Replace JS logic
js_start = html.find('function renderHeader(inst, summary)')
if js_start != -1:
    js_end = html.find('function renderMixChart', js_start)
    if js_end != -1:
        html = html[:js_start] + js_block + '\n' + html[js_end:]

# Add skeleton loading trigger into loadProfile
html = html.replace("document.getElementById('loading-state').style.display = 'block';",
                    "document.getElementById('loading-state').style.display = 'block';\n    document.getElementById('profile-content').style.display = 'block';\n    loadSkeleton();")

html = html.replace("renderHeader(profile.institution, profile.summary);",
                    "renderHeader(profile);")

with open('dashboard/gui/receptor_profile.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Updated HTML!")
