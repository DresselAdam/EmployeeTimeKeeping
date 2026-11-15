import csv
from datetime import datetime
import mysql.connector

# --- 1. CONNECT TO DATABASE ---
conn = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    password="",
    database="company_management"
)
cursor = conn.cursor()

# --- 2. OPEN CSV AND RUN BOTH PASSES ---
with open('SQL_Filler.csv', mode='r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    
    # Automatically clean whitespace out of headers
    reader.fieldnames = [field.strip() for field in reader.fieldnames]
    rows = list(reader)  

    print("Starting Pass 1: Importing cleaned employee records...")
    for row in rows:
        # DATA CLEANING 1: Clean up Site Locations
        site_loc = row['Site Location'].strip() if row.get('Site Location') else 'Unknown'
        loc_city = row['Location'].strip() if row.get('Location') else 'Unknown'
        
        cursor.execute("SELECT site_id FROM SiteLocations WHERE site_name = %s", (site_loc,))
        site = cursor.fetchone()
        if not site:
            cursor.execute("INSERT INTO SiteLocations (site_name, city_state) VALUES (%s, %s)", (site_loc, loc_city))
            site_id = cursor.lastrowid
        else:
            site_id = site[0]

        # DATA CLEANING 2: Map 'Customer Number' and 'Phone#' to Customer Table
        cust_num = row.get('Customer Number', '').strip()
        cust_phone = row.get('Phone#', '').strip()

        # Only process if there is an actual customer number
        if cust_num and cust_num.lower() != 'nan':
            # Check if this customer already exists to avoid duplicates
            cursor.execute("SELECT customer_number FROM Customers WHERE customer_number = %s", (cust_num,))
            existing_cust = cursor.fetchone()
            
            if not existing_cust:
                cursor.execute("INSERT INTO Customers (customer_number, phone_number) VALUES (%s, %s)", (cust_num, cust_phone))
        else:
            cust_num = None  # Ensure it is passed as NULL to the Employees table if missing

        # DATA CLEANING 3: Strip commas and currency markers from Salary
        raw_salary = row.get('Salary', '0')
        clean_salary = raw_salary.replace('$', '').replace(',', '').strip()

        # DATA CLEANING 4: Reformat MM/DD/YYYY to YYYY-MM-DD
        raw_date = row.get('Start Date', '').strip()
        try:
            clean_date = datetime.strptime(raw_date, '%m/%d/%Y').strftime('%Y-%m-%d')
        except ValueError:
            clean_date = "2026-01-01" # Safe fallback date if format is missing

        # Insert Employee (Leave manager_id as NULL temporarily)
        try:
            cursor.execute("""
                INSERT INTO Employees (
                    employee_number, first_name, last_name, salary, job_category, 
                    job_level, years_of_experience, manager_id, directorate, 
                    start_date, email, site_id, customer_number
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s)
            """, (
                row['Employee Number'].strip(), 
                row['First Name'].strip(), 
                row['Last Name'].strip(), 
                clean_salary, 
                row['Job Category'].strip(), 
                row['Job Level'].strip(), 
                row['Years of Experience'].strip() or 0, 
                row['Directorate'].strip(), 
                clean_date, 
                row['Email'].strip(), 
                site_id, 
                cust_num
            ))
        except mysql.connector.Error as err:
            print(f"SQL Error on employee {row['Employee Number']}: {err}")

    # Commit all core records so they exist before assigning hierarchy
    conn.commit()
    print("Pass 1 Complete! Records safely converted and saved to MySQL.")

    print("\nStarting Pass 2: Linking manager relationships...")
    for row in rows:
        manager_full_name = row.get('Manager', '').strip()
        
        if manager_full_name and manager_full_name.lower() != 'none':
            name_parts = [p.strip() for p in manager_full_name.split(" ", 1) if p.strip()]
            
            # If your CSV just lists one name like "ManagerName" instead of "First Last"
            if len(name_parts) == 1:
                cursor.execute(
                    "SELECT employee_number FROM Employees WHERE first_name = %s OR last_name = %s",
                    (name_parts[0], name_parts[0])
                )
            elif len(name_parts) == 2:
                cursor.execute(
                    "SELECT employee_number FROM Employees WHERE first_name = %s AND last_name = %s",
                    (name_parts[0], name_parts[1])
                )
                
            manager_row = cursor.fetchone()
            
            if manager_row:
                manager_emp_num = manager_row[0]
                cursor.execute(
                    "UPDATE Employees SET manager_id = %s WHERE employee_number = %s",
                    (manager_emp_num, row['Employee Number'].strip())
                )
            else:
                print(f"Warning: Manager '{manager_full_name}' needs to be a real employee with their own row in the CSV first!")

# Final save and cleanup
conn.commit()
cursor.close()
conn.close()
print("\nAll database transformations complete! Restart or refresh your Flask dashboard.")