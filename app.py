# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
import sqlite3
from datetime import datetime
import os
from docx import Document  # Per Word
import pdfkit  # Per PDF
import sqlite3 # add fo database
import DATABASE_URL # add fo database
from DATABASE_URL import extras # add fo database

app = Flask(__name__)

# Funzione per formattare le date (filtro Jinja2)
def strftime_filter(value, format='%d/%m/%Y %H:%M'):
    if value is None:
        return ""  # Gestisci eventuali valori None
    return datetime.strptime(value, '%Y-%m-%d %H:%M:%S').strftime(format)

# Registra il filtro strftime in Jinja2
app.jinja_env.filters['strftime'] = strftime_filter

# Funzione per connettersi al database
def get_db_connection():
    db_url = os.environ.get("DATABASE_URL")
    if db_url:  # Usa PostgreSQL se DATABASE_URL è impostato
        return DATABASE_URL.connect(db_url, sslmode='require', cursor_factory=extras.RealDictCursor)
    else:  # Usa SQLite in locale
        return sqlite3.connect('data.db', check_same_thread=False)

# Crea il database e le tabelle se non esistono
def init_db():
    db_url = os.environ.get("DATABASE_URL")
    if db_url:  # Usa PostgreSQL
        with DATABASE_URL.connect(db_url, sslmode='require') as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS tasks (
                        id SERIAL PRIMARY KEY,
                        title TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'To Do',
                        priority TEXT NOT NULL DEFAULT 'Medium',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                ''')
    else:  # Usa SQLite
        with sqlite3.connect('data.db') as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'To Do',
                    priority TEXT NOT NULL DEFAULT 'Medium',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP
                )
            ''')

# Genera un report settimanale sulle task completate
def generate_weekly_report():
    conn = get_db_connection()
    try:
        tasks = conn.execute('''
            SELECT title, priority, created_at, started_at, completed_at
            FROM tasks
            WHERE status = 'Done'
            AND completed_at >= datetime('now', '-7 days')
        ''').fetchall()
        report = []
        for task in tasks:
            task_dict = {
                'title': task['title'],
                'priority': task['priority'],
                'created_at': task['created_at'],
                'started_at': task['started_at'],
                'completed_at': task['completed_at']
            }
            report.append(task_dict)
        return report
    finally:
        conn.close()

# Route principale per visualizzare la Kanban Board
@app.route('/', methods=['GET', 'POST'])
def kanban():
    status_filter = request.args.get('status', None)  # Filtro per stato
    priority_filter = request.args.get('priority', None)  # Filtro per priorità

    conn = get_db_connection()
    try:
        if status_filter and priority_filter:
            tasks = conn.execute('SELECT * FROM tasks WHERE status = ? AND priority = ?', (status_filter, priority_filter)).fetchall()
        elif status_filter:
            tasks = conn.execute('SELECT * FROM tasks WHERE status = ?', (status_filter,)).fetchall()
        elif priority_filter:
            tasks = conn.execute('SELECT * FROM tasks WHERE priority = ?', (priority_filter,)).fetchall()
        else:
            tasks = conn.execute('SELECT * FROM tasks').fetchall()
        return render_template('kanban.html', tasks=tasks)
    finally:
        conn.close()

# Route per aggiungere una nuova task
@app.route('/add_task', methods=['POST'])
def add_task():
    title = request.form['title']
    priority = request.form.get('priority', 'Medium')  # Priorità predefinita "Medium"
    if not title:
        return redirect(url_for('kanban'))  # Ignora task vuote
    conn = get_db_connection()
    try:
        if isinstance(conn, sqlite3.Connection):  # Se usi SQLite
            conn.execute('INSERT INTO tasks (title, priority) VALUES (?, ?)', (title, priority))
        else:  # Se usi PostgreSQL
            with conn.cursor() as cur:
                cur.execute('INSERT INTO tasks (title, priority) VALUES (%s, %s)', (title, priority))
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for('kanban'))

# Route per aggiornare lo stato di una task
@app.route('/update_task/<int:task_id>/<new_status>')
def update_task(task_id, new_status):
    conn = get_db_connection()
    try:
        if new_status == 'In Progress':
            conn.execute('UPDATE tasks SET status = ?, started_at = ? WHERE id = ?', ('In Progress', datetime.now(), task_id))
        elif new_status == 'Done':
            conn.execute('UPDATE tasks SET status = ?, completed_at = ? WHERE id = ?', ('Done', datetime.now(), task_id))
        else:
            conn.execute('UPDATE tasks SET status = ? WHERE id = ?', (new_status, task_id))
        conn.commit()
    except Exception as e:
        print(f"Errore durante l'aggiornamento della task: {e}")
    finally:
        conn.close()
    return redirect(url_for('kanban'))

# Route per eliminare una task
@app.route('/delete_task/<int:task_id>')
def delete_task(task_id):
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        conn.commit()
    except Exception as e:
        print(f"Errore durante l'eliminazione della task: {e}")
    finally:
        conn.close()
    return redirect(url_for('kanban'))

# Route per esportare il report in Word
@app.route('/export_word', methods=['GET'])
def export_word():
    report_data = generate_weekly_report()

    # Crea un documento Word
    doc = Document()
    doc.add_heading("Report Settimanale delle Task Completate", level=1)

    if not report_data:
        doc.add_paragraph("Nessuna task completata negli ultimi 7 giorni.")
    else:
        table = doc.add_table(rows=1, cols=5)
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Titolo'
        hdr_cells[1].text = 'Priorità'
        hdr_cells[2].text = 'Creato Il'
        hdr_cells[3].text = 'Iniziato Il'
        hdr_cells[4].text = 'Completato Il'

        for task in report_data:
            row_cells = table.add_row().cells
            row_cells[0].text = task['title']
            row_cells[1].text = task['priority']
            row_cells[2].text = task['created_at']
            row_cells[3].text = task['started_at'] or "Non applicabile"
            row_cells[4].text = task['completed_at']

    # Salva il file Word
    word_filename = "weekly_report.docx"
    doc.save(word_filename)

    # Invia il file Word all'utente
    return send_file(word_filename, as_attachment=True, download_name="weekly_report.docx")

# Route per esportare la Kanban Board in PDF
@app.route('/export_pdf', methods=['GET'])
def export_pdf():
    try:
        # Renderizza il template come stringa HTML
        conn = get_db_connection()
        try:
            tasks = conn.execute('SELECT * FROM tasks').fetchall()
            html_content = render_template('kanban.html', tasks=tasks)
        finally:
            conn.close()

        # Configura pdfkit per convertire HTML in PDF
        pdf_filename = "kanban_board.pdf"
        pdfkit.from_string(html_content, pdf_filename)

        # Invia il file PDF all'utente
        return send_file(pdf_filename, as_attachment=True, download_name="kanban_board.pdf")
    except Exception as e:
        return f"Errore durante la generazione del PDF: {str(e)}", 500

if __name__ == '__main__':
    print("Route registrate:")
    for rule in app.url_map.iter_rules():
        print(f"Endpoint: {rule.endpoint}, URL: {rule.rule}, Metodi: {','.join(rule.methods)}")

    init_db()  # Crea il database se non esiste già
    port = int(os.environ.get('PORT', 5000))  # Usa la porta specificata dall'ambiente o la porta 5000
    app.run(host='0.0.0.0', port=port, debug=True)