import pyautogui
import time
print('開始抓取！按 Ctrl+C 停止')
while True:
    x, y = pyautogui.position()
    print(f'X: {x}, Y: {y} | RGB: {pyautogui.pixel(x, y)}')
    time.sleep(1)
