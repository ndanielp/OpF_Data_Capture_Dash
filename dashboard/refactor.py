import re

html_path = 'dashboard/gui/receptor_profile.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Update Title bar
html = html.replace(
'''  <div class="titlebar">
    <div class="titlebar-logo">OF</div>
    <span class="titlebar-name">Open Finance Brasil</span>
    <span class="titlebar-sep">›</span>
    <span class="titlebar-sub">Perfil Estratégico — Receptor</span>
    <div class="titlebar-spacer"></div>
    <span class="titlebar-period">Jun/2025 – Mar/2026 · Dados semanais · Intensidade normalizada 30 dias</span>
  </div>''',
'''  <!-- TITLEBAR -->
  <div class="titlebar">
    <div class="titlebar-logo">OF</div>
    <span class="titlebar-name">Open Finance Brasil</span>
    <span class="titlebar-sep" style="color: var(--text-muted); margin: 0 var(--s2);">›</span>
    
    <!-- Navegação de Abas -->
    <div style="display: flex; gap: var(--s2); margin-left: var(--s3); background: rgba(0,0,0,0.1); padding: 3px; border-radius: var(--r-md); border: 1px solid var(--border-subtle);">
      <a href="/" style="color: var(--text-secondary); text-decoration: none; font-size: var(--tx-sm); font-weight: 500; padding: 3px 12px; border-radius: var(--r-sm); transition: color 0.15s;">Ecossistema</a>
      <a href="/profile" style="color: var(--text-primary); text-decoration: none; font-size: var(--tx-sm); font-weight: 600; padding: 3px 12px; border-radius: var(--r-sm); background: var(--bg-hover); box-shadow: 0 1px 2px rgba(0,0,0,0.2);">Perfil Receptores</a>
    </div>

    <div class="titlebar-spacer"></div>
    <button id="theme-toggle" class="theme-btn" title="Alternar Tema" style="background:transparent;border:none;cursor:pointer;color:inherit">☀️/🌙</button>
  </div>'''
)

# 2. Add institution selector
header_idx = html.find('<!-- HEADER -->')
if header_idx != -1:
    selector_html = '''
  <div id="institution-selector" style="margin-bottom: var(--s5); background: var(--bg-surface); padding: var(--s4); border-radius: var(--r-md); border: 1px solid var(--border-subtle); display: flex; align-items: center; gap: var(--s3); position: relative; z-index: 100;">
    <label for="inst-search" style="font-weight: 600;">Instituição:</label>
    <div style="position: relative; width: 300px;">
      <input type="text" id="inst-search" placeholder="Buscar instituição..." autocomplete="off" style="width: 100%; background: var(--bg-elevated); border: 1px solid var(--border-default); color: var(--text-primary); padding: 8px 12px; border-radius: var(--r-sm); font-size: var(--tx-sm); outline: none;">
      <ul id="inst-dropdown" hidden style="position: absolute; top: 100%; left: 0; width: 100%; background: var(--bg-elevated); border: 1px solid var(--border-default); list-style: none; margin: 4px 0 0; padding: 0; border-radius: var(--r-sm); max-height: 200px; overflow-y: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.5);"></ul>
    </div>
  </div>
  
  <div id="empty-state" style="display:flex; flex-direction:column; align-items:center; justify-content:center; padding: 100px 20px; background: var(--bg-surface); border-radius: var(--r-lg); border: 1px dashed var(--border-subtle); margin-top: 20px;">
    <div style="font-size: 48px; margin-bottom: 20px; opacity:0.6">🏢</div>
    <div style="font-size: 18px; font-weight: 600; color: var(--text-secondary);">Selecione uma instituição acima para visualizar o perfil detalhado</div>
  </div>
  
  <div id="error-state" style="display:none; padding: 15px 20px; background: rgba(255, 77, 77, 0.15); border: 1px solid var(--error); border-radius: var(--r-md); margin-bottom: 20px; color: var(--error); font-weight: 600;">Instituição não encontrada ou erro ao carregar dados.</div>

  <div id="loading-state" style="display:none; text-align:center; padding: 60px 20px;">
    <div style="font-size: 16px; color: var(--text-muted);">Carregando métricas...</div>
  </div>

  <div id="profile-content" style="display:none;">
'''
    html = html[:header_idx] + selector_html + html[header_idx:]


script_idx = html.find('<script>')
if script_idx != -1:
    html = html[:script_idx] + '  </div>\n\n' + html[script_idx:]

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)

print("Updated DOM")
