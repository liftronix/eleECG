def get_char_bitmap(char):
    lookup = {
        " ": [0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00],
        "!": [0x18,0x3C,0x3C,0x18,0x18,0x00,0x18,0x00],
        "\"": [0x66,0x66,0x24,0x00,0x00,0x00,0x00,0x00],
        "#": [0x36,0x36,0x7F,0x36,0x7F,0x36,0x36,0x00],
        "$": [0x18,0x3E,0x60,0x3C,0x06,0x7C,0x18,0x00],
        "%": [0x66,0x66,0x0C,0x18,0x30,0x66,0x66,0x00],
        "&": [0x38,0x6C,0x38,0x76,0xDC,0xCC,0x76,0x00],
        "'": [0x0C,0x0C,0x18,0x00,0x00,0x00,0x00,0x00],
        "(": [0x0C,0x18,0x30,0x30,0x30,0x18,0x0C,0x00],
        ")": [0x30,0x18,0x0C,0x0C,0x0C,0x18,0x30,0x00],
        "*": [0x00,0x66,0x3C,0xFF,0x3C,0x66,0x00,0x00],
        "+": [0x00,0x18,0x18,0x7E,0x18,0x18,0x00,0x00],
        ",": [0x00,0x00,0x00,0x00,0x18,0x18,0x30,0x00],
        "-": [0x00,0x00,0x00,0x7E,0x00,0x00,0x00,0x00],
        ".": [0x00,0x00,0x00,0x00,0x18,0x18,0x00,0x00],
        "/": [0x06,0x0C,0x18,0x30,0x60,0xC0,0x80,0x00],
        "0": [0x3C,0x66,0x6E,0x76,0x66,0x66,0x3C,0x00],
        "1": [0x18,0x38,0x18,0x18,0x18,0x18,0x7E,0x00],
        "2": [0x3C,0x66,0x06,0x0C,0x18,0x30,0x7E,0x00],
        "3": [0x3C,0x66,0x06,0x1C,0x06,0x66,0x3C,0x00],
        "4": [0x0C,0x1C,0x3C,0x6C,0x7E,0x0C,0x0C,0x00],
        "5": [0x7E,0x60,0x7C,0x06,0x06,0x66,0x3C,0x00],
        "6": [0x1C,0x30,0x60,0x7C,0x66,0x66,0x3C,0x00],
        "7": [0x7E,0x06,0x0C,0x18,0x30,0x30,0x30,0x00],
        "8": [0x3C,0x66,0x66,0x3C,0x66,0x66,0x3C,0x00],
        "9": [0x3C,0x66,0x66,0x3E,0x06,0x0C,0x38,0x00],
        ":": [0x00,0x18,0x18,0x00,0x00,0x18,0x18,0x00],
        ";": [0x00,0x18,0x18,0x00,0x18,0x18,0x30,0x00],
        "<": [0x0C,0x18,0x30,0x60,0x30,0x18,0x0C,0x00],
        "=": [0x00,0x7E,0x00,0x7E,0x00,0x7E,0x00,0x00],
        ">": [0x30,0x18,0x0C,0x06,0x0C,0x18,0x30,0x00],
        "?": [0x3C,0x66,0x06,0x0C,0x18,0x00,0x18,0x00],
        "@": [0x3C,0x66,0x6E,0x6A,0x6E,0x60,0x3C,0x00],
        "A": [0x18,0x3C,0x66,0x66,0x7E,0x66,0x66,0x00],
        "B": [0x7C,0x66,0x66,0x7C,0x66,0x66,0x7C,0x00],
        "C": [0x3C,0x66,0x60,0x60,0x60,0x66,0x3C,0x00],
        "D": [0x78,0x6C,0x66,0x66,0x66,0x6C,0x78,0x00],
        "E": [0x7E,0x60,0x60,0x7C,0x60,0x60,0x7E,0x00],
        "F": [0x7E,0x60,0x60,0x7C,0x60,0x60,0x60,0x00],
        "G": [0x3C,0x66,0x60,0x6E,0x66,0x66,0x3C,0x00],
        "H": [0x66,0x66,0x66,0x7E,0x66,0x66,0x66,0x00],
        "I": [0x3C,0x18,0x18,0x18,0x18,0x18,0x3C,0x00],
        "J": [0x1E,0x0C,0x0C,0x0C,0x0C,0x6C,0x38,0x00],
        "K": [0x66,0x6C,0x78,0x70,0x78,0x6C,0x66,0x00],
        "L": [0x60,0x60,0x60,0x60,0x60,0x60,0x7E,0x00],
        "M": [0x63,0x77,0x7F,0x6B,0x63,0x63,0x63,0x00],
        "N": [0x66,0x76,0x7E,0x7E,0x6E,0x66,0x66,0x00],
        "O": [0x3C,0x66,0x66,0x66,0x66,0x66,0x3C,0x00],
        "P": [0x7C,0x66,0x66,0x7C,0x60,0x60,0x60,0x00],
        "Q": [0x3C,0x66,0x66,0x66,0x66,0x6C,0x36,0x00],
        "R": [0x7C,0x66,0x66,0x7C,0x78,0x6C,0x66,0x00],
        "S": [0x3C,0x66,0x60,0x3C,0x06,0x66,0x3C,0x00],
        "T": [0x7E,0x5A,0x18,0x18,0x18,0x18,0x3C,0x00],
        "U": [0x66,0x66,0x66,0x66,0x66,0x66,0x3C,0x00],
        "V": [0x66,0x66,0x66,0x66,0x66,0x3C,0x18,0x00],
        "W": [0x63,0x63,0x63,0x6B,0x7F,0x77,0x63,0x00],
        "X": [0x66,0x66,0x3C,0x18,0x3C,0x66,0x66,0x00],
        "Y": [0x66,0x66,0x3C,0x18,0x18,0x18,0x3C,0x00],
        "Z": [0x7E,0x06,0x0C,0x18,0x30,0x60,0x7E,0x00],
        "[": [0x3C,0x30,0x30,0x30,0x30,0x30,0x3C,0x00],
        "\\": [0xC0,0x60,0x30,0x18,0x0C,0x06,0x02,0x00],
        "]": [0x3C,0x0C,0x0C,0x0C,0x0C,0x0C,0x3C,0x00],
        "^": [0x08,0x1C,0x36,0x63,0x00,0x00,0x00,0x00],
        "_": [0x00,0x00,0x00,0x00,0x00,0x00,0x7E,0x00],
        "`": [0x30,0x18,0x0C,0x00,0x00,0x00,0x00,0x00],
        "a": [0x00,0x00,0x3C,0x06,0x3E,0x66,0x3E,0x00],
        "b": [0x60,0x60,0x7C,0x66,0x66,0x66,0x7C,0x00],
        "c": [0x00,0x00,0x3C,0x66,0x60,0x66,0x3C,0x00],
        "d": [0x06,0x06,0x3E,0x66,0x66,0x66,0x3E,0x00],
        "e": [0x00,0x00,0x3C,0x66,0x7E,0x60,0x3C,0x00],
        "f": [0x0E,0x18,0x7E,0x18,0x18,0x18,0x18,0x00],
        "g": [0x00,0x00,0x3E,0x66,0x66,0x3E,0x06,0x3C],
        "h": [0x60,0x60,0x7C,0x66,0x66,0x66,0x66,0x00],
        "i": [0x18,0x00,0x38,0x18,0x18,0x18,0x3C,0x00],
        "j": [0x0C,0x00,0x1C,0x0C,0x0C,0x0C,0x6C,0x38],
        "k": [0x60,0x60,0x66,0x6C,0x78,0x6C,0x66,0x00],
        "l": [0x38,0x18,0x18,0x18,0x18,0x18,0x3C,0x00],
        "m": [0x00,0x00,0x6C,0x7E,0x6B,0x6B,0x6B,0x00],
        "n": [0x00,0x00,0x7C,0x66,0x66,0x66,0x66,0x00],
        "o": [0x00,0x00,0x3C,0x66,0x66,0x66,0x3C,0x00],
        "p": [0x00,0x00,0x7C,0x66,0x66,0x7C,0x60,0x60],
        "q": [0x00,0x00,0x3E,0x66,0x66,0x3E,0x06,0x06],
        "r": [0x00,0x00,0x6C,0x76,0x60,0x60,0x60,0x00],
        "s": [0x00,0x00,0x3E,0x60,0x3C,0x06,0x7C,0x00],
        "t": [0x10,0x10,0x7C,0x10,0x10,0x10,0x0E,0x00],
        "u": [0x00,0x00,0x66,0x66,0x66,0x66,0x3E,0x00],
        "v": [0x00,0x00,0x66,0x66,0x66,0x3C,0x18,0x00],
        "w": [0x00,0x00,0x63,0x6B,0x7F,0x36,0x36,0x00],
        "x": [0x00,0x00,0x66,0x3C,0x18,0x3C,0x66,0x00],
        "y": [0x00,0x00,0x66,0x66,0x66,0x3E,0x06,0x3C],
        "z": [0x00,0x00,0x7E,0x0C,0x18,0x30,0x7E,0x00],
        "{": [0x0E,0x18,0x18,0x70,0x18,0x18,0x0E,0x00],
        "|": [0x18,0x18,0x18,0x18,0x18,0x18,0x18,0x00],
        "}": [0x70,0x18,0x18,0x0E,0x18,0x18,0x70,0x00],
        "~": [0x3B,0x6E,0x00,0x00,0x00,0x00,0x00,0x00],
        " ": [0x00] * 8
    }
    return lookup.get(char.upper(), lookup[" "])
