# -*- coding: utf-8 -*-
import sys, re, subprocess

index_path = r'C:\Users\User\Desktop\D-Dialog\roshaket\public\index.html'
sw_path = r'C:\Users\User\Desktop\D-Dialog\roshaket\public\sw.js'

with open(index_path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Prepare week 4 Mor summary
w4_mor_obj = '''    {
        id: 'sum_w4_mor_1',
        weekNum: 4,
        courseKey: 'mor',
        dateStr: '08.11.2026',
        createdAt: '2026-11-08T20:00:00+02:00',
        tabLabel: 'סיכום מפגש + 4 דורות הערכה',
        title: 'ארבעה דורות של הערכה (גובה ולינקולן) ושבוע יישור קו',
        teaser: 'עלה סיכום מפגש 4 של ד"ר ישי מור: אין מטלות חדשות השבוע! דגשים ליישור קו במודל הלוגי, חובת יומן למידה, ו-4 דורות ההערכה.',
        rules: [
            '<strong>אין מטלות חדשות לשבוע זה (שבוע יישור קו והשלמת פערים):</strong> ישי הודיע חד-משמעית כי לא הועלתה מטלה חדשה השבוע. המטרה היא להגיע למפגש הבא בקמפוס (15.11) כשחזון, תיאוריית שינוי ומודל לוגי שלמים ומוגשים.',
            '<strong>סדר עדיפויות בהגשות במודל:</strong> מטלה 4 (בניית מודל לוגי) ומטלה 2 (חזון ותיאוריית שינוי) הן הלב המהותי של הקורס. מטלה 3 (הערכה עצמית עם בוט בינה מלאכותית) נפתחה בטעות בשלב מוקדם מדי – מי שלא עשה אינו מחויב כעת.',
            '<strong>הגשה כפולה במודל (פורום + מטלה):</strong> עד שיימצא פתרון טכני לאיחוד, יש להעלות את קובץ ה-PDF של המודל הלוגי גם בפורום (למשוב עמיתים והשראה הדדית) וגם בתיבת המטלה (לבדיקה אישית ומשוב מישי).',
            '<strong>חובת יומן הלמידה (10% מהציון):</strong> להקדיש בין 5 ל-50 דקות בשבוע לרשומה אישית בבלוג הקורס (שיתוף על החוויה, מה עבד, מה תסכל, או תהליך קבלת ההחלטות במיזם).'
        ],
        concepts: [
            '<strong>ארבעת דורות ההערכה של גובה ולינקולן (Guba & Lincoln, 1989):</strong><br>• <strong>דור 1 – מדידה (Measurement):</strong> מבחנים וציונים כמותיים בלבד (סוף המאה ה-19 עד שנות ה-30).<br>• <strong>דור 2 – תיאור (Description):</strong> תיאור מילולי ודפוסי התנהגות.<br>• <strong>דור 3 – שיפוט ערכי (Judgment):</strong> קביעה האם התוצאה טובה או רעה מול קריטריונים וסטנדרטים.<br>• <strong>דור 4 – משא ומתן ודיאלוג (Responsive Constructivist):</strong> ההערכה אינה אמת אבסולוטית במספרים, אלא תהליך דיאלקטי-פרשני הנבנה מתוך שיח, הקשבה ומשא ומתן בין כל בעלי העניין סביב טענות, דאגות וסוגיות.',
            '<strong>שיחת הקורס כ"מקרה בוחן חי" להערכה דיאלוגית:</strong> הדיון הכיתתי הפתוח על העומס, הבלבול והדשבורד שישי הציג, המחיש בפועל כיצד שיתוף נתוני הערכה מייצר תיאום ציפיות, למידה הדדית וקבלת החלטות משותפת.',
            '<strong>כשל העלות השקועה (Sunk Cost Fallacy) במיזמים:</strong> האומץ לשנות כיוון במיזם (כפי שעופר שיתף בכיתה) כאשר מזהים שההנחות המקוריות אינן משרתות את היעד, במקום להמשיך להשקיע בנתיב שגוי רק בגלל הזמן והמשאבים שכבר הושקעו בו בעבר.',
            '<strong>דיאלקטיקה בין נתונים קשים לדיאלוג:</strong> שילוב בין מדדים כמותיים (אחוזי הגשה, מספר משתתפים) לבין הפרשנות והמשמעות הניתנת להם בהקשר החינוכי בשטח.'
        ],
        steps: [
            {
                num: 'שלב 1',
                title: 'בדיקת יומן הלמידה בבלוג הקורס',
                question: 'האם פרסמתי רשומות עד כה?',
                desc: 'כניסה לבלוג הקורס במודל ופרסום רשומה קצרה (5–50 דקות) על החוויה השבועית, האתגרים או התובנות מתהליך גיבוש המיזם.',
                example: 'דוגמה: כתיבה על ההתלבטויות בבחירת קהל היעד או על השינוי שביצעתם בכיוון המיזם.'
            },
            {
                num: 'שלב 2',
                title: 'דיוק מסמך החזון ותיאוריית השינוי (מטלה 2)',
                question: 'האם הגדרתי סיבה ותוצאה ברורה?',
                desc: 'בדיקה שמסמך החזון (1–2 עמודים) כולל תיאוריית שינוי ברורה ("אם נעשה X אז יקרה Y וזה יוביל ל-Z").',
                example: 'דוגמה: חיבור בין הפעילות החינוכית המוצעת לבין השינוי המצופה בתלמידים/בצוות.'
            },
            {
                num: 'שלב 3',
                title: 'ליטוש שקף 5 שלבי המודל הלוגי (מטלה 4)',
                question: 'האם חמשת השלבים מפורקים ומדויקים?',
                desc: 'מילוי שקף המודל הלוגי: משאבים (Inputs) ⬅ פעילויות (Activities) ⬅ תפוקות (Outputs) ⬅ תוצאות (Outcomes) ⬅ השפעה/חזון (Impact).',
                example: 'היעזרו בשליף האקורדיונים של שבוע 3 בראשקט להעתקת שלבים ותבניות.'
            },
            {
                num: 'שלב 4',
                title: 'הגשה כפולה במודל עד 12.11',
                question: 'האם הקובץ הועלה לשני המקומות?',
                desc: 'העלאת קובץ ה-PDF של המודל הלוגי גם בפורום "מודלים לוגיים" וגם בתיבת המטלה הרשמית במודל.',
                example: 'העלאה לפורום לשיתוף עמיתים + העלאה למטלה לקבלת משוב וציון אישי מישי.'
            },
            {
                num: 'שלב 5',
                title: 'החלפת משוב עמיתים לקראת המפגש בקמפוס',
                question: 'איזה פידבק קיבלתי ונתתי?',
                desc: 'עיון במודל לוגי של עמית/ה בפורום ומתן משוב ענייני, לקראת המפגש הפרונטלי במכללה ב-15.11.',
                example: 'הצבעה על פערים לוגיים בונה: "כיצד פעולה א\' מובילה ישירות לתוצאה ב\'?".'
            }
        ],
        template: `תבנית מוכנה: רשומת יומן למידה שבועי (לפרסום בבלוג הקורס במודל)
שבוע: 4 | תאריך: 08.11.2026 | שם: [הזן כאן]

📝 נקודת מוצא והתבוננות על השבוע:
• מה העסיק אותי השבוע במיזם ובקורס?
[השלם כאן]

💡 תובנה מרכזית משיעור "ארבעת דורות ההערכה":
• איזה דור הערכה הכי מתאים למיזם שלי בשלב זה (מדידה כמותית מול דיאלוג עם השותפים)?
[השלם כאן]

🧗 אתגר או התלבטות שעלו לי:
• איפה הרגשתי קושי, בלבול או צורך בדיוק מול המודל הלוגי?
[השלם כאן]

🎯 צעד ממוקד לקראת המפגש בקמפוס (15.11):
• מה היעד שלי להשלים עד יום ראשון הקרוב?
[השלם כאן]`
    },'''

# Insert at beginning of DEFAULT_LESSON_SUMMARIES
target_start = 'const DEFAULT_LESSON_SUMMARIES = [\n'
if target_start in text:
    text = text.replace(target_start, target_start + w4_mor_obj + '\n', 1)
    print("Inserted sum_w4_mor_1 at top of DEFAULT_LESSON_SUMMARIES!")
else:
    print("Warning: DEFAULT_LESSON_SUMMARIES start not found!")

# 2. Add localStorage cleanup for legacy rough drafts in loadAllLessonSummaries
clean_code = '''function loadAllLessonSummaries() {
    // Clean up any legacy rough draft summaries created before v68 so only pristine verified summaries are shown
    if (!localStorage.getItem('roshaket_cleaned_v68_summaries')) {
        localStorage.removeItem('roshaket_lesson_summaries_v1');
        localStorage.setItem('roshaket_cleaned_v68_summaries', 'true');
    }

    let customList = [];'''

old_load = '''function loadAllLessonSummaries() {
    let customList = [];'''

if old_load in text:
    text = text.replace(old_load, clean_code, 1)
    print("Added localStorage cleanup to loadAllLessonSummaries!")
else:
    print("Warning: old_load not found directly!")

# 3. Write back to index.html
with open(index_path, 'w', encoding='utf-8') as f:
    f.write(text)

# 4. Check JS syntax
scripts = re.findall(r'<script(?:\s+[^>]*)?>(.*?)</script>', text, re.DOTALL)
with open('temp_check.js', 'w', encoding='utf-8') as sf:
    sf.write(scripts[3])

res = subprocess.run(['node', '--check', 'temp_check.js'], capture_output=True, text=True)
print("Node check returncode:", res.returncode)
if res.returncode != 0:
    print("Error in JS syntax:", res.stderr)
    sys.exit(1)
else:
    print("JS syntax is 100% valid!")

# 5. Bump sw.js to roshaket-v68
with open(sw_path, 'r', encoding='utf-8') as f:
    sw_text = f.read()
sw_text = sw_text.replace('roshaket-v67', 'roshaket-v68')
with open(sw_path, 'w', encoding='utf-8') as f:
    f.write(sw_text)
print("Bumped sw.js to roshaket-v68!")

import os
if os.path.exists('temp_check.js'):
    os.remove('temp_check.js')
