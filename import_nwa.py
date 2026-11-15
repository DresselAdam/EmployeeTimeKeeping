import csv
import mysql.connector

# --- 1. CONNECT TO DATABASE ---
conn = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    password="",
    database="company_management"
)
cursor = conn.cursor()

print("Extracting account data from SQL_Filler.csv...")

# --- 2. READ CSV AND INSERT UNIQUE ACCOUNTS ---
with open('NWA_Filler.csv', mode='r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    
    # Automatically clean whitespace out of CSV headers
    reader.fieldnames = [field.strip() for field in reader.fieldnames]
    
    inserted_count = 0
    skipped_count = 0

    for row in reader:
        # Pull matching values based on your exact header layout
        nwa_acct = row.get('NWA_Acct', '').strip()
        network = row.get('Network', '').strip()
        description = row.get('NWA Description', '').strip()

        # Skip rows that completely lack an account identifier
        if not nwa_acct:
            continue

        try:
            # INSERT IGNORE bypasses errors if the 'nwa_acct' primary key already exists
            cursor.execute("""
                INSERT IGNORE INTO NW_Accounts (nwa_acct, network, nwa_description)
                VALUES (%s, %s, %s)
            """, (nwa_acct, network, description))
            
            # cursor.rowcount will return 1 if inserted, or 0 if it was skipped as a duplicate
            if cursor.rowcount > 0:
                inserted_count += 1
            else:
                skipped_count += 1

        except mysql.connector.Error as err:
            print(f"Error inserting account {nwa_acct}: {err}")

# --- 3. COMMIT AND CLOSE ---
conn.commit()
cursor.close()
conn.close()

print("\n--- Import Process Completed! ---")
print(f"Successfully added: {inserted_count} unique accounts.")
print(f"Skipped (duplicates): {skipped_count} entries.")