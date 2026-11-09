import sys
import re

sys.stdout.reconfigure(encoding='utf-8')

html_path = r'C:\Users\User\Desktop\D-Dialog\roshaket\public\index.html'
with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. CSS
pwa_css = """
/* --- PWA Install Features (v69) --- */
.btn-welcome-install {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    width: 100%;
    padding: 12px 18px;
    border-radius: 12px;
    font-size: 14.5px;
    font-weight: 700;
    cursor: pointer;
    border: 1.5px dashed #6366f1;
    background: #eef2ff;
    color: #4338ca;
    transition: all 0.2s ease;
    margin-top: 4px;
}
.btn-welcome-install:hover {
    background: #e0e7ff;
    transform: translateY(-1px);
}
.pwa-smart-install-banner {
    position: fixed;
    bottom: 18px;
    left: 50%;
    transform: translateX(-50%);
    width: calc(100% - 32px);
    max-width: 480px;
    background: #1e1b4b;
    color: #ffffff;
    padding: 12px 16px;
    border-radius: 16px;
    box-shadow: 0 12px 30px rgba(15, 23, 42, 0.25), 0 0 0 1px rgba(255, 255, 255, 0.1);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    z-index: 9999;
    animation: slideUpInstallBanner 0.3s ease-out;
}
@keyframes slideUpInstallBanner {
    from { transform: translate(-50%, 40px); opacity: 0; }
    to { transform: translate(-50%, 0); opacity: 1; }
}
.pwa-install-banner-content {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
}
.pwa-install-banner-icon {
    font-size: 26px;
    flex-shrink: 0;
}
.pwa-install-banner-text {
    min-width: 0;
}
.pwa-install-banner-title {
    font-weight: 800;
    font-size: 14px;
    color: #ffffff;
    line-height: 1.2;
}
.pwa-install-banner-sub {
    font-size: 11.5px;
    color: #cbd5e1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-top: 2px;
}
.pwa-install-banner-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
}
.btn-pwa-install-action {
    background: linear-gradient(135deg, #6366f1, #4f46e5);
    color: #ffffff;
    border: none;
    border-radius: 10px;
    padding: 8px 14px;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
    transition: all 0.2s;
    white-space: nowrap;
}
.btn-pwa-install-action:hover {
    background: #4338ca;
    transform: translateY(-1px);
}
.btn-pwa-install-dismiss {
    background: rgba(255, 255, 255, 0.15);
    color: #ffffff;
    border: none;
    border-radius: 50%;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 12px;
    transition: background 0.2s;
    flex-shrink: 0;
}
.btn-pwa-install-dismiss:hover {
    background: rgba(255, 255, 255, 0.25);
}
"""

if '.btn-welcome-install' not in content:
    content = content.replace('</style>', pwa_css + '\n</style>', 1)
    print('Added PWA CSS')

# 2. Welcome Gate Button
welcome_target = '''            <button class="btn-welcome-secondary" onclick="enterApp('demo')">
                <span>🚀</span>
                <span>כניסה להתנסות (מצב דמו)</span>
            </button>'''

welcome_replace = '''            <button class="btn-welcome-secondary" onclick="enterApp('demo')">
                <span>🚀</span>
                <span>כניסה להתנסות (מצב דמו)</span>
            </button>
            <button class="btn-welcome-install" id="welcomeInstallAppBtn" onclick="triggerPwaInstall()" style="display: none;">
                <span>📲</span>
                <span>התקן את ראשקט למסך הבית</span>
            </button>'''

if 'id="welcomeInstallAppBtn"' not in content:
    content = content.replace(welcome_target, welcome_replace, 1)
    print('Added Welcome Gate Install Button')

# 3. Options Menu Item
menu_target = '''                        <button class="dropdown-item" onclick="showWelcomeScreen(); closeOptionsMenu();">
                            <span>❓</span>
                            <span>הסבר ועזרה על ראשקט</span>
                        </button>'''

