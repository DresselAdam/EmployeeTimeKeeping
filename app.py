from flask import Flask, redirect, request, session, url_for, render_template, Response
import mysql.connector
import io
import csv

app = Flask(__name__)
app.secret_key = "dummy-secret-key-for-local-testing"

# --- DATABASE CONNECTION ---
def get_db_connection():
    return mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password="", 
        database="company_management"
    )

# --- ROUTES ---

@app.route("/")
def index():
    if session.get("user") and not request.args.get("view"):
        return redirect(url_for("dashboard"))
        
    current_view = request.args.get("view", "none")
    show_employee_verify = request.args.get("action") == "verify_employee"
    
    employee_rows = []
    account_rows = []
    
    if current_view != "none":
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if current_view == "accounts":
                cursor.execute("SELECT nwa_acct, network, nwa_description FROM NW_Accounts ORDER BY nwa_acct ASC")
                account_rows = cursor.fetchall()
            elif current_view == "staff":
                query = """
                    SELECT 
                        e.employee_number, e.first_name, e.last_name, e.salary, 
                        e.job_category, e.job_level, e.years_of_experience,
                        CONCAT(m.first_name, ' ', m.last_name) AS manager_name,
                        e.directorate, e.customer_number, c.phone_number AS customer_phone, 
                        e.start_date, e.email, s.city_state AS location, s.site_name AS site_location
                    FROM Employees e
                    LEFT JOIN Employees m ON e.manager_id = m.employee_number
                    LEFT JOIN SiteLocations s ON e.site_id = s.site_id
                    LEFT JOIN Customers c ON e.customer_number = c.customer_number
                    ORDER BY e.employee_number ASC
                """
                cursor.execute(query)
                employee_rows = cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    # Renders template/index.html directly passing view parameters
    return render_template(
        "index.html", 
        current_view=current_view, 
        accounts=account_rows, 
        staff=employee_rows, 
        show_employee_verify=show_employee_verify
    )

@app.route("/employee-form", methods=["POST"])
def employee_form():
    emp_num_input = request.form.get("employee_number", "").strip()
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    emp_data = None
    account_list = []
    
    try:
        cursor.execute("SELECT employee_number, first_name, last_name, team FROM Employees WHERE employee_number = %s", (emp_num_input,))
        emp_data = cursor.fetchone()
        
        if emp_data:
            cursor.execute("SELECT nwa_acct, network, nwa_description FROM NW_Accounts ORDER BY nwa_acct ASC")
            account_list = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    if not emp_data:
        return redirect(url_for("index", action="verify_employee"))

    # Renders template/employee_form.html
    return render_template("employee_form.html", emp_data=emp_data, account_list=account_list)

@app.route('/submit-time', methods=['POST'])
def submit_time_entry():
    print("FORM DATA RECEIVED:", request.form)

    if request.method == 'GET':
            return redirect(url_for('employee_form'))

    # Extract form fields matching the schema and form inputs
    employee_number = request.form.get('employee_number')
    team = request.form.get('team') or 'No Team Assigned'
    nwa_acct = request.form.get('nwa_acct')
    epic_number = request.form.get('epic_number')
    epic_description = request.form.get('epic_description')
    hours_worked = request.form.get('hours_worked')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO TimeEntries 
            (employee_number, team, nwa_acct, epic_number, epic_description, hours_worked)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (employee_number, team, nwa_acct, epic_number, epic_description, hours_worked))
        
        conn.commit()
        print(f"Successfully inserted {cursor.rowcount} row(s).")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('index'))

@app.route('/export-csv', methods=['GET'])
def export_csv():
    emp_num = request.args.get('employee_number')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        if emp_num:
            cursor.execute("""
                SELECT log_id, employee_number, team, nwa_acct, epic_number, epic_description, hours_worked, submission_timestamp 
                FROM TimeEntries 
                WHERE employee_number = %s
                ORDER BY submission_timestamp DESC
            """, (emp_num,))
        else:
            cursor.execute("""
                SELECT log_id, employee_number, team, nwa_acct, epic_number, epic_description, hours_worked, submission_timestamp 
                FROM TimeEntries 
                ORDER BY submission_timestamp DESC
            """)
        rows = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    # Generate CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Log ID', 'Employee Number', 'Team', 'NWA Account', 'Epic Number', 'Epic Description', 'Hours Worked', 'Submitted At'])
    
    # Write data rows
    for row in rows:
        writer.writerow([
            row['log_id'],
            row['employee_number'],
            row['team'],
            row['nwa_acct'],
            row['epic_number'],
            row['epic_description'],
            row['hours_worked'],
            row['submission_timestamp']
        ])

    filename = f"time_entries_emp_{emp_num}.csv" if emp_num else "all_time_entries.csv"

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.route("/mock-login")
def mock_login():
    chosen_email = request.args.get("email", "employee@company.com")
    session["user"] = chosen_email
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():
    user_email = session.get("user")
    if not user_email:
        return redirect(url_for("index"))
    
    user_role = "Manager" if user_email == "boss@company.com" else "Employee"

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT 
                e.employee_number, e.first_name, e.last_name, e.salary, 
                e.job_category, e.job_level, e.years_of_experience,
                CONCAT(m.first_name, ' ', m.last_name) AS manager_name,
                e.directorate, e.customer_number, c.phone_number AS customer_phone, 
                e.start_date, e.email, s.city_state AS location, s.site_name AS site_location
            FROM Employees e
            LEFT JOIN Employees m ON e.manager_id = m.employee_number
            LEFT JOIN SiteLocations s ON e.site_id = s.site_id
            LEFT JOIN Customers c ON e.customer_number = c.customer_number
            ORDER BY e.employee_number ASC
        """
        cursor.execute(query)
        employee_rows = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    # Renders template/dashboard.html
    return render_template("dashboard.html", email=user_email, role=user_role, staff=employee_rows)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True, port=5000)