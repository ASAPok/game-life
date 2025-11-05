import sys
import os
import random
import sqlite3
import hashlib
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QLineEdit,
                             QPushButton, QVBoxLayout, QHBoxLayout,
                             QMessageBox, QGridLayout, QMainWindow, QDialog,
                             QDialogButtonBox, QFrame, QSlider)
from PyQt6.QtGui import QPixmap, QPainter, QFont, QColor
from PyQt6.QtCore import Qt, QTimer, QRect, QPoint


def create_database():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def add_user(username, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    password_hash = hash_password(password)
    try:
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                  (username, password_hash))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def check_user(username, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    password_hash = hash_password(password)
    c.execute("SELECT * FROM users WHERE username = ? AND password_hash = ?",
              (username, password_hash))
    user = c.fetchone()
    conn.close()
    return user is not None


class ImageLabel(QLabel):
    def __init__(self, pixmap, image_id, captcha_window, parent=None):
        super().__init__(parent)
        self.setPixmap(pixmap)
        self.image_id = str(image_id)
        self.captcha_window = captcha_window
        self.offset = QPoint()
        self.original_parent = parent

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.offset = event.pos()
            global_pos = self.mapToGlobal(self.offset)
            self.setParent(self.captcha_window)
            self.show()
            self.raise_()
            new_pos = self.captcha_window.mapFromGlobal(global_pos) - self.offset
            self.move(new_pos)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = self.captcha_window.mapFromGlobal(
                event.globalPosition().toPoint()) - self.offset
            self.move(new_pos)

    def mouseReleaseEvent(self, event):
        drop_point = self.pos() + self.rect().center()
        target_found = None

        for row in self.captcha_window.drop_targets:
            for target in row:
                target_rect_in_window = QRect(
                    target.mapTo(self.captcha_window, QPoint(0, 0)),
                    target.size()
                )
                if (target_rect_in_window.contains(drop_point) and
                        target.image_id is None):
                    target_found = target
                    break
            if target_found:
                break

        if target_found:
            target_found.setPixmap(self.pixmap())
            target_found.image_id = self.image_id
            self.setParent(self.original_parent)
            self.setVisible(False)
            return

        self.setParent(self.original_parent)
        x = random.randint(0, self.original_parent.width() - self.width())
        y = random.randint(0, self.original_parent.height() - self.height())
        self.move(x, y)
        self.show()


class DropLabel(QLabel):
    def __init__(self, text, captcha_window):
        super().__init__(text)
        self.captcha_window = captcha_window
        self.setFrameShape(QFrame.Shape.Box)
        self.setFrameShadow(QFrame.Shadow.Sunken)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_id = None

    def clear(self):
        super().clear()
        self.setText("Перетащите сюда")
        self.image_id = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.image_id:
            widget_to_return = None
            for piece in self.captcha_window.pieces:
                if piece['widget'].image_id == self.image_id:
                    widget_to_return = piece['widget']
                    break

            if widget_to_return:
                source_container = self.captcha_window.source_container
                widget_to_return.setParent(source_container)
                x = random.randint(
                    0, source_container.width() - widget_to_return.width())
                y = random.randint(
                    0, source_container.height() - widget_to_return.height())
                widget_to_return.move(x, y)
                widget_to_return.show()
                self.clear()


class CaptchaWindow(QWidget):
    def __init__(self, login_window):
        super().__init__()
        self.login_window = login_window
        self.setWindowTitle("Капча - Соберите квадрат")
        self.setGeometry(300, 300, 450, 400)

        main_layout = QVBoxLayout()
        msg1 = "Ошибка входа 3 раза."
        msg2 = "Пожалуйста, соберите картинку, чтобы продолжить."
        main_layout.addWidget(QLabel(f"{msg1} {msg2}"))
        main_layout.addWidget(
            QLabel("Правильный порядок: 1-2 вверху, 3-4 внизу."))

        grid_container = QWidget()
        drop_grid = QGridLayout(grid_container)
        drop_grid.setSpacing(0)
        drop_grid.setContentsMargins(0, 0, 0, 0)
        self.drop_targets = []
        for r in range(2):
            row_list = []
            for c in range(2):
                label = DropLabel("Перетащите сюда", self)
                label.setFixedSize(105, 105)
                drop_grid.addWidget(label, r, c)
                row_list.append(label)
            self.drop_targets.append(row_list)

        centered_grid_layout = QHBoxLayout()
        centered_grid_layout.addStretch()
        centered_grid_layout.addWidget(grid_container)
        centered_grid_layout.addStretch()
        main_layout.addLayout(centered_grid_layout)

        self.source_container = QWidget()
        self.source_container.setFixedSize(430, 120)

        self.pieces = []
        source_ids = list(range(1, 5))
        random.shuffle(source_ids)

        for i in source_ids:
            pixmap = QPixmap(f"png/{i}.png").scaled(100, 100)
            img_label = ImageLabel(pixmap, i, self,
                                   parent=self.source_container)

            x = random.randint(0, self.source_container.width() - 100)
            y = random.randint(0, self.source_container.height() - 100)
            img_label.move(x, y)

            self.pieces.append({'widget': img_label})

        main_layout.addWidget(self.source_container)
        main_layout.addStretch()

        btn_layout = QHBoxLayout()
        check_btn = QPushButton("Проверить")
        check_btn.clicked.connect(self.check_captcha)
        reset_btn = QPushButton("Сбросить")
        reset_btn.clicked.connect(self.reset_captcha)
        btn_layout.addWidget(check_btn)
        btn_layout.addWidget(reset_btn)
        main_layout.addLayout(btn_layout)

        self.setLayout(main_layout)

    def check_captcha(self):
        correct_order = [['1', '2'], ['3', '4']]
        is_correct = True
        for r in range(2):
            for c in range(2):
                if self.drop_targets[r][c].image_id != correct_order[r][c]:
                    is_correct = False
                    break
            if not is_correct:
                break

        if is_correct:
            QMessageBox.information(self, "Успех",
                                    "Капча пройдена. Попробуйте войти снова.")
            self.login_window.reset_attempts()
            self.close()
        else:
            QMessageBox.warning(self, "Ошибка",
                                "Капча собрана неверно. Попробуйте еще раз.")
            self.reset_captcha()

    def reset_captcha(self):
        for row in self.drop_targets:
            for label in row:
                label.clear()
        for piece in self.pieces:
            widget = piece['widget']
            if widget.parent() != self.source_container:
                widget.setParent(self.source_container)
            x = random.randint(0, self.source_container.width() - 100)
            y = random.randint(0, self.source_container.height() - 100)
            widget.move(x, y)
            widget.setVisible(True)


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.main_window = None
        self.captcha_window = None
        self.login_attempts = 0
        self.setWindowTitle("Вход в Game of Life")
        self.setGeometry(300, 300, 300, 200)

        layout = QVBoxLayout()
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Логин")
        layout.addWidget(self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Пароль")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_input)

        login_btn = QPushButton("Войти")
        login_btn.clicked.connect(self.try_login)
        layout.addWidget(login_btn)

        register_btn = QPushButton("Регистрация")
        register_btn.clicked.connect(self.register)
        layout.addWidget(register_btn)

        self.setLayout(layout)

    def try_login(self):
        username = self.username_input.text()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "Ошибка",
                                "Логин и пароль не могут быть пустыми.")
            return

        if check_user(username, password):
            QMessageBox.information(self, "Успех", "Вход выполнен успешно!")
            self.hide()
            self.main_window = MainWindow()
            self.main_window.show()
        else:
            self.login_attempts += 1
            QMessageBox.warning(self, "Ошибка", "Неверный логин или пароль.")
            if self.login_attempts >= 3:
                self.show_captcha()

    def register(self):
        username = self.username_input.text()
        password = self.password_input.text()

        if not username or not password:
            msg = "Логин и пароль не могут быть пустыми для регистрации."
            QMessageBox.warning(self, "Ошибка", msg)
            return

        if add_user(username, password):
            QMessageBox.information(self, "Успех",
                                    "Пользователь успешно зарегистрирован.")
        else:
            QMessageBox.warning(self, "Ошибка",
                                "Пользователь с таким именем уже существует.")

    def show_captcha(self):
        if not self.captcha_window or not self.captcha_window.isVisible():
            self.captcha_window = CaptchaWindow(self)
            self.captcha_window.show()

    def reset_attempts(self):
        self.login_attempts = 0


class GameOfLifeWidget(QWidget):
    def __init__(self, mode='classic'):
        super().__init__()
        self.cell_size = 10
        self.width_cells = 80
        self.height_cells = 60
        self.grid = [[random.choice([0, 1]) for _ in range(self.width_cells)]
                     for _ in range(self.height_cells)]
        self.running = True
        self.generation = 0
        self.mode = mode
        self.speed_value = 100
        self.mode_label = mode
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_generation)
        self.timer.start(self.speed_value)

    def get_rules(self):
        rules = {
            'classic': {'survive': [2, 3], 'birth': 3},
            'supervisor': {'survive': [2, 3, 4, 5], 'birth': 3},
            'desert': {'survive': [3, 4, 5], 'birth': 4},
            'symbiosis': {'survive': [2, 3, 4], 'birth': 3}
        }
        return rules.get(self.mode, rules['classic'])

    def count_neighbors(self, r, c):
        count = 0
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                nr = (r + dr) % self.height_cells
                nc = (c + dc) % self.width_cells
                count += self.grid[nr][nc]
        return count

    def update_generation(self):
        if not self.running:
            return
        new_grid = [[0] * self.width_cells for _ in range(self.height_cells)]
        rules = self.get_rules()
        survive = rules['survive']
        birth = rules['birth']

        for r in range(self.height_cells):
            for c in range(self.width_cells):
                neighbors = self.count_neighbors(r, c)
                if self.grid[r][c] == 1:
                    if neighbors in survive:
                        new_grid[r][c] = 1
                else:
                    if neighbors == birth:
                        new_grid[r][c] = 1

        self.grid = new_grid
        self.generation += 1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0))

        for r in range(self.height_cells):
            for c in range(self.width_cells):
                if self.grid[r][c] == 1:
                    painter.fillRect(c * self.cell_size, r * self.cell_size,
                                     self.cell_size, self.cell_size,
                                     QColor(0, 255, 0))
                painter.drawRect(c * self.cell_size, r * self.cell_size,
                                 self.cell_size, self.cell_size)

        painter.setPen(QColor(0, 255, 0))
        painter.setFont(QFont("Arial", 10))
        painter.drawText(10, 20, f"Режим: {self.mode_label}")

    def set_mode(self, new_mode):
        self.mode = new_mode
        mode_names = {
            'classic': 'Классик',
            'supervisor': 'Супервайзер',
            'desert': 'Пустыня',
            'symbiosis': 'Симбиоз'
        }
        self.mode_label = mode_names.get(new_mode, 'Классик')
        self.update()

    def set_speed(self, speed):
        self.speed_value = 300 - speed
        self.timer.setInterval(self.speed_value)

    def toggle_pause(self):
        self.running = not self.running

    def reset_game(self):
        self.grid = [[random.choice([0, 1]) for _ in range(self.width_cells)]
                     for _ in range(self.height_cells)]
        self.generation = 0
        self.update()

    def clear_game(self):
        self.grid = [[0] * self.width_cells for _ in range(self.height_cells)]
        self.generation = 0
        self.update()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Game of Life")
        self.game_widget = GameOfLifeWidget('classic')

        central_widget = QWidget()
        main_layout = QVBoxLayout()

        main_layout.addWidget(self.game_widget, 1)

        btn_layout = QHBoxLayout()
        pause_btn = QPushButton("Пауза")
        pause_btn.clicked.connect(self.game_widget.toggle_pause)
        btn_layout.addWidget(pause_btn)

        reset_btn = QPushButton("Сброс")
        reset_btn.clicked.connect(self.game_widget.reset_game)
        btn_layout.addWidget(reset_btn)

        clear_btn = QPushButton("Очистить")
        clear_btn.clicked.connect(self.game_widget.clear_game)
        btn_layout.addWidget(clear_btn)

        classic_btn = QPushButton("Классик")
        classic_btn.clicked.connect(lambda: self.change_mode('classic'))
        btn_layout.addWidget(classic_btn)

        supervisor_btn = QPushButton("Супервайзер")
        supervisor_btn.clicked.connect(lambda: self.change_mode('supervisor'))
        btn_layout.addWidget(supervisor_btn)

        desert_btn = QPushButton("Пустыня")
        desert_btn.clicked.connect(lambda: self.change_mode('desert'))
        btn_layout.addWidget(desert_btn)

        symbiosis_btn = QPushButton("Симбиоз")
        symbiosis_btn.clicked.connect(lambda: self.change_mode('symbiosis'))
        btn_layout.addWidget(symbiosis_btn)

        main_layout.addLayout(btn_layout)

        slider_layout = QHBoxLayout()
        slider_layout.addWidget(QLabel("Скорость:"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setMinimum(50)
        self.speed_slider.setMaximum(280)
        self.speed_slider.setValue(100)
        self.speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.speed_slider.setTickInterval(25)
        self.speed_slider.valueChanged.connect(self.game_widget.set_speed)
        slider_layout.addWidget(self.speed_slider)
        main_layout.addLayout(slider_layout)

        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        self.setFixedSize(800, 700)

    def change_mode(self, mode):
        self.game_widget.set_mode(mode)


if __name__ == '__main__':
    create_database()
    app = QApplication(sys.argv)
    login_win = LoginWindow()
    login_win.show()
    sys.exit(app.exec())
