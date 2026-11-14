import sys
import re

sys.stdout.reconfigure(encoding='utf-8')

html_path = r'C:\Users\User\Desktop\D-Dialog\roshaket\public\index.html'
with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. In dropdown options menu: remove Alma studio item
old_menu_item = '<button class="dropdown-item" onclick="openAlmaStudioModal(); closeOptionsMenu();">🎙️ סטודיו תמלולים וסיכומים (אלמה)</button>'
if old_menu_item in content:
    content = content.replace(old_menu_item, '', 1)
    print('1. Removed Alma studio item from options menu')

# 2. In renderTaskCardHtml: disable adminMode so "+ סיכום" or "העלה תמלול אלמה" never renders
old_admin_card_code = '''    const adminMode = (typeof isOferAdmin === 'function') && isOferAdmin();

    let summaryActionRowHtml = '';
    if (isMainCourseCard && (summariesForTask.length > 0 || adminMode)) {
        if (summariesForTask.length > 0) {
            const btnLabel = summariesForTask.length > 1
                ? `סיכומי שיעור ועזרים (${summariesForTask.length})`
                : `סיכום שיעור + שליף לתרגיל`;
            summaryActionRowHtml = `
                <div class="task-summary-action-row">
                    <button type="button" class="lesson-summary-btn" onclick="event.stopPropagation(); openLessonSummaryModal(${taskWeekNum}, '${t.courseKey}')">
                        <span>✨</span>
                        <span>${btnLabel}</span>
                        <span class="lesson-summary-count-badge">${summariesForTask.length > 1 ? summariesForTask.length + ' סיכומים' : 'פתח חלונית עבודה'} ↗</span>
                    </button>
                    ${adminMode ? `
                        <button type="button" class="btn-admin-add-summary-mini" onclick="event.stopPropagation(); openAlmaStudioModal(${taskWeekNum}, '${t.courseKey}', 'new')" title="הוסף סיכום נוסף לשיעור זה (מאלמה .txt)">
                            <span>🎙️</span>
                            <span>+ סיכום</span>
                        </button>
                    ` : ''}
                </div>
            `;
        } else if (adminMode) {
            summaryActionRowHtml = `
                <div class="task-summary-action-row">
                    <button type="button" class="btn-admin-add-summary-mini" style="width: 100%; justify-content: center;" onclick="event.stopPropagation(); openAlmaStudioModal(${taskWeekNum}, '${t.courseKey}', 'new')">
                        <span>🎙️</span>
                        <span>העלה תמלול אלמה (.txt) / סיכום לשיעור זה</span>
                    </button>
                </div>
            `;
        }
    }'''

new_admin_card_code = '''    let summaryActionRowHtml = '';
    if (isMainCourseCard && summariesForTask.length > 0) {
        const btnLabel = summariesForTask.length > 1
            ? `סיכומי שיעור ועזרים (${summariesForTask.length})`
            : `סיכום שיעור + שליף לתרגיל`;
        summaryActionRowHtml = `
            <div class="task-summary-action-row">
                <button type="button" class="lesson-summary-btn" onclick="event.stopPropagation(); openLessonSummaryModal(${taskWeekNum}, '${t.courseKey}')">
                    <span>✨</span>
                    <span>${btnLabel}</span>
                    <span class="lesson-summary-count-badge">${summariesForTask.length > 1 ? summariesForTask.length + ' סיכומים' : 'פתח חלונית עבודה'} ↗</span>
                </button>
            </div>
        `;
    }'''

if old_admin_card_code in content:
    content = content.replace(old_admin_card_code, new_admin_card_code, 1)
    print('2. Removed transcription upload buttons from task cards')
else:
    print('2. Notice: old_admin_card_code not matched exactly')

# 3. In openLessonSummaryModal: if no summaries, show toast
old_summary_open_check = '''    const summaries = getSummariesForCourseWeek(activeWorkspaceWeek, activeWorkspaceCourse);
    if (summaries.length === 0) {
        if (isOferAdmin()) {
            openAlmaStudioModal(activeWorkspaceWeek, activeWorkspaceCourse, 'new');
        } else {
            showToast('טרם הועלה סיכום למפגש זה');
        }
        return;
    }'''

new_summary_open_check = '''    const summaries = getSummariesForCourseWeek(activeWorkspaceWeek, activeWorkspaceCourse);
    if (summaries.length === 0) {
        showToast('טרם הועלה סיכום למפגש זה');
        return;
    }'''

if old_summary_open_check in content:
    content = content.replace(old_summary_open_check, new_summary_open_check, 1)
    print('3. Cleaned summary open check')

# 4. Hide whatsNewAdminUploadBtn
old_whats_new_btn = 'id="whatsNewAdminUploadBtn" style="display: none;'
if old_whats_new_btn in content:
    print('4. whatsNewAdminUploadBtn already hidden with display: none')

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done cleaning transcription upload UI!')
