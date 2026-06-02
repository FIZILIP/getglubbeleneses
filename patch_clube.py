"""
Aplica os patches necessários no app.py e index.html do GETCLUB.
Execute na pasta do projeto.
"""
import re, shutil, os

BASE = r"C:\Users\Filipe Andrade\Documents\GETCLUB0\GETCLUB0\GETCLUB"

# ── 1. PATCH app.py ──────────────────────────────────────────────────
app_path = os.path.join(BASE, "app.py")
with open(app_path, "r", encoding="utf-8") as f:
    src = f.read()

# Actualizar utility_processor para expor os novos campos
old_proc = '''@app.context_processor
def utility_processor():
    from datetime import datetime
    settings = load_app_settings()
    club_name = (settings.get("club_name") or "GETCLUB").strip()
    club_logo_filename = get_logo_clube_filename()
    club_logo_url = url_for('serve_logo_clube', filename=club_logo_filename) if club_logo_filename else None
    return {
        'now': datetime.now,
        'club_display_name': club_name,
        'club_logo_url': club_logo_url
    }'''

new_proc = '''@app.context_processor
def utility_processor():
    from datetime import datetime
    settings = load_app_settings()
    club_name     = (settings.get("club_name")     or "GETCLUB").strip()
    club_subtitulo= (settings.get("club_subtitulo") or "Painel Central de Gestão do Clube").strip()
    club_meta     = (settings.get("club_meta")      or "").strip()
    club_logo_filename = get_logo_clube_filename()
    club_logo_url = url_for('serve_logo_clube', filename=club_logo_filename) if club_logo_filename else None
    return {
        'now': datetime.now,
        'club_display_name': club_name,
        'club_subtitulo': club_subtitulo,
        'club_meta': club_meta,
        'club_logo_url': club_logo_url
    }'''

if old_proc in src:
    src = src.replace(old_proc, new_proc)
    print("✅ utility_processor actualizado")
else:
    print("⚠️  utility_processor não encontrado — verifica manualmente")

# Actualizar rota /clube/nome para guardar também subtítulo e meta
old_route = '''@app.route('/clube/nome', methods=['POST'])
@login_required
def update_nome_clube():
    nome = (request.form.get('club_name') or '').strip()
    if not nome:
        flash('O nome do clube/sistema não pode ficar vazio.', 'error')
        return redirect(request.referrer or url_for('index'))
    ok = save_app_settings({"club_name": nome[:60]})
    if ok:
        flash('Nome atualizado com sucesso.', 'success')
    else:
        flash('Não foi possível salvar o nome. Verifique permissões de escrita.', 'error')
    return redirect(request.referrer or url_for('index'))'''

new_route = '''@app.route('/clube/nome', methods=['POST'])
@login_required
def update_nome_clube():
    nome      = (request.form.get('club_name')      or '').strip()
    subtitulo = (request.form.get('club_subtitulo') or '').strip()
    meta      = (request.form.get('club_meta')      or '').strip()
    if not nome:
        flash('O nome do clube não pode ficar vazio.', 'error')
        return redirect(request.referrer or url_for('index'))
    ok = save_app_settings({
        "club_name":      nome[:80],
        "club_subtitulo": subtitulo[:120],
        "club_meta":      meta[:200],
    })
    if ok:
        flash('Informações do clube atualizadas com sucesso.', 'success')
    else:
        flash('Não foi possível salvar. Verifique permissões de escrita.', 'error')
    return redirect(request.referrer or url_for('index'))'''

if old_route in src:
    src = src.replace(old_route, new_route)
    print("✅ rota update_nome_clube actualizada")
else:
    print("⚠️  rota update_nome_clube não encontrada — verifica manualmente")

with open(app_path, "w", encoding="utf-8") as f:
    f.write(src)
print("✅ app.py guardado")

# ── 2. PATCH index.html ─────────────────────────────────────────────
idx_path = os.path.join(BASE, "templates", "index.html")
with open(idx_path, "r", encoding="utf-8") as f:
    html = f.read()

# Substituir o bloco hardcoded do cabeçalho
old_header = '''    <div>
      <div class="ath-name">US 1919 Genève-Ville</div>
      <div class="ath-sub">Painel Central de Gestão do Clube</div>
      <div class="ath-meta">Suíça | Futebol Profissional | Operação diária integrada</div>
    </div>
  </div>
  <div class="actions-right">
    <a class="btn-square" href="{{ url_for('documentos') }}"><i class="fas fa-clipboard-list"></i></a>
    <a class="btn-watch" href="{{ url_for('analise_desempenho') }}"><i class="fas fa-eye"></i> Monitorar</a>
  </div>
</section>'''

