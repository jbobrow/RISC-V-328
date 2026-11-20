#!/usr/bin/python3
"""Diagrams of the documentation site, written as stand-alone SVG files (docs/diagrams/).
Each file carries its own colours for light and dark pages, so it looks the same in the
site, on GitHub and opened by itself.   site_diagrams.py"""
import os
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "diagrams")
STYLE = """<style>
text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.th{font-size:14px;font-weight:500;fill:#0b0b0b}.ts{font-size:12px;fill:#52514e}
.box{fill:#fcfcfb;stroke:#c3c2b7;stroke-width:.5}
.gray rect{fill:#F1EFE8;stroke:#5F5E5A;stroke-width:.5}.gray .th{fill:#444441}.gray .ts{fill:#5F5E5A}
.purple rect{fill:#EEEDFE;stroke:#534AB7;stroke-width:.5}.purple .th{fill:#3C3489}.purple .ts{fill:#534AB7}
.teal rect{fill:#E1F5EE;stroke:#0F6E56;stroke-width:.5}.teal .th{fill:#085041}.teal .ts{fill:#0F6E56}
.arr{stroke:#73726c;stroke-width:1.5;fill:none}
@media (prefers-color-scheme: dark){
.th{fill:#f0efec}.ts{fill:#c3c2b7}.box{fill:#151515;stroke:#383835}
.gray rect{fill:#444441;stroke:#B4B2A9}.gray .th{fill:#F1EFE8}.gray .ts{fill:#D3D1C7}
.purple rect{fill:#3C3489;stroke:#AFA9EC}.purple .th{fill:#EEEDFE}.purple .ts{fill:#CECBF6}
.teal rect{fill:#085041;stroke:#5DCAA5}.teal .th{fill:#E1F5EE}.teal .ts{fill:#9FE1CB}
.arr{stroke:#9c9a92}}
</style>
<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker></defs>"""

def svg(name, h, title, desc, body):
    open(os.path.join(OUT, name), "w").write(
        '<svg xmlns="http://www.w3.org/2000/svg" width="680" viewBox="0 0 680 %d" role="img"><title>%s</title><desc>%s</desc>\n%s\n%s\n</svg>\n'
        % (h, title, desc, STYLE, body))

def node(cls, x, y, w, h, title, sub=None, rx=4):
    cx = x + w / 2
    if sub is None:
        t = '<text class="ts" x="%g" y="%g" text-anchor="middle" dominant-baseline="central">%s</text>' % (cx, y + h / 2, title)
    else:
        t = ('<text class="th" x="%g" y="%g" text-anchor="middle" dominant-baseline="central">%s</text>'
             '<text class="ts" x="%g" y="%g" text-anchor="middle" dominant-baseline="central">%s</text>') % (cx, y + h / 2 - 10, title, cx, y + h / 2 + 10, sub)
    return '<g class="%s"><rect x="%g" y="%g" width="%g" height="%g" rx="%d"/>%s</g>' % (cls, x, y, w, h, rx, t)

def label(x, y, s, cls="ts", anchor="middle"):
    return '<text class="%s" x="%g" y="%g" text-anchor="%s" dominant-baseline="central">%s</text>' % (cls, x, y, anchor, s)

