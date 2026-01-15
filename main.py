import flet as ft
import requests
import threading
import os
import platform
import re
import time

# הגדרות קישורים
JSON_URL = "https://www.gly.co.il/_next/data/GeWFXmhG87d3ioX0F5VbE/program.json?id=3194"
LIVE_URL = "https://cdn.cybercdn.live/Galei_Israel/Live/icecast.audio"

def main(page: ft.Page):
    # הגדרות עיצוב RTL
    page.rtl = True 
    page.title = "אלעד עמדי - גלי ישראל"
    page.theme_mode = "dark"
    page.padding = 0
    page.spacing = 0
    page.bgcolor = "#101010"
    
    shutdown_timer = None

    # --- פונקציות הורדה וטיימר ---
    def get_download_folder():
        if platform.system() == "Android":
            return "/storage/emulated/0/Download"
        else:
            return os.path.join(os.path.expanduser("~"), "Downloads")

    def download_file(url, filename, progress_bar, status_text):
        try:
            folder = get_download_folder()
            if not os.path.exists(folder):
                os.makedirs(folder, exist_ok=True)
            
            clean_name = re.sub(r'[\\/*?:"<>|]', "", filename) + ".mp3"
            full_path = os.path.join(folder, clean_name)
            
            status_text.value = "מתחיל הורדה..."
            status_text.update()

            response = requests.get(url, stream=True, timeout=15)
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(full_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = downloaded / total_size
                            progress_bar.value = percent
                            progress_bar.update()
            
            status_text.value = "✅ הושלם!"
            status_text.color = "green"
            progress_bar.value = 1
            progress_bar.update()
            status_text.update()
            
            page.snack_bar = ft.SnackBar(ft.Text(f"נשמר ב: {clean_name}"))
            page.snack_bar.open = True
            page.update()

        except Exception as e:
            status_text.value = "❌ שגיאה"
            status_text.color = "red"
            status_text.update()

    def start_download_thread(url, title, date, p_bar, s_txt):
        filename = f"{date}_{title}"
        threading.Thread(target=download_file, args=(url, filename, p_bar, s_txt), daemon=True).start()

    # --- טיימר ---
    def set_timer(minutes):
        nonlocal shutdown_timer
        if shutdown_timer is not None:
            shutdown_timer.cancel()
        
        if minutes == 0:
            page.snack_bar = ft.SnackBar(ft.Text("הטיימר בוטל"))
            page.snack_bar.open = True
            page.update()
            return

        def stop_playback():
            audio_player.pause()
            btn_play_pause.icon = ft.icons.PLAY_ARROW_ROUNDED
            page.update()

        shutdown_timer = threading.Timer(minutes * 60, stop_playback)
        shutdown_timer.start()
        
        page.snack_bar = ft.SnackBar(ft.Text(f"כיבוי בעוד {minutes} דקות"))
        page.snack_bar.open = True
        page.update()

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
                ft.TextButton("סגור", on_click=close_dlg, style=ft.ButtonStyle(color=ft.colors.RED)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.dialog = dlg_modal
        dlg_modal.open = True
        page.update()

    # --- משתני UI ---
    txt_now_playing = ft.Text("מוכן להאזנה", size=14, weight="bold", color="white")
    txt_time = ft.Text("00:00", size=12, color="grey")
    txt_duration = ft.Text("--:--", size=12, color="grey")
    slider_prog = ft.Slider(min=0, max=100, value=0, height=20, expand=True, disabled=True)
    
    btn_play_pause = ft.IconButton(
        icon=ft.icons.PLAY_ARROW_ROUNDED, 
        icon_size=40, 
        icon_color=ft.colors.BLUE,
        on_click=lambda _: toggle_play()
    )

    # --- לוגיקה ונגן ---

    def play_stream(url, title, is_live=False):
        # 1. עדכון ה-UI לפני הכל כדי שהכותרת תופיע מיד
        txt_now_playing.value = f"{'🔴 ' if is_live else ''}{title}"
        btn_play_pause.icon = ft.icons.PAUSE_ROUNDED
        
        if is_live:
            txt_duration.value = "שידור חי"
            txt_time.value = ""
            slider_prog.value = 0
            slider_prog.disabled = True
        else:
            txt_duration.value = "טוען..." # יתעדכן לבד
            slider_prog.disabled = False
        
        page.update() # מרענן את המסך מיד

        # 2. טיפול בנגן - תיקון הבעיה של הלחיצה הכפולה
        audio_player.pause()       # עוצר קודם
        audio_player.src = url     # מחליף קישור
        audio_player.autoplay = True # !חשוב! מכריח אותו לנגן מיד בטעינה
        audio_player.update()      # שולח לנגן

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
        if btn_play_pause.icon == ft.icons.PAUSE_ROUNDED:
            audio_player.pause()
            btn_play_pause.icon = ft.icons.PLAY_ARROW_ROUNDED
        else:
            audio_player.resume()
            btn_play_pause.icon = ft.icons.PAUSE_ROUNDED
        page.update()

    def toggle_live_broadcast(e):
        play_stream(LIVE_URL, "שידור חי - גלי ישראל", is_live=True)

    # יצירת הנגן - autoplay=False בהתחלה כדי שלא יתחיל סתם
    audio_player = ft.Audio(
        src=LIVE_URL,
        autoplay=False,
        volume=1.0,
        on_position_changed=on_position_changed,
        on_duration_changed=on_duration_changed,
        on_state_changed=lambda e: print("State:", e.data)
    )
    page.overlay.append(audio_player)

    # --- רשימה ---
    list_view = ft.ListView(expand=True, spacing=10, padding=20)

    def load_data():
        try:
            list_view.controls.clear()
            list_view.controls.append(ft.Text("טוען נתונים...", color="white"))
            page.update()
            
            r = requests.get(JSON_URL, timeout=10).json()
            list_view.controls.clear()
            
            items_groups = r.get('pageProps', {}).get('programData', {}).get('itemsByDate', [])
            
            for group in items_groups:
                for item in group.get('items', []):
                    title = item.get('itemTitle', 'ללא שם')
                    date = item.get('itemDate', '')
                    url = item.get('item_stream_url', '')
                    
                    dl_progress = ft.ProgressBar(value=0, width=100, bgcolor="#333", color="green", height=5)
                    dl_status = ft.Text("", size=10, color="white")
                    
                    card = ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.IconButton(
                                    icon=ft.icons.PLAY_CIRCLE_FILL, icon_color=ft.colors.BLUE, icon_size=34,
                                    on_click=lambda _, u=url, t=f"{date} {title}": play_stream(u, t)
                                ),
                                ft.Column([
                                    ft.Text(title, weight="bold", size=14, color="white", overflow=ft.TextOverflow.ELLIPSIS),
                                    ft.Text(date, size=12, color="grey")
                                ], expand=True),
                                
                                ft.IconButton(
                                    icon=ft.icons.DOWNLOAD_ROUNDED, icon_color="white",
                                    on_click=lambda _, u=url, t=title, d=date, p=dl_progress, s=dl_status: start_download_thread(u, t, d, p, s)
                                )
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            
                            ft.Column([dl_status, dl_progress], spacing=2)
                        ]),
                        bgcolor="#1a1a1a", padding=10, border_radius=10
                    )
                    list_view.controls.append(card)
            page.update()

        except Exception as e:
            list_view.controls.append(ft.Text(f"שגיאה בטעינה: {e}", color="red"))
            page.update()

    # --- מבנה המסך ---
    header = ft.Container(
        content=ft.Row([
            ft.Text("גלי ישראל", size=20, weight="bold", color="white"),
            ft.ElevatedButton("🔴 LIVE", bgcolor="#da3633", color="white", on_click=toggle_live_broadcast),
            ft.IconButton(icon=ft.icons.REFRESH, icon_color="white", on_click=lambda _: threading.Thread(target=load_data, daemon=True).start())
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        padding=ft.padding.symmetric(vertical=15, horizontal=20), bgcolor="#1f1f1f"
    )

    bottom_bar = ft.Container(
        content=ft.Column([
            ft.Row([txt_now_playing], alignment=ft.MainAxisAlignment.CENTER),
            ft.Row([
                txt_time, 
                slider_prog, 
                txt_duration
            ], alignment=ft.MainAxisAlignment.CENTER),
            ft.Row([
                ft.IconButton(icon=ft.icons.TIMER, icon_color="white", tooltip="טיימר שינה", on_click=open_timer_dialog),
                btn_play_pause,
                ft.IconButton(icon=ft.icons.SETTINGS, icon_color="grey", tooltip="הגדרות") 
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=30)
        ]),
        bgcolor="#080808", padding=15, border_radius=ft.border_radius.only(top_left=15, top_right=15)
    )

    page.add(header, list_view, bottom_bar)
    threading.Thread(target=load_data, daemon=True).start()

ft.app(target=main)