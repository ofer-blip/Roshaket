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

function createJsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
