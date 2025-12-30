from flask import Flask, render_template, request, redirect, session
from db import *

app = Flask(__name__)
app.secret_key = "my_secret_key"   # REQUIRED for session

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login")
def login():
    return render_template("login.html")


# ================= LOGIN ACTION =================
@app.route("/loginaction", methods=["POST"])
def loginaction():
    email = request.form["email"]
    password = request.form["password"]

    # Fetch entire user row
    query = """SELECT * FROM users WHERE email = %s AND password = %s """
    user = select_record(query, (email, password))

    # Invalid credentials
    if not user:
        return '''
            <script>
                alert("Invalid email or password");
                window.location.href = "/login";
            </script>
        '''

    session["user"] = user

    print(user)

    # Admin login
    if user[4] == 0:
        return '''
            <script>
                alert("Admin login successful");
                window.location.href = "/adminhome";
            </script>
        '''

    # Normal user login
    if user[3] == 1:
        if user[4] == 1:
            return '''
                <script>
                    alert("Login successful");
                    window.location.href = "/userhome";
                </script>
            '''
        else:
            return '''
                <script>
                    alert("Account pending verification");
                    window.location.href = "/login";
                </script>
            '''


@app.route("/register")
def register():
    return render_template("register.html")


# ================= REGISTER ACTION =================
@app.route("/regaction", methods=["POST"])
def regaction():
    full_name = request.form["fullname"]
    email = request.form["email"]
    password = request.form["password"]
    confirm_password = request.form["cpassword"]

    if password != confirm_password:
        return '''
            <script>
                alert("Passwords do not match");
                window.location.href = "/register";
            </script>
        '''

    check_query = "SELECT id FROM users WHERE email = %s"
    existing_user = select_record(check_query, (email,))

    if existing_user:
        return '''
            <script>
                alert("Email already exists");
                window.location.href = "/register";
            </script>
        '''

    insert_query = """
        INSERT INTO users (full_name, email, password)
        VALUES (%s, %s, %s)
    """
    insert_record(insert_query, (full_name, email, password))

    return '''
        <script>
            alert("Registration successful");
            window.location.href = "/login";
        </script>
    '''



# ================= USER HOME =================

@app.route("/userhome")
def userhome():
    # Optional: basic session check
    if "user" not in session:
        return '''
            <script>
                alert("Please login first");
                window.location.href = "/login";
            </script>
        '''

    return render_template("userhome.html")


# ================= ADMIN HOME =================

@app.route("/adminhome")
def adminhome():
    if "user" not in session:
        return '''
            <script>
                alert("Please login first");
                window.location.href = "/login";
            </script>
        '''

    # Ensure only admin can access
    if session["user"][4] != 0:   # user_type check
        return '''
            <script>
                alert("Unauthorized access");
                window.location.href = "/login";
            </script>
        '''

    return render_template("adminhome.html")



@app.route("/logout")
def logout():
    session.clear()
    return '''
        <script>
            alert("Logged out successfully");
            window.location.href = "/";
        </script>
    '''

if __name__ == "__main__":
    app.run(debug=True)
