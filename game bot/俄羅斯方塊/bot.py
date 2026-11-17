
"""
俄羅斯方塊自動遊玩程式

使用方式：
python tetris_bot_simple.py --check
python tetris_bot_simple.py --play
python tetris_bot_simple.py --demo

注意：
1. 座標是根據截圖暫時估計，必須先使用 --check 驗證。
2. 遊戲視窗大小和瀏覽器縮放比例必須固定。
3. --play 應從全新、空白的遊戲開始。
"""

import sys
import time
import os

import pyautogui
from PIL import ImageDraw


# ==========================================
# 1. 基本設定
# ==========================================

pyautogui.FAILSAFE = True

ROWS = 20
COLS = 10


# 棋盤左上角與右上角
BOARD_TOP_LEFT = (285, 240)
BOARD_TOP_RIGHT = (595, 240)

# NEXT 第一個方塊的辨識範圍
NEXT_TOP_LEFT = (625, 305)
NEXT_BOTTOM_RIGHT = (677, 342)


START_DELAY = 5
SETTLE_DELAY = 0.5
RETRY_DELAY = 0.2
RETRY_COUNT = 2
KEY_DELAY = 0.05

EMPTY_MAX_SUM = 140
COLOR_DISTANCE = 65
MIN_COLOR_PIXELS = 6
TOP_ROWS_TO_IGNORE = 4


# ==========================================
# 2. 方塊形狀
# ==========================================

SHAPES = {
    "I": [[1, 1, 1, 1]],
    "J": [[1, 0, 0], [1, 1, 1]],
    "L": [[0, 0, 1], [1, 1, 1]],
    "O": [[1, 1], [1, 1]],
    "S": [[0, 1, 1], [1, 1, 0]],
    "T": [[0, 1, 0], [1, 1, 1]],
    "Z": [[1, 1, 0], [0, 1, 1]],
}

COLORS = {
    "I": (0, 221, 242),
    "J": (0, 106, 254),
    "L": (254, 127, 0),
    "O": (255, 233, 2),
    "S": (8, 216, 10),
    "T": (171, 46, 204),
    "Z": (228, 33, 11),
}

START_COLS = {
    "I": [3, 5],
    "J": [3, 4, 3, 3],
    "L": [3, 4, 3, 3],
    "O": [4],
    "S": [3, 4],
    "T": [3, 4, 3, 3],
    "Z": [3, 4],
}


# ==========================================
# 3. 座標設定與棋盤讀取
# ==========================================

def check_settings():
    points = (
        BOARD_TOP_LEFT,
        BOARD_TOP_RIGHT,
        NEXT_TOP_LEFT,
        NEXT_BOTTOM_RIGHT,
    )

    if any(p is None for p in points):
        raise ValueError("請先設定所有座標。")

    if BOARD_TOP_RIGHT[0] <= BOARD_TOP_LEFT[0]:
        raise ValueError("棋盤右上角座標錯誤。")

    if abs(BOARD_TOP_RIGHT[1] - BOARD_TOP_LEFT[1]) > 2:
        raise ValueError("棋盤左右上角高度不一致。")

    if (
        NEXT_BOTTOM_RIGHT[0] <= NEXT_TOP_LEFT[0]
        or NEXT_BOTTOM_RIGHT[1] <= NEXT_TOP_LEFT[1]
    ):
        raise ValueError("NEXT 座標錯誤。")


def cell_center(row, col):
    size = (
        BOARD_TOP_RIGHT[0] - BOARD_TOP_LEFT[0]
    ) / COLS

    x = BOARD_TOP_LEFT[0] + (col + 0.5) * size
    y = BOARD_TOP_LEFT[1] + (row + 0.5) * size

    return round(x), round(y)


def read_board(image):
    board = []

    for row in range(ROWS):
        line = []

        for col in range(COLS):
            x, y = cell_center(row, col)
            rgb = image.getpixel((x, y))[:3]

            occupied = sum(rgb) > EMPTY_MAX_SUM
            line.append(1 if occupied else 0)

        board.append(line)

    return board


def read_next(image):
    votes = {name: 0 for name in COLORS}

    for y in range(
        NEXT_TOP_LEFT[1],
        NEXT_BOTTOM_RIGHT[1],
        2
    ):
        for x in range(
            NEXT_TOP_LEFT[0],
            NEXT_BOTTOM_RIGHT[0],
            2
        ):
            rgb = image.getpixel((x, y))[:3]

            for name, color in COLORS.items():
                distance = sum(
                    (rgb[i] - color[i]) ** 2
                    for i in range(3)
                )

                if distance <= COLOR_DISTANCE ** 2:
                    votes[name] += 1
                    break

    winner = max(votes, key=votes.get)

    if votes[winner] < MIN_COLOR_PIXELS:
        return None, votes

    return winner, votes


