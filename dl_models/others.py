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
                        f"{missing_id}_{video_id}_{frame_no}_{confidence}.jpg"
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