new_header = '''    <div>
      <div class="ath-name" id="clubNomeDisplay">{{ club_display_name }}</div>
      <div class="ath-sub"  id="clubSubDisplay">{{ club_subtitulo }}</div>
      <div class="ath-meta" id="clubMetaDisplay">{{ club_meta }}</div>
    </div>
  </div>
  <div class="actions-right">
    {% if current_user.is_admin %}
    <button class="btn-square" onclick="document.getElementById('modalEditClub').style.display='flex'" title="Editar informações do clube">
      <i class="fas fa-pen"></i>
    </button>
    {% endif %}
    <a class="btn-square" href="{{ url_for('documentos') }}"><i class="fas fa-clipboard-list"></i></a>
    <a class="btn-watch" href="{{ url_for('analise_desempenho') }}"><i class="fas fa-eye"></i> Monitorar</a>
  </div>
</section>

<!-- Modal editar clube -->
<div id="modalEditClub" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:9999;align-items:center;justify-content:center;">
  <div style="background:#fff;border-radius:16px;padding:32px;width:100%;max-width:480px;box-shadow:0 20px 60px rgba(0,0,0,.3);">
    <h3 style="margin:0 0 20px;font-size:20px;font-weight:800;">Editar Informações do Clube</h3>
    <form method="POST" action="{{ url_for('update_nome_clube') }}">
      <div style="margin-bottom:14px;">
        <label style="display:block;font-size:12px;font-weight:700;color:#6b7280;margin-bottom:6px;">NOME DO CLUBE</label>
        <input name="club_name" value="{{ club_display_name }}" required
               style="width:100%;padding:10px 14px;border:1px solid #d1d5db;border-radius:8px;font-size:15px;box-sizing:border-box;">
      </div>
      <div style="margin-bottom:14px;">
        <label style="display:block;font-size:12px;font-weight:700;color:#6b7280;margin-bottom:6px;">SUBTÍTULO</label>
        <input name="club_subtitulo" value="{{ club_subtitulo }}"
               style="width:100%;padding:10px 14px;border:1px solid #d1d5db;border-radius:8px;font-size:15px;box-sizing:border-box;"
               placeholder="Ex: Painel Central de Gestão do Clube">
      </div>
      <div style="margin-bottom:20px;">
        <label style="display:block;font-size:12px;font-weight:700;color:#6b7280;margin-bottom:6px;">META / DESCRIÇÃO</label>
        <input name="club_meta" value="{{ club_meta }}"
               style="width:100%;padding:10px 14px;border:1px solid #d1d5db;border-radius:8px;font-size:15px;box-sizing:border-box;"
               placeholder="Ex: Portugal | Futebol Profissional | Operação diária integrada">
      </div>
      <div style="display:flex;gap:10px;justify-content:flex-end;">
        <button type="button" onclick="document.getElementById('modalEditClub').style.display='none'"
                style="padding:10px 20px;border:1px solid #d1d5db;border-radius:8px;background:#fff;cursor:pointer;font-size:14px;">
          Cancelar
        </button>
        <button type="submit"
                style="padding:10px 20px;border:none;border-radius:8px;background:#2e6dff;color:#fff;cursor:pointer;font-size:14px;font-weight:700;">
          Guardar
        </button>
      </div>
    </form>
  </div>
</div>'''

# Também substituir "US 1919 Genève-Ville" hardcoded na tabela
old_table_rows = '''            <tr><td>{{ now().year }}</td><td>Gestão do plantel</td><td>US 1919 Genève-Ville</td><td>{{ num_atletas }}</td><td>{{ num_reunioes }}</td><td>{{ atletas_lesionados }}</td><td>{{ total_documentos }}</td></tr>
            <tr><td>{{ now().year }}</td><td>Calendário e logística</td><td>US 1919 Genève-Ville</td><td>{{ total_itens_inventario }}</td><td>{{ proximas_reunioes|length }}</td><td>{{ fichas_medicas_recentes|length }}</td><td>{{ eventos_calendario|length }}</td></tr>
            <tr><td>{{ now().year }}</td><td>Financeiro mensal</td><td>US 1919 Genève-Ville</td><td>€ {{ '%.0f'|format(total_compras_mes) }}</td><td>€ {{ '%.0f'|format(total_gastos) }}</td><td>€ {{ '%.0f'|format(total_contas_fixas_ativas) }}</td><td>€ {{ '%.0f'|format(total_patrocinios_ativos) }}</td></tr>'''

new_table_rows = '''            <tr><td>{{ now().year }}</td><td>Gestão do plantel</td><td>{{ club_display_name }}</td><td>{{ num_atletas }}</td><td>{{ num_reunioes }}</td><td>{{ atletas_lesionados }}</td><td>{{ total_documentos }}</td></tr>
            <tr><td>{{ now().year }}</td><td>Calendário e logística</td><td>{{ club_display_name }}</td><td>{{ total_itens_inventario }}</td><td>{{ proximas_reunioes|length }}</td><td>{{ fichas_medicas_recentes|length }}</td><td>{{ eventos_calendario|length }}</td></tr>
            <tr><td>{{ now().year }}</td><td>Financeiro mensal</td><td>{{ club_display_name }}</td><td>€ {{ '%.0f'|format(total_compras_mes) }}</td><td>€ {{ '%.0f'|format(total_gastos) }}</td><td>€ {{ '%.0f'|format(total_contas_fixas_ativas) }}</td><td>€ {{ '%.0f'|format(total_patrocinios_ativos) }}</td></tr>'''

if old_header in html:
    html = html.replace(old_header, new_header)
    print("✅ cabeçalho do dashboard actualizado")
else:
    print("⚠️  cabeçalho não encontrado — verifica manualmente")

if old_table_rows in html:
    html = html.replace(old_table_rows, new_table_rows)
    print("✅ tabela actualizada")
else:
    print("⚠️  linhas da tabela não encontradas")

with open(idx_path, "w", encoding="utf-8") as f:
    f.write(html)
print("✅ index.html guardado")
print("\n🎉 Patch concluído! Reinicia o servidor para ver as alterações.")
