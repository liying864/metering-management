import hashlib
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from functools import wraps

app = Flask(__name__)
app.secret_key = 'metering-system-secret-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///metering.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Models
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='admin')

class Device(db.Model):
    __tablename__ = 'devices'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    model = db.Column(db.String(100), default='')
    manufacturer = db.Column(db.String(200), default='')
    purchase_date = db.Column(db.String(20), default='')
    keeper = db.Column(db.String(100), default='')
    calibration_cycle = db.Column(db.Integer, default=365)
    last_calibration_date = db.Column(db.String(20), default='')
    next_calibration_date = db.Column(db.String(20), default='')
    status = db.Column(db.String(20), default='在用')
    created_at = db.Column(db.DateTime, default=datetime.now)

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
        except:
            pass
    return ''

@app.route('/')
@login_required
def index():
    devices = Device.query.order_by(Device.created_at.desc()).all()
    today = datetime.now().date()
    alerts = []
    for d in devices:
        if d.next_calibration_date:
            try:
                nd = datetime.strptime(d.next_calibration_date, '%Y-%m-%d').date()
                dl = (nd - today).days
                if 0 <= dl <= 30:
                    alerts.append({
                        'name': d.name, 'days_left': dl,
                        'id': d.id, 'status': d.status,
                        'model': d.model, 'keeper': d.keeper,
                        'calibration_cycle': d.calibration_cycle,
                        'last_calibration_date': d.last_calibration_date,
                        'next_calibration_date': d.next_calibration_date
                    })
            except:
                pass
    return render_template('dashboard.html', devices=devices, alerts=alerts)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        user = User.query.filter_by(username=u).first()
        if user and user.password_hash == hashlib.sha256(p.encode()).hexdigest():
            session['user_id'] = user.id
            session['username'] = user.username
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
        device = Device(
            name=request.form['name'],
            model=request.form.get('model', ''),
            manufacturer=request.form.get('manufacturer', ''),
            purchase_date=request.form.get('purchase_date', ''),
            keeper=request.form.get('keeper', ''),
            calibration_cycle=cy,
            last_calibration_date=lc,
            next_calibration_date=nc,
            status=request.form.get('status', '在用')
        )
        db.session.add(device)
        db.session.commit()
        flash('器具添加成功')
        return redirect(url_for('index'))
    return render_template('form.html', device=None, action='添加')

@app.route('/device/<int:device_id>')
@login_required
def device_detail(device_id):
    d = Device.query.get_or_404(device_id)
    return render_template('detail.html', device=d)

@app.route('/device/<int:device_id>/edit', methods=['GET', 'POST'])
@login_required
def device_edit(device_id):
    d = Device.query.get_or_404(device_id)
    if request.method == 'POST':
        d.name = request.form['name']
        d.model = request.form.get('model', '')
        d.manufacturer = request.form.get('manufacturer', '')
        d.purchase_date = request.form.get('purchase_date', '')
        d.keeper = request.form.get('keeper', '')
        d.calibration_cycle = int(request.form.get('calibration_cycle', 365) or 365)
        d.last_calibration_date = request.form.get('last_calibration_date', '')
        d.next_calibration_date = next_cal(d.last_calibration_date, d.calibration_cycle)
        d.status = request.form.get('status', '在用')
        db.session.commit()
        flash('更新成功')
        return redirect(url_for('device_detail', device_id=device_id))
    return render_template('form.html', device=d, action='编辑')

@app.route('/device/<int:device_id>/delete', methods=['POST'])
@login_required
def device_delete(device_id):
    d = Device.query.get_or_404(device_id)
    db.session.delete(d)
    db.session.commit()
    flash('已删除')
    return redirect(url_for('index'))

def init_db():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        pw = hashlib.sha256('123456'.encode()).hexdigest()
        db.session.add(User(username='admin', password_hash=pw, role='admin'))
        db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
