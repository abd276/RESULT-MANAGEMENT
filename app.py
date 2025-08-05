import io
import csv
import json
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
import mysql.connector
from datetime import datetime
import re
from markupsafe import Markup

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

def get_subjects_for_semester(semester):
    subjects_map = {
        1: ['Programming with C++', 'Digital Electronics', 'Operating System', 'Mathematics 1', 'Communication Skills'],
        2: ['Python Programming', 'Microprocessor Architecture and Interfacing', 'Introduction to Unity', 'Mathematics 2', 'Green Computing'],
        3: ['Web Programming', 'Software Engineering', 'Database Management System', 'Applied Mathematics', 'Android Progamming'],
        4: ['Data Structures', 'Data Communication', 'Software Testing', '.Net Technologies', 'Core Java'],
        5: ['Software Project Management', 'Internet of Things', 'Virtual Reality', 'Artificial Intelligence', 'Enterprise Java'],
        6: ['Crptography', 'Data Mining', 'Cloud Computing', 'DevOps', 'Project Implementaion']
    }
    return subjects_map.get(semester, [])

def populate_result_table(cursor, table_name, semester):
    subjects = get_subjects_for_semester(semester)
    if not subjects:
        return
    exam_types = ['Internal', 'Theory', 'Practical']
    for subject in subjects:
        if subject == 'Project Implementaion' and semester == 6:
            max_marks, min_marks = 150, 60
            cursor.execute(f"""
                INSERT INTO `{table_name}` (subject_name, exam_type, maximum_marks, minimum_marks, marks_obtained, remarks)
                VALUES (%s, %s, %s, %s, NULL, NULL)
            """, (subject, 'Project', max_marks, min_marks))
        else:
            for exam_type in exam_types:
                if exam_type == 'Internal': max_marks, min_marks = 40, 16
                elif exam_type == 'Theory': max_marks, min_marks = 60, 24
                else: max_marks, min_marks = 50, 20
                cursor.execute(f"""
                    INSERT INTO `{table_name}` (subject_name, exam_type, maximum_marks, minimum_marks, marks_obtained, remarks)
                    VALUES (%s, %s, %s, %s, NULL, NULL)
                """, (subject, exam_type, max_marks, min_marks))

