import glob
import json
import os

target_dir = r'Z:\TEGR Collider'
files = glob.glob(os.path.join(target_dir, 'sindy_report_RAE Matrix_*.json'))

results = []
for f in files:
    with open(f, 'r', encoding='utf-8') as fp:
        data = json.load(fp)
        results.append({
            'label': data.get('run_label', os.path.basename(f)),
            'r2': data.get('r2_score', 0)
        })

results.sort(key=lambda x: x['label'])

table_md = '\n## 7. Lab Extension: RAE Matrix Experiments\n\n'
table_md += 'We conducted a 16-experiment matrix isolating the effects of the Relativistic Adler Equation (RAE) surrogate, Pauli exclusion variants ($1/r^2$ vs $1/r^3$), Entanglement (Ent), and Kinematic Coupling (Coup).\n\n'
table_md += '| Experiment Label | R2 Score |\n'
table_md += '|---|---|\n'
for r in results:
    table_md += f"| {r['label']} | {r['r2']:.4f} |\n"

table_md += '\n---\n\n'

ms_path = r'Z:\TEGR 2600\manuscript_5_einsteins_stick.md'
with open(ms_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('## 7. References', table_md + '## 8. References')

with open(ms_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Success')
