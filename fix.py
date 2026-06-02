import os
pasta = 'templates'

fixes = {
    'ativar_licenca.html': [("img/us1919-logo.jpeg", "img/getclub-logo.png")],
    'atleta_form.html': [('US Gen\u00e8ve-Ville<span>1919</span>', '{{ club_display_name }}')],
    'editar_atleta.html': [('US Gen\u00e8ve-Ville<span>1919</span>', '{{ club_display_name }}')]
}

for f, substitutions in fixes.items():
    path = os.path.join(pasta, f)
    with open(path, 'r', encoding='utf-8') as fh:
        c = fh.read()
    for old, new in substitutions:
        c = c.replace(old, new)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(c)
    print(f'{f}: corrigido')
