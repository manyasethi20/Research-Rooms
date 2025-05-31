from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
import threading
import queue
import time
import sqlite3
import uuid
from werkzeug.utils import secure_filename
import fitz  

app = Flask(__name__)
app.secret_key = 'research_rooms_secret_key'

UPLOAD_FOLDER = 'static/papers'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def init_db():
    conn = sqlite3.connect('research_rooms.db')
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS rooms (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        creator_id TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (creator_id) REFERENCES users(id)
    )''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS papers (
        id TEXT PRIMARY KEY,
        room_id TEXT NOT NULL,
        filename TEXT NOT NULL,
        title TEXT NOT NULL,
        uploaded_by TEXT NOT NULL,
        summary TEXT,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (room_id) REFERENCES rooms(id),
        FOREIGN KEY (uploaded_by) REFERENCES users(id)
    )''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS notes (
        id TEXT PRIMARY KEY,
        paper_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (paper_id) REFERENCES papers(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    # Add to init_db() function after the existing tables
    c.execute('''
    CREATE TABLE IF NOT EXISTS annotations (
        id TEXT PRIMARY KEY,
        paper_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        page_number INTEGER,
        position_data TEXT,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (paper_id) REFERENCES papers(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS questions (
        id TEXT PRIMARY KEY,
        paper_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (paper_id) REFERENCES papers(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS answers (
        id TEXT PRIMARY KEY,
        question_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        content TEXT NOT NULL,
        upvotes INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (question_id) REFERENCES questions(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    conn.commit()
    conn.close()

init_db()

task_queues = {}
room_locks = {}

class RoomThread(threading.Thread):
    def __init__(self, room_id):
        super().__init__()
        self.room_id = room_id
        self.daemon = True
        self.task_queue = queue.Queue()
        task_queues[room_id] = self.task_queue
        room_locks[room_id] = threading.Lock()

    def run(self):
        while True:
            try:
                task = self.task_queue.get(timeout=60)
                if task['type'] == 'summarize':
                    self.summarize_paper(task['paper_id'])
                elif task['type'] == 'annotate':
                    self.process_annotation(task['paper_id'], task['user_id'], task['content'])
                self.task_queue.task_done()
            except queue.Empty:
                pass
            except Exception as e:
                print(f"Error in room thread: {e}")

    def summarize_paper(self, paper_id):
        try:
            conn = sqlite3.connect('research_rooms.db')
            c = conn.cursor()
            c.execute("SELECT filename FROM papers WHERE id = ?", (paper_id,))
            result = c.fetchone()
            conn.close()

            if not result:
                return

            filename = result[0]
            filepath = os.path.join(UPLOAD_FOLDER, f"{paper_id}_{filename}")

            doc = fitz.open(filepath)
            text = ""
            for page in doc:
                text += page.get_text()
                if len(text) > 1000:
                    break
            doc.close()

            summary = text.strip().split('\n')[0:5]
            summary = ' '.join([line.strip() for line in summary if line.strip()])
            if not summary:
                summary = "Summary could not be generated. The document might be empty."

            conn = sqlite3.connect('research_rooms.db')
            c = conn.cursor()
            c.execute("UPDATE papers SET summary = ? WHERE id = ?", (summary, paper_id))
            conn.commit()
            conn.close()

        except Exception as e:
            print(f"Error summarizing paper: {e}")

    def process_annotation(self, paper_id, user_id, content):
        with room_locks[self.room_id]:
            conn = sqlite3.connect('research_rooms.db')
            c = conn.cursor()
            note_id = str(uuid.uuid4())
            c.execute("INSERT INTO notes (id, paper_id, user_id, content) VALUES (?, ?, ?, ?)",
                      (note_id, paper_id, user_id, content))
            conn.commit()
            conn.close()

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    search_query = request.args.get('q', '').strip().lower()

    conn = sqlite3.connect('research_rooms.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if search_query:
        c.execute("SELECT * FROM rooms WHERE LOWER(name) LIKE ? ORDER BY created_at DESC", ('%' + search_query + '%',))
    else:
        c.execute("SELECT * FROM rooms ORDER BY created_at DESC")

    rooms = c.fetchall()
    conn.close()

    return render_template('index.html', rooms=rooms)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('research_rooms.db')
        c = conn.cursor()
        c.execute("SELECT id, username FROM users WHERE username = ? AND password = ?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('research_rooms.db')
        c = conn.cursor()
        try:
            user_id = str(uuid.uuid4())
            c.execute("INSERT INTO users (id, username, password) VALUES (?, ?, ?)",
                      (user_id, username, password))
            conn.commit()
            conn.close()
            session['user_id'] = user_id
            session['username'] = username
            return redirect(url_for('index'))
        except sqlite3.IntegrityError:
            flash('Username already exists')
            conn.close()
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/create_room', methods=['GET', 'POST'])
def create_room():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        room_name = request.form['room_name']
        conn = sqlite3.connect('research_rooms.db')
        c = conn.cursor()
        room_id = str(uuid.uuid4())
        c.execute("INSERT INTO rooms (id, name, creator_id) VALUES (?, ?, ?)",
                  (room_id, room_name, session['user_id']))
        conn.commit()
        conn.close()
        room_thread = RoomThread(room_id)
        room_thread.start()
        return redirect(url_for('room', room_id=room_id))
    return render_template('create_room.html')

@app.route('/room/<room_id>')
def room(room_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('research_rooms.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM rooms WHERE id = ?", (room_id,))
    room = c.fetchone()
    if not room:
        conn.close()
        flash('Room not found')
        return redirect(url_for('index'))
    c.execute("""
        SELECT p.*, u.username as uploader_name
        FROM papers p
        JOIN users u ON p.uploaded_by = u.id
        WHERE p.room_id = ?
        ORDER BY p.uploaded_at DESC
    """, (room_id,))
    papers = c.fetchall()
    conn.close()
    if room_id not in task_queues:
        room_thread = RoomThread(room_id)
        room_thread.start()
    return render_template('room.html', room=room, papers=papers)

@app.route('/upload_paper/<room_id>', methods=['POST'])
def upload_paper(room_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if 'paper' not in request.files:
        flash('No file part')
        return redirect(url_for('room', room_id=room_id))
    file = request.files['paper']
    paper_title = request.form['title']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('room', room_id=room_id))
    if file:
        filename = secure_filename(file.filename)
        paper_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_FOLDER, f"{paper_id}_{filename}")
        file.save(file_path)
        conn = sqlite3.connect('research_rooms.db')
        c = conn.cursor()
        c.execute("""
            INSERT INTO papers (id, room_id, filename, title, uploaded_by)
            VALUES (?, ?, ?, ?, ?)
        """, (paper_id, room_id, filename, paper_title, session['user_id']))
        conn.commit()
        conn.close()
        task_queues[room_id].put({
            'type': 'summarize',
            'paper_id': paper_id
        })
        flash('Paper uploaded successfully')
    return redirect(url_for('room', room_id=room_id))

@app.route('/paper/<paper_id>')
def view_paper(paper_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('research_rooms.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
    SELECT p.*, r.id as room_id, r.name as room_name, u.username as uploader_name
    FROM papers p
    JOIN rooms r ON p.room_id = r.id
    JOIN users u ON p.uploaded_by = u.id
    WHERE p.id = ?
    """, (paper_id,))
    paper = c.fetchone()
    
    if not paper:
        conn.close()
        flash('Paper not found')
        return redirect(url_for('index'))
    
    c.execute("""
    SELECT n.*, u.username
    FROM notes n
    JOIN users u ON n.user_id = u.id
    WHERE n.paper_id = ?
    ORDER BY n.created_at DESC
    """, (paper_id,))
    notes = c.fetchall()
    
    c.execute("""
    SELECT a.*, u.username
    FROM annotations a
    JOIN users u ON a.user_id = u.id
    WHERE a.paper_id = ?
    ORDER BY a.page_number, a.created_at DESC
    """, (paper_id,))
    annotations = c.fetchall()
    
    c.execute("""
    SELECT q.*, u.username, (SELECT COUNT(*) FROM answers WHERE question_id = q.id) as answer_count
    FROM questions q
    JOIN users u ON q.user_id = u.id
    WHERE q.paper_id = ?
    ORDER BY q.created_at DESC
    """, (paper_id,))
    questions = c.fetchall()
    
    conn.close()
    return render_template('paper.html', paper=paper, notes=notes, annotations=annotations, questions=questions)

@app.route('/add_note/<paper_id>', methods=['POST'])
def add_note(paper_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    content = request.form['content']
    conn = sqlite3.connect('research_rooms.db')
    c = conn.cursor()
    c.execute("SELECT room_id FROM papers WHERE id = ?", (paper_id,))
    result = c.fetchone()
    conn.close()
    if result:
        room_id = result[0]
        task_queues[room_id].put({
            'type': 'annotate',
            'paper_id': paper_id,
            'user_id': session['user_id'],
            'content': content
        })
        flash('Note added successfully')
    else:
        flash('Paper not found')
    return redirect(url_for('view_paper', paper_id=paper_id))

@app.route('/add_annotation/<paper_id>', methods=['POST'])
def add_annotation(paper_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    content = request.form['content']
    page_number = request.form.get('page_number', 1)
    position_data = request.form.get('position_data', '{}')
    
    conn = sqlite3.connect('research_rooms.db')
    c = conn.cursor()
    annotation_id = str(uuid.uuid4())
    c.execute("""
    INSERT INTO annotations (id, paper_id, user_id, page_number, position_data, content)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (annotation_id, paper_id, session['user_id'], page_number, position_data, content))
    conn.commit()
    conn.close()
    
    flash('Annotation added successfully')
    return redirect(url_for('view_paper', paper_id=paper_id))

@app.route('/ask_question/<paper_id>', methods=['POST'])
def ask_question(paper_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    title = request.form['title']
    content = request.form['content']
    
    conn = sqlite3.connect('research_rooms.db')
    c = conn.cursor()
    question_id = str(uuid.uuid4())
    c.execute("""
    INSERT INTO questions (id, paper_id, user_id, title, content)
    VALUES (?, ?, ?, ?, ?)
    """, (question_id, paper_id, session['user_id'], title, content))
    conn.commit()
    conn.close()
    
    flash('Question posted successfully')
    return redirect(url_for('view_paper', paper_id=paper_id))

@app.route('/add_answer/<question_id>', methods=['POST'])
def add_answer(question_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    content = request.form['content']
    
    conn = sqlite3.connect('research_rooms.db')
    c = conn.cursor()
    c.execute("SELECT questions.paper_id FROM questions WHERE id = ?", (question_id,))
    result = c.fetchone()
    if not result:
        conn.close()
        flash('Question not found')
        return redirect(url_for('index'))
    
    paper_id = result[0]
    answer_id = str(uuid.uuid4())
    c.execute("""
    INSERT INTO answers (id, question_id, user_id, content)
    VALUES (?, ?, ?, ?)
    """, (answer_id, question_id, session['user_id'], content))
    conn.commit()
    conn.close()
    
    flash('Answer posted successfully')
    return redirect(url_for('view_paper', paper_id=paper_id))

@app.route('/upvote_answer/<answer_id>')
def upvote_answer(answer_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('research_rooms.db')
    c = conn.cursor()
    c.execute("UPDATE answers SET upvotes = upvotes + 1 WHERE id = ?", (answer_id,))
    conn.commit()
    
    c.execute("""
    SELECT q.paper_id FROM answers a
    JOIN questions q ON a.question_id = q.id
    WHERE a.id = ?
    """, (answer_id,))
    result = c.fetchone()
    conn.close()
    
    if result:
        return redirect(url_for('view_paper', paper_id=result[0]))
    return redirect(url_for('index'))

@app.route('/questions/<question_id>')
def view_question(question_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('research_rooms.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("""
    SELECT q.*, u.username, p.id as paper_id, p.title as paper_title
    FROM questions q
    JOIN users u ON q.user_id = u.id
    JOIN papers p ON q.paper_id = p.id
    WHERE q.id = ?
    """, (question_id,))
    question = c.fetchone()
    
    c.execute("""
    SELECT a.*, u.username
    FROM answers a
    JOIN users u ON a.user_id = u.id
    WHERE a.question_id = ?
    ORDER BY a.upvotes DESC, a.created_at ASC
    """, (question_id,))
    answers = c.fetchall()
    
    conn.close()
    
    if not question:
        flash('Question not found')
        return redirect(url_for('index'))
    
    return render_template('question.html', question=question, answers=answers)

if __name__ == '__main__':
    app.run(debug=True)
