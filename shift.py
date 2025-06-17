import streamlit as st
import duckdb
from datetime import datetime, date, time
import pandas as pd
from zoneinfo import ZoneInfo
import os
from dotenv import load_dotenv

 
load_dotenv()

password = os.getenv("PASSWORD")


# הגדרת הדף
st.set_page_config(page_title="דיווח משמרת", layout="centered", page_icon="📝")

# התחברות לבסיס הנתונים
@st.cache_resource
def init_database():
    try:
        con = duckdb.connect("reports.db")
        # יצירת טבלת דיווחים
        con.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            report_type TEXT, 
            personal_id TEXT,
            rahal TEXT,
            work_location TEXT,
            replacing_who TEXT,
            replacement_person TEXT,
            reports_count INTEGER,
            special_notes TEXT,
            timestamp TEXT,
            start_date TEXT,
            start_time TEXT,
            end_date TEXT,
            end_time TEXT
        )
        """)
        # יצירת טבלת היכן אני כעת
        con.execute("""
        CREATE TABLE IF NOT EXISTS green_eyes (
            personal_id TEXT,
            current_location TEXT,
            timestamp TEXT, 
            on_shift TEXT,
            PRIMARY KEY (personal_id)
        )
        """)
        return con
    except Exception as e:
        st.error(f"שגיאה בהתחברות למסד הנתונים: {e}")
        return None



# בדיקה אם יש חיבור למסד נתונים
con = init_database()

if con is None:
    st.stop()

# תפריט ניווט
st.sidebar.title("🧭 ניווט")
page = st.sidebar.selectbox("בחר עמוד:", ["""דוח משמרת""", "היכן אני כעת", "ADMIN"])


# עמוד היכן אני כעת

if page == "היכן אני כעת":
    st.title("👀 היכן אני כעת")
    st.markdown("---")
    
    # טופס דיווח היכן אני כעת
    with st.form("green_eyes_form", clear_on_submit=True):
        st.subheader("דיווח מיקום נוכחי")
        
        col1, col2 = st.columns(2)
        
        with col1:
            personal_id = st.text_input("מ.א - ארבע ספרות אחרונות*", placeholder="הכנס מספר", max_chars=4)

        
        with col2:
            current_location = st.text_input("מיקום נוכחי *", placeholder="הכנס מיקום חופשי")

            on_shift = st.radio("? האם אתה במשמרת או בפעילות", ["כן", "לא"])
            
        # כפתור שליחה
        submitted = st.form_submit_button("📍 עדכן מיקום", type="primary")
        
        if submitted:
            # בדיקת שדות חובה
            if not personal_id or not current_location.strip():
                st.error("❌ נא למלא את כל השדות הנדרשים")
            else:
                try:
                    # timestamp = datetime.now()
                    timestamp = datetime.now(ZoneInfo("Asia/Jerusalem"))
                    con.execute("""
                        INSERT OR REPLACE INTO green_eyes (
                            personal_id, current_location, on_shift, timestamp
                        ) VALUES (?, ?,?, ?)
                    """, (personal_id, current_location.strip(),on_shift,timestamp))
                    
                    st.success(f"✅ דווח בהצלחה")
                    st.balloons()
                    
                except Exception as e:
                    st.error(f"❌ שגיאה בשמירת הנתונים: {str(e)}")

    # הצגת מי כבר דיווח היום
    st.markdown("---")
    

# עמוד דיווח שעות עם הגנת קוד
elif page == "ADMIN":
    st.title("⏰ דף ניהול")
    st.markdown("---")
    
    # בדיקת קוד גישה
    if 'access_granted' not in st.session_state:
        st.session_state.access_granted = False
    
    if not st.session_state.access_granted:
        st.subheader("🔐 הכנס קוד גישה")
        access_code = st.text_input("קוד גישה:", type="password")
        
        if st.button("אמת קוד"):
            if access_code == password:
                st.session_state.access_granted = True
                st.rerun()
            else:
                st.error("❌ קוד שגוי!")
        st.stop()
    
    # תפריט בדף ניהול
    admin_tab = st.selectbox("בחר סוג דיווח:", [
        "סיכום שעות עבודה", 
        "היכן אני כעת - מעקב", 
        "ניהול נתונים"
    ])
    
    if admin_tab == "סיכום שעות עבודה":
        # הצגת דיווח שעות
        st.subheader("📊 סיכום שעות עבודה השבוע")
        
        try:
            # חישוב תאריכי השבוע הנוכחי (ראשון עד ראשון)
            today = date.today()
            days_since_sunday = (today.weekday() + 1) % 7
            week_start = today - pd.Timedelta(days=days_since_sunday)
            week_end = week_start + pd.Timedelta(days=6)
            
            st.info(f"השבוע: {week_start.strftime('%d/%m/%Y')} - {week_end.strftime('%d/%m/%Y')}")
            
            # שאילתה לחישוב שעות עבודה - מפושטת
            hours_query = """
            WITH entry_exits AS (
                SELECT 
                    e.personal_id,
                    e.work_location,
                    e.start_date,
                    e.start_time,
                    e.timestamp as entry_time,
                    (SELECT x.end_date FROM reports x 
                     WHERE x.personal_id = e.personal_id 
                     AND x.report_type = 'exit' 
                     AND x.timestamp > e.timestamp 
                     ORDER BY x.timestamp LIMIT 1) as end_date,
                    (SELECT x.end_time FROM reports x 
                     WHERE x.personal_id = e.personal_id 
                     AND x.report_type = 'exit' 
                     AND x.timestamp > e.timestamp 
                     ORDER BY x.timestamp LIMIT 1) as end_time
                FROM reports e
                WHERE e.report_type = 'entry'
                AND DATE(e.start_date) >= ? 
                AND DATE(e.start_date) <= ?
            ),
            calculated_hours AS (
                SELECT 
                    personal_id,
                    work_location,
                    start_date,
                    start_time,
                    end_date,
                    end_time,
                    CASE 
                        WHEN start_time IS NOT NULL AND end_time IS NOT NULL 
                        AND start_date IS NOT NULL AND end_date IS NOT NULL THEN
                            CASE 
                                WHEN start_date = end_date THEN
                                    (EXTRACT('hour' FROM CAST(end_time AS TIME)) * 60 + EXTRACT('minute' FROM CAST(end_time AS TIME))) -
                                    (EXTRACT('hour' FROM CAST(start_time AS TIME)) * 60 + EXTRACT('minute' FROM CAST(start_time AS TIME)))
                                ELSE
                                    -- חישוב עבור משמרות שעוברות חצות
                                    (24 * 60) - (EXTRACT('hour' FROM CAST(start_time AS TIME)) * 60 + EXTRACT('minute' FROM CAST(start_time AS TIME))) +
                                    (EXTRACT('hour' FROM CAST(end_time AS TIME)) * 60 + EXTRACT('minute' FROM CAST(end_time AS TIME)))
                            END / 60.0
                        ELSE NULL
                    END as hours_worked
                FROM entry_exits
            )
            SELECT 
                personal_id,
                work_location,
                COUNT(*) as total_shifts,
                COUNT(*) FILTER (WHERE hours_worked IS NOT NULL) as completed_shifts,
                ROUND(SUM(COALESCE(hours_worked, 0)), 2) as total_hours,
                ROUND(AVG(hours_worked), 2) as avg_hours_per_shift,
                MIN(start_date) as first_shift_date,
                MAX(COALESCE(end_date, start_date)) as last_shift_date
            FROM calculated_hours
            GROUP BY personal_id, work_location
            ORDER BY total_hours DESC
            """
            
            results = con.execute(hours_query, [week_start.strftime('%Y-%m-%d'), week_end.strftime('%Y-%m-%d')]).fetchall()
            
            if results:
                # יצירת DataFrame להצגה
                df = pd.DataFrame(results, columns=[
                    'מ.א','מיקום עבודה' , 'סה״כ משמרות', 'משמרות שהושלמו', 
                    'סה״כ שעות', 'ממוצע שעות למשמרת', 'תאריך ראשון', 'תאריך אחרון'
                ])
                
                # הצגת סיכום כללי
                total_hours_all = df['סה״כ שעות'].sum()
                total_shifts_all = df['סה״כ משמרות'].sum()
                active_employees = len(df)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("סה״כ שעות השבוע", f"{total_hours_all:.1f}")
                with col2:
                    st.metric("סה״כ משמרות", total_shifts_all)
                with col3:
                    st.metric("עובדים פעילים", active_employees)
                
                # הצגת הטבלה
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True
                )
                
                # גרף שעות עבודה
                if len(df) > 0:
                    st.subheader("📈 גרף שעות עבודה")
                    chart_data = df.set_index('מ.א')['סה״כ שעות']
                    st.bar_chart(chart_data)
            else:
                st.info("אין נתונים לשבוע הנוכחי")
                
        except Exception as e:
            st.error(f"שגיאה בטעינת נתוני השעות: {str(e)}")
    
    elif admin_tab == "היכן אני כעת - מעקב":
        st.subheader("👀 מעקב היכן אני כעת")
    
        try:
            # הצגת כל הדיווחים עם המרה מפורשת ל-TIMESTAMP
            all_reports = con.execute("""
                SELECT personal_id, current_location, on_shift,
                       strftime('%d/%m/%Y %H:%M', 
                                datetime(timestamp, '+3 hours')) as report_datetime
                FROM green_eyes 
                ORDER BY timestamp DESC
            """).fetchall()


            




            
            # יצירת רשימת מי דיווח
            reported_ids = [report[0] for report in all_reports] if all_reports else []
        
            # # מי לא דיווח
            # not_reported = []
            # for pid, name in personal_data.items():
            #     if pid not in reported_ids:
            #         not_reported.append((pid, name))
            reported_count = len(set(reported_ids))
            not_reported = 95 - reported_count

        
            # הצגת סיכום
            col1, col2 = st.columns(2)
            with col1:
                st.metric("דיווחו על מיקום", (reported_count))
            with col2:
                st.metric("לא דיווחו", not_reported)
        
            # טבלת הדיווחים
            if all_reports:
                st.subheader("📊 כל הדיווחים")
                df_reports = pd.DataFrame(all_reports, columns=[
                'מ.א', 'מיקום נוכחי', 'האם במשמרת' , 'תאריך ושעת עדכון'
            ])
                st.dataframe(df_reports, use_container_width=True, hide_index=True)
         
            # # מי לא דיווח
            # if not_reported:
            #     st.subheader("⚠️ לא דיווחו על מיקום")
            #     for pid in not_reported:
            #         st.warning(f" (מ.א. {pid}) - לא דיווח על מיקום")
            # else:
            #     st.success("✅ כולם דיווחו על מיקום!")
            
        except Exception as e:
            st.error(f"שגיאה בטעינת נתוני היכן אני כעת: {str(e)}")
    elif admin_tab == "ניהול נתונים":
        st.subheader("🗂️ ניהול נתונים")
        
        st.warning("⚠️ פעולות אלו יימחקו נתונים לצמיתות!")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🗑️ איפוס נתוני היכן אני כעת", type="secondary"):
                if st.session_state.get('confirm_green_eyes_reset', False):
                    try:
                        con.execute("DELETE FROM green_eyes")
                        st.success("✅ נתוני היכן אני כעת נמחקו בהצלחה!")
                        st.session_state.confirm_green_eyes_reset = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ שגיאה במחיקת הנתונים: {str(e)}")
                else:
                    st.session_state.confirm_green_eyes_reset = True
                    st.warning("לחץ שוב לאישור המחיקה")
        
        with col2:
            if st.button("🗑️ איפוס נתוני דיווחי משמרות", type="secondary"):
                if st.session_state.get('confirm_reports_reset', False):
                    try:
                        con.execute("DELETE FROM reports")
                        st.success("✅ נתוני דיווחי המשמרות נמחקו בהצלחה!")
                        st.session_state.confirm_reports_reset = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ שגיאה במחיקת הנתונים: {str(e)}")
                else:
                    st.session_state.confirm_reports_reset = True
                    st.warning("לחץ שוב לאישור המחיקה")
        
        # איפוס סטטוס האישורים
        if st.button("❌ ביטול", type="primary"):
            st.session_state.confirm_green_eyes_reset = False
            st.session_state.confirm_reports_reset = False
            st.rerun()
    
    # כפתור יציאה
    if st.button("🚪 יציאה מדף ניהול"):
        st.session_state.access_granted = False
        st.rerun()

# עמוד דיווח משמרת הרגיל
else:
    # כותרת ראשית
    st.title("""📝 דוח משמרת""")
    st.markdown("---")

    # בחירת סוג דיווח
    report_type = st.selectbox(
        "בחר סוג דיווח:", 
        ["entry", "exit"], 
        format_func=lambda x: "🟢 כניסה למשמרת" if x == "entry" else "🔴 יציאה ממשמרת"
    )
    

    # טופס הדיווח
    with st.form("report_form", clear_on_submit=True):
        st.subheader(f"{'כניסה למשמרת' if report_type == 'entry' else 'יציאה ממשמרת'}")
        
        # שדות משותפים
        col1, col2 = st.columns(2)
        
        with col1:
            personal_id = st.text_input("מ.א - ארבע ספרות אחרונות*", placeholder="הכנס מספר", max_chars=4 )


        
        with col2:
            rahal = st.selectbox("""רח"ל""", ["ויסאם אסד" , "יובל שטפל" , "ירדן קרן", "דניאל הנו" , "נזיה הנו" , "אסף גבור" , "נתי שיינפלד","כנרת המבורגר","ישי ספיבק"])
        
        # שדות ספציפיים לסוג דיווח
        if report_type == "entry":
            col3, col4 = st.columns(2)
            
            with col3:
                work_location = st.selectbox("מיקום עבודה:", ["גלילות", "משגב","צניפים", "בית", "אחר"])
                if work_location == "אחר":
                    work_location = st.text_input("פרט מיקום:", placeholder="הכנס מיקום")
            
            with col4:
                replacing_who = st.text_input("? מי חפף אותי בכניסה למשמרת:",placeholder="הכנס שם")
    

            current_date = datetime.now(ZoneInfo("Asia/Jerusalem")).date()
            current_time = datetime.now(ZoneInfo("Asia/Jerusalem")).time().replace(microsecond=0)

            
            col5, col6 = st.columns(2)
            with col5:
                st.text_input("תאריך תחילת משמרת:", value=current_date.strftime('%d/%m/%Y'), disabled=True)
                start_date = current_date
            with col6:
                st.text_input("שעת תחילת משמרת:", value=current_time.strftime('%H:%M'), disabled=True)
                start_time = current_time

            # משתנים ריקים ליציאה
            replacement_person = None
            reports_count = None
            end_date = None
            end_time = None
            special_notes = None

        else:  # exit
            col3, col4 = st.columns(2)
            
            with col3:
                replacement_person  = st.text_input("? מי חפף אותי בכניסה למשמרת:",placeholder="הכנס שם")

            
            with col4:
                reports_count = st.number_input(" מספר דיווחים שהעלית במשמרת -נתון זה לא בוחן את עבודתך *:", min_value=0, step=1, value=0)
            
            # תאריך ושעה נוכחיים (לא ניתנים לשינוי)
            current_date = datetime.now(ZoneInfo("Asia/Jerusalem")).date()
            current_time = datetime.now(ZoneInfo("Asia/Jerusalem")).time().replace(microsecond=0)
            
            col5, col6 = st.columns(2)
            with col5:
                st.text_input("תאריך סיום משמרת:", value=current_date.strftime('%d/%m/%Y'), disabled=True)
                end_date = current_date
            with col6:
                st.text_input("שעת סיום משמרת:", value=current_time.strftime('%H:%M'), disabled=True)
                end_time = current_time
            
            special_notes = st.text_area("הערות מיוחדות:", placeholder="הערות או דברים חשובים...")

            # משתנים ריקים לכניסה
            work_location = None
            replacing_who = None
            start_date = None
            start_time = None

        # כפתור שליחה
        submitted = st.form_submit_button("📤 שלח דיווח", type="primary")

        if submitted:
            # בדיקת שדות חובה
            required_fields_missing = []
            if not personal_id:
                required_fields_missing.append("מספר אישי")
            if not rahal:
                required_fields_missing.append("רח'ל")
            if report_type == "exit" and reports_count is None:
                required_fields_missing.append("מספר דיווחים")
            if required_fields_missing:
                st.error(f"❌ נא למלא את השדות הנדרשים: {', '.join(required_fields_missing)}")
            if personal_id and not personal_id.isdigit():
             st.error("הכנס רק ספרות.")    
            else:
                try:
                    timestamp = datetime.now().isoformat()
                    
                    con.execute("""
                        INSERT INTO reports (
                            report_type, personal_id, rahal,
                            work_location, replacing_who, replacement_person,
                            reports_count, special_notes, timestamp,
                            start_date, start_time, end_date, end_time
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        report_type, 
                        personal_id,
                        rahal,
                        work_location,
                        replacing_who,
                        replacement_person,
                        reports_count,
                        special_notes,
                        timestamp,
                        str(start_date) if start_date else None,
                        str(start_time) if start_time else None,
                        str(end_date) if end_date else None,
                        str(end_time) if end_time else None
                    ))
                    
                    st.success("✅ הדיווח נשלח בהצלחה!")
                    st.balloons()
                    
                except Exception as e:
                    st.error(f"❌ שגיאה בשמירת הדיווח: {str(e)}")

    # קו הפרדה
    st.markdown("---")

with st.expander("ℹ️ הוראות שימוש"):
        st.markdown("""
        **איך להשתמש במערכת:**
        
        1. **בחר סוג דיווח** - כניסה או יציאה ממשמרת
        2. **מלא את הפרטים הנדרשים** - שדות עם כוכבית (*) הם חובה
        3. **ביציאה - ציין כמות הדיווחים שהעלית** - זה נתון חשוב למעקב
        4. **התאריך והשעה נקבעים אוטומטית** - לא ניתן לשינוי
        5. **לחץ על 'שלח דיווח'** לשמירה במערכת
        
        **הערות חשובות:**
        - ✅ וודא שמספר האישי נכון
        - ✅ במשמרת יציאה - חובה לציין כמות הדיווחים שהעלית
        - ✅ התאריך והשעה נקבעים אוטומטית למועד הדיווח
        - ✅ כתוב הערות מיוחדות במידת הצורך
        - ✅ המערכת תשמור את הדיווח באופן אוטומטי
        - 🔐 לגישה לדיווח שעות השתמש בתפריט הצד
        """)

# פוטר
st.markdown("---")
st.markdown("*מערכת דיווח משמרות - גרסה 2.2*")
