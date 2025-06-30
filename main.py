import random
from datetime import datetime, timedelta
from flask_dance.contrib.google import make_google_blueprint, google
from flask import Flask, request, render_template, flash, url_for, session
from flask_mysqldb import MySQL
from oauthlib.oauth2 import TokenExpiredError
from werkzeug.utils import redirect
from services import users
from common.excel_sheet_reader import excel_sheet_reader
from common.mailcinfig import mailotp
import os

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'



app = Flask(__name__)

app.secret_key = "your_secret_key_here"
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '12345'
app.config['MYSQL_DB'] = 'automation_suite'

mysql = MySQL(app)

blueprint = make_google_blueprint(
    # client_id="",
    # client_secret="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",
    scope=[
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile"
    ],
    redirect_url="/google_login"
)

app.register_blueprint(blueprint, url_prefix="/login")

@app.route('/')
def welcome():
    return render_template('welcome.html')

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        fullname=request.form['fullname']
        email=request.form['email']
        phone=request.form['phone']
        company=request.form['company']
        username=request.form['username']
        password=request.form['password']
        new_password = request.form['confirm_password']
        created_by = request.form['created_by']
        role = request.form['role']
        admin_id = session['admin_id']
        cur=mysql.connection.cursor()
        cur.execute('INSERT into users(fullname,email,phone,company,username,password,confirm_password,created_by,role,admin_id)'
                    'VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
        (fullname,email,phone,company,username,password,new_password,created_by,role,admin_id))
        mysql.connection.commit()
        cur.close()
        if password != new_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('register'))

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('register'))
    return render_template('signup.html')

@app.route('/login',methods=['GET','POST'])
def login():

    if request.method=='POST':
        Email=request.form['email']
        Password=request.form['password']
        cur=mysql.connection.cursor()
        cur.execute('select * from users WHERE email = %s and password = %s',(Email,Password))
        data=cur.fetchone()
        cur.close()

        if data:
            session['user_id'] = data[0]

            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route("/google_login")
def google_login():
    if not google.authorized:
        return redirect(url_for("google.login") + "?prompt=select_account")

    try:
        resp = google.get("/oauth2/v2/userinfo")
        if not resp.ok:
            return "Failed to fetch user info", 400
    except TokenExpiredError:

        session.clear()
        return redirect(url_for("google.login") + "?prompt=select_account")



    user_info = resp.json()
    email = user_info["email"]
    name = user_info["name"]

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cur.fetchone()

    if user:
        session['user_id'] = user[0]
    else:
        cur.execute("INSERT INTO users (fullname, email, username, created_by) VALUES (%s, %s, %s, %s)",
                    (name, email, email, 'Google'))
        mysql.connection.commit()
        session['user_id'] = cur.lastrowid
    cur.close()

    return redirect('/dashboard')


@app.route('/sendotp',methods=['GET','POST'])
def forget_password():
    if request.method=='POST':
        email=request.form['email']
        if not email:
            flash("Email is missing! Please enter a valid email.", "error")
            return redirect('/sendotp')
        cur=mysql.connection.cursor()
        cur.execute('select * from users WHERE email=%s',(email,))
        data=cur.fetchone()

        cur.close()
        if data:
            otp = random .randint(100000, 999999)
            expiry_time = datetime.now() + timedelta(minutes=5)
            cur=mysql.connection.cursor()
            cur.execute('UPDATE users SET otp=%s,expiry_time=%s WHERE email=%s',(otp,expiry_time,email))
            cur.connection.commit()
            cur.close()
            subject = "Password Reset OTP"
            message = f"Your OTP for password reset is: {otp}. It is valid for 5 minutes."

            if mailotp( email,subject, message):
                flash("OTP sent successfully! Check your email.", "success")
                return redirect('/reset-password')
            else:
                flash("Failed to send OTP. Try again.", "error")
                return redirect('/sendotp')

    return render_template('sendotp.html')

@app.route('/reset-password',methods=['GET','POST'])
def reset_password():
    if request.method=='POST':
        email=request.form['email']
        otp=request.form['otp']
        new_password=request.form['new_password']
        confirm_password=request.form['confirm_password']

        if new_password != confirm_password:
            flash("Passwords do not match!", "error")
            return redirect('/reset-password')

        cur = mysql.connection.cursor()
        cur.execute("SELECT otp, expiry_time FROM users WHERE email=%s", (email,))
        data = cur.fetchone()
        db_otp, expiry_time_str = data

        if otp != str(db_otp):
            flash("Invalid OTP!", "error")
            return redirect('/reset-password')
        expiry_time = datetime.strptime(expiry_time_str, "%Y-%m-%d %H:%M:%S.%f")

        if datetime.now() > expiry_time:
            flash("OTP expired! Please request a new one.", "error")
            return redirect('/sendotp')
        cur.execute('UPDATE users SET password_hash=%s, otp=NULL, expiry_time=NULL WHERE email=%s', (new_password, email))
        mysql.connection.commit()
        cur.close()

        flash("Password reset successfully!", "success")
        return redirect('/login')
    return render_template('forget-password.html')

