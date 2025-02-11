from flask import Flask, render_template, redirect, url_for, flash, request, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = '7721'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///appointments.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database Models

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # "teacher" or "student"
    appointments = db.relationship('Appointment', backref='user', lazy=True)
    semester = db.Column(db.Integer, nullable=True)  # Only for students
    branch = db.Column(db.String(50), nullable=False)  # For both students and teachers

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    student_id = db.Column(db.Integer, nullable=True)  # will be set when a student books an appointment
    appointment_date = db.Column(db.DateTime, nullable=False)
    booked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Work(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    branch = db.Column(db.String(50), nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Helper Decorators for Access Control

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def teacher_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'teacher':
            flash('Access restricted to teachers.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'student':
            flash('Access restricted to students.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Routes

@app.route('/')
def index():
    return render_template('index.html')

# --- Signup Route ---
@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        branch = request.form.get('branch')
        semester = request.form.get('semester') if role == 'student' else None
        
        if not username or not password or role not in ['teacher', 'student'] or not branch:
            flash('Please fill all fields correctly.', 'danger')
            return redirect(url_for('signup'))
        
        if role == 'student' and (not semester or not semester.isdigit() or int(semester) not in range(1, 9)):
            flash('Please provide a valid semester for students.', 'danger')
            return redirect(url_for('signup'))
        
        # Check if user exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists.', 'danger')
            return redirect(url_for('signup'))
        
        # Hash the password and create the new user
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password, role=role, branch=branch, semester=int(semester) if semester else None)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

# --- Login Route ---
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password, password):
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('login'))
        # Save user info in session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        flash('Logged in successfully!', 'success')
        if user.role == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return render_template('login.html')

# --- Logout Route ---
@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('index'))

# Route for About Page
@app.route('/about')
def about():
    return render_template('about.html')

# --- Teacher Dashboard ---
@app.route('/teacher/dashboard')
@login_required
@teacher_required
def teacher_dashboard():
    teacher_id = session['user_id']
    teacher = User.query.get(teacher_id)
    # Get all appointments created by this teacher
    appointments = Appointment.query.filter_by(teacher_id=teacher_id).order_by(Appointment.appointment_date).all()
    # Get all works created by this teacher
    works = Work.query.filter_by(teacher_id=teacher_id).order_by(Work.created_at).all()
    return render_template('teacher_dashboard.html', teacher=teacher, appointments=appointments, works=works)

# --- Add Appointment Slot (Teacher) ---
@app.route('/teacher/add_appointment', methods=['GET','POST'])
@login_required
@teacher_required
def add_appointment():
    if request.method == 'POST':
        date_str = request.form.get('appointment_date')
        try:
            # Expecting format "YYYY-MM-DDTHH:MM" from input type="datetime-local"
            appointment_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Invalid date format. Please try again.', 'danger')
            return redirect(url_for('add_appointment'))
        teacher_id = session['user_id']
        new_appointment = Appointment(teacher_id=teacher_id, appointment_date=appointment_date)
        db.session.add(new_appointment)
        db.session.commit()
        flash('Appointment slot added successfully!', 'success')
        return redirect(url_for('teacher_dashboard'))
    return render_template('add_appointment.html')

# --- Add Work (Teacher) ---
@app.route('/teacher/add_work', methods=['GET', 'POST'])
@login_required
@teacher_required
def add_work():
    if request.method == 'POST':
        semester = request.form.get('semester')
        content = request.form.get('content')
        
        if not semester or not content:
            flash('Please fill all fields.', 'danger')
            return redirect(url_for('add_work'))
        
        try:
            semester = int(semester)
            if semester not in range(1, 9):
                raise ValueError
        except ValueError:
            flash('Please provide a valid semester.', 'danger')
            return redirect(url_for('add_work'))
        
        teacher_id = session['user_id']
        teacher = User.query.get(teacher_id)
        new_work = Work(teacher_id=teacher_id, branch=teacher.branch, semester=semester, content=content)
        db.session.add(new_work)
        db.session.commit()
        flash('Work added successfully!', 'success')
        return redirect(url_for('teacher_dashboard'))
    return render_template('add_work.html')

