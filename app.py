# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
import sqlite3
from datetime import datetime, timedelta
import os
from docx import Document  # Per Word
import pdfkit  # Per PDF

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
        import psycopg2
        return psycopg2.connect(db_url, sslmode='require')
    else:  # Usa SQLite in locale
        return sqlite3.connect('data.db', check_same_thread=False)

# Funzione generica per eseguire query
def execute_query(conn, query, params=None):
    if isinstance(conn, sqlite3.Connection):  # Se usi SQLite
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        result = cursor.fetchall()
        cursor.close()
        return result
    else:  # Se usi PostgreSQL
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            result = cur.fetchall()
        return result

# Crea il database e le tabelle se non esistono
def init_db():
    db_url = os.environ.get("DATABASE_URL")
    try:
        if db_url:  # Usa PostgreSQL
            import psycopg2
            with psycopg2.connect(db_url, sslmode='require') as conn:
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
    except Exception as e:
        print(f"Errore durante l'inizializzazione del database: {e}")
        raise

# Genera un report settimanale sulle task completate
def generate_weekly_report():
    conn = get_db_connection()
    try:
        one_week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        query = '''
            SELECT title, priority, created_at, started_at, completed_at
            FROM tasks
            WHERE status = 'Done'
            AND completed_at >= %s
        ''' if isinstance(conn, sqlite3.Connection) else '''
            SELECT title, priority, created_at, started_at, completed_at
            FROM tasks
            WHERE status = 'Done'
            AND completed_at >= %s
        '''
        tasks = execute_query(conn, query, (one_week_ago,))
        report = []
        for task in tasks:
            if isinstance(conn, sqlite3.Connection):  # Se usi SQLite
                task_dict = {
                    'title': task[0],
                    'priority': task[1],
                    'created_at': task[2],
                    'started_at': task[3],
                    'completed_at': task[4]
                }
            else:  # Se usi PostgreSQL
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
            query = "SELECT * FROM tasks WHERE status = %s AND priority = %s"
            params = (status_filter, priority_filter)
        elif status_filter:
            query = "SELECT * FROM tasks WHERE status = %s"
            params = (status_filter,)
        elif priority_filter:
            query = "SELECT * FROM tasks WHERE priority = %s"
            params = (priority_filter,)
        else:
            query = "SELECT * FROM tasks"
            params = None

        tasks = execute_query(conn, query, params)
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
    except Exception as e:
        print(f"Errore durante l'inserimento della task: {e}")
    finally:
        conn.close()

    return redirect(url_for('kanban'))

# Route per aggiornare lo stato di una task
@app.route('/update_task/<int:task_id>/<new_status>')
def update_task(task_id, new_status):
    conn = get_db_connection()
    try:
        if isinstance(conn, sqlite3.Connection):  # Se usi SQLite
            if new_status == 'In Progress':
                conn.execute('UPDATE tasks SET status = ?, started_at = ? WHERE id = ?', ('In Progress', datetime.now(), task_id))
            elif new_status == 'Done':
                conn.execute('UPDATE tasks SET status = ?, completed_at = ? WHERE id = ?', ('Done', datetime.now(), task_id))
            else:
                conn.execute('UPDATE tasks SET status = ? WHERE id = ?', (new_status, task_id))
        else:  # Se usi PostgreSQL
            with conn.cursor() as cur:
                if new_status == 'In Progress':
                    cur.execute('UPDATE tasks SET status = %s, started_at = %s WHERE id = %s', ('In Progress', datetime.now(), task_id))
                elif new_status == 'Done':
                    cur.execute('UPDATE tasks SET status = %s, completed_at = %s WHERE id = %s', ('Done', datetime.now(), task_id))
                else:
                    cur.execute('UPDATE tasks SET status = %s WHERE id = %s', (new_status, task_id))
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
        if isinstance(conn, sqlite3.Connection):  # Se usi SQLite
            conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        else:  # Se usi PostgreSQL
            with conn.cursor() as cur:
                cur.execute('DELETE FROM tasks WHERE id = %s', (task_id,))
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

    word_filename = "weekly_report.docx"
    doc.save(word_filename)
    return send_file(word_filename, as_attachment=True, download_name="weekly_report.docx")

# Route per esportare la Kanban Board in PDF
@app.route('/export_pdf', methods=['GET'])
def export_pdf():
    try:
        conn = get_db_connection()
        tasks = execute_query(conn, "SELECT * FROM tasks")
        html_content = render_template('kanban.html', tasks=tasks)
        pdf_filename = "kanban_board.pdf"
        pdfkit.from_string(html_content, pdf_filename)
        return send_file(pdf_filename, as_attachment=True, download_name="kanban_board.pdf")
    except Exception as e:
        return f"Errore durante la generazione del PDF: {str(e)}", 500
    finally:
        conn.close()

if __name__ == '__main__':
    print("Route registrate:")
    for rule in app.url_map.iter_rules():
        print(f"Endpoint: {rule.endpoint}, URL: {rule.rule}, Metodi: {','.join(rule.methods)}")
    init_db()  # Crea il database se non esiste già
    port = int(os.environ.get('PORT', 5000))  # Usa la porta specificata dall'ambiente o la porta 5000
    app.run(host='0.0.0.0', port=port, debug=False)