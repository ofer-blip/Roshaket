function doGet(e) {
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let sheet = ss.getActiveSheet();
    
    // בניית כותרות אוטומטית בפעם הראשונה
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(['תאריך רישום', 'שם מלא', 'כתובת מייל', 'סטטוס', 'הערות']);
      sheet.getRange(1, 1, 1, 5).setFontWeight('bold').setBackground('#E8EAED');
      sheet.setFrozenRows(1);
    }
    
    const params = e.parameter || {};
    const action = params.action || 'check';
    const email = (params.email || '').toLowerCase().trim();
    const name = (params.name || '').trim();
    const consent = (params.consent || '').toString().toLowerCase();
    const isConsentApproved = (consent === 'true' || consent === 'approved' || consent === '1');
    
    // בדיקת סטטוס משתמש
    // רישום אירוע פעילות שקט בטאב יומן פעילות
    if (action === 'log_event') {
      let logSheet = ss.getSheetByName('יומן פעילות');
      if (!logSheet) {
        logSheet = ss.insertSheet('יומן פעילות');
        logSheet.appendRow(['תאריך ושעה', 'שם', 'אימייל', 'אירוע', 'פירוט', 'פלטפורמה']);
        logSheet.getRange(1, 1, 1, 6).setFontWeight('bold').setBackground('#E0E7FF');
        logSheet.setFrozenRows(1);
      }
      const eventName = params.event || '';
      const eventDetails = params.details || '';
      const platform = params.platform || 'Web';
      const nowStr = Utilities.formatDate(new Date(), 'Asia/Jerusalem', 'yyyy-MM-dd HH:mm:ss');
      logSheet.appendRow([nowStr, name || 'אורח/ת', email || 'ללא מייל', eventName, eventDetails, platform]);
      return createJsonResponse({ status: 'logged' });
    }

    // שליחת פידבק או דיווח תקלה ממשתמשים
    if (action === 'submit_feedback') {
      let fbSheet = ss.getSheetByName('פידבק ותקלות');
      if (!fbSheet) {
        fbSheet = ss.insertSheet('פידבק ותקלות');
        fbSheet.appendRow(['תאריך ושעה', 'שם', 'אימייל', 'סוג', 'תיאור', 'מכשיר וגרסה', 'סטטוס']);
        fbSheet.getRange(1, 1, 1, 7).setFontWeight('bold').setBackground('#FCE7F3');
        fbSheet.setFrozenRows(1);
      }
      const fbType = (params.type || 'פידבק').trim();
      const fbMsg = (params.message || '').trim();
      const fbMeta = (params.meta || '').trim();
      const nowStr = Utilities.formatDate(new Date(), 'Asia/Jerusalem', 'yyyy-MM-dd HH:mm:ss');
      fbSheet.appendRow([nowStr, name || 'אורח/ת', email || 'ללא מייל', fbType, fbMsg, fbMeta, 'חדש']);
      return createJsonResponse({ status: 'ok', savedAt: nowStr });
    }

    // שליפת נתוני בקרה למנהל (עופר)
    if (action === 'admin_insights') {
      const admins = ['saritofer.k@gmail.com', 'ofer@ddialog.co.il'];
      if (admins.indexOf(email) === -1) {
        return createJsonResponse({ status: 'unauthorized' });
      }
      const logSheet = ss.getSheetByName('יומן פעילות');
      const fbSheet = ss.getSheetByName('פידבק ותקלות');
      let videoPlays = 0, videoCompletes = 0, podcastPlays = 0, guidePlays = 0, errorCount = 0;
      const userMap = {};
      const recentEvents = [];

      if (logSheet && logSheet.getLastRow() > 1) {
        const totalRows = logSheet.getLastRow();
        const startRow = Math.max(2, totalRows - 299);
        const rows = logSheet.getRange(startRow, 1, totalRows - startRow + 1, 6).getValues();
        for (let i = rows.length - 1; i >= 0; i--) {
          const r = rows[i];
          const tStr = String(r[0] || '');
          const uName = String(r[1] || 'אורח/ת');
          const uEmail = String(r[2] || '').toLowerCase().trim();
          const ev = String(r[3] || '');
          const det = String(r[4] || '');
          const plat = String(r[5] || '');

          if (ev === 'lesson_video_play') videoPlays++;
          else if (ev === 'lesson_video_complete') videoCompletes++;
          else if (ev === 'podcast_play') podcastPlays++;
          else if (ev === 'guide_video_play') guidePlays++;
          else if (ev === 'client_error') errorCount++;

          const uKey = (uEmail && uEmail !== 'ללא מייל') ? uEmail : uName;
          if (!userMap[uKey]) {
            userMap[uKey] = { name: uName, email: uEmail, lastSeen: tStr, platform: plat, eventCount: 0 };
          }
          userMap[uKey].eventCount++;

          if (recentEvents.length < 40) {
            recentEvents.push({ time: tStr, name: uName, email: uEmail, event: ev, details: det, platform: plat });
          }
        }
      }

      const feedbackList = [];
      if (fbSheet && fbSheet.getLastRow() > 1) {
        const fbTotal = fbSheet.getLastRow();
        const fbStart = Math.max(2, fbTotal - 29);
        const fbRows = fbSheet.getRange(fbStart, 1, fbTotal - fbStart + 1, 7).getValues();
        for (let i = fbRows.length - 1; i >= 0; i--) {
          const f = fbRows[i];
          feedbackList.push({
            time: String(f[0] || ''),
            name: String(f[1] || ''),
            email: String(f[2] || ''),
            type: String(f[3] || ''),
            message: String(f[4] || ''),
            meta: String(f[5] || ''),
            status: String(f[6] || '')
          });
        }
      }

      const recentUsers = Object.keys(userMap).map(function(k) { return userMap[k]; }).slice(0, 30);
      return createJsonResponse({
        status: 'ok',
        summary: {
          uniqueUsersCount: recentUsers.length,
          videoPlays: videoPlays,
          videoCompletes: videoCompletes,
          podcastPlays: podcastPlays,
          guidePlays: guidePlays,
          errorCount: errorCount,
          feedbackCount: feedbackList.length
        },
        recentUsers: recentUsers,
        recentEvents: recentEvents,
        feedbackList: feedbackList
      });
    }

    // שליפת מצב משתמשת לסנכרון בין מכשירים
    if (action === 'get_state') {
      if (!email) return createJsonResponse({ status: 'not_found' });
      let stateSheet = ss.getSheetByName('מצב משתמשים');
      if (!stateSheet) return createJsonResponse({ status: 'not_found' });
      const data = stateSheet.getDataRange().getValues();
      for (let i = 1; i < data.length; i++) {
        const rowEmail = (data[i][0] || '').toString().toLowerCase().trim();
        if (rowEmail === email) {
          let doneTasks = [];
          let userNotes = {};
          try { doneTasks = JSON.parse(data[i][2] || '[]'); } catch (err) {}
          try { userNotes = JSON.parse(data[i][3] || '{}'); } catch (err) {}
          return createJsonResponse({
            status: 'found',
            updatedAt: data[i][1] || '',
            doneTasks: Array.isArray(doneTasks) ? doneTasks : [],
            userNotes: (userNotes && typeof userNotes === 'object') ? userNotes : {},
            userName: data[i][4] || ''
          });
        }
      }
      return createJsonResponse({ status: 'not_found' });
    }

    if (action === 'check') {
      const data = sheet.getDataRange().getValues();
      for (let i = 1; i < data.length; i++) {
        const rowEmail = (data[i][2] || '').toString().toLowerCase().trim();
        if (rowEmail === email) {
          return createJsonResponse({
            status: 'found',
            approvalStatus: data[i][3] || 'ממתין לאישור',
            name: data[i][1]
          });
        }
      }
      return createJsonResponse({ status: 'not_found' });
    }
    
    // רישום בקשה חדשה / אישור הסכמה
    if (action === 'register') {
      if (!email) {
        return createJsonResponse({ error: 'Missing email' });
      }
      
      const data = sheet.getDataRange().getValues();
      let existingRow = -1;
      for (let i = 1; i < data.length; i++) {
        const rowEmail = (data[i][2] || '').toString().toLowerCase().trim();
        if (rowEmail === email) {
          existingRow = i + 1;
          break;
        }
      }
      
      const nowStr = Utilities.formatDate(new Date(), 'Asia/Jerusalem', 'yyyy-MM-dd HH:mm');
      
      // אם המשתמש כבר קיים בגיליון
      if (existingRow > 0) {
        const currentStatus = sheet.getRange(existingRow, 4).getValue() || 'ממתין לאישור';
        
        // אם המשתמש מאשר הסכמה והסטטוס שלו טרם אושר - מאשרים אותו מיד!
        if (isConsentApproved && currentStatus !== 'מאושר') {
          sheet.getRange(existingRow, 4).setValue('מאושר');
          sheet.getRange(existingRow, 5).setValue('אושר ונרשם עם הסכמת מייל - ' + nowStr);
          return createJsonResponse({ 
            status: 'registered', 
            approvalStatus: 'מאושר',
            message: 'ההרשמה אושרה בהצלחה'
          });
        }
        
        return createJsonResponse({ 
          status: 'exists', 
          approvalStatus: currentStatus,
          message: 'משתמש כבר רשום במערכת'
        });
      } else {
        // משתמש חדש: אם נתן הסכמה למאגר המיילים מקבל סטטוס "מאושר" ישירות
        const assignedStatus = isConsentApproved ? 'מאושר' : 'ממתין לאישור';
        const note = isConsentApproved ? 'אושר ונרשם עם הסכמת מייל' : 'הוגש דרך ראשקט';
        
        sheet.appendRow([nowStr, name, email, assignedStatus, note]);
        const newRow = sheet.getLastRow();
        
        // יצירת תפריט נפתח (Dropdown) צבעוני אוטומטית לעמודת הסטטוס
        const rule = SpreadsheetApp.newDataValidation()
          .requireValueInList(['מאושר', 'ממתין לאישור', 'נדחה'], true)
          .build();
        sheet.getRange(newRow, 4).setDataValidation(rule);
        
        // שליחת התראה מיידית בדוא"ל לעופר
        let mailSent = false;
        let mailErrorMsg = null;
        try {
          MailApp.sendEmail({
            to: 'saritofer.k@gmail.com',
            subject: (isConsentApproved ? '🎉 סטודנט/ית חדש/ה הצטרפ/ה לראשקט: ' : '🎓 בקשת הצטרפות חדשה לראשקט: ') + (name || email),
            htmlBody: `
              <div dir="rtl" style="font-family: Arial, sans-serif; text-align: right; color: #1e293b; max-width: 500px; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px;">
                <h2 style="color: #4338ca; margin-top: 0;">${isConsentApproved ? '🎉 סטודנט/ית חדש/ה הצטרפ/ה לראשקט!' : '🎓 בקשת הצטרפות חדשה לראשקט!'}</h2>
                <p style="font-size: 15px;">היי עופר, התקבלה הצטרפות חדשה לקורס:</p>
                <div style="background: #f8fafc; border-radius: 8px; padding: 12px 16px; margin: 15px 0;">
                  <p style="margin: 4px 0;"><strong>👤 שם מלא:</strong> ${name || 'לא צוין'}</p>
                  <p style="margin: 4px 0;"><strong>📧 כתובת מייל:</strong> <a href="mailto:${email}">${email}</a></p>
                  <p style="margin: 4px 0;"><strong>⏰ תאריך ושעה:</strong> ${nowStr}</p>
                  <p style="margin: 4px 0;"><strong>🔒 הסכמה למאגר:</strong> ${isConsentApproved ? 'אושרה ע"י המשתמש/ת ✅' : 'טרם אושרה'}</p>
                  <p style="margin: 4px 0;"><strong>📌 סטטוס נוכחי:</strong> <span style="background: ${isConsentApproved ? '#dcfce7' : '#fef3c7'}; color: ${isConsentApproved ? '#166534' : '#b45309'}; padding: 2px 8px; border-radius: 4px; font-weight: bold;">${assignedStatus}</span></p>
                </div>
                <p style="font-size: 14px; color: #475569;">
                  לצפייה ברשימת הסטודנטים או שינוי הרשאות:
                </p>
                <a href="https://docs.google.com/spreadsheets/d/13IBGegk35Hj7RNpEcEzBahPYFRl97G06UjT1RFIxZdE/edit" 
                   style="display: inline-block; background: #4338ca; color: #ffffff; padding: 10px 18px; border-radius: 8px; text-decoration: none; font-weight: bold; margin-top: 8px;">
                  📊 פתח את גיליון המשתמשים
                </a>
                <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0 10px 0;">
                <p style="color: #94a3b8; font-size: 11px; margin: 0;">הודעה אוטומטית ממערכת ראשקט • D-Dialog</p>
              </div>
            `
          });
          mailSent = true;
        } catch (mailErr) {
          mailErrorMsg = mailErr.toString();
          console.warn('Mail notification warning:', mailErr);
        }
        
        return createJsonResponse({ 
          status: 'registered', 
          approvalStatus: assignedStatus,
          mailSent: mailSent,
          mailError: mailErrorMsg,
          message: 'הבקשה נקלטה בהצלחה'
        });
      }
    }
    
    return createJsonResponse({ error: 'Unknown action' });
  } catch (err) {
    return createJsonResponse({ error: err.toString() });
  }
}