def floorplans():
    b = []
    for x, name, sub in ((40, "Today", "Pads behind memory"), (250, "Logic ring", "Pads next to logic"), (460, "Finished blocks", "Each block closed alone")):
        b += [label(x + 90, 40, name, "th"), '<rect class="box" x="%d" y="60" width="180" height="240" rx="4"/>' % x, label(x + 90, 322, sub)]
    b += [node("gray", 48, 68, 138, 64, "Memory"), node("purple", 48, 138, 92, 74, "Logic"), node("teal", 146, 146, 66, 58, "Analog"),
          node("gray", 48, 218, 138, 74, "Memory"), node("purple", 192, 68, 20, 72, ""), node("purple", 192, 210, 20, 82, "")]
    b += ['<g class="purple"><rect x="258" y="68" width="164" height="224" rx="4"/>%s</g>' % label(340, 80, "Logic"),
          node("gray", 276, 92, 92, 182, "Memory"), node("teal", 374, 124, 42, 118, "Analog")]
    b[-1] = b[-1].replace(">Analog<", ">Ana.<")
    b += [node("gray", 468, 68, 164, 110, "Cache block"), node("gray", 468, 184, 60, 50, "RAM"), node("purple", 534, 184, 98, 50, "Processor"),
          node("purple", 468, 240, 98, 52, "Peripherals"), node("teal", 572, 240, 60, 52, "Analog")]
    for x, cls, name in ((190, "gray", "Memory"), (290, "purple", "Logic"), (380, "teal", "Analog macro")):
        b += ['<g class="%s"><rect x="%d" y="346" width="12" height="12" rx="2"/></g>' % (cls, x), label(x + 18, 352, name, "ts", "start")]
    svg("floorplans.svg", 380, "Three ways to arrange the full-height chip",
        "Today: memory blocks at top and bottom with logic between. Logic ring: memory in the centre, logic next to the pads. Finished blocks: separately completed blocks tiled together.", "\n".join(b))

def system():
    b = ['<rect class="box" x="20" y="20" width="640" height="300" rx="8" stroke-dasharray="4 3"/>', label(40, 40, "32-pin package", "ts", "start"),
         node("gray", 44, 120, 130, 80, "Serial memory", "program, 32 KB"),
         '<rect class="box" x="230" y="60" width="406" height="236" rx="6"/>', label(246, 78, "RV328 die", "ts", "start"),
         node("gray", 250, 120, 110, 80, "Cache", "12 KB, three-way"),
         node("purple", 392, 96, 110, 56, "Processor", "RV32IMC"),
         node("gray", 392, 168, 110, 56, "RAM", "2 KB"),
         node("purple", 534, 96, 86, 128, "Peripherals", "16 slots"),
         node("teal", 392, 236, 228, 50, "Analog macro", "converter, oscillators, reset"),
         node("purple", 250, 236, 110, 50, "Clock unit", "reset, sleep"),
         '<line class="arr" x1="176" y1="160" x2="246" y2="160" marker-start="url(#arrow)" marker-end="url(#arrow)"/>', label(211, 146, "SPI"),
         '<line class="arr" x1="362" y1="134" x2="388" y2="134" marker-end="url(#arrow)"/>',
         '<line class="arr" x1="504" y1="124" x2="530" y2="124" marker-start="url(#arrow)" marker-end="url(#arrow)"/>',
         '<line class="arr" x1="447" y1="154" x2="447" y2="166" marker-start="url(#arrow)" marker-end="url(#arrow)"/>']
    svg("system.svg", 340, "The chip and its package", "A serial memory die holding the program sits in the package beside the RV328 die and is read through a cache; the die holds the processor, RAM, peripherals, clock unit and the analog macro.", "\n".join(b))

def roadmap():
    b = [node("gray", 30, 30, 186, 76, "Half-height, digital only", "signed off, kept ready", 8),
         node("purple", 247, 30, 186, 76, "Full-height, full chip", "routed, 20 MHz met", 8),
         node("teal", 464, 30, 186, 76, "Final chip", "finished blocks, the goal", 8),
         '<line class="arr" x1="218" y1="68" x2="243" y2="68" marker-end="url(#arrow)"/>',
         '<line class="arr" x1="435" y1="68" x2="460" y2="68" marker-end="url(#arrow)"/>',
         label(123, 124, "2 KB cache, 5.0 mm2 core"), label(340, 124, "12 KB cache, analog macro, 12.9 mm2"), label(557, 124, "denser memory, if it proves out")]
    svg("roadmap.svg", 146, "Where the project stands", "Three stages: a signed-off half-height digital-only layout kept ready; the full-height full chip, routed and meeting 20 MHz; the final chip built from finished blocks.", "\n".join(b))

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    floorplans(); system(); roadmap()
