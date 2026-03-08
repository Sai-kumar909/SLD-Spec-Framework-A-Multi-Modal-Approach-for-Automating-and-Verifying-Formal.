import os
import re
import ollama
import shutil
import ast
import json
import io
from flask import Flask, render_template, request, send_file
from graphviz import Digraph

app = Flask(__name__)

# --- GLOBAL CONFIGURATION ---
LANG_CONFIG = {
    "C": {"pattern": r'\bint\s*\*?\s*([a-zA-Z_]\w*)', "spec": "ACSL"},
    "Java": {"pattern": r'\b(?:int|double|String)\s+([a-zA-Z_]\w*)', "spec": "JML"},
    "Python": {"pattern": r'([a-zA-Z_]\w*)\s*[:=]', "spec": "iContract"}
}

# --- GRAPH LOGIC ---
def generate_workflow_graph():
    """Generates the framework flowchart."""
    dot = Digraph(comment='Workflow')
    dot.attr(rankdir='TB', bgcolor='transparent', size='4,4!')
    dot.attr('node', fontname='Courier', shape='rect', style='filled', 
             color='#64ffda', fontcolor='#0a192f', fontsize='14', penwidth='2')
    dot.attr('edge', color='#64ffda', penwidth='2')
    
    dot.node('P1', 'P1: SLICING')
    dot.node('P2', 'P2: GUESSING')
    dot.node('P3', 'P3: DELETION')
    dot.node('P4', 'P4: VERIFY')
    
    dot.edge('P1', 'P2')
    dot.edge('P2', 'P3')
    dot.edge('P3', 'P4')
    
    try: return dot.pipe(format='svg').decode('utf-8')
    except: return ""

def generate_pdg_graph(slice_code, var_name):
    """Generates the Program Dependence Graph."""
    dot = Digraph(comment=f'PDG for {var_name}')
    dot.attr(rankdir='LR', bgcolor='transparent')
    dot.attr('node', fontname='Courier', color='#64ffda', fontcolor='#64ffda', 
             shape='ellipse', fontsize='16', penwidth='2')
    dot.attr('edge', color='#8892b0', fontname='Courier', fontsize='12', 
             arrowhead='vee', penwidth='1.5')

    lines = [l.strip() for l in slice_code.split('\n') if l.strip()]
    for i in range(len(lines)):
        clean_label = lines[i].replace('"', "'")
        dot.node(f'L{i}', clean_label)
        if i > 0:
            dot.edge(f'L{i-1}', f'L{i}', label='Data Dep')
    try: return dot.pipe(format='svg').decode('utf-8')
    except: return "<p>PDG Offline</p>"

# --- ROUTES ---
# --- ROUTES ---
@app.route('/')
def index():
    # Points to the code entry page
    return render_template('index.html', graph_svg=generate_workflow_graph())

@app.route('/about')
def about():
    # Points to the documentation page
    return render_template('about.html', graph_svg=generate_workflow_graph())

@app.route('/process')
def process():
    return render_template('process.html')

@app.route('/run_pipeline', methods=['POST'])
def run_pipeline():
    lang = request.form.get('language')
    full_code = request.form.get('code')
    config = LANG_CONFIG.get(lang)
    
    variables = list(set(re.findall(config['pattern'], full_code)))
    results = []
    
    for var in variables:
        slice_code = "\n".join([l for l in full_code.split('\n') if var in l])
        pdg_svg = generate_pdg_graph(slice_code, var)

        # Ollama Integration
        g_prompt = f"Expert {lang}. Write {config['spec']} ensures for '{var}' in:\n{slice_code}\nOutput ONLY code."
        candidate = ollama.chat(model='llama3', messages=[{'role': 'user', 'content': g_prompt}])['message']['content'].strip()
        
        j_prompt = f"Code: {slice_code}\nSpec: {candidate}\nLogical? Explain then VERDICT: KEEP or DELETE."
        reasoning = ollama.chat(model='llama3', messages=[{'role': 'user', 'content': j_prompt}])['message']['content'].strip()
        
        results.append({
            "variable": var, "phase1": slice_code, "phase2": candidate,
            "phase3": reasoning, "phase4": "KEEP" if "KEEP" in reasoning.upper() else "DELETE",
            "pdg": pdg_svg
        })

    return render_template('results.html', results=results, lang=lang, graph_svg=generate_workflow_graph())

@app.route('/download', methods=['POST'])
def download():
    """Generates a downloadable audit log."""
    results = json.loads(request.form.get('results_data'))
    lang = request.form.get('lang')
    report = io.StringIO()
    report.write(f"SLD-SPEC AUDIT REPORT | {lang}\n" + "="*40 + "\n\n")
    for r in results:
        report.write(f"VAR: {r['variable']} | VERDICT: {r['phase4']}\n")
        report.write(f"SLICE:\n{r['phase1']}\n")
        report.write(f"SPEC: {r['phase2']}\n")
        report.write(f"REASON: {r['phase3']}\n\n")
    
    mem = io.BytesIO(report.getvalue().encode('utf-8'))
    return send_file(mem, as_attachment=True, download_name=f"audit_{lang}.txt", mimetype='text/plain')

if __name__ == '__main__':
    app.run(debug=True)