@app.route('/profile', methods=['GET', 'POST'])
def update_profile():
    if 'user_id' not in session:
        flash("Please login first!", "warning")
        return redirect(url_for('login'))
    if request.method == 'GET':
        user_id = session['user_id']

        if not user_id:
            return "Error: User ID nahi mila!", 400
        cur = mysql.connection.cursor()
        cur.execute("SELECT idusers, fullname, email, phone, company, username, created_by, role FROM users WHERE idusers = %s", (user_id,))
        user = cur.fetchone()
        cur.close()



        if user:
            userData = {
                'idusers': user[0],
                "fullname": user[1],
                "email": user[2],
                "phone": user[3],
                "company": user[4],
                "username": user[5],
                "created_by": user[6],
                "role": user[7],
            }
            return render_template('profile.html', user=userData)
        else:
            return "Error: User not found!", 404
    return render_template('profile.html', user=None)


@app.route('/update_profile',methods=['POST'])
def updated_profile():
    if 'user_id' not in session:
        flash("Please login first!", "warning")
        return redirect(url_for('login'))
    users.update_user_profile(request)
    user_id = session['user_id']
    if request.method=='POST':
        fullname = request.form['fullname']
        email = request.form['email']
        phone = request.form['phone']
        company = request.form['company']

        cur = mysql.connection.cursor()
        data=cur.execute("UPDATE users SET fullname = %s ,email = %s ,phone = %s ,company = %s WHERE idusers = %s",(fullname,email,phone,company,user_id))

        mysql.connection.commit()
        cur.close()
        flash("Update profile successfully!", "success")
    return redirect(url_for('update_profile'))



@app.route('/sendotp')
def sendotp():
    try:
        return render_template('sendotp.html')
    except Exception as error:
        print(error)

@app.route('/home')
def home():
    return render_template('welcome.html')

@app.route('/work-flow')
def workflow():
    if 'user_id' not in session:
        flash("Please login first!", "warning")
        return redirect(url_for('login'))
    user_id = session['user_id']
    data = excel_sheet_reader(mysql, user_id)


    cur = mysql.connection.cursor()

    cur.execute('select username from users where idusers = %s',(user_id,))
    username = cur.fetchone()
    if username:
        username = username[0]
    else:
        username = "unkown user"


    cur.execute("""
                SELECT status, COUNT(*) 
    FROM workflows 
    WHERE user_id = %s
    GROUP BY status
""", (user_id,))


    result = cur.fetchall()

    workflow_data = {
        'Pending': 0,
        'In Progress': 0,
        'Completed': 0
    }




    # Process the result to map status count for each user
    for status, count in result:
        status = status.strip().title()  # Example: 'pending' -> 'Pending'
        if status in workflow_data:
            workflow_data[status] = count



    cur.close()

    return render_template("workflow_status.html", workflow_data=workflow_data,username = username)



@app.route('/logout')
def loginpage():
    session.pop('user_id')
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    cur = mysql.connection.cursor()
    cur.execute('select username from users where idusers = %s',(user_id,))
    username = cur.fetchone()

    if username:
        username = username[0]
    else:
        username = 'Unknow user'

    cur.execute('select workflow_name , status from workflows where user_id = %s',(user_id,))
    data = cur.fetchall()
    workflow = []
    for row in data:
        workflow.append({
            'Task':row[0],
            'status':row[1]
        })

    return  render_template('dashboard.html',username = username , data =workflow )

@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    cur = mysql.connection.cursor()
    cur.execute("select username from users where idusers = %s",(user_id,))
    user = cur.fetchone()
    if user:
        username = user[0]

    else:
        username = 'unknownuser'
    cur.execute("SELECT workflow_name, status, created_on, last_updated from workflows where user_id = %s",(user_id,))
    data = cur.fetchall()

    history = []
    for row in data:
        history.append({
            'workflow_name':row[0],
            'status':row[1],
            'created_on':row[2],
            'last_updated':row[3]

        })
    return render_template('history.html',history = history,username = username)

