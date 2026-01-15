import flet as ft
import requests
import threading
import os
import platform
import re
import time
import urllib3
import logging

# ביטול אזהרות אבטחה ורישום לוגים
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO)

# הגדרות קישורים
DEFAULT_JSON_URL = "https://www.gly.co.il/_next/data/GeWFXmhG87d3ioX0F5VbE/program.json?id=3194"
LIVE_URL = "https://cdn.cybercdn.live/Galei_Israel/Live/icecast.audio"
LIVE_INFO_API = "https://api_new.radiodarom.co.il/api/broadcastSchedule/GetPlayingProgram?radioStationId=2"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def main(page: ft.Page):
    # מנגנון לכידת שגיאות קריטי - מונע מסך שחור
    try:
        page.rtl = True 
        page.title = "אלעד עמדי"
        page.theme_mode = "dark"
        page.padding = 0
        page.spacing = 0
        page.bgcolor = "#101010"
        
        current_json_url = DEFAULT_JSON_URL
        is_live_mode = False
        active_downloads = {} 
        timer_running = False
        timer_seconds_left = 0

        # רכיבי UI
        txt_now_playing = ft.Text("מוכן להאזנה", size=14, weight="bold", color="white")
        txt_time = ft.Text("00:00", size=12, color="grey")
        txt_duration = ft.Text("--:--", size=12, color="grey")
        slider_prog = ft.Slider(min=0, max=100, value=0, height=20, expand=True, disabled=True)
        txt_timer_countdown = ft.Text("", color="red", weight="bold", size=12)

        # שימוש במחרוזות לאייקונים למניעת קריסה
        btn_play_pause = ft.IconButton(
            icon="play_arrow",  # שימוש בסטרינג בטוח
            icon_size=40, 
            icon_color="blue",
            on_click=lambda _: toggle_play()
        )

        # --- פונקציות ---
        
        def update_timer_countdown():
            nonlocal timer_seconds_left, timer_running
            while timer_running and timer_seconds_left > 0:
                time.sleep(1)
                timer_seconds_left -= 1
                mins, secs = divmod(timer_seconds_left, 60)
                txt_timer_countdown.value = f"{mins:02d}:{secs:02d}"
                txt_timer_countdown.update()
            
            if timer_running and timer_seconds_left <= 0:
                stop_playback_timer()

        def stop_playback_timer():
            nonlocal timer_running
            timer_running = False
            audio_player.pause()
            btn_play_pause.icon = "play_arrow"
            txt_timer_countdown.value = ""
            page.update()
            page.open(ft.SnackBar(ft.Text("הנגן כבה עקב טיימר")))

        def set_timer(minutes):
            nonlocal timer_running, timer_seconds_left
            if minutes == 0:
                timer_running = False
                txt_timer_countdown.value = ""
                page.update()
                page.open(ft.SnackBar(ft.Text("הטיימר בוטל")))
                return

            timer_seconds_left = minutes * 60
            if not timer_running:
                timer_running = True
                threading.Thread(target=update_timer_countdown, daemon=True).start()
            
            page.open(ft.SnackBar(ft.Text(f"כיבוי בעוד {minutes} דקות")))

        def open_timer_dialog(e):
            def close_dlg(e):
                dlg_modal.open = False
                page.update()

            dlg_modal = ft.AlertDialog(
                modal=True,
                title=ft.Text("טיימר שינה"),
                content=ft.Text("בחר זמן לכיבוי:"),
                actions=[
                    ft.TextButton("15 דק'", on_click=lambda e: [set_timer(15), close_dlg(e)]),
                    ft.TextButton("30 דק'", on_click=lambda e: [set_timer(30), close_dlg(e)]),
                    ft.TextButton("60 דק'", on_click=lambda e: [set_timer(60), close_dlg(e)]),
                    ft.TextButton("בטל", on_click=lambda e: [set_timer(0), close_dlg(e)]),
                    ft.TextButton("סגור", on_click=close_dlg, style=ft.ButtonStyle(color="red")),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.dialog = dlg_modal
            dlg_modal.open = True
            page.update()

        def get_download_folder():
            try:
                if platform.system() == "Android":
                    return "/storage/emulated/0/Download"
                else:
                    return os.path.join(os.path.expanduser("~"), "Downloads")
            except:
                return ""

        def toggle_download(url, title, date, btn, p_bar, s_txt):
            if active_downloads.get(url):
                active_downloads[url] = False
                btn.icon = "download"
                btn.icon_color = "white"
                s_txt.value = "מבטל..."
                btn.update()
                s_txt.update()
            else:
                active_downloads[url] = True
                btn.icon = "close"
                btn.icon_color = "red"
                btn.update()
                threading.Thread(target=download_file_thread, args=(url, title, date, btn, p_bar, s_txt), daemon=True).start()

        def download_file_thread(url, title, date, btn, progress_bar, status_text):
            filename = f"{date}_{title}"
            try:
                folder = get_download_folder()
                if not folder or not os.path.exists(folder):
                    try: os.makedirs(folder, exist_ok=True)
                    except: pass
                
                clean_name = re.sub(r'[\\/*?:"<>|]', "", filename) + ".mp3"
                full_path = os.path.join(folder, clean_name)
                
                status_text.value = "מוריד..."
                status_text.color = "blue"
                status_text.update()

                response = requests.get(url, stream=True, timeout=15, headers=HEADERS, verify=False)
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(full_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if not active_downloads.get(url, False):
                            f.close()
                            try: os.remove(full_path)
                            except: pass
                            status_text.value = "בוטל"
                            status_text.color = "red"
                            progress_bar.value = 0
                            status_text.update()
                            progress_bar.update()
                            return

                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                percent = downloaded / total_size
                                progress_bar.value = percent
                                progress_bar.update()
                
                active_downloads[url] = False
                status_text.value = "✅ הושלם!"
                status_text.color = "green"
                progress_bar.value = 1
                btn.icon = "folder_open"
                btn.tooltip = "הורדה הסתיימה"
                
                btn.update()
                progress_bar.update()
                status_text.update()
                page.open(ft.SnackBar(ft.Text(f"נשמר ב: {clean_name}")))

            except Exception as e:
                active_downloads[url] = False
                status_text.value = "שגיאה"
                status_text.color = "red"
                btn.icon = "download"
                btn.icon_color = "white"
                status_text.update()
                btn.update()

        def get_live_info_text():
            try:
                r = requests.get(LIVE_INFO_API, timeout=4, headers=HEADERS, verify=False).json()
                program_data = r.get("program") 
                if program_data:
                    title = program_data.get("title")
                    subtitle = program_data.get("subTitle")
                    if title and subtitle:
                        return f"🔴 {title}\n{subtitle}"
                    elif title:
                        return f"🔴 {title}"
                return "🔴 שידור חי - גלי ישראל"
            except:
                return "🔴 שידור חי - גלי ישראל"

        def fetch_live_metadata():
            while True:
                if is_live_mode:
                    info = get_live_info_text()
                    if is_live_mode and info:
                        txt_now_playing.value = info
                        page.update()
                time.sleep(30)

        threading.Thread(target=fetch_live_metadata, daemon=True).start()

        def fetch_live_metadata_once():
            if not is_live_mode: return
            info = get_live_info_text()
            if info:
                txt_now_playing.value = info
                page.update()

        def play_stream(url, title, is_live=False):
            nonlocal is_live_mode
            is_live_mode = is_live 

            display_title = title 
            if is_live:
                display_title = "🔴 טוען מידע..."

            txt_now_playing.value = display_title
            btn_play_pause.icon = "pause"
            
            if is_live:
                txt_duration.value = "שידור חי"
                txt_time.value = ""
                slider_prog.value = 0
                slider_prog.disabled = True
                threading.Thread(target=lambda: [time.sleep(0.5), fetch_live_metadata_once()]).start()
            else:
                txt_duration.value = "טוען..." 
                slider_prog.disabled = False
            
            page.update()

            audio_player.pause()
            audio_player.src = url
            audio_player.update()
            time.sleep(0.1) 
            audio_player.resume()
            
        def on_duration_changed(e):
            try:
                duration = int(e.data)
                slider_prog.max = duration
                slider_prog.disabled = False
                mins, secs = divmod(duration // 1000, 60)
                if mins > 60:
                    hours, mins = divmod(mins, 60)
                    txt_duration.value = f"{hours:02d}:{mins:02d}:{secs:02d}"
                else:
                    txt_duration.value = f"{mins:02d}:{secs:02d}"
                page.update()
            except: pass

        def on_position_changed(e):
            try:
                if slider_prog.disabled: return 
                position = int(e.data)
                slider_prog.value = position
                mins, secs = divmod(position // 1000, 60)
                if mins > 60:
                    hours, mins = divmod(mins, 60)
                    txt_time.value = f"{hours:02d}:{mins:02d}:{secs:02d}"
                else:
                    txt_time.value = f"{mins:02d}:{secs:02d}"
                page.update()
            except: pass

        def toggle_play():
            if btn_play_pause.icon == "pause":
                audio_player.pause()
                btn_play_pause.icon = "play_arrow"
            else:
                audio_player.resume()
                btn_play_pause.icon = "pause"
            page.update()

        def toggle_live_broadcast(e):
            play_stream(LIVE_URL, "שידור חי", is_live=True)

        audio_player = ft.Audio(
            src=LIVE_URL,
            autoplay=False,
            volume=1.0,
            on_position_changed=on_position_changed,
            on_duration_changed=on_duration_changed
        )
        page.overlay.append(audio_player)

        list_view = ft.ListView(expand=True, spacing=10, padding=20)

        def load_data():
            try:
                list_view.controls.clear()
                list_view.controls.append(ft.Text("טוען ארכיון...", color="white"))
                page.update()
                
                r = requests.get(current_json_url, timeout=10, headers=HEADERS, verify=False).json()
                list_view.controls.clear()
                
                items_groups = r.get('pageProps', {}).get('programData', {}).get('itemsByDate', [])
                
                found = False
                for group in items_groups:
                    for item in group.get('items', []):
                        found = True
                        title = item.get('itemTitle', 'ללא שם')
                        date = item.get('itemDate', '')
                        url = item.get('item_stream_url', '')
                        
                        dl_progress = ft.ProgressBar(value=0, width=100, bgcolor="#333", color="green", height=5)
                        dl_status = ft.Text("", size=10, color="white")
                        
                        btn_dl = ft.IconButton(
                            icon="download", 
                            icon_color="white",
                            tooltip="הורדה",
                        )
                        btn_dl.on_click = lambda _, u=url, t=title, d=date, b=btn_dl, p=dl_progress, s=dl_status: toggle_download(u, t, d, b, p, s)

                        card = ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.IconButton(
                                        icon="play_circle_filled", 
                                        icon_color="blue", 
                                        icon_size=34,
                                        on_click=lambda _, u=url, t=f"{date} {title}": play_stream(u, t)
                                    ),
                                    ft.Column([
                                        ft.Text(title, weight="bold", size=14, color="white", overflow=ft.TextOverflow.ELLIPSIS),
                                        ft.Text(date, size=12, color="grey")
                                    ], expand=True),
                                    btn_dl
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Column([dl_status, dl_progress], spacing=2)
                            ]),
                            bgcolor="#1a1a1a", padding=10, border_radius=10
                        )
                        list_view.controls.append(card)
                
                if not found:
                    list_view.controls.append(ft.Text("לא נמצאו פריטים", color="orange"))
                    
                page.update()
            except Exception as e:
                list_view.controls.clear()
                list_view.controls.append(ft.Text(f"שגיאה בטעינה: {e}", color="red"))
                page.update()

        def open_settings_dialog(e):
            def close_dlg(e):
                dlg_settings.open = False
                page.update()
            
            txt_url_input = ft.TextField(
                label="קישור ל-JSON (ארכיון)", 
                value=current_json_url, 
                multiline=True, 
                min_lines=2, 
                max_lines=3,
                text_size=12
            )

            def save_settings(e):
                nonlocal current_json_url
                new_url = txt_url_input.value.strip()
                if new_url:
                    current_json_url = new_url
                    page.open(ft.SnackBar(ft.Text("הגדרות נשמרו. מרענן...")))
                    close_dlg(e)
                    threading.Thread(target=load_data, daemon=True).start()

            def reset_settings(e):
                txt_url_input.value = DEFAULT_JSON_URL
                txt_url_input.update()

            dlg_settings = ft.AlertDialog(
                modal=True,
                title=ft.Text("הגדרות מתקדמות"),
                content=ft.Column([
                    ft.Text("כתובת מקור המידע:", weight="bold"),
                    txt_url_input,
                    ft.Row([
                        ft.TextButton("אפס לברירת מחדל", on_click=reset_settings, style=ft.ButtonStyle(color="orange")),
                    ], alignment=ft.MainAxisAlignment.START),
                    ft.Divider(),
                    ft.Text(f"נתיב הורדה משוער:\n{get_download_folder()}", size=11, color="grey"),
                ], height=250, width=320),
                actions=[
                    ft.TextButton("ביטול", on_click=close_dlg, style=ft.ButtonStyle(color="red")),
                    ft.TextButton("שמור ורענן", on_click=save_settings, style=ft.ButtonStyle(color="green")),
                ],
            )
            page.dialog = dlg_settings
            dlg_settings.open = True
            page.update()

        header = ft.Container(
            content=ft.Row([
                ft.Text("גלי ישראל", size=20, weight="bold", color="white"),
                ft.ElevatedButton("🔴 LIVE", bgcolor="#da3633", color="white", on_click=toggle_live_broadcast),
                ft.IconButton(icon="refresh", icon_color="white", on_click=lambda _: threading.Thread(target=load_data, daemon=True).start())
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.symmetric(vertical=15, horizontal=20), bgcolor="#1f1f1f"
        )

        bottom_bar = ft.Container(
            content=ft.Column([
                ft.Row([txt_now_playing], alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([txt_time, slider_prog, txt_duration], alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([
                    ft.Row([ft.IconButton(icon="timer", icon_color="white", on_click=open_timer_dialog), txt_timer_countdown], spacing=0),
                    btn_play_pause,
                    ft.IconButton(icon="settings", icon_color="grey", on_click=open_settings_dialog) 
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=30)
            ]),
            bgcolor="#080808", padding=15, border_radius=ft.border_radius.only(top_left=15, top_right=15)
        )

        page.add(header, list_view, bottom_bar)
        threading.Thread(target=load_data, daemon=True).start()

    except Exception as e:
        # אם יש קריסה כללית - נציג אותה במקום מסך שחור
        page.add(ft.Text(f"Critical Error: {e}", color="red", size=20))
        logging.error(f"App Crash: {e}")

ft.app(target=main)
