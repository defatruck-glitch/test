# @title 預設標題文字
import random
import os
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.core.audio import SoundLoader

# 直接使用你測試成功的中文字型設定
from kivy.core.text import LabelBase
LabelBase.register(name='Roboto', fn_regular='DroidSansFallback.ttf')


# 輔助函式：若找不到圖片，自動產生彩色方塊代替
def create_character_widget(img_name, fallback_color, pos_hint):
    if os.path.exists(img_name):
        return Image(source=img_name, size_hint=(0.22, 0.3), pos_hint=pos_hint)
    else:
        box = Widget(size_hint=(0.18, 0.25), pos_hint=pos_hint)
        with box.canvas:
            Color(*fallback_color)
            box.rect = Rectangle(pos=box.pos, size=box.size)
        box.bind(pos=lambda inst, val: setattr(inst.rect, 'pos', val))
        box.bind(size=lambda inst, val: setattr(inst.rect, 'size', val))
        return box


class RPGGame(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 載入音效檔案
        self.sfx_attack = SoundLoader.load('attack.wav')  # 主角揮擊音效
        self.sfx_hit = SoundLoader.load('hit.wav')        # 主角受傷音效
        self.sfx_heal = SoundLoader.load('heal.wav')      # 喝藥水音效
        self.sfx_win = SoundLoader.load('win.mp3')        # 打贏暗黑魔龍（全破）音效
        self.sfx_lose = SoundLoader.load('lose.wav')      # 新增：主角死亡音效

        # 怪物圖鑑：[名稱, 血量, 力量, 圖片檔名, 備用顏色]
        self.monsters = [
            ['麥克哥', 200, 2, 'mon1.png', (0.2, 0.8, 0.3, 1)],
            ['黑皮哥', 350, 5, 'mon2.png', (1.0, 0.5, 0.1, 1)],
            ['豬尾哥', 420, 7, 'mon3.png', (0.5, 0.7, 0.2, 1)],
            ['黑人哥', 1000, 8, 'mon4.png', (0.9, 0.1, 0.2, 1)]
        ]
        self.stage = 0

        # 主角初始屬性
        self.hero_name = '林帥同'
        self.lv = 1
        self.max_hp = 250
        self.hp = self.max_hp
        self.str = 1
        self.luk = 2
        self.potions = 5
        self.is_animating = False

        # 頂部狀態欄
        self.status_label = Label(
            text='', font_size='18sp',
            size_hint=(1, 0.1), pos_hint={'x': 0, 'top': 1}
        )
        self.add_widget(self.status_label)

        # 中央戰鬥訊息提示
        self.msg_label = Label(
            text='戰鬥開始！請選擇行動', font_size='22sp',
            color=(1, 0.9, 0.2, 1), size_hint=(1, 0.12), pos_hint={'x': 0, 'top': 0.88}
        )
        self.add_widget(self.msg_label)

        # 主角血量文字與角色圖
        self.hero_hp_label = Label(
            text='', font_size='18sp',
            size_hint=(0.3, 0.08), pos_hint={'x': 0.08, 'y': 0.62}
        )
        self.add_widget(self.hero_hp_label)
        self.hero_widget = create_character_widget('hero.png', (0.2, 0.6, 1, 1), {'x': 0.1, 'y': 0.3})
        self.add_widget(self.hero_widget)

        # 怪物血量文字與怪物圖
        self.mon_hp_label = Label(
            text='', font_size='18sp',
            size_hint=(0.3, 0.08), pos_hint={'right': 0.92, 'y': 0.62}
        )
        self.add_widget(self.mon_hp_label)
        self.mon_widget = None
        self.hit_event = None

        # 底部操作按鈕區
        btn_box = BoxLayout(size_hint=(0.85, 0.12), pos_hint={'x': 0.075, 'y': 0.08}, spacing=15)
        self.atk_btn = Button(text='發動攻擊', font_size='20sp', background_color=(0.2, 0.6, 1, 1))
        self.heal_btn = Button(text='喝回復藥水 (+100HP)', font_size='20sp', background_color=(0.2, 0.8, 0.4, 1))

        self.atk_btn.bind(on_press=self.on_attack)
        self.heal_btn.bind(on_press=self.on_heal)

        btn_box.add_widget(self.atk_btn)
        btn_box.add_widget(self.heal_btn)
        self.add_widget(btn_box)

        self.load_stage()

    # 安全播放音效的輔助函式
    def play_sfx(self, sound):
        if sound:
            sound.stop()
            sound.play()

    def show_hit(self, target, normal_file):
        # Prefer a dedicated hurt sprite; otherwise flash the existing sprite.
        hurt_file = os.path.splitext(normal_file)[0] + '_hit.png'
        if self.hit_event:
            self.hit_event.cancel()
            self.hit_event = None
        if isinstance(target, Image):
            if os.path.exists(hurt_file):
                target.source = hurt_file
                target.reload()
            else:
                target.color = (1, 0.35, 0.35, 1)
        else:
            target.opacity = 0.35

        def restore(dt):
            if isinstance(target, Image):
                target.source = normal_file
                target.color = (1, 1, 1, 1)
                target.reload()
            else:
                target.opacity = 1
            self.hit_event = None

        self.hit_event = Clock.schedule_once(restore, 0.4)

    def load_stage(self):
        mon_name, mon_hp, mon_str, mon_img_file, fallback_color = self.monsters[self.stage]
        self.mon_image_file = mon_img_file
        self.mon_name = mon_name
        self.mon_max_hp = mon_hp
        self.mon_hp = mon_hp
        self.mon_atk = mon_str * 5

        if self.mon_widget:
            self.remove_widget(self.mon_widget)
        self.mon_widget = create_character_widget(mon_img_file, fallback_color, {'x': 0.68, 'y': 0.3})
        self.add_widget(self.mon_widget)

        self.msg_label.text = f'第 {self.stage + 1} 關：野生的 {self.mon_name} 出現了！'
        self.update_ui()

    def update_ui(self):
        atk = self.str * 5
        crit = min(80, self.luk * 10)
        self.status_label.text = f'{self.hero_name} (LV.{self.lv}) | 攻擊: {atk} | 暴擊: {crit}% | 藥水: {self.potions}'
        self.hero_hp_label.text = f'{self.hero_name}\nHP: {self.hp} / {self.max_hp}'
        self.mon_hp_label.text = f'{self.mon_name}\nHP: {self.mon_hp} / {self.mon_max_hp}'

    def on_attack(self, instance):
        if self.is_animating:
            return
        self.is_animating = True

        dash = Animation(pos_hint={'x': 0.52, 'y': 0.3}, duration=0.18)
        retreat = Animation(pos_hint={'x': 0.1, 'y': 0.3}, duration=0.18)
        dash.bind(on_complete=self.calc_hero_damage)
        (dash + retreat).start(self.hero_widget)

    def calc_hero_damage(self, animation, widget):
        self.play_sfx(self.sfx_attack)

        atk = self.str * 5
        crit_rate = min(80, self.luk * 10)

        roll = random.randint(1, 10)
        combo = 1 if roll <= 6 else (2 if roll <= 9 else 3)

        base_dmg = random.randint(int(atk * 0.8), atk) * combo
        is_crit = random.randint(1, 100) <= crit_rate

        dmg = base_dmg * 2 if is_crit else base_dmg
        self.mon_hp = max(0, self.mon_hp - dmg)
        self.show_hit(self.mon_widget, self.mon_image_file)

        crit_text = '【暴擊！】' if is_crit else ''
        self.msg_label.text = f'{crit_text}{self.hero_name} 造成 {dmg} 點傷害 ({combo}連擊)！'
        self.update_ui()

        if self.mon_hp <= 0:
            Clock.schedule_once(self.on_stage_clear, 0.8)
        else:
            Clock.schedule_once(self.monster_turn, 0.8)

    def on_heal(self, instance):
        if self.is_animating:
            return
        if self.potions <= 0:
            self.msg_label.text = '藥水已經用光了！'
            return

        self.play_sfx(self.sfx_heal)

        self.is_animating = True
        self.potions -= 1
        self.hp = min(self.max_hp, self.hp + 100)
        self.msg_label.text = f'{self.hero_name} 喝下藥水，恢復 100 點 HP！'
        self.update_ui()
        Clock.schedule_once(self.monster_turn, 0.8)

    def monster_turn(self, dt):
        dash = Animation(pos_hint={'x': 0.25, 'y': 0.3}, duration=0.18)
        retreat = Animation(pos_hint={'x': 0.68, 'y': 0.3}, duration=0.18)
        dash.bind(on_complete=self.calc_mon_damage)
        (dash + retreat).start(self.mon_widget)

    def calc_mon_damage(self, animation, widget):
        self.play_sfx(self.sfx_hit)

        dmg = random.randint(int(self.mon_atk * 0.7), self.mon_atk)
        self.hp = max(0, self.hp - dmg)
        self.show_hit(self.hero_widget, 'hero.png')
        self.msg_label.text = f'{self.mon_name} 反擊！造成 {dmg} 點傷害！'
        self.update_ui()

        if self.hp <= 0:
            self.play_sfx(self.sfx_lose)
            self.msg_label.text = f'遊戲結束... {self.hero_name} 倒下了！'
            self.atk_btn.disabled = True
            self.heal_btn.disabled = True
        else:
            self.is_animating = False

    def show_victory_screen(self):
        self.clear_widgets()
        with self.canvas.before:
            Color(0, 0, 0, 1)
            self.victory_background = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda instance, value: setattr(self.victory_background, 'pos', value))
        self.bind(size=lambda instance, value: setattr(self.victory_background, 'size', value))

        if os.path.exists('victory.png'):
            self.add_widget(Image(
                source='victory.png',
                size_hint=(1, 1),
                pos_hint={'x': 0, 'y': 0},
                fit_mode='fill'
            ))
        else:
            self.add_widget(Label(
                text='Victory!\nMissing victory.png',
                font_size='32sp',
                size_hint=(1, 1)
            ))

    def on_stage_clear(self, dt):
        if random.choice([True, False]):
            self.potions += 1
            drop_msg = '（獲得戰利品：回復藥水 x1）'
        else:
            drop_msg = ''

        if self.stage + 1 >= len(self.monsters):
            self.play_sfx(self.sfx_win)
            self.msg_label.text = f'恭喜 {self.hero_name} 擊敗所有魔王，全破通關！'
            self.atk_btn.disabled = True
            self.heal_btn.disabled = True
            self.show_victory_screen()
            return

        self.lv += 1
        self.hp = self.max_hp
        self.points = 3
        self.update_ui()
        self.show_level_up_popup(drop_msg)

    def show_level_up_popup(self, drop_msg):
        box = BoxLayout(orientation='vertical', padding=15, spacing=10)
        info = Label(
            text=f'擊敗 {self.mon_name}！{drop_msg}\n升級至 LV.{self.lv}（血量已全滿）\n剩餘屬性點數：{self.points} 點',
            font_size='18sp', halign='center'
        )
        box.add_widget(info)

        popup = Popup(title='升級自由配點', content=box, size_hint=(0.75, 0.65), auto_dismiss=False)

        def add_stat(stat_type):
            if stat_type == 'hp':
                self.max_hp += 100
                self.hp = self.max_hp
            elif stat_type == 'str':
                self.str += 1
            elif stat_type == 'luk':
                self.luk += 1

            self.points -= 1
            self.update_ui()
            info.text = f'升級至 LV.{self.lv}\n剩餘屬性點數：{self.points} 點'

            if self.points == 0:
                popup.dismiss()
                self.stage += 1
                self.is_animating = False
                self.load_stage()

        btn_hp = Button(text='體力上限 +100 (HP)', font_size='18sp')
        btn_str = Button(text='力量 +1 (攻擊力 +5)', font_size='18sp')
        btn_luk = Button(text='幸運 +1 (暴擊率 +10%)', font_size='18sp')

        btn_hp.bind(on_press=lambda x: add_stat('hp'))
        btn_str.bind(on_press=lambda x: add_stat('str'))
        btn_luk.bind(on_press=lambda x: add_stat('luk'))

        box.add_widget(btn_hp)
        box.add_widget(btn_str)
        box.add_widget(btn_luk)
        popup.open()


class MyRPGApp(App):
    def build(self):
        self.title = '林帥同的冒險 RPG'
        return RPGGame()

    def load_kv(self, *args, **kwargs):
        # 覆寫此方法，防止 Kivy 在 Colab 互動式環境下因尋找主類別檔案而報錯 OSError
        pass


if __name__ == '__main__':
    MyRPGApp().run()