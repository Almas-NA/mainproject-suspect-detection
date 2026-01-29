from flask import Flask, render_template, request, redirect, session
from db import *
import os
from werkzeug.utils import secure_filename
import cv2
import numpy as np
from datetime import datetime
import time


MATCH_CONSTANT = 70
MATCH_CONSTANT2 = 95   # lower = stricter match
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

# MISSING_FACE_DEBUG_FOLDER = "static/missing_face_debug"
# os.makedirs(MISSING_FACE_DEBUG_FOLDER, exist_ok=True)


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

    photos = request.files.getlist("photo")

    insert_query = """
        INSERT INTO missing_persons
        (user_id, full_name, age, gender, last_seen_location,
         start_date, end_date, photo_file)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """
    insert_record(insert_query, (
        session["user"][0],
        full_name,
        age,
        gender,
        last_seen_location,
        start_date,
        end_date,
        ""   # temp placeholder
    ))

    get_id_query = "SELECT MAX(id) FROM missing_persons WHERE user_id = %s"
    missing_id = select_record(get_id_query, (session["user"][0],))[0]

    safe_name = secure_filename(full_name.replace(" ", "_"))
    folder_name = f"{missing_id}_{safe_name}"
    folder_path = os.path.join(app.config["USER_UPLOAD_FOLDER"], folder_name)

    os.makedirs(folder_path, exist_ok=True)

    for idx, photo in enumerate(photos, start=1):
        ext = photo.filename.rsplit(".", 1)[1]
        image_name = f"{idx}.{ext}"
        photo.save(os.path.join(folder_path, image_name))

    update_query = """
        UPDATE missing_persons
        SET photo_file = %s
        WHERE id = %s
    """
    update_record(update_query, (folder_name, missing_id))

    return redirect(f"/missingconfirm/{missing_id}")

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

    (
        full_name,
        age,
        gender,
        last_seen_location,
        start_date,
        end_date,
        folder_name
    ) = mp

    # ================= GET ONE IMAGE FOR PREVIEW =================
    image_path = None
    folder_path = os.path.join(app.config["USER_UPLOAD_FOLDER"], folder_name)

    if os.path.exists(folder_path):
        images = sorted(os.listdir(folder_path))
        if images:
            image_path = f"{folder_name}/{images[0]}"  # usually 1.jpg

    # Count CCTV videos in date range
    video_count_query = """
        SELECT COUNT(*)
        FROM cctv_videos
        WHERE video_date BETWEEN %s AND %s
          AND status = 1
    """
    video_count = select_record(
        video_count_query, (start_date, end_date)
    )[0]

    return render_template(
        "missingconfirm.html",
        mp={
            "full_name": full_name,
            "age": age,
            "gender": gender,
            "last_seen_location": last_seen_location,
            "start_date": start_date,
            "end_date": end_date,
            "image_path": image_path
        },
        mid=mid,
        video_count=video_count
    )


