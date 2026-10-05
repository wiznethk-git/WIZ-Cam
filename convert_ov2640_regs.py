"""Convert active uint8_t[][2] tables in ov2640_regs.h to Python.

Run from the repository root:

    python gen/convert_ov2640_regs.py
"""

from pathlib import Path
import re


SOURCE = Path("ov2640_regs.h")
OUTPUT = Path("gen/ov2640_regs.py")


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//.*", "", text)


def parse_tables(text):
    clean = strip_comments(text)
    pattern = re.compile(
        r"static\s+const\s+uint8_t\s+(\w+)\s*\[\]\s*\[2\]\s*=\s*\{"
        r"(.*?)\}\s*;",
        re.S,
    )
    tables = []
    for name, body in pattern.findall(clean):
        numbers = [int(value, 0) for value in re.findall(r"0[xX][0-9a-fA-F]+|\d+", body)]
        if len(numbers) % 2:
            raise ValueError("{} contains an odd number of bytes".format(name))
        tables.append((name.upper(), list(zip(numbers[::2], numbers[1::2]))))
    return tables


def render(tables):
    lines = [
        '"""Generated OV2640 register tables; do not reorder writes.',
        "",
        "Source: ov2640_regs.h. Regenerate with gen/convert_ov2640_regs.py.",
        '"""',
        "",
    ]
    for name, pairs in tables:
        lines.append("{} = [".format(name))
        lines.extend("    (0x{:02X}, 0x{:02X}),".format(reg, cmd) for reg, cmd in pairs)
        lines.extend(("]", ""))

    resolution_names = {
        "OV2640_UXGA_1280X960": (1280, 960),
        "OV2640_UXGA_1024X768": (1024, 768),
        "OV2640_SVGA_800X600": (800, 600),
        "OV2640_SVGA_640X480": (640, 480),
        "OV2640_CIF_400X296": (400, 296),
        "OV2640_CIF_320X240": (320, 240),
        "OV2640_CIF_176X144": (176, 144),
    }
    present = {name for name, _ in tables}
    lines.extend(("RESOLUTION_TABLES = {",))
    for name, size in resolution_names.items():
        if name in present:
            lines.append("    {}: {},".format(size, name))
    lines.extend(("}", ""))
    lines.extend(
        (
            "def write_table(camera, commands):",
            '    """Write (register, value) commands in their original order."""',
            "    for register, value in commands:",
            "        camera.write_reg(register, value)",
            "",
            "",
            "def configure_resolution(camera, width, height):",
            '    """Apply one converted resolution table and return it."""',
            "    commands = RESOLUTION_TABLES[(width, height)]",
            "    write_table(camera, commands)",
            "    return commands",
            "",
        )
    )
    return "\n".join(lines)


def main():
    tables = parse_tables(SOURCE.read_text(encoding="utf-8"))
    if not tables:
        raise RuntimeError("no active register tables found")
    OUTPUT.write_text(render(tables), encoding="utf-8", newline="\n")
    print("wrote {} tables to {}".format(len(tables), OUTPUT))


if __name__ == "__main__":
    main()