menu_replace = '''                        <button class="dropdown-item" onclick="showWelcomeScreen(); closeOptionsMenu();">
                            <span>❓</span>
                            <span>הסבר ועזרה על ראשקט</span>
                        </button>
                        <button class="dropdown-item" id="menuInstallAppItem" onclick="triggerPwaInstall(); closeOptionsMenu();" style="display: none; color: #4338ca; font-weight: 800; background: #eef2ff;">
                            <span>📲</span>
                            <span>התקן אפליקציה למכשיר</span>
                        </button>'''

if 'id="menuInstallAppItem"' not in content:
    content = content.replace(menu_target, menu_replace, 1)
    print('Added Options Menu Install Item')

# 4. Smart Install Banner & iOS Modal
banner_and_modal = '''
<!-- Smart PWA Floating Install Banner -->
<div class="pwa-smart-install-banner" id="pwaSmartInstallBanner" style="display: none;">
    <div class="pwa-install-banner-content">
        <div class="pwa-install-banner-icon">📲</div>
        <div class="pwa-install-banner-text">
            <div class="pwa-install-banner-title">התקן את "ראש שקט"</div>
            <div class="pwa-install-banner-sub">גישה מהירה ממסך הבית, עבודה חלקה ואופליין</div>
        </div>
    </div>
    <div class="pwa-install-banner-actions">
        <button class="btn-pwa-install-action" onclick="triggerPwaInstall()">התקן עכשיו</button>
        <button class="btn-pwa-install-dismiss" onclick="dismissSmartInstallBanner()" title="סגור">✕</button>
    </div>
</div>

<!-- iOS Install Modal Guide -->
<div class="modal-overlay" id="iosInstallModal" onclick="if(event.target === this) closeIosInstallModal()">
    <div class="modal-card" style="max-width: 400px; text-align: center; padding: 28px 22px;">
        <div style="font-size: 42px; margin-bottom: 12px;">🍎 📲</div>
        <h3 style="font-size: 19px; font-weight: 800; color: #1e1b4b; margin: 0 0 10px 0;">התקנה באייפון (iOS)</h3>
        <p style="font-size: 14px; color: #475569; line-height: 1.5; margin: 0 0 18px 0;">
            באייפון ההתקנה מתבצעת ישירות מדפדפן Safari:
        </p>
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px; text-align: right; font-size: 13.5px; line-height: 1.6; color: #1e293b; margin-bottom: 20px;">
            <div style="margin-bottom: 8px;">1. לחצי על כפתור השיתוף בתחתית המסך <strong>( <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2.5" style="vertical-align: middle;"><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><polyline points="16 6 12 2 8 6"/><line x1="12" y1="2" x2="12" y2="15"/></svg> Share )</strong></div>
            <div>2. גללי מעט מטה ולחצי על <strong>"הוסף למסך הבית" (Add to Home Screen)</strong> 📲</div>
        </div>
        <button class="btn-welcome-primary" onclick="closeIosInstallModal()" style="width: 100%;">
            <span>הבנתי, תודה!</span>
            <span>👍</span>
        </button>
    </div>
</div>
'''

if 'id="pwaSmartInstallBanner"' not in content:
    content = content.replace('</body>', banner_and_modal + '\n</body>', 1)
    print('Added Banner & iOS Modal')

