import os
import csv
import logging
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename  
from flask_sqlalchemy import SQLAlchemy


# Configure logging
logging.basicConfig(level=logging.DEBUG)

current_dir = os.getcwd()
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(current_dir, "students.db") + "?check_same_thread=False&journal_mode=WAL"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Define the models
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    matric_no = db.Column(db.String(100), unique=True, nullable=False)
    level = db.Column(db.String(10), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(100), nullable=False)  # Store passwords as plain text

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)  # Store passwords as plain text

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_name = db.Column(db.String(100), nullable=False)
    course_code = db.Column(db.String(10), unique=True, nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=False)
    admin = db.relationship('Admin', backref=db.backref('courses', lazy=True))

class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100), nullable=False)
    course_name = db.Column(db.String(100), nullable=False)
    course_code = db.Column(db.String(10), nullable=False)
    level = db.Column(db.String(10), nullable=False)
    date_taken = db.Column(db.String(50), nullable=False)
    score = db.Column(db.String(10), nullable=False)

# Routes for the app
@app.route('/')
def index():
    return render_template('login.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        admin = Admin.query.filter_by(username=username).first()
        if admin:
            logging.debug(f"Admin found: {admin.username}")
            if admin.password == password:  # Check password directly
                session['admin'] = username
                session['admin_id'] = admin.id
                logging.debug("Admin login successful")
                return redirect(url_for('upload_result'))
            else:
                logging.debug("Admin password is incorrect")
                flash('Invalid username or password')
        else:
            logging.debug("Admin username does not exist")
            flash('Invalid username or password')
    return render_template('admin_login.html')

@app.route('/upload_result', methods=['GET', 'POST'])
def upload_result():
    if 'admin_id' not in session:
        flash('You must be logged in to access this page.', 'danger')
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        course_code = request.form['course_code']
        result_file = request.files['result_file']

        if result_file and secure_filename(result_file.filename):
            filename = secure_filename(result_file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            result_file.save(filepath)

            with open(filepath, mode='r') as file:
                csv_reader = csv.DictReader(file)
                for row in csv_reader:
                    new_result = Result(
                        student_name=row['Student Name'].strip().title(),
                        course_name=row['Course Name'].strip().title(),  # Normalize data
                        course_code=row['Course Code'].strip().upper(),
                        level=row['Level'].strip().upper(),
                        date_taken=row['Date Taken'].strip(),
                        score=row['Score (n/total)'].strip()
                    )
                    db.session.add(new_result)
                    logging.debug(f"Added result: {new_result}")
                db.session.commit()

            flash('Results uploaded successfully!', 'success')
            return redirect(url_for('upload_result'))

    # Fetch courses for the dropdown
    courses = Course.query.filter_by(admin_id=session['admin_id']).all()
    return render_template('upload_result.html', courses=courses)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        matric_no = request.form['matric_no']
        level = request.form['level']
        department = request.form['department']
        password = request.form['password']
        new_student = Student(name=name, matric_no=matric_no, level=level, department=department, password=password)  # Store password directly
        db.session.add(new_student)
        db.session.commit()
        flash('Registration successful')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/manage_students')
def manage_students():
    students = Student.query.all()
    return render_template('manage_students.html', students=students)


@app.route('/print_results')
def print_results():
    results = Result.query.all()
    for result in results:
        logging.debug(f"Student Name: {result.student_name}, Course Code: {result.course_code}, Level: {result.level}, Date Taken: {result.date_taken}, Score: {result.score}")
    return "Results printed in console"


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        matric_no = request.form['matric_no']
        password = request.form['password']
        student = Student.query.filter_by(matric_no=matric_no).first()
        if student:
            logging.debug(f"Student found: {student.matric_no}")
            if student.password == password:  # Check password directly
                session['matric_no'] = matric_no
                logging.debug("Student login successful")
                return redirect(url_for('select_course'))
            else:
                logging.debug("Student password is incorrect")
                flash('Invalid matric number or password')
        else:
            logging.debug("Student matric number does not exist")
            flash('Invalid matric number or password')
    return render_template('login.html')


@app.route('/select_course', methods=['GET', 'POST'])
def select_course():
    if 'matric_no' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        level = request.form['level'].strip().upper()
        course_code = request.form['course_code'].strip().upper()
        student = Student.query.filter_by(matric_no=session['matric_no']).first()

        if student:
            logging.debug(f"Student found: {student.name}, {level}, {course_code}")
            results = Result.query.filter_by(
                student_name=student.name.strip().title(),
                course_code=course_code,
                level=level
            ).all()
            
            if results:
                logging.debug(f"Results found: {results}")
                return render_template('result.html', results=results)
            else:
                logging.debug("No results found for the selected course and level")
                flash('No results found for the selected course and level', 'danger')
        else:
            logging.debug("Student not found in the database")
            flash('Student not found', 'danger')
    
    courses = Course.query.all()
    return render_template('select_course.html', courses=courses)


@app.route('/add_course', methods=['GET', 'POST'])
def add_course():
    if 'admin_id' not in session:
        flash('You must be logged in to access this page.', 'danger')
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        course_name = request.form['course_name']
        course_code = request.form['course_code']
        admin_id = session['admin_id']  # Use admin_id from session

        new_course = Course(course_name=course_name, course_code=course_code, admin_id=admin_id)
        db.session.add(new_course)
        db.session.commit()

        flash('Course added successfully!', 'success')
        return redirect(url_for('upload_result'))

    return render_template('add_course.html')

@app.route('/delete_student/<matric_no>', methods=['POST'])
def delete_student(matric_no):
    # Connect to your database
    conn = sqlite3.connect('your_database.db')
    cursor = conn.cursor()

    # Execute the DELETE statement
    cursor.execute("DELETE FROM students WHERE matric_no = ?", (matric_no,))
    conn.commit()

    # Close the database connection
    cursor.close()
    conn.close()

    # Redirect back to the manage students page
    return redirect(url_for('manage_students'))


@app.route('/logout')
def logout():
    session.pop('admin_id', None)
    session.pop('admin', None)
    session.pop('matric_no', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('admin_login'))

@app.route('/student_logout')
def student_logout():
    session.pop('matric_no', None)  # Remove the student matric number from the session
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))  # Redirect to the login page


if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])  # Ensure the upload folder exists
        


    with app.app_context():
        db.create_all()  # Create tables
    app.run(debug=True)