@app.route('/task')
def task():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    cur = mysql.connection.cursor()
    cur.execute("select username from users where idusers = %s",(user_id,))
    username = cur.fetchone()
    if username:
        user = username[0]
    else:
        user = 'username'
    cur.execute("SELECT workflow_id, workflow_name, start_date, end_date, status FROM workflows WHERE user_id = %s", (user_id,))
    data = cur.fetchall()
    task = []
    for row in data:
        task.append({
            'workflow_id': row[0],
            'workflow_name':row[1],
            'start_date':row[2],
            'end_date':row[3],
            'status':row[4]
        })
    mysql.connection.commit()
    cur.close()
    return render_template('task.html', task = task , username = user)

''' there is update_status '''

@app.route('/update_status', methods = ['POST'])
def updated_status():
    user_id = session['user_id']
    print(user_id)
    status = request.form['status']
    comment = request.form['comment']
    workflow_id = request.form['workflow_id']
    print(workflow_id)

    cur = mysql.connection.cursor()

    cur.execute('select username from users where idusers = %s', (user_id,))
    username = cur.fetchone()

    if username:
        username = username[0]
    else:
        username = 'Unknow user'

    data=cur.execute("UPDATE workflows SET status = %s WHERE  workflow_id = %s and user_id = %s ",(status,workflow_id,user_id))

    print(data)
    mysql.connection.commit()
    cur.close()
    flash("Update Task successfully!", "success")

    return render_template('task.html', username = username)




@app.route('/workflow')
def view_workflow():

    # Query parameter se workflow_id ko fetch karna
    workflow_id = request.args.get('workflow_id')  # Gets the workflow_id from URL query string

    if not workflow_id:
        return "No workflow ID provided", 400  # Agar workflow_id nahi mila, to error return karo

    cur = mysql.connection.cursor()
    cur.execute("SELECT workflow_name, start_date, end_date, status FROM workflows WHERE workflow_id = %s",
                (workflow_id,))
    workflow = cur.fetchone()

    if not workflow:
        return "Workflow not found", 404

    return render_template('task_details.html', workflow={
        'name': workflow[0],
        'start_date': workflow[1],
        'end_date': workflow[2],
        'status': workflow[3]
    })

@app.route('/admin_register', methods=['GET', 'POST'])
def admin_register():
    if request.method == 'POST':
        fullname = request.form['fullname']
        email = request.form['email']
        username = request.form['username']

        company = request.form['company']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('admin_register'))

        '''----------------sending register mail-------------'''

        subject = "Admin Registration Successful - Automation Suite"
        message = (
            "Your admin account has been successfully registered on Automation Suite.\n"
            "You can now log in and start managing your workflows and users.\n\n"
            "- Automation Suite Team"
        )
        mailotp(email, subject, message)

        '''---------------Database connection---------'''
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO admin_table (fullname, email, username,  company, password,confirm_password) VALUES ( %s, %s, %s, %s,%s,%s)",
            (fullname, email, username,  company, password,confirm_password))

        mysql.connection.commit()
        cur.close()
        flash('Admin registered successfully!', 'success')
        return redirect(url_for('admin_register'))

    return render_template('admin_register.html')