@app.route("/scancctv/<int:mid>")
def scancctv(mid):

    # ================= FETCH MISSING PERSON =================
    mp_query = """SELECT id, full_name, photo_file, start_date, end_date FROM missing_persons WHERE id = %s"""
    mp = select_record(mp_query, (mid,))

    if not mp:
        return "Missing person record not found"

    missing_id, name, folder_name, start_date, end_date = mp

    folder_path = os.path.join( "static/uploads/missing_persons", folder_name)

    if not os.path.exists(folder_path):
        return "Missing person image folder not found"

    # ================= PREPARE TRAINING DATA =================
    training_faces = []
    labels = []
    label_id = 0

    for img_file in sorted(os.listdir(folder_path)):
        if not img_file.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        img_path = os.path.join(folder_path, img_file)
        img = cv2.imread(img_path)

        if img is None:
            print("Skipping unreadable image:", img_path)
            continue

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray,scaleFactor=1.2,minNeighbors=6,minSize=(100, 100))

        if len(faces) == 0:
            print("⚠ No face found in:", img_path)
            continue

        x, y, w, h = faces[0]
        face = gray[y:y+h, x:x+w]
        face = cv2.resize(face, (200, 200))
        face = cv2.equalizeHist(face)

        training_faces.append(face)
        labels.append(label_id)

    if len(training_faces) == 0:
        return "No usable faces found in missing person images"

    # ================= TRAIN LBPH =================
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(training_faces, np.array(labels))

    # ================= CREATE RUN FOLDER =================
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_folder_name = f"missing_{missing_id}_{timestamp}"
    RUN_MATCH_FOLDER = os.path.join(FACE_MATCH_FOLDER, run_folder_name)
    os.makedirs(RUN_MATCH_FOLDER, exist_ok=True)

    # ================= INSERT SCAN RUN =================
    insert_run_query = """INSERT INTO scan_runs (missing_person_id, run_folder) VALUES (%s, %s)"""
    insert_record(insert_run_query, (missing_id, run_folder_name))
    scan_run_id = select_record("SELECT MAX(id) FROM scan_runs WHERE missing_person_id=%s",(missing_id,))[0]

    # ================= FETCH CCTV VIDEOS =================
    video_query = """SELECT id, video_file FROM cctv_videos WHERE video_date BETWEEN %s AND %s AND status = 1"""
    videos = select_records(video_query, (start_date, end_date))
    total_matches = 0

    # ================= PROCESS EACH VIDEO =================
    for vid in videos:
        video_id, video_file = vid
        video_path = f"static/uploads/cctv_videos/{video_file}"

        print(f"▶ Scanning video: {video_file}")

        cap = cv2.VideoCapture(video_path)
        fps = int(cap.get(cv2.CAP_PROP_FPS)) or 25
        frame_no = 0
        best_confidence = 999

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            frame_no += 1
            # ⏱ process 1 frame every 2 seconds
            if frame_no % (fps * 2) != 0:
                continue

            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray_frame,scaleFactor=1.2,minNeighbors=6,minSize=(80, 80))
            profiles = profile_cascade.detectMultiScale(gray_frame,scaleFactor=1.2,minNeighbors=6,minSize=(80, 80))
            detections = list(faces) + list(profiles)

            for (x, y, w, h) in detections:
                face = gray_frame[y:y+h, x:x+w]
                face = cv2.resize(face, (200, 200))
                face = cv2.equalizeHist(face)

                label, confidence = recognizer.predict(face)
                print("confidence", confidence)

                if confidence < best_confidence:
                    best_confidence = confidence

                if confidence < MATCH_CONSTANT:
                    crop_name = secure_filename(
                        f"{missing_id}_{video_id}_{frame_no}_{round(confidence,2)}.jpg"
                    )

                    cv2.imwrite(
                        os.path.join(RUN_MATCH_FOLDER, crop_name),
                        frame[y:y+h, x:x+w]
                    )

                    # ================= SAVE MATCH =================
                    insert_match_query = """
                        INSERT INTO scan_matches
                        (scan_run_id, cctv_video_id, frame_no, confidence, match_image)
                        VALUES (%s, %s, %s, %s, %s)
                    """
                    insert_record(insert_match_query, (
                        scan_run_id,
                        video_id,
                        frame_no,
                        round(confidence, 2),
                        crop_name
                    ))

                    total_matches += 1
                    break

        cap.release()
        print(f"✔ Best confidence for {video_file}: {best_confidence}")

    # ================= UPDATE TOTAL MATCH COUNT =================
    update_query = """UPDATE scan_runs SET total_matches = %s WHERE id = %s"""
    update_record(update_query, (total_matches, scan_run_id))

    return f"""
        <script>
            alert("Scan completed successfully. Matches found: {total_matches}");
            window.location.href = "/scanresults/{scan_run_id}";
        </script>
    """




@app.route("/listmissing")
def listmissing():
    if "user" not in session:
        return '''
            <script>
                alert("Please login first");
                window.location.href = "/login";
            </script>
        '''

    query = """
        SELECT id, full_name, age, gender,
               last_seen_location, start_date, end_date, photo_file
        FROM missing_persons
        WHERE user_id = %s
        ORDER BY id DESC
    """
    records = select_records(query, (session["user"][0],))

    return render_template(
        "listmissing.html",
        records=records
    )


@app.route("/myscan")
def myscan():
    if "user" not in session:
        return '''
            <script>
                alert("Please login first");
                window.location.href = "/login";
            </script>
        '''

    query = "SELECT sr.id AS scan_id, mp.full_name, sr.run_folder, sr.total_matches, sr.scanned_on FROM scan_runs sr JOIN missing_persons mp ON sr.missing_person_id = mp.id WHERE mp.user_id = %s ORDER BY sr.scanned_on DESC"
    scans = select_records(query, (session["user"][0],))

    return render_template("myscan.html", scans=scans)

