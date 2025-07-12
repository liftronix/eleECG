from scaled_ui.font_map import get_char_bitmap

def draw_char(oled, char, x, y, scale=2):
    bmp = get_char_bitmap(char)
    for row in range(8):
        line = bmp[row]
        for col in range(8):
            if (line >> (7 - col)) & 1:
                oled.fill_rect(x + col*scale, y + row*scale, scale, scale, 1)

def draw_text(oled, text, x=0, y=0, scale=2):
    max_cols = oled.width // (8 * scale)
    max_rows = oled.height // (8 * scale)
    line_height = 8 * scale

    oled.fill(0)

    lines = text.split('\n')  # explicit newlines first
    for row, line in enumerate(lines):
        if row >= max_rows:
            break
        for col, char in enumerate(line):
            if col >= max_cols:
                break
            draw_char(oled, char, x + col * 8 * scale, y + row * line_height, scale)

    oled.show()