@app.route('/admin_login', methods = ['GET','POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        '''-----------------connection to database---------------'''
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM admin_table WHERE username = %s AND password = %s", (username, password))

        login_data = cur.fetchone()
        if login_data:
            session['admin_id'] = login_data[0]

        mysql.connection.commit()
        cur.close()

        if login_data:
            return redirect(url_for('admin_pannel'))

        else:
            flash('Invalid username or password. Please try again.', 'danger')





    return render_template('admin_login.html')


@app.route('/admin_send_otp', methods=['GET', 'POST'])
def admin_send_otp():
    if request.method == 'POST':
        email = request.form['Email']
        if not email:
            flash("Email is missing! Please enter a valid email.", "error")
            return redirect('/admin_send_otp')

        cur = mysql.connection.cursor()
        cur.execute('SELECT * FROM admin_table WHERE email = %s', (email,))
        data = cur.fetchone()

        if data:
            otp = random.randint(100000, 999999)
            expiry_time = datetime.now() + timedelta(minutes=5)
            cur.execute('UPDATE admin_table SET otp = %s, expiry_time = %s WHERE email = %s',
                        (otp, expiry_time, email))
            mysql.connection.commit()
            cur.close()

            subject = "Password Reset OTP"
            message = f"Your OTP for password reset is: {otp}. It is valid for 5 minutes."

            if mailotp(email, subject, message):
                flash("OTP sent successfully! Check your email.", "success")
                return redirect('/admin_reset_password')
            else:
                flash("Failed to send OTP. Try again.", "error")
                return redirect('/admin_send_otp')
        else:
            flash("Email not found in admin records.", "error")
            return redirect('/admin_send_otp')

    return render_template('admin_send_otpp.html')

@app.route('/admin_reset_password', methods=['GET', 'POST'])
def admin_reset_password():
    if request.method == 'POST':
        email = request.form['email']
        otp = request.form['otp']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if new_password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect('/admin_reset_password')

        cur = mysql.connection.cursor()
        cur.execute("SELECT otp, expiry_time FROM admin_table WHERE email=%s", (email,))
        data = cur.fetchone()

        if not data:
            flash("Invalid email or OTP.", "error")
            return redirect('/admin_reset_password')

        db_otp, expiry_time_str = data

        if otp != str(db_otp):
            flash("Invalid OTP!", "error")
            return redirect('/admin_reset_password')

        expiry_time = datetime.strptime(str(expiry_time_str), "%Y-%m-%d %H:%M:%S.%f")
        if datetime.now() > expiry_time:
            flash("OTP expired! Please request a new one.", "error")
            return redirect('/admin_send_otp')

        cur.execute('UPDATE admin_table SET password_hash=%s, otp=NULL, expiry_time=NULL WHERE email=%s',
                    (new_password, email))
        mysql.connection.commit()
        cur.close()

        flash("Password reset successfully!", "success")
        return redirect('/login')

    return render_template('admin_reset_password.html')

@app.route('/admin_profile', methods = ['GET','POST'])
def admin_profile():

    if request.method == 'GET':
        admin_id = session['admin_id']
        cur = mysql.connection.cursor()
        cur.execute('SELECT idadmin_table,fullname,email,username,company FROM admin_table WHERE idadmin_table = %s',(admin_id,))
        admin_profile = cur.fetchone()
        #print(admin_profile)
        cur.close()
        if admin_profile:
            adminData = {
                'idadmin_table':admin_profile[0],
                'fullname':admin_profile[1],
                'email':admin_profile[2],
                'username':admin_profile[3],
                'company':admin_profile[4],
            }
            #print(adminData)
            return render_template('admin_profile.html',admindata = adminData)
        else:

            flash("Invalid admin session", "error")
            return redirect('/admin_login')
    return render_template('admin_profile.html')


@app.route('/admin_update_profile',methods = ['POST'])
def admin_updated_profile():
    if request.method == 'POST':
        fullname = request.form['fullname']
        email = request.form['email']
        company = request.form['company']


        admin_id = session['admin_id']

        cur = mysql.connection.cursor()
        cur.execute("UPDATE admin_table SET fullname = %s,email = %s,company = %s WHERE idadmin_table = %s",(fullname,email,company,admin_id))
        mysql.connection.commit()
        cur.close()
        flash("Profile updated successfully!", "success")

    return redirect(url_for('admin_profile'))

@app.route('/create_task', methods=['GET', 'POST'])
def create_task():
    if 'admin_id' not in session:
        return redirect('/admin_login')

    admin_id = session['admin_id']
    #print(admin_id)
    cur = mysql.connection.cursor()


    cur.execute("SELECT idusers, fullname FROM users WHERE admin_id = %s", (admin_id,))

    users = cur.fetchall()
    #print(users)

    if request.method == 'POST':
        task_name = request.form['task_name']
        task_description = request.form['task_description']
        priority = request.form['priority']
        due_date = request.form['due_date']
        status = request.form['status']
        assigned_user = request.form['assigned_user']


        data=cur.execute("""
            INSERT INTO admin_create_task 
            (task_name, task_description, priority, due_date, status, assigned_user_id, created_by_admin_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (task_name, task_description, priority, due_date, status, assigned_user, admin_id))
        #print(data)
        mysql.connection.commit()
        flash("Task created successfully!", "success")
        return redirect("/create_task")


    return render_template('create_task.html', users=users)



@app.route('/admin_pannel')
def admin_pannel():
    admin_id = session['admin_id']
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM admin_table WHERE idadmin_table = %s",(admin_id,))
    data = cur.fetchone()
    print(data)
    if data:
        data = data[1]
    else:
        data = 'unknownuser'
    cur.close()
    return render_template('admin_panel.html',data = data)

if __name__ == '__main__':
    app.run(host='localhost', port=5003, debug=True)