# ==========================================
# 4. 方塊旋轉與落點計算
# ==========================================

def rotate(shape):
    return [
        list(row)
        for row in zip(*shape[::-1])
    ]


def rotations(shape):
    result = []

    while shape not in result:
        result.append(shape)
        shape = rotate(shape)

    return result


def fits(board, shape, row, col):
    for r in range(len(shape)):
        for c in range(len(shape[0])):
            if shape[r][c]:
                y = row + r
                x = col + c

                if (
                    y < 0
                    or y >= ROWS
                    or x < 0
                    or x >= COLS
                    or board[y][x]
                ):
                    return False

    return True


def drop_row(board, shape, col):
    if not fits(board, shape, 0, col):
        return None

    row = 0

    while fits(board, shape, row + 1, col):
        row += 1

    return row


def place_and_clear(board, shape, row, col):
    new_board = [line[:] for line in board]

    for r in range(len(shape)):
        for c in range(len(shape[0])):
            if shape[r][c]:
                new_board[row + r][col + c] = 1

    remaining = [
        line for line in new_board
        if 0 in line
    ]

    cleared = ROWS - len(remaining)

    return (
        [[0] * COLS for _ in range(cleared)]
        + remaining,
        cleared,
    )


def count_holes(board):
    holes = 0

    for col in range(COLS):
        covered = False

        for row in range(ROWS):
            if board[row][col]:
                covered = True
            elif covered:
                holes += 1

    return holes


def choose_move(board, piece):
    best = None

    for turns, shape in enumerate(
        rotations(SHAPES[piece])
    ):
        for col in range(
            COLS - len(shape[0]) + 1
        ):
            row = drop_row(board, shape, col)

            if row is None:
                continue

            after, cleared = place_and_clear(
                board, shape, row, col
            )

            score = (
                row
                + 100 * cleared
                - 50 * count_holes(after)
            )

            if best is None or score > best[0]:
                best = (
                    score,
                    turns,
                    col,
                    row,
                    after,
                )

    return best


# ==========================================
# 5. 自動按鍵
# ==========================================

def send_move(piece, turns, col):
    for _ in range(turns):
        pyautogui.press("up")
        time.sleep(KEY_DELAY)

    distance = (
        col - START_COLS[piece][turns]
    )

    direction = (
        "right" if distance > 0 else "left"
    )

    for _ in range(abs(distance)):
        pyautogui.press(direction)
        time.sleep(KEY_DELAY)

    pyautogui.press("space")


# ==========================================
# 6. 顯示棋盤
# ==========================================

def show_board(board):
    print("   0123456789")

    for row, line in enumerate(board):
        symbols = "".join(
            "#" if cell else "."
            for cell in line
        )

        print(f"{row:2} {symbols}")


def check_board(expected):
    for attempt in range(RETRY_COUNT + 1):
        actual = read_board(
            pyautogui.screenshot()
        )

        if (
            actual[TOP_ROWS_TO_IGNORE:]
            == expected[TOP_ROWS_TO_IGNORE:]
        ):
            return True, actual

        if attempt < RETRY_COUNT:
            time.sleep(RETRY_DELAY)

    return False, actual


def countdown():
    print(
        f"{START_DELAY} 秒後開始，"
        "請切回遊戲畫面。"
    )
    time.sleep(START_DELAY)


# ==========================================
# 7. 偵測範圍視覺化（新增）
# ==========================================

