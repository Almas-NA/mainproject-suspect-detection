from flask import Flask, render_template, request, redirect, session
from db import *
import os
from werkzeug.utils import secure_filename
import cv2
import numpy as np

MATCH_CONSTANT = 80   # lower = stricter match
MIN_MATCH_FRAMES = 3


app = Flask(__name__)
app.secret_key = "my_secret_key"   # REQUIRED for session

UPLOAD_FOLDER = "static/uploads/cctv_videos"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

USER_UPLOAD_FOLDER = "static/uploads/missing_persons"
app.config["USER_UPLOAD_FOLDER"] = USER_UPLOAD_FOLDER
os.makedirs(USER_UPLOAD_FOLDER, exist_ok=True)

FACE_MATCH_FOLDER = "static/matches"
os.makedirs(FACE_MATCH_FOLDER, exist_ok=True)

face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login")
def login():
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return '''
        <script>
            alert("Logged out successfully");
            window.location.href = "/";
        </script>
    '''



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
    if user[4] == 1:
        if user[5] == 1:
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



# ================= USER =================

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


@app.route("/addmissing")
def addmissing():
    if "user" not in session:
        return '''
            <script>
                alert("Please login first");
                window.location.href = "/login";
            </script>
        '''
    return render_template("addmissing.html")

@app.route("/addmissingaction", methods=["POST"])
def addmissingaction():
    if "user" not in session:
        return '''
            <script>
                alert("Please login first");
                window.location.href = "/login";
            </script>
        '''

    full_name = request.form["full_name"]
    age = request.form["age"]
    gender = request.form["gender"]
    last_seen_location = request.form["last_seen_location"]
    start_date = request.form["start_date"]
    end_date = request.form["end_date"]
    photo = request.files["photo"]

    ext = photo.filename.rsplit(".", 1)[1]
    filename = secure_filename(f"{session['user'][0]}_{full_name}.{ext}")
    photo.save(os.path.join(app.config["USER_UPLOAD_FOLDER"], filename))

    # Insert missing person
    query = """
        INSERT INTO missing_persons
        (user_id, full_name, age, gender, last_seen_location,
         start_date, end_date, photo_file)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """
    insert_record(query, (
        session["user"][0],
        full_name,
        age,
        gender,
        last_seen_location,
        start_date,
        end_date,
        filename
    ))

    # Get inserted record ID
    get_id_query = "SELECT MAX(id) FROM missing_persons WHERE user_id = %s"
    missing_id = select_record(get_id_query, (session["user"][0],))[0]

    return redirect(f"/missingconfirm/{missing_id}")

