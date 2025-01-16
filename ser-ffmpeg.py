#!/usr/bin/env python
# SER ファイルをフレームカウント指定で切り出して ffmpeg でエンコードします。
# 事前に ffmpeg をインストールしてパスを通しておく必要があります。
# 例: ser-ffmpeg.py foo.ser 123 456 29.97 -c:v libx264 -crf 17 test-h264.mp4
# 5つ目以降のコマンドライン引数は ffmpeg にそのまま渡されます。

import argparse
import os
import sys
import subprocess
import traceback
import platform
import datetime
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

# Only for RAW8 or RAW16 file of bayer color camera.
class SerVideo:
    EPOCH = datetime.datetime(1, 1, 1, tzinfo=datetime.timezone.utc)
    BAYER_PATTERNS = {
        0: cv2.COLOR_GRAY2RGB,
        8: cv2.COLOR_BAYER_RGGB2RGB,
        9: cv2.COLOR_BAYER_GRBG2RGB,
        10: cv2.COLOR_BAYER_GBRG2RGB,
        11: cv2.COLOR_BAYER_BGGR2RGB
    }
    def read_int(self, f, n):
        return int.from_bytes(f.read(n), 'little')
    def int_to_timestamp(self, t8):
        return self.EPOCH + datetime.timedelta(microseconds=t8/10)
    def read_timestamp(self, f):
        return self.int_to_timestamp(self.read_int(f, 8))

    def __init__(self, input):
        f = open(input, "rb")
        file_id = f.read(14).decode(encoding='utf-8')
        lu_id = self.read_int(f, 4)
        self.color_id = self.read_int(f, 4)
        self.little_endian = self.read_int(f, 4)
        self.image_width = self.read_int(f, 4)
        self.image_height = self.read_int(f, 4)
        self.pixel_depth = self.read_int(f, 4)
        self.frame_count = self.read_int(f, 4)
        self.observer = f.read(40).decode(encoding='utf-8')
        self.instrume = f.read(40).decode(encoding='utf-8')
        self.telescope = f.read(40).decode(encoding='utf-8')
        self.date_time = self.read_int(f, 8)
        self.date_time_utc = self.read_int(f, 8)

        if self.date_time == 0:
            raise RuntimeError(f"SER file '{input}' has no frame timestamps.")

        self.frame_length = \
            self.image_width * self.image_height * self.pixel_depth//8
        if self.pixel_depth == 8:
            self.dtype = np.dtype('u1')
        elif self.pixel_depth == 16:
            self.dtype = np.dtype('u2')
        else:
            raise RuntimeError(f"Unsupported pixel depth: {self.pixel_depth}")

        if self.little_endian == 0:
            self.dtype = self.dtype.newbyteorder('>')
        else:
            self.dtype = self.dtype.newbyteorder('<')
        
        self.timestamps = []
        f.seek(178 + self.frame_count * self.frame_length)
        for p in range(self.frame_count):
            self.timestamps.append(self.read_timestamp(f))
        self.f = f

    def timestamp_of_frame_number(self, frame_number):
        return self.timestamps[frame_number - 1]

    def image_of_frame_number(self, frame_number):
        self.f.seek(178 + (frame_number - 1) * self.frame_length)
        array = np.frombuffer(self.f.read(self.frame_length), dtype=self.dtype)
        image_array = np.reshape(array, (self.image_height, self.image_width))
        cv2_image = cv2.cvtColor(image_array, self.BAYER_PATTERNS[self.color_id])
        return cv2_image

    def close(self):
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self):
        self.close()

FONTS = {
    "Linux": "Courier_New.ttf",
    "Windows": "cour.ttf",
    "Darwin": "Courier.ttc"
}
TEXT_ANCHORS = {
    "top-left": "la",
    "top-middle": "ma",
    "top-right": "ra",
    "bottom-left": "ld",
    "bottom-middle": "md",
    "bottom-right": "rd"
}

LOCAL_TZ = datetime.datetime.now().astimezone().tzinfo

def get_font(font_filename, font_size):
    if font_filename is None:
        if platform.system() not in FONTS:
            abort("ERROR: Default font of OS is not detected."\
                  " Please specify font filename with --font.")
        else:
            font_filename = FONTS[platform.system()]
    
    return ImageFont.truetype(font_filename, font_size)

def test_text_position(pos):
    if pos not in TEXT_ANCHORS:
        pos_keys = None
        for pos_key in TEXT_ANCHORS.keys():
            if pos_keys is None:
                pos_keys = ""
            else:
                pos_keys += ", "
            pos_keys += f"'{pos_key}'"
        abort(f"ERROR: Unknown text position: '{pos}'. Specify {pos_keys}.")
    return True
    
def get_text_position(pos, width, height, margin_x, margin_y):
    if pos =="top-left":
        return (margin_x, margin_y)
    elif pos == "top-middle":
        return (width/2, 0 + margin_y)
    elif pos == "top-right":
        return (width - margin_x, margin_y)
    elif pos == "bottom-left":
        return (margin_x, height - margin_y)
    elif pos == "bottom-middle":
        return (width/2, height - margin_y)
    elif pos == "bottom-right":
        return (width - margin_x , height - margin_y)
    else:
        return None

def draw_timestamp(draw, t, pos, anchor, font, color):
    t_str = f"{str(t)}"
    draw.text(pos, f"{t_str}", fill=color, font=font, anchor=anchor)

def scale_to_16bit(canvas_16, channel_index):
    return canvas_16[..., channel_index] * 257

def split_channel(image_16, channel_index):
    return image_16[..., channel_index]

def blend_channel(fg, alpha, bg):
    return (alpha/65535 * fg + (65535 - alpha)/65535 * bg).astype(np.uint16)

