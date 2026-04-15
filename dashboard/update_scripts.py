import re

html_path = 'dashboard/gui/receptor_profile.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

new_script = """<script>
Chart.defaults.color='#8B95B0';
Chart.defaults.borderColor='#252A3A';
Chart.defaults.font.family="-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif";
Chart.defaults.font.size=11;
const TT={backgroundColor:'#1B1F2E',borderColor:'#333B54',borderWidth:1, titleColor:'#EEF0F6',bodyColor:'#8B95B0',padding:10,cornerRadius:6};

let activeCharts = {};

function fmtDate(d){
  const [y,m]=d.split('-');
  return ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'][+m-1]+'/'+y.slice(2);
}
function fmtVal(v, dec=2){ return (v||0).toFixed(dec); }

const GROUP_COLORS={'Conta':'#4A9EFF','Cartão de Crédito':'#F472B6','Investimentos':'#2ECC7F',
  'Crédito':'#FF6B6B','Câmbio':'#A855F7','Identidade':'#F5A623','Resource':'#14B8A6'};

document.addEventListener("DOMContentLoaded", async () => {
    // Carregar Instituições
    try {
        const res = await fetch('/api/of/institutions');
        const data = await res.json();
        const drop = document.getElementById('inst-dropdown');
        data.institutions.forEach(inst => {
            const li = document.createElement('li');
            li.style.cssText = "padding: 8px 12px; cursor: pointer; color: var(--text-secondary);";
            li.textContent = inst.label;
            li.addEventListener('mouseenter', () => li.style.background = 'var(--bg-hover)');
            li.addEventListener('mouseleave', () => li.style.background = 'transparent');
            li.addEventListener('click', () => {
                document.getElementById('inst-search').value = inst.label;
                drop.hidden = true;
                history.replaceState(null, '', `?institution=${encodeURIComponent(inst.id)}`);
                loadProfile(inst.id);
            });
            drop.appendChild(li);
        });
        
        const input = document.getElementById('inst-search');
        input.addEventListener('focus', () => drop.hidden = false);
        input.addEventListener('input', (e) => {
            const val = e.target.value.toLowerCase();
            Array.from(drop.children).forEach(li => {
                li.style.display = li.textContent.toLowerCase().includes(val) ? 'block' : 'none';
            });
        });
        
        // Clicar fora para fechar o dropdown
        document.addEventListener('click', (e) => {
            if (!document.getElementById('institution-selector').contains(e.target)) {
                drop.hidden = true;
            }
        });
        
        // Initial load
        const params = new URLSearchParams(window.location.search);
        const inst = params.get('institution');
        if (inst) {
            const match = data.institutions.find(i => i.id === inst);
            if (match) input.value = match.label;
            loadProfile(inst);
        }
    } catch(err) {
        console.error(err);
    }
});

async function loadProfile(institutionId) {
    document.getElementById('empty-state').style.display = 'none';
    document.getElementById('error-state').style.display = 'none';
    document.getElementById('profile-content').style.display = 'none';
    document.getElementById('loading-state').style.display = 'block';

    try {
        const [profileRes, statsRes] = await Promise.all([
            fetch(`/api/of/receptor-profile?institution=${encodeURIComponent(institutionId)}`),
            fetch('/api/of/ecosystem-stats')
        ]);

        if (!profileRes.ok) {
            document.getElementById('error-state').style.display = 'block';
            document.getElementById('error-state').textContent = `Erro ao carregar dados (${profileRes.status}): Instituição não encontrada ou sem volume.`;
            document.getElementById('loading-state').style.display = 'none';
            return;
        }

        const profile = await profileRes.json();
        const ecosystemStats = await statsRes.json();

        document.getElementById('loading-state').style.display = 'none';
        document.getElementById('profile-content').style.display = 'block';

        renderHeader(profile.institution, profile.summary);
        renderTornadoChart(profile.tornado_data);
        renderMixChart(profile.mix_data);
        renderEndpointSection(profile.endpoint_data, ecosystemStats.stats);
    } catch(err) {
        console.error(err);
        document.getElementById('error-state').style.display = 'block';
        document.getElementById('loading-state').style.display = 'none';
    }
}

function renderHeader(inst, summary) {
    document.querySelector('.receptor-logo').textContent = inst.id.substring(0,3);
    document.querySelector('.receptor-name').textContent = inst.label;
    document.querySelector('.receptor-uuid').textContent = inst.uuid || 'N/A';
    document.querySelector('.archetype-badge').textContent = inst.archetype;
    
    // update kpis strips
    const kpis = document.querySelectorAll('.kpi-value');
    if(kpis.length >= 4){
        // API total (not returned by PRD exactly? let's mock or use active apis)
        kpis[0].textContent = summary.active_apis;
        kpis[0].nextElementSibling.textContent = "APIs Ativas Mapeadas";
        
        kpis[1].textContent = (summary.total_consents > 1000000 ? (summary.total_consents/1000000).toFixed(1) + 'M' : (summary.total_consents/1000).toFixed(1) + 'k');
        kpis[1].nextElementSibling.textContent = "Consentimentos no Período";
        
        kpis[2].textContent = summary.top_category || "N/A";
        kpis[2].nextElementSibling.textContent = "Categoria Principal";
        
        kpis[3].textContent = summary.weeks_count;
        kpis[3].nextElementSibling.textContent = "Semanas Analisadas";
    }
    
    document.querySelector('.titlebar-period').textContent = "Dados atualizados";
}

function renderMixChart(mixData) {
    const dates = mixData.map(d => d.date);
    // groups mapping based on PRD slug keys vs colors
    const datasetDefs = [
        {key: 'accounts', label: 'Conta', color: GROUP_COLORS['Conta']},
        {key: 'credit_cards_accounts', label: 'Cartão', color: GROUP_COLORS['Cartão de Crédito']},
        {key: 'bank_fixed_incomes', label: 'Investimento', color: GROUP_COLORS['Investimentos']},
        {key: 'loans', label: 'Crédito', color: GROUP_COLORS['Crédito']},
        {key: 'customers', label: 'Identidade', color: GROUP_COLORS['Identidade']},
        {key: 'exchanges', label: 'Câmbio', color: GROUP_COLORS['Câmbio']}
    ];

    const datasets = datasetDefs.map(def => {
        return {
            label: def.label,
            data: mixData.map(d => {
                // Sum any keys that might belong to the same overarching group if needed, but here we just take the primary one as representation
                // Or better, PRD mixData has discrete api_slugs.
                return d[def.key] || 0;
            }),
            backgroundColor: def.color + 'BB',
            borderColor: def.color,
            borderWidth: 0.5,
            fill: true,
            tension: 0.3,
            pointRadius: 0,
            pointHoverRadius: 4
        };
    });

    if(activeCharts['stacked']) activeCharts['stacked'].destroy();
    
    const ctx = document.getElementById('stackedIntensityChart');
    if(!ctx) return;
    
    activeCharts['stacked'] = new Chart(ctx, {
        type: 'line',
        data: {labels: dates.map(fmtDate), datasets},
        options: {
            responsive: true, maintainAspectRatio: false,
            interaction: {mode: 'index', intersect: false},
            scales: {
                x: {grid: {color: '#252A3A'}, ticks: {maxRotation: 0, maxTicksLimit: 13}},
                y: {stacked: true, grid: {color: '#252A3A'}, min: 0,
                   ticks: {callback: v => v.toFixed(0)},
                   title: {display: true, text: 'req/consent/30d', color: '#4A5270', font: {size: 10}}}
            },
            plugins: {
                legend: {display: false},
                tooltip: {...TT}
            }
        }
    });
}

function renderTornadoChart(tornadoData) {
    const container = document.getElementById('tornadoContainer');
    if(!container) return;
    container.innerHTML = '';
    
    // Change labels to match PRD tornado data (institution vs ecosystem share)
    document.querySelector('.tornado-header-left').textContent = "Share Ecossistema";
    document.querySelector('.tornado-header-center').textContent = "Categoria";
    document.querySelector('.tornado-header-right').textContent = "Share Instituição";
    document.querySelector('.chart-title:nth-of-type(1)').textContent = "Perfil de Consumo vs Ecossistema";
    
    const maxVal = Math.max(...tornadoData.map(d => Math.max(d.ecosystem_share||0, d.institution_share||0)), 0.1);
    const BAR_MAX = 160;
    
    tornadoData.forEach(d => {
        const row = document.createElement('div');
        row.className = 'tornado-row';
        const leftW = Math.round(((d.ecosystem_share||0)/maxVal)*BAR_MAX);
        const rightW = Math.round(((d.institution_share||0)/maxVal)*BAR_MAX);
        
        row.innerHTML = `
          <div class="tornado-left-bar">
            <div class="tornado-value">${((d.ecosystem_share||0)*100).toFixed(1)}%</div>
            <div class="t-bar" style="background:#4A5270; width:${leftW}px; margin-left:4px"></div>
          </div>
          <div class="tornado-name" title="${d.label}">${d.label}</div>
          <div class="tornado-right-bar">
            <div class="t-bar" style="background:var(--text-accent); width:${rightW}px; margin-right:4px"></div>
            <div class="tornado-value">${((d.institution_share||0)*100).toFixed(1)}%</div>
          </div>
        `;
        container.appendChild(row);
    });
}

function renderEndpointSection(endpointData, ecosystemStats) {
  const section = document.getElementById('endpointSection');
  if(!section) return;
  section.innerHTML = '';
  const EP_BAR_W = 120;
  const GRP_BAR_W = 110;

  function fmtVal(v){return v<0.01?v.toFixed(4):v<0.1?v.toFixed(3):v.toFixed(2);}
  
  function intensityBar(total, color, trackW, height){
    const fillW=Math.max(1,Math.min(trackW,Math.round((total/50)*trackW))); // 50 as a generic max ref
    return `<div style="display:flex;align-items:center;gap:5px;margin-left:auto;flex-shrink:0">
      <div style="width:${trackW}px;height:${height}px;background:var(--bg-base);border-radius:${height}px;overflow:hidden;flex-shrink:0">
        <div style="width:${fillW}px;height:100%;background:${color};opacity:0.75;border-radius:${height}px"></div>
      </div>
      <span style="font-size:10px;color:var(--text-muted);font-variant-numeric:tabular-nums;min-width:38px;text-align:right">${total.toFixed(1)}</span>
    </div>`;
  }
  
  function epRow(displayName, rawEpName, apiKey, val, maxEp, color){
    const barFill=Math.max(1,Math.min(EP_BAR_W,Math.round((val/maxEp)*EP_BAR_W)));
    const statsKey=apiKey+'|||'+rawEpName;
    const stats=ecosystemStats[statsKey]||null;
    let ticks='';
    if(stats){
      const mPx=Math.min(Math.round((stats.median/maxEp)*EP_BAR_W),EP_BAR_W);
      const q3Px=Math.min(Math.round((stats.q3/maxEp)*EP_BAR_W),EP_BAR_W);
      if(mPx>0) ticks+=`<div class="ep-ref-tick ep-ref-median" style="left:${mPx}px" title="Mediana ecossistema: ${fmtVal(stats.median)}"></div>`;
      if(q3Px>0) ticks+=`<div class="ep-ref-tick ep-ref-q3" style="left:${q3Px}px" title="3º Quartil (top 25%): ${fmtVal(stats.q3)}"></div>`;
    }
    return `<div class="ep-row">
      <div class="ep-name" title="${displayName}">${displayName}</div>
      <div class="ep-bar-track-wrap">
        <div class="ep-bar-track" style="width:${EP_BAR_W}px;height:6px;background:var(--bg-surface);border-radius:3px;position:relative">
          <div class="ep-bar-fill" style="width:${barFill}px;background:${color}88;height:100%;border-radius:3px"></div>
          ${ticks}
        </div>
      </div>
      <div class="ep-val">${fmtVal(val)}</div>
    </div>`;
  }

  Object.entries(endpointData).forEach(([groupName, groupObj]) => {
    const groupDiv = document.createElement('div');
    groupDiv.className = 'ep-group';
    const bgBase = `${groupObj.color}18`;
    const bgHover = `${groupObj.color}2E`;
    
    const hdr = document.createElement('div');
    hdr.className = 'ep-group-header';
    hdr.style.cssText = `display:flex;align-items:center;gap:var(--s2);padding:var(--s2) var(--s3);
      border-radius:var(--r-sm);background:${bgBase};border-left:3px solid ${groupObj.color};
      transition:background 0.15s; cursor:pointer;`;
      
    // Group totals
    let grpTotal = 0;
    Object.values(groupObj.apis).forEach(a => {
        Object.values(a.endpoints).forEach(v => grpTotal += v);
    });
    
    hdr.innerHTML = `
      <span class="ep-chevron" id="chev-${groupName}">▼</span>
      <div class="ep-group-name" style="color:${groupObj.color}">${groupName}</div>
      ${intensityBar(grpTotal, groupObj.color, GRP_BAR_W, 5)}
    `;
    hdr.addEventListener('mouseenter',()=> hdr.style.background=bgHover );
    hdr.addEventListener('mouseleave',()=> hdr.style.background=bgBase );
    groupDiv.appendChild(hdr);

    const grid = document.createElement('div');
    grid.className = 'ep-apis-grid';
    grid.style.marginTop = 'var(--s3)';

    hdr.addEventListener('click', () => {
      const isOpen = grid.style.display !== 'none';
      grid.style.display = isOpen ? 'none' : 'grid';
      document.getElementById('chev-'+groupName).classList.toggle('collapsed', isOpen);
    });

    Object.entries(groupObj.apis).forEach(([apiKey, apiData]) => {
        const card = document.createElement('div');
        card.className = 'ep-api-card';
        let apiTotal = 0;
        Object.values(apiData.endpoints).forEach(v => apiTotal+=v);
        
        let cardInner = `<div class="ep-api-name" style="flex-wrap:wrap;row-gap:4px">
          <div class="ep-api-dot" style="background:${groupObj.color}"></div>
          <span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis">${apiData.label}</span>
          ${intensityBar(apiTotal, groupObj.color, GRP_BAR_W, 4)}
        </div>`;
        
        const epQ3s = Object.keys(apiData.endpoints).map(ep=>(ecosystemStats[apiKey+'|||'+ep]||{}).q3||0);
        const maxEp = Math.max(...Object.values(apiData.endpoints), ...epQ3s, 1.0);
        
        Object.entries(apiData.endpoints).forEach(([ep, val]) => {
          cardInner += epRow(ep, ep, apiKey, val, maxEp, groupObj.color);
        });
        
        card.innerHTML = cardInner;
        grid.appendChild(card);
    });
    
    groupDiv.appendChild(grid);
    section.appendChild(groupDiv);
  });
}
</script>"""

script_start = html.find('<script>')
if script_start != -1:
    html = html[:script_start] + new_script
else:
    html += new_script

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
print("Updated Scripts!")