# 5. JavaScript Logic
pwa_js = '''
// ==========================================
// PWA INSTALLATION ENGINE (Chrome/Android + iOS) - v69
// ==========================================
let deferredInstallPrompt = null;

function isRunningStandalone() {
    return window.matchMedia('(display-mode: standalone)').matches || 
           window.navigator.standalone === true ||
           (typeof document !== 'undefined' && document.referrer && document.referrer.includes('android-app://'));
}

function isIOS() {
    return /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
}

function showInstallPrompts() {
    if (isRunningStandalone()) return;
    
    const menuItem = document.getElementById('menuInstallAppItem');
    if (menuItem) menuItem.style.display = 'flex';

    const welcomeBtn = document.getElementById('welcomeInstallAppBtn');
    if (welcomeBtn) welcomeBtn.style.display = 'inline-flex';

    const isDismissed = sessionStorage.getItem('roshaket_dismiss_install_banner');
    const banner = document.getElementById('pwaSmartInstallBanner');
    if (banner && !isDismissed) {
        banner.style.display = 'flex';
    }
}

function hideInstallPrompts() {
    const menuItem = document.getElementById('menuInstallAppItem');
    if (menuItem) menuItem.style.display = 'none';

    const welcomeBtn = document.getElementById('welcomeInstallAppBtn');
    if (welcomeBtn) welcomeBtn.style.display = 'none';

    const banner = document.getElementById('pwaSmartInstallBanner');
    if (banner) banner.style.display = 'none';
}

function dismissSmartInstallBanner() {
    sessionStorage.setItem('roshaket_dismiss_install_banner', 'true');
    const banner = document.getElementById('pwaSmartInstallBanner');
    if (banner) banner.style.display = 'none';
}

function openIosInstallModal() {
    const modal = document.getElementById('iosInstallModal');
    if (modal) modal.classList.add('open');
}

function closeIosInstallModal() {
    const modal = document.getElementById('iosInstallModal');
    if (modal) modal.classList.remove('open');
}

async function triggerPwaInstall() {
    if (isRunningStandalone()) {
        showToast('✅ האפליקציה כבר מותקנת ופועלת במכשיר שלך!');
        return;
    }

    if (isIOS()) {
        openIosInstallModal();
        return;
    }

    if (!deferredInstallPrompt) {
        showToast('💡 להתקנה: לחצי על סמל ההתקנה ⊕ בשורת הכתובת בדפדפן, או על 3 הנקודות > "התקן אפליקציה"');
        return;
    }

    try {
        deferredInstallPrompt.prompt();
        const choiceResult = await deferredInstallPrompt.userChoice;
        if (choiceResult && choiceResult.outcome === 'accepted') {
            console.log('User accepted PWA install');
            if (typeof trackEvent === 'function') {
                trackEvent('pwa_install_accepted');
            }
            hideInstallPrompts();
        } else {
            console.log('User dismissed PWA install');
            if (typeof trackEvent === 'function') {
                trackEvent('pwa_install_dismissed');
            }
        }
    } catch (err) {
        console.warn('Install prompt error:', err);
    } finally {
        deferredInstallPrompt = null;
    }
}

window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredInstallPrompt = e;
    showInstallPrompts();
});

window.addEventListener('appinstalled', () => {
    deferredInstallPrompt = null;
    hideInstallPrompts();
    showToast('🎉 ראש שקט הותקנה בהצלחה במסך הבית שלך!');
    if (typeof trackEvent === 'function') {
        trackEvent('pwa_installed_success');
    }
});

// Check standalone and iOS on initial load
window.addEventListener('DOMContentLoaded', () => {
    if (!isRunningStandalone()) {
        if (isIOS()) {
            showInstallPrompts();
        }
    }
});
'''

if 'PWA INSTALLATION ENGINE' not in content:
    content = content.replace('</script>', pwa_js + '\n</script>', 1)
    print('Added PWA JavaScript Logic')

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated index.html successfully')

# Update sw.js to roshaket-v69
sw_path = r'C:\Users\User\Desktop\D-Dialog\roshaket\public\sw.js'
with open(sw_path, 'r', encoding='utf-8') as f:
    sw_content = f.read()

sw_content = re.sub(r'roshaket-v\d+', 'roshaket-v69', sw_content)
with open(sw_path, 'w', encoding='utf-8') as f:
    f.write(sw_content)
print('Updated sw.js to roshaket-v69')