def inspect_screen():
    countdown()

    image = pyautogui.screenshot()
    board = read_board(image)
    piece, votes = read_next(image)

    # 先印出辨識結果
    print("\n========== 棋盤辨識 ==========")
    show_board(board)

    print("\n========== NEXT 辨識 ==========")
    print("NEXT 方塊：", piece)
    print("顏色票數：", votes)

    # 複製截圖，在上面畫輔助線
    debug_image = image.copy()
    draw = ImageDraw.Draw(debug_image)

    cell_size = (
        BOARD_TOP_RIGHT[0] - BOARD_TOP_LEFT[0]
    ) / COLS

    board_bottom = (
        BOARD_TOP_LEFT[1]
        + ROWS * cell_size
    )

    # 紅框：棋盤
    draw.rectangle(
        [
            BOARD_TOP_LEFT,
            (
                BOARD_TOP_RIGHT[0],
                round(board_bottom),
            ),
        ],
        outline="red",
        width=3,
    )

    # 黃點：200 個格子中心
    for row in range(ROWS):
        for col in range(COLS):
            x, y = cell_center(row, col)

            draw.ellipse(
                (
                    x - 2,
                    y - 2,
                    x + 2,
                    y + 2,
                ),
                fill="yellow",
            )

    # 藍框：NEXT 偵測區域
    draw.rectangle(
        [
            NEXT_TOP_LEFT,
            NEXT_BOTTOM_RIGHT,
        ],
        outline="blue",
        width=3,
    )

    # 儲存到程式所在的資料夾
    folder = os.path.dirname(
        os.path.abspath(__file__)
    )

    file_path = os.path.join(
        folder,
        "tetris_debug.png"
    )

    debug_image.save(file_path)

    print("\n========== 偵測圖片 ==========")
    print("圖片位置：")
    print(file_path)

    print("\n紅框：棋盤範圍")
    print("黃點：每一格的中心")
    print("藍框：NEXT 偵測範圍")


# ==========================================
# 8. 自動遊玩
# ==========================================

def play():
    countdown()

    image = pyautogui.screenshot()
    board = read_board(image)

    if any(
        any(line)
        for line in board[TOP_ROWS_TO_IGNORE:]
    ):
        print(
            "棋盤不是空的，"
            "請重新開始遊戲並檢查座標。"
        )
        return

    current, _ = read_next(image)

    if current is None:
        print(
            "NEXT 辨識失敗，"
            "請先使用 --check。"
        )
        return

    print(
        f"記住下一塊 {current}，"
        "先讓第一塊落下。"
    )

    pyautogui.press("space")
    time.sleep(SETTLE_DELAY)

    board = read_board(
        pyautogui.screenshot()
    )

    count = sum(
        sum(line)
        for line in board[TOP_ROWS_TO_IGNORE:]
    )

    if count != 4:
        print(
            f"第一塊落地後讀到 {count} 格，"
            "預期是 4 格，停止。"
        )
        return

    board[:TOP_ROWS_TO_IGNORE] = [
        [0] * COLS
        for _ in range(TOP_ROWS_TO_IGNORE)
    ]

    while True:
        image = pyautogui.screenshot()

        next_piece, _ = read_next(image)

        if next_piece is None:
            print("無法辨識下一塊，停止。")
            return

        move = choose_move(board, current)

        if move is None:
            print("沒有可放的位置。")
            return

        score, turns, col, row, expected = move

        print(
            f"{current}："
            f"旋轉 {turns} 次，"
            f"第 {col} 欄，"
            f"第 {row} 列，"
            f"評分 {score}",
            flush=True,
        )

        send_move(current, turns, col)
        time.sleep(SETTLE_DELAY)

        if any(
            any(line)
            for line in expected[:TOP_ROWS_TO_IGNORE]
        ):
            print("方塊接近頂端，停止。")
            return

        matches, actual = check_board(expected)

        if not matches:
            print("\n實際盤面與預測不一致。")

            print("\n預測盤面：")
            show_board(expected)

            print("\n實際盤面：")
            show_board(actual)

            return

        board = expected
        current = next_piece


# ==========================================
# 9. 測試模式
# ==========================================

def demo():
    board = [
        [0] * COLS
        for _ in range(ROWS)
    ]

    board[-1] = [
        1, 1, 1, 0, 0,
        0, 1, 1, 1, 1
    ]

    print("測試前：")
    show_board(board)

    move = choose_move(board, "T")

    if move is None:
        print("沒有可放的位置。")
        return

    score, turns, col, row, after = move

    print(
        f"T 方塊：旋轉 {turns} 次，"
        f"第 {col} 欄，第 {row} 列，"
        f"評分 {score}"
    )

    print("\n測試後：")
    show_board(after)


# ==========================================
# 10. 主程式
# ==========================================

if __name__ == "__main__":
    try:
        if len(sys.argv) == 1:
            demo()

        elif sys.argv[1:] == ["--check"]:
            check_settings()
            inspect_screen()

        elif sys.argv[1:] == ["--play"]:
            check_settings()
            play()

        elif sys.argv[1:] == ["--demo"]:
            demo()

        else:
            print(
                "使用方式：\n"
                "python tetris_bot_simple.py --check\n"
                "python tetris_bot_simple.py --play\n"
                "python tetris_bot_simple.py --demo"
            )

    except (
        pyautogui.FailSafeException,
        KeyboardInterrupt,
    ):
        print("\n程式已停止。")

    except ValueError as error:
        print("設定錯誤：", error)