@app.route("/scanresults/<int:scan_id>")
def scanresults(scan_id):
    if "user" not in session:
        return '''
            <script>
                alert("Please login first");
                window.location.href = "/login";
            </script>
        '''

    scan_query = "SELECT sr.id, sr.run_folder, sr.total_matches, sr.scanned_on, mp.full_name FROM scan_runs sr JOIN missing_persons mp ON sr.missing_person_id = mp.id WHERE sr.id = %s AND mp.user_id = %s"
    scan = select_record(scan_query, (scan_id, session["user"][0]))

    if not scan:
        return '''
            <script>
                alert("Invalid scan request");
                window.location.href = "/myscan";
            </script>
        '''

    scan_id, run_folder, total_matches, scanned_on, person_name = scan

    match_query = "SELECT sm.frame_no, sm.confidence, sm.match_image, cv.video_file, cv.location, cv.video_date FROM scan_matches sm JOIN cctv_videos cv ON sm.cctv_video_id = cv.id WHERE sm.scan_run_id = %s ORDER BY sm.confidence ASC"
    matches = select_records(match_query, (scan_id,))

    return render_template(
        "scanresults.html",
        scan_id=scan_id,
        run_folder=run_folder,
        total_matches=total_matches,
        scanned_on=scanned_on,
        person_name=person_name,
        matches=matches
    )


@app.route("/searchcriminal")
def searchcriminal():
    if "user" not in session:
        return '''
            <script>
                alert("Please login first");
                window.location.href = "/login";
            </script>
        '''

    return render_template("searchcriminal.html")

@app.route("/searchcriminalaction", methods=["POST"])
def searchcriminalaction():
    if "user" not in session:
        return '''
            <script>
                alert("Please login first");
                window.location.href = "/login";
            </script>
        '''

    search_title = request.form["search_title"]
    remarks = request.form.get("remarks")
    photos = request.files.getlist("photos")

    # ===== INSERT SEARCH RECORD =====
    query = "INSERT INTO criminal_searches (user_id, search_title, remarks) VALUES (%s,%s,%s)"
    insert_record(query, (session["user"][0], search_title, remarks))

    search_id = select_record("SELECT MAX(id) FROM criminal_searches WHERE user_id=%s", (session["user"][0],))[0]

    # ===== CREATE FOLDER USING SEARCH ID =====
    folder_path = os.path.join("static/criminal_searches", str(search_id))
    os.makedirs(folder_path, exist_ok=True)

    # ===== SAVE IMAGES =====
    count = 1
    for photo in photos:
        if photo and photo.filename:
            ext = photo.filename.rsplit(".", 1)[1]
            filename = f"{count}.{ext}"
            photo.save(os.path.join(folder_path, filename))
            count += 1

    return '''
        <script>
            alert("Criminal search submitted successfully");
            window.location.href = "/mycriminalsearches";
        </script>
    '''


@app.route("/mycriminalsearches")
def mycriminalsearches():
    if "user" not in session:
        return '''
            <script>
                alert("Please login first");
                window.location.href = "/login";
            </script>
        '''

    query = "SELECT id, search_title, remarks, created_on FROM criminal_searches WHERE user_id=%s ORDER BY id DESC"
    searches = select_records(query, (session["user"][0],))

    return render_template("mycriminalsearches.html", searches=searches)


