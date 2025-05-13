#!/usr/bin/env python3
import time
import os
import threading
from PIL import Image, ImageDraw, ImageFont
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from evdev import InputDevice, categorize, ecodes
import RPi.GPIO as GPIO

class DirectTestCounter:
    def __init__(self, logo_path="/home/dietpi/logo.png", debounce_time=0.5):
        self.count = 0
        self.logo_path = logo_path
        self.debounce_time = debounce_time
        self.last_hit_time = time.time()
        self.mode = "beam"
        self.flashing = False
        self.input_buffer = ""
        self.last_flash_time = 0
        self.flash_interval = 0.5

        self.beam_pins = [26, 16, 5, 6]
        GPIO.setmode(GPIO.BCM)
        for pin in self.beam_pins:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        self.options = RGBMatrixOptions()
        self.options.rows = 64
        self.options.cols = 64
        self.options.chain_length = 1
        self.options.parallel = 1
        self.options.hardware_mapping = 'regular'
        self.options.gpio_slowdown = 5
        self.options.brightness = 100
        self.options.disable_hardware_pulsing = True

        self.matrix = RGBMatrix(options=self.options)
        self.canvas = self.matrix.CreateFrameCanvas()

        self.font = None
        self.font_size = 56
        self.text_color = (214, 160, 255)
        self.font_path = '/usr/share/fonts/truetype/Inter/Inter-Italic-VariableFont_opszwght.ttf'

        try:
            if os.path.exists(self.font_path):
                self.font = ImageFont.truetype(self.font_path, self.font_size)
                print(f"Loaded font: {self.font_path}")
            else:
                raise FileNotFoundError("Inter font not found")
        except Exception as e:
            print(f"Error loading font: {e}")
            print("Falling back to default font.")
            self.font = ImageFont.load_default()

    def init(self):
        print("Starting test hit counter...")
        if os.path.exists(self.logo_path):
            print(f"Displaying startup logo: {self.logo_path}")
            self.display_image(self.logo_path)
        else:
            print(f"Logo file not found: {self.logo_path}")
        self.display_number(0)

    def run(self):
        try:
            self.init()
            kb_thread = threading.Thread(target=self.check_for_keyboard_input)
            kb_thread.daemon = True
            kb_thread.start()
            print("Counter started.")

            while True:
                current_time = time.time()
                if current_time - self.last_hit_time > self.debounce_time:
                    for pin in self.beam_pins:
                        if GPIO.input(pin) == GPIO.LOW:
                            self.increment_counter()
                            break
                time.sleep(0.01)

        except KeyboardInterrupt:
            print("Program interrupted")
        finally:
            self.cleanup()

    def cleanup(self):
        print(f"Final count: {self.count}")
        self.canvas.Clear()
        self.matrix.SwapOnVSync(self.canvas)
        GPIO.cleanup()

    def check_for_keyboard_input(self):
        device_path = '/dev/input/event0'
        try:
            dev = InputDevice(device_path)
            print(f"Listening for keypresses from: {device_path}")
        except Exception as e:
            print(f"Failed to open device at {device_path}: {e}")
            return

        for event in dev.read_loop():
            if event.type == ecodes.EV_KEY:
                key_event = categorize(event)
                if key_event.keystate == key_event.key_down:
                    keycode = key_event.keycode
                    print(f"Key pressed: {keycode}")
                    if keycode == 'KEY_KPPLUS':
                        self.decrement_counter()
                    elif keycode in ('KEY_EQUAL', 'KEY_KPMINUS'):
                        self.increment_counter()
                    elif keycode in ('KEY_SLASH', 'KEY_KPSLASH'):
                        self.display_number("/")
                    elif keycode in ('KEY_0', 'KEY_KP0'):
                        self.count = 0
                        self.update_display()

    def increment_counter(self):
        current_time = time.time()
        if current_time - self.last_hit_time > self.debounce_time:
            self.count += 1
            self.last_hit_time = current_time
            print(f"Increment! Count: {self.count}")
            self.update_display()

    def decrement_counter(self):
        current_time = time.time()
        if current_time - self.last_hit_time > self.debounce_time:
            self.count -= 1
            self.last_hit_time = current_time
            print(f"Decrement! Count: {self.count}")
            self.update_display()

    def update_display(self):
        self.display_number(self.count)

    def display_image(self, image_path, duration=None):
        try:
            if not os.path.exists(image_path):
                print(f"Image not found: {image_path}")
                return False

            img = Image.open(image_path).convert('RGB')
            img.thumbnail((self.matrix.width, self.matrix.height), Image.LANCZOS)

            width, height = img.size
            x_offset = (self.matrix.width - width) // 2
            y_offset = (self.matrix.height - height) // 2

            temp_canvas = self.matrix.CreateFrameCanvas()
            temp_canvas.Clear()
            temp_canvas.SetImage(img, x_offset, y_offset)
            self.canvas = self.matrix.SwapOnVSync(temp_canvas)

            if duration:
                time.sleep(duration)

            return True

        except Exception as e:
            print(f"Error displaying image: {e}")
            return False

    def display_number(self, number):
        if str(number) == "0":
            print("Count is 0 — displaying logo instead of 0")
            self.display_image(self.logo_path)
            return

        img = Image.new('RGB', (self.matrix.width, self.matrix.height), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        text = str(number)

        max_font_size = 60
        min_font_size = 10
        font_size = max_font_size

        while font_size >= min_font_size:
            font = ImageFont.truetype(self.font_path, font_size)
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            if text_width <= self.matrix.width and text_height <= self.matrix.height:
                break
            font_size -= 1

        x_position = (self.matrix.width - text_width) // 2
        bbox_top = text_bbox[1]
        y_position = (self.matrix.height - text_height) // 2 - bbox_top

        print(f"Auto font size: {font_size}, Text: {text}, Pos: ({x_position}, {y_position})")

        draw.text((x_position, y_position), text, font=font, fill=self.text_color)
        self.canvas.SetImage(img)
        self.canvas = self.matrix.SwapOnVSync(self.canvas)

if __name__ == "__main__":
    counter = DirectTestCounter()
    counter.run()
