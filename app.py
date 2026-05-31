import sqlite3
import hashlib
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from functools import wraps

app = Flask(__name__)
app.secret_key = 'metering-system-secret-2024'

DATABASE = 'metering.db'

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db:
        db.close()

def init_db():
    db = sqlite3.connect(DATABASE)
    c = db.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT ''admin'')''')
    c.execute('''CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        model TEXT DEFAULT '''',
        manufacturer TEXT DEFAULT '''',
        purchase_date TEXT DEFAULT '''',
        keeper TEXT DEFAULT '''',
        calibration_cycle INTEGER DEFAULT 365,
        last_calibration_date TEXT DEFAULT '''',
        next_calibration_date TEXT DEFAULT '''',
        status TEXT DEFAULT ''在用'',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    pw = hashlib.sha256('123456'.encode()).hexdigest()
    try:
        c.execute('INSERT INTO users (username, password_hash, role) VALUES (?,?,?)',
                  ('admin', pw, 'admin'))
    except sqlite3.IntegrityError:
        pass
    db.commit()
    db.close()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def next_cal(last_date, cycle):
    if last_date and cycle:
        try:
            d = datetime.strptime(last_date, '%Y-%m-%d') + timedelta(days=cycle)
            return d.strftime('%Y-%m-%d')
        except: pass
    return ''

@app.route('/')
@login_required
def index():
    db = get_db()
    devices = db.execute('SELECT * FROM devices ORDER BY created_at DESC').fetchall()
    today = datetime.now().date()
    alerts = []
    for d in devices:
        if d['next_calibration_date']:
            try:
                nd = datetime.strptime(d['next_calibration_date'], '%Y-%m-%d').date()
                dl = (nd - today).days
                if 0 <= dl <= 30:
                    alerts.append({**dict(d), 'days_left': dl})
            except: pass
    return render_template('dashboard.html', devices=[dict(r) for r in devices], alerts=alerts)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username=?', (u,)).fetchone()
        if user and user['password_hash'] == hashlib.sha256(p.encode()).hexdigest():
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('index'))
        flash('用户名或密码错误')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/device/add', methods=['GET', 'POST'])
@login_required
def device_add():
    if request.method == 'POST':
        lc = request.form.get('last_calibration_date', '')
        cy = int(request.form.get('calibration_cycle', 365) or 365)
        nc = next_cal(lc, cy)
        db = get_db()
        db.execute('''INSERT INTO devices (name, model, manufacturer, purchase_date, keeper,
            calibration_cycle, last_calibration_date, next_calibration_date, status)
            VALUES (?,?,?,?,?,?,?,?,?)''',
            (request.form['name'], request.form.get('model',''), request.form.get('manufacturer',''),
             request.form.get('purchase_date',''), request.form.get('keeper',''),
             cy, lc, nc, request.form.get('status','在用')))
        db.commit()
        flash('器具添加成功')
        return redirect(url_for('index'))
    return render_template('form.html', device=None, action='添加')

@app.route('/device/<int:device_id>')
@login_required
def device_detail(device_id):
    db = get_db()
    d = db.execute('SELECT * FROM devices WHERE id=?', (device_id,)).fetchone()
    if not d:
        flash('器具不存在'); return redirect(url_for('index'))
    return render_template('detail.html', device=dict(d))

@app.route('/device/<int:device_id>/edit', methods=['GET', 'POST'])
@login_required
def device_edit(device_id):
    db = get_db()
    d = db.execute('SELECT * FROM devices WHERE id=?', (device_id,)).fetchone()
    if not d:
        flash('器具不存在'); return redirect(url_for('index'))
    if request.method == 'POST':
        lc = request.form.get('last_calibration_date', '')
        cy = int(request.form.get('calibration_cycle', 365) or 365)
        nc = next_cal(lc, cy)
        db.execute('''UPDATE devices SET name=?, model=?, manufacturer=?, purchase_date=?,
            keeper=?, calibration_cycle=?, last_calibration_date=?, next_calibration_date=?, status=?
            WHERE id=?''',
            (request.form['name'], request.form.get('model',''), request.form.get('manufacturer',''),
             request.form.get('purchase_date',''), request.form.get('keeper',''),
             cy, lc, nc, request.form.get('status','在用'), device_id))
        db.commit()
        flash('更新成功')
        return redirect(url_for('device_detail', device_id=device_id))
    return render_template('form.html', device=dict(d), action='编辑')

@app.route('/device/<int:device_id>/delete', methods=['POST'])
@login_required
def device_delete(device_id):
    db = get_db()
    db.execute('DELETE FROM devices WHERE id=?', (device_id,))
    db.commit()
    flash('已删除')
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
