import pandas as pd
import os

excel_path = 'excel sheet/sample_workflow_datasas.xlsx'

def excel_sheet_reader(mysql, default_user_id):
    try:
        if not os.path.exists(excel_path):
            return "❌ Excel file not found."

        df = pd.read_excel(excel_path)

        if df.empty:
            return "❌ Excel file is empty."

        cur = mysql.connection.cursor()

        for index, row in df.iterrows():
            created_by_email = str(row.get('Created by Email', '')).strip()

            if not created_by_email:
                #print(f"Row {index}: ❌ Email missing. Skipping.")
                continue

            # Get user ID from email
            cur.execute("SELECT idusers FROM users WHERE email = %s", (created_by_email,))
            result = cur.fetchone()
            print(result)

            if result:
                user_id_from_db = result[0]
                #print(f"Row {index}: ✅ Found user ID {user_id_from_db} for email {created_by_email}")
            else:
                user_id_from_db = default_user_id
                #print(f"Row {index}: ⚠️ Email not found. Using default user ID {default_user_id}")

            workflow_id = row.get('Workflow ID')
            if pd.isna(workflow_id):
                #print(f"Row {index}: ❌ Workflow ID missing. Skipping.")
                continue

            # Check for duplicate workflow
            cur.execute("SELECT workflow_id FROM workflows WHERE workflow_id = %s", (workflow_id,))
            if cur.fetchone():
                #print(f"Row {index}: ⚠️ Workflow ID {workflow_id} already exists. Skipping.")
                continue

            try:
                # Convert date fields safely
                start_date = pd.to_datetime(row['Start Date']).date()
                end_date = pd.to_datetime(row['End Date']).date()
                created_on = pd.to_datetime(row['Created On']).date()
                last_updated = pd.to_datetime(row['Last Updated']).date()

                cur.execute("""
                    INSERT INTO workflows (
                        workflow_id, workflow_name, assigned_to, status,
                        start_date, end_date, created_on, last_updated, user_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    workflow_id,
                    row['Workflow Name'],
                    row['Assigned To'],
                    row['Status'],
                    start_date,
                    end_date,
                    created_on,
                    last_updated,
                    user_id_from_db
                ))

                #print(f"✅ Row {index}: Inserted Workflow ID {workflow_id} for User ID {user_id_from_db}", flush=True)

            except Exception as e:
                print(f"❌ Row {index}: Error inserting data - {e}", flush=True)

        mysql.connection.commit()
        cur.close()
        return "✅ Data imported successfully!"

    except Exception as e:
        return f"❌ Error during processing: {e}"