# --- Edit Work (Teacher) ---
@app.route('/teacher/edit_work/<int:work_id>', methods=['GET', 'POST'])
@login_required
@teacher_required
def edit_work(work_id):
    work = Work.query.get_or_404(work_id)
    if request.method == 'POST':
        work.content = request.form.get('content')
        work.semester = request.form.get('semester')
        db.session.commit()
        flash('Work updated successfully!', 'success')
        return redirect(url_for('teacher_dashboard'))
    return render_template('edit_work.html', work=work)

# --- Delete Work (Teacher) ---
@app.route('/teacher/delete_work/<int:work_id>')
@login_required
@teacher_required
def delete_work(work_id):
    work = Work.query.get_or_404(work_id)
    db.session.delete(work)
    db.session.commit()
    flash('Work deleted successfully!', 'success')
    return redirect(url_for('teacher_dashboard'))

# --- View Appointment Details (Teacher) ---
@app.route('/teacher/view_appointments/<int:appointment_id>')
@login_required
@teacher_required
def view_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.teacher_id != session['user_id']:
        flash('You do not have permission to view this appointment.', 'danger')
        return redirect(url_for('teacher_dashboard'))
    student = None
    if appointment.student_id:
        student = User.query.get(appointment.student_id)
    return render_template('view_appointment.html', appointment=appointment, student=student)

# --- Cancel Appointment (Teacher) ---
@app.route('/teacher/cancel_appointment/<int:appointment_id>')
@login_required
@teacher_required
def cancel_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.teacher_id != session['user_id']:
        flash('You do not have permission to cancel this appointment.', 'danger')
        return redirect(url_for('teacher_dashboard'))
    db.session.delete(appointment)
    db.session.commit()
    flash('Appointment canceled successfully!', 'success')
    return redirect(url_for('teacher_dashboard'))

# --- Reschedule Appointment (Teacher) ---
@app.route('/teacher/reschedule_appointment/<int:appointment_id>', methods=['GET', 'POST'])
@login_required
@teacher_required
def reschedule_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.teacher_id != session['user_id']:
        flash('You do not have permission to reschedule this appointment.', 'danger')
        return redirect(url_for('teacher_dashboard'))
    if request.method == 'POST':
        date_str = request.form.get('appointment_date')
        try:
            # Expecting format "YYYY-MM-DDTHH:MM" from input type="datetime-local"
            new_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Invalid date format. Please try again.', 'danger')
            return redirect(url_for('reschedule_appointment', appointment_id=appointment_id))
        appointment.appointment_date = new_date
        db.session.commit()
        flash('Appointment rescheduled successfully!', 'success')
        return redirect(url_for('teacher_dashboard'))
    return render_template('reschedule_appointment.html', appointment=appointment)

# --- Student Dashboard ---
@app.route('/student/dashboard')
@login_required
@student_required
def student_dashboard():
    student_id = session['user_id']
    student = db.session.get(User, student_id)
    
    # Appointments that are not yet booked and are from teachers of the same branch
    available_appointments = db.session.query(Appointment, User).join(User, Appointment.teacher_id == User.id).filter(Appointment.booked == False, User.branch == student.branch).order_by(Appointment.appointment_date).all()
    
    # Appointments booked by the logged-in student
    booked_appointments = Appointment.query.filter_by(student_id=student_id).order_by(Appointment.appointment_date).all()
    
    # Works assigned to the student's branch and semester
    works = db.session.query(Work, User).join(User, Work.teacher_id == User.id).filter(Work.branch == student.branch, Work.semester == student.semester).order_by(Work.created_at).all()
    
    return render_template('student_dashboard.html', 
                           student=student,
                           available_appointments=available_appointments, 
                           booked_appointments=booked_appointments,
                           works=works)

# --- Book an Appointment Slot (Student) ---
@app.route('/student/book_appointment/<int:appointment_id>')
@login_required
@student_required
def book_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.booked:
        flash('This appointment slot is already booked.', 'danger')
        return redirect(url_for('student_dashboard'))
    
    appointment.booked = True
    appointment.student_id = session['user_id']
    db.session.commit()
    flash('Appointment booked successfully!', 'success')
    return redirect(url_for('student_dashboard'))

# Run the Application
if __name__:
    with app.app_context():
        db.create_all()  # Create database tables if they don't exist
    app.run(debug=True)