function sendTestNotification() {
  MailApp.sendEmail({
    to: 'saritofer.k@gmail.com',
    subject: '🎓 בדיקת אישור הרשאות מייל לראשקט',
    htmlBody: '<div dir="rtl"><h2>בדיקת אישור הרשאות!</h2><p>אם המייל הזה התקבל, הרשאת השליחה ב-Google Apps Script פעילה ומאושרת בהצלחה.</p></div>'
  });
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(8000);
    const body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    if (body.action !== 'save_state') {
      return createJsonResponse({ error: 'Unknown action' });
    }
    const email = (body.email || '').toLowerCase().trim();
    if (!email) {
      return createJsonResponse({ error: 'Missing email' });
    }

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let stateSheet = ss.getSheetByName('מצב משתמשים');
    if (!stateSheet) {
      stateSheet = ss.insertSheet('מצב משתמשים');
      stateSheet.appendRow(['אימייל', 'עודכן לאחרונה', 'משימות שבוצעו', 'הערות אישיות', 'שם תצוגה']);
      stateSheet.getRange(1, 1, 1, 5).setFontWeight('bold').setBackground('#E0E7FF');
      stateSheet.setFrozenRows(1);
    }

    const nowStr = Utilities.formatDate(new Date(), 'Asia/Jerusalem', 'yyyy-MM-dd HH:mm:ss');
    const tasksJson = JSON.stringify(Array.isArray(body.doneTasks) ? body.doneTasks : []);
    const notesJson = JSON.stringify((body.userNotes && typeof body.userNotes === 'object') ? body.userNotes : {});
    const userName = (body.userName || '').toString().trim();

    const data = stateSheet.getDataRange().getValues();
    let existingRow = -1;
    for (let i = 1; i < data.length; i++) {
      const rowEmail = (data[i][0] || '').toString().toLowerCase().trim();
      if (rowEmail === email) {
        existingRow = i + 1;
        break;
      }
    }

    if (existingRow > 0) {
      stateSheet.getRange(existingRow, 2, 1, 4).setValues([[nowStr, tasksJson, notesJson, userName]]);
    } else {
      stateSheet.appendRow([email, nowStr, tasksJson, notesJson, userName]);
    }

    return createJsonResponse({ status: 'saved', updatedAt: nowStr });
  } catch (err) {
    return createJsonResponse({ error: err.toString() });
  } finally {
    try { lock.releaseLock(); } catch (e2) {}
  }
}

function createJsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