@app.route("/criminalsearchresults/<int:sid>")
def criminalsearchresults(sid):
    if "user" not in session:
        return '''
            <script>
                alert("Please login first");
                window.location.href = "/login";
            </script>
        '''

    # ===== FETCH SEARCH DETAILS =====
    search = select_record("SELECT id, search_title, remarks FROM criminal_searches WHERE id=%s AND user_id=%s", (sid, session["user"][0]))
    if not search:
        return '''
            <script>
                alert("Invalid request");
                window.location.href = "/mycriminalsearches";
            </script>
        '''

    # ===== LOAD SEARCH IMAGES =====
    search_folder = os.path.join("static/criminal_searches", str(sid))
    if not os.path.exists(search_folder):
        return "Search images not found"

    search_images = []
    for f in os.listdir(search_folder):
        if f.lower().endswith((".jpg", ".jpeg", ".png")):
            search_images.append(os.path.join(search_folder, f))

    if not search_images:
        return "No valid search images found"

    # ===== LOAD CRIMINAL DATA =====
    criminals = select_records("SELECT id, full_name, crime_type FROM criminals", ())
    if not criminals:
        return "No criminals available in database"

    training_faces = []
    labels = []
    label_map = {}

    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    label_id = 0
    for c in criminals:
        criminal_id, name, crime_type = c
        criminal_folder = os.path.join("static/criminals", str(criminal_id))

        if not os.path.exists(criminal_folder):
            continue

        label_map[label_id] = {
            "criminal_id": criminal_id,
            "name": name,
            "crime_type": crime_type
        }

        for img_file in os.listdir(criminal_folder):
            if not img_file.lower().endswith((".jpg", ".jpeg", ".png")):
                continue

            img_path = os.path.join(criminal_folder, img_file)
            img = cv2.imread(img_path)
            if img is None:
                continue

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.2, 6)

            if len(faces) == 0:
                continue

            x, y, w, h = faces[0]
            face = gray[y:y+h, x:x+w]
            face = cv2.resize(face, (200, 200))
            face = cv2.equalizeHist(face)

            training_faces.append(face)
            labels.append(label_id)

        label_id += 1

    if not training_faces:
        return "No valid criminal face data available"

    # ===== TRAIN MODEL =====
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(training_faces, np.array(labels))

    # ===== RUN SEARCH =====
    results = {}

    for img_path in search_images:
        img = cv2.imread(img_path)
        if img is None:
            continue

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.2, 6)

        for (x, y, w, h) in faces:
            face = gray[y:y+h, x:x+w]
            face = cv2.resize(face, (200, 200))
            face = cv2.equalizeHist(face)

            label, confidence = recognizer.predict(face)
            print(confidence)
            if confidence < MATCH_CONSTANT2:
                criminal = label_map[label]
                cid = criminal["criminal_id"]

                if cid not in results or confidence < results[cid]["confidence"]:
                    results[cid] = {
                        "name": criminal["name"],
                        "crime_type": criminal["crime_type"],
                        "confidence": round(confidence, 2)
                    }

    # ===== SORT RESULTS =====
    final_results = sorted(results.values(), key=lambda x: x["confidence"])

    print(final_results)
    return render_template(
        "criminalsearchresults.html",
        search=search,
        results=final_results
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


@app.route("/addcriminal")
def addcriminal():
    if "user" not in session:
        return '''
            <script>
                alert("Please login first");
                window.location.href = "/login";
            </script>
        '''

    return render_template("addcriminal.html")


@app.route("/addcriminalaction", methods=["POST"])
def addcriminalaction():
    if "user" not in session:
        return '''
            <script>
                alert("Please login first");
                window.location.href = "/login";
            </script>
        '''

    # ======== FETCH FORM DATA ========
    full_name = request.form["full_name"]
    alias_name = request.form.get("alias_name")
    age = request.form.get("age")
    gender = request.form.get("gender")
    crime_type = request.form.get("crime_type")
    crime_description = request.form.get("crime_description")
    identification_mark = request.form.get("identification_mark")
    last_known_location = request.form.get("last_known_location")

    # ======== INSERT INTO DATABASE ========
    query = "INSERT INTO criminals (full_name, alias_name, age, gender, crime_type, crime_description, identification_mark, last_known_location) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"
    insert_record(query, (full_name, alias_name, age, gender, crime_type, crime_description, identification_mark, last_known_location))

    criminal_id = select_record("SELECT MAX(id) FROM criminals", ())[0]

    # ======== CREATE IMAGE FOLDER ========
    save_dir = os.path.join("static/criminals", str(criminal_id))
    os.makedirs(save_dir, exist_ok=True)

    # ======== LOAD FACE CASCADE ========
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    # ======== START WEBCAM (NO GUI) ========
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return "Webcam not accessible"

    img_count = 0
    start_time = time.time()

    while img_count < 50:
        ret, frame = cap.read()
        if not ret or frame is None:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in faces:
            face_img = gray[y:y+h, x:x+w]
            face_img = cv2.resize(face_img, (200, 200))

            img_count += 1
            cv2.imwrite(os.path.join(save_dir, f"{img_count}.jpg"), face_img)

            if img_count >= 50:
                break

        # Safety timeout (15 seconds)
        if time.time() - start_time > 15:
            break

    cap.release()

    return '''
        <script>
            alert("Criminal record added and face data captured successfully");
            window.location.href = "/listcriminals";
        </script>
    '''


@app.route("/listcriminals")
def listcriminals():
    if "user" not in session:
        return '''
            <script>
                alert("Please login first");
                window.location.href = "/login";
            </script>
        '''

    query = "SELECT id, full_name, alias_name, crime_type, last_known_location, status, created_on FROM criminals ORDER BY created_on DESC"
    criminals = select_records(query, ())

    return render_template("listcriminals.html", criminals=criminals)



if __name__ == "__main__":
    app.run(debug=True)
