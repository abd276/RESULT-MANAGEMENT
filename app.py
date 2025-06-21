from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps
import mysql.connector
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a secure secret key in production

# MySQL Connection
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="admin",
        database="students"
    )

# Admin credentials (in a real application, these would be stored securely in a database)
ADMIN_CREDENTIALS = {
    'admin': '123'
}

# Login decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_authenticated' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def calculate_grade(marks_obtained, maximum_marks):
    percentage = (marks_obtained / maximum_marks) * 100
    if percentage >= 80:
        return 'O'
    elif percentage >= 70:
        return 'A+'
    elif percentage >= 60:
        return 'A'
    elif percentage >= 55:
        return 'B+'
    elif percentage >= 50:
        return 'B'
    elif percentage >= 45:
        return 'C'
    elif percentage >= 40:
        return 'D'
    else:
        return '-'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        admin_id = request.form['adminId']
        password = request.form['password']
        
        if admin_id in ADMIN_CREDENTIALS and ADMIN_CREDENTIALS[admin_id] == password:
            session['admin_authenticated'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            error = 'Invalid credentials'
    
    return render_template('admin_login.html', error=error)

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    # Always fetch the latest student list from student_info table
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM student_info")
    students = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin_dashboard.html', students=students)

@app.route('/add-student', methods=['POST'])
@admin_required
def add_student():
    try:
        roll_no = int(request.form['roll_no'])
        name = request.form['name']
        dob = datetime.strptime(request.form['dob'], '%Y-%m-%d').date()
        course = request.form['course']

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if roll number already exists
        cursor.execute("SELECT roll_no FROM student_info WHERE roll_no = %s", (roll_no,))
        if cursor.fetchone():
            flash('Roll number already exists! Please use a different roll number.', 'error')
            cursor.close()
            conn.close()
            # Get all students for the table
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM student_info")
            students = cursor.fetchall()
            cursor.close()
            conn.close()
            # Pass the form data back to the template
            return render_template('admin_dashboard.html', 
                                students=students,
                                form_data={
                                    'roll_no': roll_no,
                                    'name': name,
                                    'dob': request.form['dob'],
                                    'course': course
                                })

        # Create new student
        cursor.execute(
            "INSERT INTO student_info (roll_no, name, dob, course) VALUES (%s, %s, %s, %s)",
            (roll_no, name, dob, course)
        )
        conn.commit()

        # Create student's result table
        table_name = name.lower().replace(' ', '_')
        create_student_table(cursor, table_name)
        conn.commit()

        cursor.close()
        conn.close()
        flash('Student added successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        flash(f'Error adding student: {str(e)}', 'error')
        if 'conn' in locals():
            conn.rollback()
            cursor.close()
            conn.close()
        # Get all students for the table
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM student_info")
        students = cursor.fetchall()
        cursor.close()
        conn.close()
        # Pass the form data back to the template in case of any error
        return render_template('admin_dashboard.html', 
                            students=students,
                            form_data={
                                'roll_no': request.form.get('roll_no', ''),
                                'name': request.form.get('name', ''),
                                'dob': request.form.get('dob', ''),
                                'course': request.form.get('course', '')
                            })

def create_student_table(cursor, table_name):
    query = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        subject TEXT,
        type TEXT,
        maximum_marks INT,
        minimum_marks INT,
        marks_obtained INT,
        remarks TEXT,
        grade TEXT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    cursor.execute(query)

@app.route('/results')
@admin_required
def results():
    roll_no = request.args.get('roll_no')
    student_name = request.args.get('student_name')
    
    # If no roll_no and student_name in args, try to get from session
    if not roll_no and not student_name:
        roll_no = session.get('student_roll_no')
        student_name = session.get('student_name')
    
    if not roll_no or not student_name:
        flash('Please enter both Roll No and Student Name', 'error')
        return redirect(url_for('admin_dashboard'))
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # First check if student exists in student_info
        cursor.execute("SELECT name, course FROM student_info WHERE roll_no = %s", (int(roll_no),))
        student = cursor.fetchone()
        
        if not student:
            flash('Student not found with the given Roll No', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_dashboard'))
        
        # Get the student's name from student_info to ensure we use the correct name
        student_name = student['name']
        
        # Create table name from student's name
        table_name = student_name.lower().replace(' ', '_')
        
        # Create table if it doesn't exist
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                subject VARCHAR(100) NOT NULL,
                type VARCHAR(50) NOT NULL,
                maximum_marks INT NOT NULL,
                minimum_marks INT NOT NULL,
                marks_obtained INT NOT NULL,
                remarks TEXT,
                grade VARCHAR(2) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        conn.commit()
        
        # Get results from student's table
        cursor.execute(f"SELECT * FROM {table_name}")
        results = cursor.fetchall()

        # Calculate overall result and grade
        overall_result = 'Pass'
        overall_grade = '-'
        total_marks_obtained = 0
        total_maximum_marks = 0
        has_fail = False
        has_dash_grade = False
        for row in results:
            if row['remarks'] != 'Pass':
                overall_result = 'Fail'
                has_fail = True
            if row['grade'] == '-':
                has_dash_grade = True
            total_marks_obtained += row['marks_obtained']
            total_maximum_marks += row['maximum_marks']
        if has_dash_grade:
            overall_grade = '-'
        elif not has_fail and total_maximum_marks > 0:
            percentage = (total_marks_obtained / total_maximum_marks) * 100
            if percentage >= 80:
                overall_grade = 'O'
            elif percentage >= 70:
                overall_grade = 'A+'
            elif percentage >= 60:
                overall_grade = 'A'
            elif percentage >= 55:
                overall_grade = 'B+'
            elif percentage >= 50:
                overall_grade = 'B'
            elif percentage >= 45:
                overall_grade = 'C'
            elif percentage >= 40:
                overall_grade = 'D'
            else:
                overall_grade = '-'
        else:
            overall_grade = '-'

        cursor.close()
        conn.close()
        
        return render_template('results.html', 
                             student_name=student_name, 
                             results=results, 
                             course_name=student['course'],
                             overall_result=overall_result,
                             overall_grade=overall_grade)
    except Exception as e:
        flash(f'Error fetching results: {str(e)}', 'error')
        if 'conn' in locals():
            cursor.close()
            conn.close()
        return redirect(url_for('admin_dashboard'))

def get_all_students():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM student_info")
    students = cursor.fetchall()
    cursor.close()
    conn.close()
    return students

@app.route('/result-calculator/<student_name>', methods=['GET'])
@admin_required
def result_calculator(student_name):
    # No id-based editing, just show the form for adding a new result
    return render_template('result_calculator.html', student_name=student_name, result=None, result_id=None)

@app.route('/calculate-result/<student_name>', methods=['POST'])
@admin_required
def calculate_result(student_name):
    try:
        subject = request.form['subject']
        exam_type = request.form['type']
        maximum_marks = int(request.form['maximum_marks'])
        minimum_marks = int(request.form['minimum_marks'])
        marks_obtained = int(request.form['marks_obtained'])

        # Calculate remarks and grade
        remarks = "Pass" if marks_obtained >= minimum_marks else "Fail"
        grade = calculate_grade(marks_obtained, maximum_marks)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Create table name from student's name
        table_name = student_name.lower().replace(' ', '_')
        
        # Create table if it doesn't exist
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                subject VARCHAR(100) NOT NULL,
                type VARCHAR(50) NOT NULL,
                maximum_marks INT NOT NULL,
                minimum_marks INT NOT NULL,
                marks_obtained INT NOT NULL,
                remarks TEXT,
                grade VARCHAR(2) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        
        # Insert result
        cursor.execute(f"""
            INSERT INTO {table_name} 
            (subject, type, maximum_marks, minimum_marks, marks_obtained, remarks, grade)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (subject, exam_type, maximum_marks, minimum_marks, 
              marks_obtained, remarks, grade))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Values Inserted Successfully!', 'success')
        return redirect(url_for('result_calculator', student_name=student_name))
    except Exception as e:
        flash(f'Error calculating result: {str(e)}', 'error')
        if 'conn' in locals():
            conn.rollback()
            cursor.close()
            conn.close()
        return redirect(url_for('result_calculator', student_name=student_name))

@app.route('/update-result/<student_name>', methods=['POST'])
@admin_required
def update_result(student_name):
    try:
        subject = request.form['subject']
        exam_type = request.form['type']
        maximum_marks = int(request.form['maximum_marks'])
        minimum_marks = int(request.form['minimum_marks'])
        marks_obtained = int(request.form['marks_obtained'])

        # Calculate remarks and grade
        remarks = "Pass" if marks_obtained >= minimum_marks else "Fail"
        grade = calculate_grade(marks_obtained, maximum_marks)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Create table name from student's name
        table_name = student_name.lower().replace(' ', '_')
        
        # Check if the record exists
        cursor.execute(f"""
            SELECT * FROM {table_name} 
            WHERE subject = %s AND type = %s
        """, (subject, exam_type))
        
        if not cursor.fetchone():
            flash('No record found with the given Subject and Exam Type. Please check both fields.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('result_calculator', student_name=student_name))
        
        # Update the record
        cursor.execute(f"""
            UPDATE {table_name} 
            SET maximum_marks = %s, minimum_marks = %s, marks_obtained = %s, remarks = %s, grade = %s
            WHERE subject = %s AND type = %s
        """, (maximum_marks, minimum_marks, marks_obtained, remarks, grade, subject, exam_type))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Result Updated Successfully!', 'success')
        return redirect(url_for('result_calculator', student_name=student_name))
    except Exception as e:
        flash(f'Error updating result: {str(e)}', 'error')
        if 'conn' in locals():
            conn.rollback()
            cursor.close()
            conn.close()
        return redirect(url_for('result_calculator', student_name=student_name))

@app.route('/delete-result/<student_name>', methods=['POST'])
@admin_required
def delete_result(student_name):
    try:
        subject = request.form['subject']
        exam_type = request.form['type']

        conn = get_db_connection()
        cursor = conn.cursor()

        # Create table name from student's name
        table_name = student_name.lower().replace(' ', '_')
        
        # Check if the record exists
        cursor.execute(f"""
            SELECT * FROM {table_name} 
            WHERE subject = %s AND type = %s
        """, (subject, exam_type))

        record = cursor.fetchall()  # ✅ Fetch the result to clear it

        if not record:
            flash('No record found with the given Subject and Exam Type. Please check both fields.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('result_calculator', student_name=student_name))

        
        # Delete the record
        cursor.execute(f"""
            DELETE FROM {table_name} 
            WHERE subject = %s AND type = %s
        """, (subject, exam_type))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Result Deleted Successfully!', 'success')
        return redirect(url_for('result_calculator', student_name=student_name))
    except Exception as e:
        flash(f'Error deleting result: {str(e)}', 'error')
        if 'conn' in locals():
            conn.rollback()
            cursor.close()
            conn.close()
        return redirect(url_for('result_calculator', student_name=student_name))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/check-result', methods=['GET', 'POST'])
@admin_required
def check_result():
    if request.method == 'POST':
        roll_no = request.form.get('roll_no')
        student_name = request.form.get('name')
    else:
        roll_no = request.args.get('roll_no')
        student_name = request.args.get('student_name')
    
    if not roll_no or not student_name:
        flash('Please enter both Roll No and Student Name', 'error')
        return redirect(url_for('admin_dashboard'))
    
    # Check if both roll_no and student_name match a record
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM student_info WHERE roll_no = %s AND name = %s", (int(roll_no), student_name))
    student = cursor.fetchone()
    cursor.close()
    conn.close()
    if not student:
        flash('No student found with the given Roll No or Name. Please check both fields.', 'error')
        return redirect(url_for('admin_dashboard'))

    # Store in session
    session['student_roll_no'] = roll_no
    session['student_name'] = student_name
    
    return redirect(url_for('results', roll_no=roll_no, student_name=student_name))

# Create database and tables if they don't exist
def init_db():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="admin"
    )
    cursor = conn.cursor()
    
    # Create database if it doesn't exist
    cursor.execute("CREATE DATABASE IF NOT EXISTS students")
    cursor.execute("USE students")
    
    # Create student_info table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS student_info (
        roll_no INT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        dob DATE NOT NULL,
        course VARCHAR(100) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """)
    
    conn.commit()
    cursor.close()
    conn.close()

# Initialize database
init_db()

if __name__ == '__main__':
    app.run(debug=True) 