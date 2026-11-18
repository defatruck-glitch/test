#qpy:kivy
from kivy.app import App
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.core.text import LabelBase
import time

# 載入小米平板內建繁體中文字型
try:
    LabelBase.register(name='Roboto', fn_regular='/system/fonts/NotoSansCJK-Regular.ttc')
except Exception:
    pass

class FloatingApp(App):
    floating_view = None
    wm = None
    params = None
    
    initial_x = 0
    initial_y = 0
    initial_touch_x = 0
    initial_touch_y = 0
    click_count = 0
    last_click_time = 0

    def build(self):
        self.status_label = Label(text="【帥同外掛系統】載入懸浮視窗...", font_size='20sp')
        Clock.schedule_once(self.init_android_overlay, 1.0)
        return self.status_label

    def set_status(self, msg):
        Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', msg), 0)

    def init_android_overlay(self, dt):
        try:
            from jnius import autoclass, PythonJavaClass, java_method, cast

            Looper = autoclass('android.os.Looper')
            Handler = autoclass('android.os.Handler')
            Context = autoclass('android.content.Context')
            WindowManager = autoclass('android.view.WindowManager')
            LayoutParams = autoclass('android.view.WindowManager$LayoutParams')
            LinearLayout = autoclass('android.widget.LinearLayout')
            TextView = autoclass('android.widget.TextView')
            Gravity = autoclass('android.view.Gravity')
            Color = autoclass('android.graphics.Color')
            BuildVersion = autoclass('android.os.Build$VERSION')
            MotionEvent = autoclass('android.view.MotionEvent')
            ActivityThread = autoclass('android.app.ActivityThread')
            JString = autoclass('java.lang.String')

            def to_char_seq(text):
                return cast('java.lang.CharSequence', JString(text))

            class UIRunnable(PythonJavaClass):
                __javainterfaces__ = ['java/lang/Runnable']
                def __init__(self, func):
                    super().__init__()
                    self.func = func
                @java_method('()V')
                def run(self):
                    self.func()

            # 關閉視窗的共用函式
            def close_overlay():
                if self.wm and self.floating_view:
                    try:
                        self.wm.removeView(self.floating_view)
                        self.floating_view = None
                        self.set_status("懸浮視窗已關閉。")
                    except Exception as e:
                        self.set_status(f"關閉失敗：{str(e)}")

            # 1. 主視窗觸控監聽器（拖曳 + 單擊計數 + 雙擊關閉）
            class DragTouchListener(PythonJavaClass):
                __javainterfaces__ = ['android/view/View$OnTouchListener']
                def __init__(self, app_instance, target_tv):
                    super().__init__()
                    self.app = app_instance
                    self.tv = target_tv

                @java_method('(Landroid/view/View;Landroid/view/MotionEvent;)Z')
                def onTouch(self, view, event):
                    action = event.getAction()
                    
                    if action == MotionEvent.ACTION_DOWN:
                        self.app.initial_x = self.app.params.x
                        self.app.initial_y = self.app.params.y
                        self.app.initial_touch_x = event.getRawX()
                        self.app.initial_touch_y = event.getRawY()
                        return True

                    elif action == MotionEvent.ACTION_MOVE:
                        dx = int(event.getRawX() - self.app.initial_touch_x)
                        dy = int(event.getRawY() - self.app.initial_touch_y)
                        self.app.params.x = self.app.initial_x + dx
                        self.app.params.y = self.app.initial_y + dy
                        # 更新整個容器 (floating_view) 的位置
                        self.app.wm.updateViewLayout(self.app.floating_view, self.app.params)
                        return True

                    elif action == MotionEvent.ACTION_UP:
                        dx = abs(event.getRawX() - self.app.initial_touch_x)
                        dy = abs(event.getRawY() - self.app.initial_touch_y)
                        # 放寬平板高解析度螢幕的點擊容差至 40 像素
                        if dx < 40 and dy < 40:
                            now = time.time()
                            # 放寬雙擊判定時間至 0.6 秒
                            if now - self.app.last_click_time < 0.6:
                                close_overlay()
                            else:
                                self.app.click_count += 1
                                new_text = f" 懸浮視窗運行中 \n 點擊次數：{self.app.click_count} \n (拖曳 / 雙擊關閉) "
                                self.tv.setText(to_char_seq(new_text))
                            self.app.last_click_time = now
                        return True
                    return False

            # 2. 右側「✕」按鈕專屬點擊監聽器
            class CloseClickListener(PythonJavaClass):
                __javainterfaces__ = ['android/view/View$OnClickListener']
                @java_method('(Landroid/view/View;)V')
                def onClick(self, view):
                    close_overlay()

            def create_view():
                try:
                    context = ActivityThread.currentApplication()
                    self.wm = context.getSystemService(Context.WINDOW_SERVICE)

                    # 建立水平容器，左側放資訊文字，右側放關閉按鈕
                    container = LinearLayout(context)
                    container.setOrientation(LinearLayout.HORIZONTAL)
                    container.setGravity(Gravity.CENTER_VERTICAL)
                    container.setBackgroundColor(Color.parseColor("#DD1E1E1E"))

                    # 左側文字區
                    tv = TextView(context)
                    init_text = " 掛B視窗運行中 \n 點擊次數：0 \n (拖曳 / 雙擊關閉) "
                    tv.setText(to_char_seq(init_text))
                    tv.setTextColor(Color.WHITE)
                    tv.setTextSize(16)
                    tv.setPadding(35, 20, 25, 20)

                    # 右側紅色關閉按鈕
                    close_btn = TextView(context)
                    close_btn.setText(to_char_seq(" ✕ "))
                    close_btn.setTextColor(Color.WHITE)
                    close_btn.setBackgroundColor(Color.parseColor("#CC3333"))
                    close_btn.setTextSize(20)
                    close_btn.setPadding(25, 35, 25, 35)

                    # 綁定監聽器
                    self.touch_listener = DragTouchListener(self, tv)
                    tv.setOnTouchListener(self.touch_listener)

                    self.close_listener = CloseClickListener()
                    close_btn.setOnClickListener(self.close_listener)

                    # 將元件加入容器
                    container.addView(tv)
                    container.addView(close_btn)

                    window_type = (
                        LayoutParams.TYPE_APPLICATION_OVERLAY
                        if BuildVersion.SDK_INT >= 26
                        else LayoutParams.TYPE_PHONE
                    )

                    self.params = LayoutParams(
                        LayoutParams.WRAP_CONTENT,
                        LayoutParams.WRAP_CONTENT,
                        window_type,
                        LayoutParams.FLAG_NOT_FOCUSABLE,
                        -3
                    )

                    self.params.gravity = Gravity.TOP | Gravity.LEFT
                    self.params.x = 150
                    self.params.y = 200

                    self.wm.addView(container, self.params)
                    self.floating_view = container
                    self.set_status("掛B視窗已建立！\n支援雙擊文字區關閉，或直接點擊右側紅色「✕」關閉。")

                except Exception as e:
                    self.set_status(f"建立視窗錯誤：\n{str(e)}")

            self.runnable = UIRunnable(create_view)
            self.ui_handler = Handler(Looper.getMainLooper())
            self.ui_handler.post(self.runnable)

        except Exception as e:
            self.set_status(f"載入錯誤：\n{str(e)}")

    def on_stop(self):
        if self.wm and self.floating_view:
            try:
                self.wm.removeView(self.floating_view)
            except Exception:
                pass

if __name__ == '__main__':
    FloatingApp().run()