@app.route("/scancctv/<int:mid>")
def scancctv(mid):

    mp_query = """
        SELECT id, full_name, photo_file, start_date, end_date
        FROM missing_persons
        WHERE id = %s
    """
    mp = select_record(mp_query, (mid,))

    if not mp:
        return "Missing person record not found"

    missing_id, name, photo_file, start_date, end_date = mp
    photo_path = f"static/uploads/missing_persons/{photo_file}"

    # ================= LOAD & PREPARE MISSING FACE =================
    img = cv2.imread(photo_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    faces = face_cascade.detectMultiScale(
        gray, scaleFactor=1.2, minNeighbors=6, minSize=(100, 100)
    )

    if len(faces) == 0:
        return "No clear face detected in missing person image"

    x, y, w, h = faces[0]
    missing_face = gray[y:y+h, x:x+w]
    missing_face = cv2.resize(missing_face, (200, 200))
    missing_face = cv2.equalizeHist(missing_face)

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train([missing_face], np.array([0]))

    # ================= FETCH CCTV VIDEOS =================
    video_query = """
        SELECT id, video_file
        FROM cctv_videos
        WHERE video_date BETWEEN %s AND %s
          AND status = 1
    """
    videos = select_records(video_query, (start_date, end_date))

    total_matches = 0

    # ================= PROCESS EACH VIDEO =================
    for vid in videos:
        video_id, video_file = vid
        video_path = f"static/uploads/cctv_videos/{video_file}"

        print(f"Scanning video: {video_file}")

        cap = cv2.VideoCapture(video_path)
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        frame_no = 0

        video_match_count = 0
        best_confidence = 999

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_no += 1

            # ⏱ process 1 frame every 2 seconds
            if frame_no % (fps * 2) != 0:
                continue

            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            faces = face_cascade.detectMultiScale(
                gray_frame, scaleFactor=1.2, minNeighbors=6, minSize=(80, 80)
            )
            profiles = profile_cascade.detectMultiScale(
                gray_frame, scaleFactor=1.2, minNeighbors=6, minSize=(80, 80)
            )

            detections = list(faces) + list(profiles)

            for (x, y, w, h) in detections:
                face = gray_frame[y:y+h, x:x+w]
                face = cv2.resize(face, (200, 200))
                face = cv2.equalizeHist(face)

                label, confidence = recognizer.predict(face)

                print("confidence",confidence)

                if confidence < best_confidence:
                    best_confidence = confidence

                if confidence < MATCH_CONSTANT:
                    video_match_count += 1

                   
                    crop_name = secure_filename(
                        f"{missing_id}_{video_id}_{frame_no}.jpg"
                    )

                    cv2.imwrite(
                        os.path.join(FACE_MATCH_FOLDER, crop_name),
                        frame[y:y+h, x:x+w]
                    )

                    total_matches += 1
                    break

        cap.release()
        print(f"Best confidence for {video_file}: {best_confidence}")

    return f"""
        <script>
            alert("Scan completed successfully. Matches found: {total_matches}");
            window.location.href = "/userhome";
        </script>
    """



# @app.route("/scancctv/<int:mid>")
# def scancctv(mid):
#     if "user" not in session:
#         return '''
#             <script>
#                 alert("Please login first");
#                 window.location.href = "/login";
#             </script>
#         '''

#     # 1️⃣ Get missing person details
#     mp_query = """
#         SELECT id, full_name, photo_file, start_date, end_date
#         FROM missing_persons
#         WHERE id = %s
#     """
#     mp = select_record(mp_query, (mid,))

#     if not mp:
#         return '''
#             <script>
#                 alert("Missing person record not found");
#                 window.location.href = "/userhome";
#             </script>
#         '''

#     missing_id = mp[0]
#     missing_name = mp[1]
#     photo_file = mp[2]
#     start_date = mp[3]
#     end_date = mp[4]

#     # 2️⃣ Get CCTV videos within date range
#     cctv_query = """
#         SELECT id, cctv_id, video_id, video_file, video_date
#         FROM cctv_videos
#         WHERE video_date BETWEEN %s AND %s
#           AND status = 1
#     """
#     videos = select_records(cctv_query, (start_date, end_date))

#     # For now, just confirm preparation is done
#     return render_template(
#         "scancctv.html",
#         missing_name=missing_name,
#         photo_file=photo_file,
#         video_count=len(videos),
#         videos=videos
#     )


# @app.route("/scancctv/<int:mid>")
# def scancctv(mid):

#     # ================= GET MISSING PERSON =================
#     mp_query = """
#         SELECT id, full_name, photo_file, start_date, end_date
#         FROM missing_persons
#         WHERE id = %s
#     """
#     mp = select_record(mp_query, (mid,))

#     if not mp:
#         return "Missing person not found"

#     missing_id, name, photo_file, start_date, end_date = mp

#     photo_path = f"static/uploads/missing_persons/{photo_file}"

#     # ================= LOAD & TRAIN FACE =================
#     img = cv2.imread(photo_path)
#     gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

#     faces = face_cascade.detectMultiScale(gray, 1.2, 5)

#     if len(faces) == 0:
#         return "No face detected in missing person image"

#     x, y, w, h = faces[0]
#     missing_face = gray[y:y+h, x:x+w]
#     missing_face = cv2.resize(missing_face, (200, 200))

#     recognizer = cv2.face.LBPHFaceRecognizer_create()
#     recognizer.train([missing_face], np.array([0]))

#     # ================= GET CCTV VIDEOS =================
#     video_query = """
#         SELECT id, video_file
#         FROM cctv_videos
#         WHERE video_date BETWEEN %s AND %s
#           AND status = 1
#     """
#     videos = select_records(video_query, (start_date, end_date))

#     match_count = 0

#     # ================= PROCESS EACH VIDEO =================
#     for vid in videos:
#         print("video started")
#         video_id, video_file = vid
#         video_path = f"static/uploads/cctv_videos/{video_file}"

#         cap = cv2.VideoCapture(video_path)
#         fps = int(cap.get(cv2.CAP_PROP_FPS))
#         frame_no = 0

#         while cap.isOpened():
#             ret, frame = cap.read()
#             if not ret:
#                 break

#             frame_no += 1

#             # ⏱ Process 1 frame per second
#             if frame_no % fps != 0:
#                 continue

#             gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
#             faces = face_cascade.detectMultiScale(gray_frame, 1.2, 5)

#             for (x, y, w, h) in faces:
#                 face = gray_frame[y:y+h, x:x+w]
#                 face = cv2.resize(face, (200, 200))

#                 label, confidence = recognizer.predict(face)

#                 print("confidence",confidence)

#                 # ================= MATCH FOUND =================
#                 if confidence < MATCH_CONSTANT:
#                     match_count += 1

#                     crop_name = secure_filename(
#                         f"{missing_id}_{video_id}_{frame_no}.jpg"
#                     )

#                     cv2.imwrite(
#                         os.path.join(FACE_MATCH_FOLDER, crop_name),
#                         frame[y:y+h, x:x+w]
#                     )

#         cap.release()

#     return f"""
#         <script>
#             alert("Scan completed. Matches found: {match_count}");
#             window.location.href = "/userhome";
#         </script>
#     """




# ================= MISSING PERSON CONFIRMATION =================

@app.route("/missingconfirm/<int:mid>")
def missingconfirm(mid):
    if "user" not in session:
        return '''
            <script>
                alert("Please login first");
                window.location.href = "/login";
            </script>
        '''

    # Fetch missing person details
    mp_query = """
        SELECT full_name, age, gender, last_seen_location,
               start_date, end_date, photo_file
        FROM missing_persons
        WHERE id = %s AND user_id = %s
    """
    mp = select_record(mp_query, (mid, session["user"][0]))

    if not mp:
        return '''
            <script>
                alert("Invalid request");
                window.location.href = "/userhome";
            </script>
        '''

    # Count CCTV videos in date range
    video_count_query = """
        SELECT COUNT(*)
        FROM cctv_videos
        WHERE video_date BETWEEN %s AND %s
          AND status = 1
    """
    video_count = select_record(
        video_count_query, (mp[4], mp[5])
    )[0]

    return render_template(
        "missingconfirm.html",
        mp=mp,
        mid=mid,
        video_count=video_count
    )


# ================= ADMIN =================

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

@app.route("/manageusers")
def manageusers():
    if "user" not in session:
        return '''
            <script>
                alert("Please login first");
                window.location.href = "/login";
            </script>
        '''

    # Admin check
    if session["user"][4] != 0:
        return '''
            <script>
                alert("Unauthorized access");
                window.location.href = "/login";
            </script>
        '''

    query = """
        SELECT id, full_name, email, status
        FROM users
        WHERE user_type = 1
    """
    users = select_records(query, ())

    return render_template("manageusers.html", users=users)

@app.route("/removeuser/<int:user_id>")
def removeuser(user_id):
    if "user" not in session:
        return '''
            <script>
                alert("Please login first");
                window.location.href = "/login";
            </script>
        '''

    if session["user"][4] != 0:
        return '''
            <script>
                alert("Unauthorized access");
                window.location.href = "/login";
            </script>
        '''

    query = "UPDATE users SET status = 0 WHERE id = %s"
    update_record(query, (user_id,))

    return '''
        <script>
            alert("User deactivated successfully");
            window.location.href = "/manageusers";
        </script>
    '''

@app.route("/uploadcctv")
def uploadcctv():
    if "user" not in session:
        return '''
            <script>
                alert("Please login first");
                window.location.href = "/login";
            </script>
        '''

    # Admin check (as per your memory)
    if session["user"][4] != 0:
        return '''
            <script>
                alert("Unauthorized access");
                window.location.href = "/login";
            </script>
        '''

    return render_template("uploadcctv.html")

@app.route("/uploadcctvaction", methods=["POST"])
def uploadcctvaction():
    if "user" not in session or session["user"][4] != 0:
        return '''
            <script>
                alert("Unauthorized access");
                window.location.href = "/login";
            </script>
        '''

    cctv_id = request.form["cctv_id"]
    video_id = request.form["video_id"]
    location = request.form["location"]
    video_date = request.form["video_date"]
    video = request.files["video"]

    if video.filename == "":
        return '''
            <script>
                alert("No video selected");
                window.location.href = "/uploadcctv";
            </script>
        '''

    # Build filename: CCTVID_VIDEOID.ext
    ext = video.filename.rsplit(".", 1)[1]
    filename = secure_filename(f"{cctv_id}_{video_id}.{ext}")

    video_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    video.save(video_path)

    query = """
        INSERT INTO cctv_videos
        (cctv_id, video_id, video_file, location, video_date, uploaded_by)
        VALUES (%s, %s, %s, %s, %s, %s)
    """

    insert_record(query, (
        cctv_id,
        video_id,
        filename,
        location,
        video_date,
        session["user"][0]
    ))

    return '''
        <script>
            alert("CCTV video uploaded successfully");
            window.location.href = "/adminhome";
        </script>
    '''

@app.route("/viewcctv")
def viewcctv():
    if "user" not in session:
        return '''
            <script>
                alert("Please login first");
                window.location.href = "/login";
            </script>
        '''

    # Admin check (user_type at index 4)
    if session["user"][4] != 0:
        return '''
            <script>
                alert("Unauthorized access");
                window.location.href = "/login";
            </script>
        '''

    query = """
        SELECT id, cctv_id, video_id, video_file, location, video_date
        FROM cctv_videos
        ORDER BY uploaded_at DESC
    """
    videos = select_records(query, ())

    return render_template("viewcctv.html", videos=videos)


if __name__ == "__main__":
    app.run(debug=True)