@app.route('/add-student', methods=['POST'])
@admin_required
def add_student():
    try:
        roll_no = request.form['roll_no']
        name = request.form['name']
        dob = datetime.strptime(request.form['dob'], '%Y-%m-%d').date()
        course = 'IT'
        semester = int(request.form['semester'])

        # Roll number validation
        roll_pattern = r'^(FYIT|SYIT|TYIT)([1-9][0-9]*)$'
        match = re.match(roll_pattern, roll_no)
        if not match:
            flash('Roll number must start with FYIT, SYIT, or TYIT followed by a positive integer with no extra text.', 'error')
            return redirect(url_for('admin_dashboard'))
        prefix = match.group(1)
        if semester in [1, 2] and prefix != 'FYIT':
            flash('For semester 1 or 2, roll number must start with FYIT.', 'error')
            return redirect(url_for('admin_dashboard'))
        elif semester in [3, 4] and prefix != 'SYIT':
            flash('For semester 3 or 4, roll number must start with SYIT.', 'error')
            return redirect(url_for('admin_dashboard'))
        elif semester in [5, 6] and prefix != 'TYIT':
            flash('For semester 5 or 6, roll number must start with TYIT.', 'error')
            return redirect(url_for('admin_dashboard'))

        today = datetime.now().date()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

        error_message = None
        if semester in [1, 2]:
            if not (17 <= age <= 30):
                error_message = "Criteria 17 to 30 years not matched"
        elif semester in [3, 4]:
            if not (18 <= age <= 31):
                error_message = "Criteria 18 to 31 years not matched"
        elif semester in [5, 6]:
            if not (19 <= age <= 32):
                error_message = "Criteria 19 to 32 years not matched"
        
        if error_message:
            flash(error_message, 'error')
            return redirect(url_for('admin_dashboard'))

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT roll_no FROM student_info WHERE roll_no = %s", (roll_no,))
        if cursor.fetchone():
            flash('Roll number already exists!', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_dashboard'))
        cursor.execute(
            "INSERT INTO student_info (roll_no, name, dob, course, semester) VALUES (%s, %s, %s, %s, %s)",
            (roll_no, name, dob, course, semester)
        )
        conn.commit()
        table_name = str(roll_no)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS `{table_name}` (
                subject_name VARCHAR(100) NOT NULL,
                exam_type VARCHAR(50) NOT NULL,
                maximum_marks INT NOT NULL,
                minimum_marks INT NOT NULL,
                marks_obtained INT,
                remarks TEXT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        populate_result_table(cursor, table_name, semester)
        conn.commit()
        flash('Student added successfully!', 'success')
        cursor.close()
        conn.close()
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        flash(f'Error adding student: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

def create_student_table(cursor, table_name):
    # Deprecated: now handled inline in add_student
    pass

@app.route('/results')
@admin_required
def results():
    roll_no = request.args.get('roll_no')
    student_name = request.args.get('student_name')
    # If no roll_no and student_name in args, try to get from session
    if not roll_no and not student_name:
        roll_no = session.get('student_roll_no')
        student_name = session.get('student_name')
    
    if not roll_no:
        flash('Please enter Roll No', 'error')
        return redirect(url_for('admin_dashboard'))
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # First check if student exists in student_info
        cursor.execute("SELECT name, course, semester FROM student_info WHERE roll_no = %s", (roll_no,))
        student = cursor.fetchone()
        if not student:
            flash('Student not found with the given Roll No', 'error')
            cursor.close()
            conn.close()
            student_name = ''  # Ensure student_name is defined
            return redirect(url_for('admin_dashboard'))
        student_name = student['name']
        table_name = str(roll_no)
        # Get results from student's table
        cursor.execute(f"""
            SELECT * FROM `{table_name}`
            ORDER BY
                CASE exam_type
                    WHEN 'Internal' THEN 1
                    WHEN 'Theory' THEN 2
                    WHEN 'Practical' THEN 3
                    WHEN 'Project' THEN 4
                    ELSE 5
                END
        """)
        results = cursor.fetchall()
        # Calculate overall result and percentage
        overall_result = 'Pass'
        total_marks_obtained = 0
        total_maximum_marks = 0
        for row in results:
            if row['remarks'] != 'Pass' and row['remarks'] is not None:
                overall_result = 'Fail'
            if row['marks_obtained'] is not None:
                total_marks_obtained += row['marks_obtained']
            total_maximum_marks += row['maximum_marks']
        if overall_result == 'Pass' and total_maximum_marks > 0:
            percentage = f"{(total_marks_obtained / total_maximum_marks) * 100:.2f}%"
        else:
            percentage = '-'
        # --- CSV preview logic ---
        # Only show CSV preview if released result does NOT exist
        csv_preview = None
        try:
            conn2 = get_db_connection()
            cursor2 = conn2.cursor()
            result_table = f"{roll_no}_result"
            cursor2.execute(f"SHOW TABLES LIKE '{result_table}'")
            if not cursor2.fetchone():
                cursor2.close()
                conn2 = get_db_connection()
                cursor2 = conn2.cursor(dictionary=True)
                cursor2.execute("SELECT data FROM student_csv_results WHERE roll_no = %s", (roll_no,))
                csv_row = cursor2.fetchone()
                if csv_row:
                    csv_preview = json.loads(csv_row['data'])
            cursor2.close()
            conn2.close()
        except Exception:
            csv_preview = None
        cursor.close()
        conn.close()
        return render_template('results.html', 
            student_name=student_name, 
            results=results, 
            course_name='IT',
            semester=student['semester'],
            overall_result=overall_result,
            percentage=percentage,
            roll_no=roll_no,
            csv_preview=csv_preview
        )

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

@app.route('/result-calculator/<roll_no>', methods=['GET'])
@admin_required
def result_calculator(roll_no):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    table_name = str(roll_no)
    
    # Get student's semester
    cursor.execute("SELECT semester FROM student_info WHERE roll_no = %s", (roll_no,))
    student = cursor.fetchone()
    semester = student['semester'] if student else None
    
    cursor.execute(f"SELECT DISTINCT subject_name FROM `{table_name}`")
    subjects = [row['subject_name'] for row in cursor.fetchall()]
    # Calculate overall result and percentage
    cursor.execute(f"SELECT * FROM `{table_name}`")
    rows = cursor.fetchall()
    overall_result = 'Pass'
    total_marks_obtained = 0
    total_maximum_marks = 0
    for row in rows:
        if row['remarks'] != 'Pass' and row['remarks'] is not None:
            overall_result = 'Fail'
        if row['marks_obtained'] is not None:
            total_marks_obtained += row['marks_obtained']
            total_maximum_marks += row['maximum_marks']
    if overall_result == 'Pass' and total_maximum_marks > 0:
        percentage = f"{(total_marks_obtained / total_maximum_marks) * 100:.2f}%"
    else:
        percentage = '-'
    cursor.close()
    conn.close()
    return render_template('result_calculator.html', roll_no=roll_no, subjects=subjects, overall_result=overall_result, percentage=percentage, semester=semester)

@app.route('/calculate-result/<roll_no>', methods=['POST'])
@admin_required
def calculate_result(roll_no):
    try:
        subject = request.form['subject']
        exam_type = request.form['type']
        maximum_marks = int(request.form['maximum_marks'])
        minimum_marks = int(0.4 * maximum_marks)
        marks_obtained = int(request.form['marks_obtained'])

        remarks = "Pass" if marks_obtained >= minimum_marks else "Fail"
        grade = calculate_grade(marks_obtained, maximum_marks)

        conn = get_db_connection()
        cursor = conn.cursor()
        table_name = str(roll_no)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS `{table_name}` (
                subject VARCHAR(100) NOT NULL,
                type VARCHAR(50) NOT NULL,
                maximum_marks INT NOT NULL,
                minimum_marks INT NOT NULL,
                marks_obtained INT NOT NULL,
                remarks TEXT,
                grade VARCHAR(2) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        cursor.execute(f"""
            INSERT INTO `{table_name}` 
            (subject, type, maximum_marks, minimum_marks, marks_obtained, remarks, grade)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (subject, exam_type, maximum_marks, minimum_marks, marks_obtained, remarks, grade))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Values Inserted Successfully!', 'success')
        return redirect(url_for('result_calculator', roll_no=roll_no))
    except Exception as e:
        flash(f'Error calculating result: {str(e)}', 'error')
        if 'conn' in locals():
            conn.rollback()
            cursor.close()
            conn.close()
        return redirect(url_for('result_calculator', roll_no=roll_no))

@app.route('/update-result/<roll_no>', methods=['POST'])
@admin_required
def update_result(roll_no):
    subject = request.form['subject']
    exam_type = request.form.get('type')

    if not exam_type:
        if subject == 'Project Implementaion':
            exam_type = 'Project'
        else:
            flash('Exam Type is required.', 'error')
            return redirect(url_for('result_calculator', roll_no=roll_no))

    marks_obtained = int(request.form['marks_obtained'])
    table_name = str(roll_no)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Get the row to check max marks
    cursor.execute(f"SELECT maximum_marks, minimum_marks FROM `{table_name}` WHERE subject_name = %s AND exam_type = %s", (subject, exam_type))
    row = cursor.fetchone()
    if not row:
        flash('No record found with the given Subject and Exam Type. Please check both fields.', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('result_calculator', roll_no=roll_no))
    if marks_obtained > row['maximum_marks']:
        flash('Marks obtained cannot be greater than maximum marks.', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('result_calculator', roll_no=roll_no))
    remarks = 'Pass' if marks_obtained >= row['minimum_marks'] else 'Fail'
    cursor.execute(f"UPDATE `{table_name}` SET marks_obtained = %s, remarks = %s WHERE subject_name = %s AND exam_type = %s", (marks_obtained, remarks, subject, exam_type))
    
    # Update permanent table if it exists
    try:
        cursor.execute(f"SELECT * FROM `{table_name}`")
        all_results = cursor.fetchall()
        
        overall_result = 'Pass'
        total_marks_obtained = 0
        total_maximum_marks = 0
        
        for result_row in all_results:
            if result_row['remarks'] != 'Pass' and result_row['remarks'] is not None:
                overall_result = 'Fail'
            if result_row['marks_obtained'] is not None:
                total_marks_obtained += result_row['marks_obtained']
            total_maximum_marks += result_row['maximum_marks']
        
        if overall_result == 'Pass' and total_maximum_marks > 0:
            percentage = f"{(total_marks_obtained / total_maximum_marks) * 100:.2f}%"
        else:
            percentage = '-'
        
        # Get student info
        cursor.execute("SELECT name, semester FROM student_info WHERE roll_no = %s", (roll_no,))
        student_info = cursor.fetchone()
        current_year = datetime.now().year
        
        # Update permanent table (update only, do not insert new row)
        cursor.execute("""
            UPDATE student_result_data
            SET name = %s, percentage = %s, updated_at = CURRENT_TIMESTAMP
            WHERE roll_no = %s AND year = %s AND semester = %s
        """, (student_info['name'], percentage, roll_no, current_year, student_info['semester']))
    except Exception as e:
        # If permanent table doesn't exist or error occurs, continue without updating it
        pass
    
    conn.commit()
    cursor.close()
    conn.close()
    flash('Result Updated Successfully!', 'success')
    return redirect(url_for('result_calculator', roll_no=roll_no))

@app.route('/delete-result/<roll_no>', methods=['POST'])
@admin_required
def delete_result(roll_no):
    try:
        subject = request.form['subject']
        exam_type = request.form['type']
        conn = get_db_connection()
        cursor = conn.cursor()
        table_name = str(roll_no)
        cursor.execute(f"SELECT * FROM `{table_name}` WHERE subject = %s AND type = %s", (subject, exam_type))
        if not cursor.fetchone():
            flash('No record found with the given Subject and Exam Type. Please check both fields.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('result_calculator', roll_no=roll_no))
        cursor.execute(f"DELETE FROM `{table_name}` WHERE subject = %s AND type = %s", (subject, exam_type))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Result Deleted Successfully!', 'success')
        return redirect(url_for('result_calculator', roll_no=roll_no))
    except Exception as e:
        flash(f'Error deleting result: {str(e)}', 'error')
        if 'conn' in locals():
            conn.rollback()
            cursor.close()
            conn.close()
        return redirect(url_for('result_calculator', roll_no=roll_no))

@app.route('/release-result/<roll_no>', methods=['POST'])
@admin_required
def release_result(roll_no):
    try:
        # If CSV exists for this roll_no, show success message and dashboard link, do not change any data
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT data FROM student_csv_results WHERE roll_no = %s", (roll_no,))
        csv_row = cursor.fetchone()
        cursor.close()
        conn.close()
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        table_name = str(roll_no)
        result_table = f"{roll_no}_result"
        cursor.execute(f"SELECT subject_name, exam_type, marks_obtained, remarks FROM `{table_name}`")
        rows = cursor.fetchall()
        if not rows:
            flash('No results found for this student.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('results', roll_no=roll_no))
        subjects = {}
        for row in rows:
            subj = row['subject_name']
            etype = row['exam_type']
            marks = row['marks_obtained']
            remark = row['remarks']
            if marks is None:
                flash('Please input marks for all subjects and exam types before releasing result.', 'error')
                cursor.close()
                conn.close()
                return redirect(url_for('results', roll_no=roll_no))
            if subj not in subjects:
                subjects[subj] = {'Internal': None, 'Theory': None, 'Practical': None, 'remarks': {}}
            subjects[subj][etype] = marks
            subjects[subj]['remarks'][etype] = remark
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS `{result_table}` (
                subject VARCHAR(100) NOT NULL,
                internal VARCHAR(10),
                theory VARCHAR(10),
                practical VARCHAR(10),
                total INT,
                remarks VARCHAR(10)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        cursor.execute(f"DELETE FROM `{result_table}`")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS student_result_data (
                roll_no VARCHAR(20) NOT NULL,
                name VARCHAR(100) NOT NULL,
                year INT NOT NULL,
                semester INT NOT NULL,
                percentage VARCHAR(10) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        cursor.execute(f"SELECT * FROM `{table_name}`")
        original_results = cursor.fetchall()
        overall_result = 'Pass'
        total_marks_obtained = 0
        total_maximum_marks = 0
        for row in original_results:
            if row['remarks'] != 'Pass' and row['remarks'] is not None:
                overall_result = 'Fail'
            if row['marks_obtained'] is not None:
                total_marks_obtained += row['marks_obtained']
            total_maximum_marks += row['maximum_marks']
        if overall_result == 'Pass' and total_maximum_marks > 0:
            percentage = f"{(total_marks_obtained / total_maximum_marks) * 100:.2f}%"
        else:
            percentage = '-'
        cursor.execute("SELECT name, semester FROM student_info WHERE roll_no = %s", (roll_no,))
        student_info = cursor.fetchone()
        current_year = datetime.now().year
        cursor.execute("""
            INSERT INTO student_result_data (roll_no, name, year, semester, percentage) 
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            name = VALUES(name), 
            year = VALUES(year), 
            semester = VALUES(semester), 
            percentage = VALUES(percentage)
        """, (roll_no, student_info['name'], current_year, student_info['semester'], percentage))
        for subject, data in subjects.items():
            internal = data.get('Internal')
            theory = data.get('Theory')
            practical = data.get('Practical')
            remarks = data.get('remarks', {})
            fail = False
            internal_val = str(internal) if remarks.get('Internal') == 'Pass' else f"{internal}F"
            theory_val = str(theory) if remarks.get('Theory') == 'Pass' else f"{theory}F"
            practical_val = str(practical) if remarks.get('Practical') == 'Pass' else f"{practical}F"
            for et in ['Internal', 'Theory', 'Practical']:
                if remarks.get(et) != 'Pass':
                    fail = True
            total = sum([v for v in [internal, theory, practical] if v is not None])
            row_remarks = 'Fail' if fail else 'Pass'
            cursor.execute(f"""
                INSERT INTO `{result_table}` (subject, internal, theory, practical, total, remarks)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (subject, internal_val, theory_val, practical_val, total, row_remarks))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Result released successfully!', 'success')
        return redirect(url_for('results', roll_no=roll_no))
    except Exception as e:
        flash(f'Error releasing result: {str(e)}', 'error')
        if 'conn' in locals():
            conn.rollback()
            cursor.close()
            conn.close()
        return redirect(url_for('results', roll_no=roll_no))
    
@app.route('/upload-csv', methods=['POST'])
def upload_csv():
    roll_no = request.args.get('roll_no')
    student_name = request.args.get('student_name')
    if not roll_no and not student_name:
        roll_no = session.get('student_roll_no')
        student_name = session.get('student_name')

    if not roll_no:
        flash('Please enter Roll No', 'error')
        return redirect(url_for('admin_dashboard'))

    # Block CSV upload if released result exists
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        result_table = f"{roll_no}_result"
        cursor.execute(f"SHOW TABLES LIKE '{result_table}'")
        if cursor.fetchone():
            flash('Result already released', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('results', roll_no=roll_no, student_name=student_name))
        cursor.close()
        conn.close()
    except Exception as e:
        flash(f'Error checking released result: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT name, course, semester FROM student_info WHERE roll_no = %s", (roll_no,))
        student = cursor.fetchone()
        if not student:
            flash('Student not found with the given Roll No', 'error')
            cursor.close()
            conn.close()
            student_name = ''
            return redirect(url_for('admin_dashboard'))
        student_name = student['name']
        table_name = str(roll_no)
        cursor.close()
        conn.close()
    except Exception as e:
        flash(f'Error fetching results: {str(e)}', 'error')
        if 'conn' in locals():
            cursor.close()
            conn.close()
        return redirect(url_for('admin_dashboard'))

    file = request.files.get('csvFile')
    if not file or not file.filename.endswith('.csv'):
        flash("Please upload a valid CSV file.", "error")
        return redirect(request.referrer)

    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"))
        reader = csv.DictReader(stream)
        csv_data = list(reader)

        # Store CSV data permanently in DB
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS student_csv_results (
                roll_no VARCHAR(20) PRIMARY KEY,
                data LONGTEXT NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        # Upsert CSV data
        cursor.execute("""
            INSERT INTO student_csv_results (roll_no, data)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE data = VALUES(data), uploaded_at = CURRENT_TIMESTAMP
        """, (roll_no, json.dumps(csv_data)))
        conn.commit()
        cursor.close()
        conn.close()

        flash('CSV uploaded and saved successfully!', 'success')
        return redirect(url_for('results', roll_no=roll_no, student_name=student_name))
    except Exception as e:
        flash(f'Error reading or saving CSV: {str(e)}', 'error')
        return redirect(request.referrer)


@app.route('/update_student', methods=['POST'])
@admin_required
def update_student():
    roll_no = request.form['roll_no']
    name = request.form['name']
    dob = datetime.strptime(request.form['dob'], '%Y-%m-%d').date()
    course = 'IT'
    new_semester = int(request.form['semester'])

    # Roll number validation
    roll_pattern = r'^(FYIT|SYIT|TYIT)([1-9][0-9]*)$'
    match = re.match(roll_pattern, roll_no)
    if not match:
        flash('Roll number must start with FYIT, SYIT, or TYIT followed by a positive integer with no extra text.', 'error')
        return redirect(url_for('admin_dashboard'))
    prefix = match.group(1)
    if new_semester in [1, 2] and prefix != 'FYIT':
        flash('For semester 1 or 2, roll number must start with FYIT.', 'error')
        return redirect(url_for('admin_dashboard'))
    elif new_semester in [3, 4] and prefix != 'SYIT':
        flash('For semester 3 or 4, roll number must start with SYIT.', 'error')
        return redirect(url_for('admin_dashboard'))
    elif new_semester in [5, 6] and prefix != 'TYIT':
        flash('For semester 5 or 6, roll number must start with TYIT.', 'error')
        return redirect(url_for('admin_dashboard'))

    today = datetime.now().date()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    error_message = None
    if new_semester in [1, 2]:
        if not (17 <= age <= 30):
            error_message = "Criteria 17 to 30 years not matched"
    elif new_semester in [3, 4]:
        if not (18 <= age <= 31):
            error_message = "Criteria 18 to 31 years not matched"
    elif new_semester in [5, 6]:
        if not (19 <= age <= 32):
            error_message = "Criteria 19 to 32 years not matched"

    if error_message:
        flash(error_message, 'error')
        return redirect(url_for('admin_dashboard'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT semester FROM student_info WHERE roll_no = %s", (roll_no,))
        student = cursor.fetchone()
        if not student:
            flash('Roll No does not exist.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_dashboard'))
        current_semester = student['semester']
        cursor.execute("UPDATE student_info SET name = %s, dob = %s, course = %s, semester = %s WHERE roll_no = %s",
                       (name, dob, course, new_semester, roll_no))
        if new_semester != current_semester:
            table_name = str(roll_no)
            cursor.execute(f"DELETE FROM `{table_name}`")
            populate_result_table(cursor, table_name, new_semester)
            # Drop released result table if exists
            cursor.execute(f"DROP TABLE IF EXISTS `{roll_no}_result`")
            flash('Student details and result table updated successfully for new semester!', 'success')
        else:
            flash('Student details updated successfully!', 'success')
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        flash(f'Error updating student: {str(e)}', 'error')
        if 'conn' in locals():
            conn.rollback()
        return redirect(url_for('admin_dashboard'))

@app.route('/delete_student', methods=['POST'])
@admin_required
def delete_student():
    roll_no = request.form['roll_no']
    name = request.form['name']
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Check if roll_no and name exist
        cursor.execute("SELECT * FROM student_info WHERE roll_no = %s AND name = %s", (roll_no, name))
        if not cursor.fetchone():
            flash('No student found with the given Roll No and Name.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_dashboard'))
        # Delete from student_info
        cursor.execute("DELETE FROM student_info WHERE roll_no = %s AND name = %s", (roll_no, name))
        # Drop the result table
        table_name = str(roll_no)
        cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
        # Drop released result table if exists
        cursor.execute(f"DROP TABLE IF EXISTS `{roll_no}_result`")
        conn.commit()
        cursor.close()
        conn.close()
        flash('Student deleted successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        flash(f'Error deleting student: {str(e)}', 'error')
        if 'conn' in locals():
            conn.rollback()
            cursor.close()
            conn.close()
        return redirect(url_for('admin_dashboard'))

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
    cursor.execute("SELECT * FROM student_info WHERE roll_no = %s AND name = %s", (roll_no, student_name))
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

@app.route('/student-login', methods=['GET', 'POST'])
def student_login():
    error = None
    if request.method == 'POST':
        roll_no = request.form['roll_no']
        dob = request.form['dob']

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM student_info WHERE roll_no = %s AND dob = %s", (roll_no, dob))
            student = cursor.fetchone()
            cursor.close()
            conn.close()

            if student:
                session['student_authenticated'] = True
                session['student_roll_no'] = roll_no
                return redirect(url_for('student_dashboard'))
            else:
                error = 'Invalid roll number or date of birth'
        except Exception as e:
            error = 'Error during login'

    return render_template('student_login.html', error=error)

@app.route('/student-dashboard')
def student_dashboard():
    if 'student_authenticated' not in session:
        return redirect(url_for('student_login'))

    roll_no = session.get('student_roll_no')
    if not roll_no:
        return redirect(url_for('student_login'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get student info
        cursor.execute("SELECT * FROM student_info WHERE roll_no = %s", (roll_no,))
        student = cursor.fetchone()

        if not student:
            flash('Student not found', 'error')
            return redirect(url_for('student_login'))

        # First, check if released result exists (give it priority)
        result_table = f"{roll_no}_result"
        cursor.execute(f"SHOW TABLES LIKE '{result_table}'")
        if cursor.fetchone():
            # Get released results
            cursor.execute(f"SELECT * FROM `{result_table}`")
            released_results = cursor.fetchall()
            # Calculate overall result and percentage from original table (same as results page)
            table_name = str(roll_no)
            cursor.execute(f"SELECT * FROM `{table_name}`")
            original_results = cursor.fetchall()
            overall_result = 'Pass'
            total_marks_obtained = 0
            total_maximum_marks = 0
            for row in original_results:
                if row['remarks'] != 'Pass' and row['remarks'] is not None:
                    overall_result = 'Fail'
                if row['marks_obtained'] is not None:
                    total_marks_obtained += row['marks_obtained']
                total_maximum_marks += row['maximum_marks']
            if overall_result == 'Pass' and total_maximum_marks > 0:
                percentage = f"{(total_marks_obtained / total_maximum_marks) * 100:.2f}%"
            else:
                percentage = '-'
            cursor.close()
            conn.close()
            return render_template('student_dashboard.html',
                                 student=student,
                                 results=released_results,
                                 overall_result=overall_result,
                                 percentage=percentage,
                                 total_marks_obtained=total_marks_obtained)
        # If no released result, check for CSV result
        conn2 = get_db_connection()
        cursor2 = conn2.cursor(dictionary=True)
        cursor2.execute("""
            CREATE TABLE IF NOT EXISTS student_csv_results (
                roll_no VARCHAR(20) PRIMARY KEY,
                data LONGTEXT NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        cursor2.execute("SELECT data FROM student_csv_results WHERE roll_no = %s", (roll_no,))
        csv_row = cursor2.fetchone()
        cursor2.close()
        conn2.close()
        if csv_row:
            csv_data = json.loads(csv_row['data'])
            return render_template('student_dashboard_csv.html', student=student, csv_data=csv_data)
        # If neither, show error
        flash('No released result found for this student', 'error')
        return redirect(url_for('student_login'))

        # Check if released result exists
        result_table = f"{roll_no}_result"
        cursor.execute(f"SHOW TABLES LIKE '{result_table}'")
        if not cursor.fetchone():
            flash('No released result found for this student', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('student_login'))

        # Get released results
        cursor.execute(f"SELECT * FROM `{result_table}`")
        released_results = cursor.fetchall()

        # Calculate overall result and percentage from original table (same as results page)
        table_name = str(roll_no)
        cursor.execute(f"SELECT * FROM `{table_name}`")
        original_results = cursor.fetchall()

        overall_result = 'Pass'
        total_marks_obtained = 0
        total_maximum_marks = 0

        for row in original_results:
            if row['remarks'] != 'Pass' and row['remarks'] is not None:
                overall_result = 'Fail'
            if row['marks_obtained'] is not None:
                total_marks_obtained += row['marks_obtained']
            total_maximum_marks += row['maximum_marks']

        if overall_result == 'Pass' and total_maximum_marks > 0:
            percentage = f"{(total_marks_obtained / total_maximum_marks) * 100:.2f}%"
        else:
            percentage = '-'

        cursor.close()
        conn.close()

        return render_template('student_dashboard.html',
                             student=student,
                             results=released_results,
                             overall_result=overall_result,
                             percentage=percentage,
                             total_marks_obtained=total_marks_obtained)

    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return redirect(url_for('student_login'))



@app.route('/student-logout')
def student_logout():
    session.pop('student_authenticated', None)
    session.pop('student_roll_no', None)
    return redirect(url_for('index'))

@app.route('/check-released-result/<roll_no>')
@admin_required
def check_released_result(roll_no):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        result_table = f"{roll_no}_result"
        cursor.execute(f"SHOW TABLES LIKE '{result_table}'")
        released_result_exists = cursor.fetchone() is not None
        cursor.close()
        conn.close()
        return jsonify({'released_result_exists': released_result_exists})
    except Exception as e:
        return jsonify({'released_result_exists': False})

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
        roll_no VARCHAR(20) PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        dob DATE NOT NULL,
        course VARCHAR(100) NOT NULL,
        semester INT NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """)
    
    conn.commit()
    cursor.close()
    conn.close()

# Initialize database
init_db()

@app.route('/manage-subjects', methods=['GET', 'POST'])
@admin_required
def manage_subjects():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    message = None

    if request.method == 'POST':
        old_subject = request.form.get('old_subject')
        new_subject = request.form.get('new_subject')
        if old_subject and new_subject:
            cursor.execute("UPDATE subjects SET subject = %s WHERE subject = %s", (new_subject, old_subject))
            conn.commit()
            message = f"Subject '{old_subject}' updated to '{new_subject}' successfully."

    cursor.execute("SELECT subject, semester FROM subjects ORDER BY semester, subject")
    subjects_data = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('subject.html', subjects_data=subjects_data, message=message)

@app.route('/performance', methods=['GET', 'POST'])
@admin_required
def performance():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch all student result data by default
    cursor.execute("SELECT * FROM student_result_data")
    student_result_data = cursor.fetchall()

    trend_data = None
    student_name = None
    year = None

    if request.method == 'POST':
        student_name = request.form['student_name']
        year = request.form['year']
        # Find the latest year for this student
        cursor.execute(
            "SELECT MAX(year) as latest_year FROM student_result_data WHERE name = %s",
            (student_name,)
        )
        row = cursor.fetchone()
        latest_year = row['latest_year'] if row and row['latest_year'] else None
        if not latest_year or str(year) != str(latest_year):
            flash(f"Please enter the latest year for this student: {latest_year}", 'error')
            trend_data = None
        else:
            # Fetch trend data for the given student and year (which is latest)
            cursor.execute(
                "SELECT semester, percentage FROM student_result_data WHERE name = %s AND year = %s ORDER BY semester",
                (student_name, year)
            )
            results = cursor.fetchall()
            if results:
                trend_data = {
                    'semesters': [f"{row['semester']}" for row in results],
                    'percentages': [float(row['percentage'].strip('%')) for row in results if row['percentage'] != '-']
                }

    cursor.close()
    conn.close()

    return render_template(
        'performance.html',
        student_result_data=student_result_data,
        trend_data=trend_data,
        student_name=student_name,
        year=year
    )

if __name__ == '__main__':
    app.run(debug=True)