def alpha_blending(canvas_8, image):
    canvas_16 = np.array(canvas_8, dtype=np.uint16)
    canvas_r = scale_to_16bit(canvas_16, 0)
    canvas_g = scale_to_16bit(canvas_16, 1)
    canvas_b = scale_to_16bit(canvas_16, 2)
    canvas_a = scale_to_16bit(canvas_16, 3)
    image_r = split_channel(image, 0)
    image_g = split_channel(image, 1)
    image_b = split_channel(image, 2)
    image_r = blend_channel(canvas_r, canvas_a, image_r)
    image_g = blend_channel(canvas_g, canvas_a, image_g)
    image_b = blend_channel(canvas_b, canvas_a, image_b)
    return np.stack((image_r, image_g, image_b), axis=-1)

parser = argparse.ArgumentParser()
parser.add_argument("ser_file", 
                    help="SER file.")
parser.add_argument("start", type=int,
                    help="start frame count.")
parser.add_argument("end", type=int,
                    help="end frame count.")
parser.add_argument("framerate",
                    help="framerate of SER.")
parser.add_argument("--speed", type=int, default=1,
                    help="skip frames for Nx speed.")
parser.add_argument("--ffplay", action="store_true",
                    help="exec ffplay instead of ffmpeg.")

parser.add_argument("--no-timestamp", action="store_true",
                    help="do not draw timestamps")
parser.add_argument("--timestamp-only", action="store_true",
                    help="output frames with only timestamps drawn.")
parser.add_argument("--localtime", action="store_true",
                    help="draw timestamps in local time.")
parser.add_argument("--font", default=None,
                    help="Font filename of timestamps.")
parser.add_argument("--font-size", type=int, default=24,
                    help="Font size (pixels) of timestamps.")
parser.add_argument("--font-color", default="#FF8800C0",
                    help="Font color of timestamps.")
parser.add_argument("--timestamp-position", default="top-left",
                    help="Position of timestamps. The options 'top-left',"\
                    " 'top-middle', 'top-right', 'bottom-left', 'bottom-middle',"\
                    " and 'bottom-right' can be specified.")
parser.add_argument("--timestamp-margin", nargs=2, type=int, default=[0,0],
                    help="x and y margin width (pixels) of timestamps.")
args, ffmpeg_args = parser.parse_known_args()

if args.no_timestamp and args.timestamp_only:
    abort("ERROR: --no-timestamp and --timestamp-only are exclusive options.")

ser = SerVideo(args.ser_file)
pix_fmt = None
if args.timestamp_only:
    pix_fmt = "rgba"
else:
    if ser.pixel_depth == 8:
        pix_fmt = "rgb24"
    elif ser.pixel_depth == 16:
        pix_fmt = "rgb48"

if pix_fmt is None:
    sys.exit(f"ERROR: unsupported pixel depth: {ser.pixel_depth}")
if not ser.color_id in ser.BAYER_PATTERNS:
    sys.exit(f"ERROR: unsupported SER color id: {ser.color_id}")
if args.start <= 0 or ser.frame_count < args.start:
    sys.exit(f"ERROR: invalid `start` value "\
             f"(valid range: 1-{ser.framecount}).")
if ser.frame_count < args.end or args.end < args.start:
    sys.exit(f"ERROR: invalid `end` value "\
             f"(valid range: {args.start}-{ser.frame_count}).")

font = None
font_color = None
text_pos = None
text_anchor = None
if not args.no_timestamp:
    test_text_position(args.timestamp_position)
    text_anchor = TEXT_ANCHORS[args.timestamp_position]
    text_pos = get_text_position(args.timestamp_position,
                                 ser.image_width,
                                 ser.image_height,
                                 args.timestamp_margin[0],
                                 args.timestamp_margin[1])
    font = get_font(args.font, args.font_size)
    font_color = args.font_color

ffmpeg = "ffmpeg"
if args.ffplay:
    ffmpeg = "ffplay"
ffmpeg_cmd = [ffmpeg,
              "-f", "rawvideo",
              "-pixel_format", pix_fmt,
              "-s", f"{ser.image_width}x{ser.image_height}",
              "-framerate", args.framerate,
              "-i", "-"]
ffmpeg_cmd.extend(ffmpeg_args)
ffmpeg_process = subprocess.Popen(ffmpeg_cmd,
                                  stdin=subprocess.PIPE,
                                  stdout=sys.stdout,
                                  stderr=sys.stderr)
try:
    for i in range(args.start, args.end + 1):
        if (i - args.start) % args.speed != 0:
            continue
        image = None
        if args.no_timestamp:
            image = ser.image_of_frame_number(i)
        else:
            if pix_fmt == "rgb24":
                canvas = Image.fromarray(ser.image_of_frame_number(i))
            else:
                canvas = Image.new(mode="RGBA", color="#00000000",
                                   size=(ser.image_width, ser.image_height))
            draw = ImageDraw.Draw(canvas)
            t = ser.timestamp_of_frame_number(i)
            if args.localtime:
                t = t.astimezone(LOCAL_TZ)
            draw_timestamp(draw, t, text_pos, text_anchor, font, font_color)
            if pix_fmt == "rgb48":
                image = alpha_blending(canvas, ser.image_of_frame_number(i))
            else:
                image = np.array(canvas)
        
        ffmpeg_process.stdin.write(image.tobytes())
    
except Exception as e:
    print(f"ERROR: {e}")
    print(traceback.format_exc())
finally:
    ser.close()
    if ffmpeg_process.poll() is None:
        ffmpeg_process.stdin.close()
        ffmpeg_process.wait()
        ffmpeg_process.terminate()
