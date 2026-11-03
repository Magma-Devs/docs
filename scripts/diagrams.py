#!/usr/bin/env python3
"""Generate the animated diagrams in docs/assets/diagrams/.

Run from the repo root:

    python3 scripts/diagrams.py

Each diagram is a plain SVG animated with CSS keyframes, so it plays inside an
<img> tag, stays sharp at any size, and weighs a few kilobytes. Readers who turn
on reduced motion in their OS get a still diagram and a one-line summary
instead. Colors are copied from docs/stylesheets/tokens.css.

Timing is written in percent of one loop: move() slides a dot or label from one
point to another, show() switches an element on and off, grow() fills a bar
from left to right.
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "assets" / "diagrams"

INK, SUB, ACCENT, WASH, PAPER, FAINT = "#26221F", "#6E6A64", "#E8431C", "#F6F3EF", "#FFFFFF", "#9A958E"
OK, CRIT, BLUE = "#2E8540", "#C9302C", "#27598C"
FONT = "sohne, 'Helvetica Neue', Helvetica, Arial, sans-serif"


def pct(v):
    return f"{max(0, min(100, round(v, 2))):g}%"


class Diagram:
    def __init__(self, width, height, loop, label, still):
        self.w, self.h, self.loop = width, height, loop
        self.label, self.still = label, still
        self.css, self.animated, self.body = [], [], []

    # --- timing -----------------------------------------------------------

    def _register(self, name, frames):
        self.css.append(f"@keyframes {name} {{ {frames} }}")
        self.css.append(f".{name} {{ animation: {name} {self.loop}s linear infinite; }}")
        self.animated.append(name)

    def move(self, name, points, t0, t1):
        """Slide element `name` along straight segments between t0 and t1 (percent)."""
        lengths = [((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
                   for (x0, y0), (x1, y1) in zip(points, points[1:])]
        total = sum(lengths) or 1
        tr = lambda p: f"transform: translate({p[0]}px, {p[1]}px);"
        frames = [f"0%, {pct(t0)} {{ {tr(points[0])} opacity: 0; }}",
                  f"{pct(t0 + 0.8)} {{ {tr(points[0])} opacity: 1; }}"]
        t, span = t0 + 0.8, t1 - (t0 + 0.8)
        for p, seg in zip(points[1:], lengths):
            t += span * seg / total
            frames.append(f"{pct(t)} {{ {tr(p)} opacity: 1; }}")
        frames.append(f"{pct(t1 + 0.8)}, 100% {{ {tr(points[-1])} opacity: 0; }}")
        self._register(name, " ".join(frames))
        self.css.append(f".{name} {{ opacity: 0; }}")

    def show(self, name, on, off):
        """Element `name` is visible from `on` to `off` (percent of the loop)."""
        start = "" if on <= 0 else f"0%, {pct(on - 0.6)} {{ opacity: 0; }} "
        self._register(name, f"{start}{pct(on)}, {pct(off)} {{ opacity: 1; }} {pct(off + 0.6)}, 100% {{ opacity: 0; }}")
        self.css.append(f".{name} {{ opacity: 0; }}")

    def grow(self, name, t0, t1, hold=96):
        """Bar `name` fills left to right between t0 and t1, then fades at the loop end."""
        self._register(name, (
            f"0%, {pct(t0)} {{ transform: scaleX(0); opacity: 1; }} "
            f"{pct(t1)}, {pct(hold)} {{ transform: scaleX(1); opacity: 1; }} "
            f"100% {{ transform: scaleX(1); opacity: 0; }}"))
        self.css.append(f".{name} {{ transform-box: fill-box; transform-origin: left center; }}")

    # --- drawing ----------------------------------------------------------

    def add(self, *parts):
        self.body.extend(parts)

    @staticmethod
    def card(x, y, w, h, title, sub="", cls=""):
        cx = x + w / 2
        out = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{PAPER}" '
               f'stroke="{INK}" stroke-opacity="0.2" stroke-width="1.5"/>'
               f'<text x="{cx}" y="{y + (28 if sub else h / 2 + 5)}" text-anchor="middle" class="t b">{title}</text>')
        if sub:
            out += f'<text x="{cx}" y="{y + 47}" text-anchor="middle" class="s {cls}">{sub}</text>'
        return out

    @staticmethod
    def hub(x, y, w, h, title, sub):
        cx = x + w / 2
        return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{ACCENT}"/>'
                f'<text x="{cx}" y="{y + h / 2 - 4}" text-anchor="middle" class="b" font-size="20" fill="{PAPER}">{title}</text>'
                f'<text x="{cx}" y="{y + h / 2 + 19}" text-anchor="middle" font-size="12.5" fill="{PAPER}">{sub}</text>')

    @staticmethod
    def line(points, dashed=False):
        d = " ".join(f"{'M' if i == 0 else 'L'} {x} {y}" for i, (x, y) in enumerate(points))
        dash = ' stroke-dasharray="5 5"' if dashed else ""
        return f'<path d="{d}" fill="none" stroke="{INK}" stroke-opacity="0.2" stroke-width="1.5"{dash}/>'

    @staticmethod
    def outline(cls, x, y, w, h, color, rx=12):
        return f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="none" stroke="{color}" stroke-width="2.5"/>'

    @staticmethod
    def badge(cls, x, y, color, mark):
        return (f'<g class="{cls}"><circle cx="{x}" cy="{y}" r="11" fill="{color}"/>'
                f'<text x="{x}" y="{y + 4.5}" text-anchor="middle" class="b" font-size="13" fill="{PAPER}">{mark}</text></g>')

    @staticmethod
    def dot(cls, color):
        return f'<circle class="dot {cls}" cx="0" cy="0" r="6" fill="{color}"/>'

    @staticmethod
    def pill(cls, letter, color):
        return (f'<g class="dot {cls}"><rect x="-13" y="-11" width="26" height="22" rx="6" fill="{color}"/>'
                f'<text x="0" y="5" text-anchor="middle" class="b" font-size="13" fill="{PAPER}">{letter}</text></g>')

    def captions(self, y, steps):
        """steps: (name, on, off, text). Text starts with the step number and a period."""
        for name, on, off, text in steps:
            self.show(name, on, off)
            num, rest = text.split(" ", 1)
            self.add(f'<text x="24" y="{y}" class="t anim {name}"><tspan class="b" fill="{ACCENT}">{num}</tspan> {rest}</text>')
        self.add(f'<text x="24" y="{y}" class="t still">{self.still}</text>')

    def svg(self):
        names = ", ".join(f".{n}" for n in self.animated)
        css = "\n    ".join(self.css)
        body = "\n  ".join(self.body)
        return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" role="img" aria-label="{self.label}">
  <!-- Generated by scripts/diagrams.py; edit there, not here. -->
  <style>
    text {{ font-family: {FONT}; }}
    .t {{ font-size: 14px; fill: {INK}; }}
    .b {{ font-weight: 700; }}
    .s {{ font-size: 12.5px; fill: {SUB}; }}
    .still {{ display: none; }}
    {css}
    @media (prefers-reduced-motion: reduce) {{
      {names} {{ animation: none; }}
      .dot, .anim {{ display: none; }}
      .keep {{ opacity: 1; }}
      .still {{ display: inline; }}
    }}
  </style>
  {body}
</svg>
'''


# --- Why Smart Router: one request end to end ---------------------------------

def topology():
    d = Diagram(880, 400, 10,
                "How a request flows: your app calls Smart Router, which checks the shared cache, retries on another "
                "provider when one fails, and saves the answer so a repeat request is served from the cache.",
                "Smart Router checks the shared cache, retries on another provider when one fails, and caches the answer.")
    L = d.line
    d.add(L([(174, 182), (330, 182)]), L([(550, 160), (690, 72)]), L([(550, 182), (690, 182)]),
          L([(550, 204), (690, 292)]), L([(440, 232), (440, 296)]))
    d.add(d.card(24, 150, 150, 64, "Your app", "RPC client"),
          d.card(690, 40, 166, 64, "Provider 1", "paid, archive"),
          d.card(690, 150, 166, 64, "Provider 2", "your own node"),
          d.card(690, 260, 166, 64, "Provider 3", "free, public"),
          d.hub(330, 132, 220, 100, "Smart Router", "routes, caches, fails over"),
          f'<rect x="360" y="296" width="160" height="48" rx="12" fill="{WASH}"/>'
          f'<text x="440" y="325" text-anchor="middle" class="t b">Shared cache</text>')
    for name, on, off in [("p2fail", 24, 64), ("p1ok", 40, 50), ("appok", 58, 64), ("appok2", 85, 96),
                          ("miss", 13, 20), ("saved", 63, 70), ("hit", 77, 90)]:
        d.show(name, on, off)
    d.add('<g class="anim">',
          d.outline("p2fail", 690, 150, 166, 64, CRIT), d.badge("p2fail", 856, 150, CRIT, "&#x2715;"),
          d.outline("p1ok", 690, 40, 166, 64, OK),
          d.outline("appok", 24, 150, 150, 64, OK), d.badge("appok", 174, 150, OK, "&#x2713;"),
          d.outline("appok2", 24, 150, 150, 64, OK), d.badge("appok2", 174, 150, OK, "&#x2713;"),
          '<text x="534" y="325" class="s miss">miss</text>',
          f'<text x="534" y="325" class="s b saved" style="fill:{OK}">saved</text>',
          f'<text x="534" y="325" class="s b hit" style="fill:{OK}">hit</text>',
          '</g>')
    for name, color, pts, t0, t1 in [
        ("req1", INK, [(174, 182), (330, 182)], 0, 8),
        ("check", INK, [(440, 232), (440, 296)], 9, 13),
        ("try2", INK, [(550, 182), (690, 182)], 15, 24),
        ("try1", INK, [(550, 160), (690, 72)], 31, 40),
        ("ans1", OK, [(690, 72), (550, 160)], 41, 49),
        ("ans2", OK, [(330, 182), (174, 182)], 51, 58),
        ("store", OK, [(440, 232), (440, 296)], 59, 64),
        ("req2", INK, [(174, 182), (330, 182)], 67, 72),
        ("hitdot", INK, [(440, 232), (440, 296)], 73, 77),
        ("ans3", OK, [(330, 182), (174, 182)], 79, 85),
    ]:
        d.move(name, pts, t0, t1)
        d.add(d.dot(name, color))
    d.captions(384, [
        ("c1", 0, 14, "1. A request arrives. Smart Router checks the shared cache first: not there yet."),
        ("c2", 14, 50, "2. It tries Provider 2, which does not answer in time, so it retries on Provider 1."),
        ("c3", 50, 65, "3. The answer goes back to your app and is saved in the shared cache."),
        ("c4", 65, 99, "4. The same request again is answered from the cache. No provider is called."),
    ])
    return d


# --- Cross-validation: 2 of 3 must agree --------------------------------------

def consensus():
    d = Diagram(880, 420, 10,
                "Cross-validation with a threshold of 2 of 3: Smart Router sends the same request to three providers, "
                "two return answer A and one returns answer B, so answer A goes back to your app.",
                "The same request goes to three providers. Two return A, one returns B, so A goes back to your app.")
    L = d.line
    d.add(L([(174, 210), (330, 210)]), L([(550, 188), (690, 90)]), L([(550, 210), (690, 210)]),
          L([(550, 232), (690, 330)]))
    d.add(d.card(24, 178, 150, 64, "Your app", "RPC client"),
          d.card(690, 58, 166, 64, "Provider 1", " "),
          d.card(690, 178, 166, 64, "Provider 2", " "),
          d.card(690, 298, 166, 64, "Provider 3", " "),
          d.hub(330, 160, 220, 100, "Smart Router", "asks 3, needs 2 to agree"))
    # Running count under the router.
    d.show("n0", 0, 28)
    d.show("n1", 28, 50)
    d.show("n2", 50, 96)
    d.add('<g class="anim">',
          '<text x="440" y="292" text-anchor="middle" class="s n0">Matching answers: 0 of 2</text>',
          '<text x="440" y="292" text-anchor="middle" class="s n1">Matching answers: 1 of 2</text>',
          f'<text x="440" y="292" text-anchor="middle" class="s b n2" style="fill:{OK}">Matching answers: 2 of 2</text>',
          '</g>')
    # What each provider answered, and the verdict.
    for name, on, off in [("a1", 28, 96), ("b3", 39, 96), ("a2", 50, 96), ("bad3", 39, 96),
                          ("good", 50, 70), ("appok", 61, 82)]:
        d.show(name, on, off)
    d.add('<g class="anim">',
          '<text x="773" y="105" text-anchor="middle" class="s a1">answered A</text>',
          '<text x="773" y="225" text-anchor="middle" class="s a2">answered A</text>',
          f'<text x="773" y="345" text-anchor="middle" class="s b b3" style="fill:{CRIT}">answered B, ignored</text>',
          d.outline("bad3", 690, 298, 166, 64, CRIT), d.badge("bad3", 856, 298, CRIT, "&#x2715;"),
          d.outline("good", 690, 58, 166, 64, OK), d.outline("good", 690, 178, 166, 64, OK),
          d.outline("appok", 24, 178, 150, 64, OK), d.badge("appok", 174, 178, OK, "&#x2713;"),
          '</g>')
    d.move("req", [(174, 210), (330, 210)], 0, 7)
    d.add(d.dot("req", INK))
    for name, pts in [("f1", [(550, 188), (690, 90)]), ("f2", [(550, 210), (690, 210)]),
                      ("f3", [(550, 232), (690, 330)])]:
        d.move(name, pts, 10, 18)
        d.add(d.dot(name, INK))
    for name, letter, pts, t0, t1 in [("r1", "A", [(690, 90), (550, 188)], 20, 28),
                                       ("r3", "B", [(690, 330), (550, 232)], 31, 39),
                                       ("r2", "A", [(690, 210), (550, 210)], 42, 50)]:
        d.move(name, pts, t0, t1)
        d.add(d.pill(name, letter, INK))
    d.move("ret", [(330, 210), (174, 210)], 53, 61)
    d.add(d.pill("ret", "A", OK))
    d.captions(404, [
        ("c1", 0, 9, "1. A read arrives. For this method, 2 of 3 providers must agree."),
        ("c2", 9, 20, "2. Smart Router sends the same request to all three at once."),
        ("c3", 20, 50, "3. Answers arrive one by one. Provider 3's answer differs from the other two."),
        ("c4", 50, 99, "4. Two answers match, which meets the threshold. Answer A goes back to your app."),
    ])
    return d


# --- Failover: integrity, selection, attempt, retry ---------------------------

def failsafe_flow():
    d = Diagram(880, 470, 12,
                "Failover pipeline: an integrity check skips a node that is behind the chain head, selection picks "
                "Node A, Node A returns a retryable error, the router retries on Node B, and Node B's answer goes "
                "back to your app. A legend lists the four outcomes of an attempt.",
                "Lagging nodes are skipped, a retryable error moves the request to another node, the answer returns.")
    L = d.line
    # Lanes: the answer travels back above the boxes, a retry loops back below them.
    d.add(L([(152, 72), (192, 72)]), L([(368, 72), (408, 72)]), L([(584, 72), (624, 72)]),
          L([(740, 40), (740, 22), (88, 22), (88, 40)], dashed=True),
          L([(740, 104), (740, 122), (496, 122), (496, 104)], dashed=True),
          f'<text x="414" y="16" text-anchor="middle" class="s">answer</text>',
          f'<text x="618" y="138" text-anchor="middle" class="s">retry</text>')
    d.add(d.card(24, 40, 128, 64, "Your app", "RPC client"),
          d.card(192, 40, 176, 64, "1. Integrity", "skips lagging nodes"),
          d.card(408, 40, 176, 64, "2. Selection", "picks the best node"),
          d.card(624, 40, 232, 64, "3. Attempt", " "))
    d.show("onA", 28, 46)
    d.show("onB", 58, 96)
    d.add('<g class="anim">',
          '<text x="740" y="87" text-anchor="middle" class="s onA">sent to Node A</text>',
          '<text x="740" y="87" text-anchor="middle" class="s onB">sent to Node B</text>',
          '</g>')
    # Node pool.
    d.add('<text x="192" y="176" class="s b">Node pool</text>')
    for i, n in enumerate("ABCD"):
        d.add(f'<rect x="{192 + i * 102}" y="188" width="86" height="40" rx="8" fill="{PAPER}" stroke="{INK}" '
              f'stroke-opacity="0.2" stroke-width="1.5"/>'
              f'<text x="{235 + i * 102}" y="213" text-anchor="middle" class="t">Node {n}</text>')
    for name, on, off in [("lagD", 8, 96), ("pickA", 18, 36), ("failA", 36, 96), ("pickB", 48, 62),
                          ("okB", 62, 96), ("attFail", 36, 46), ("attOk", 62, 82), ("appok", 76, 90),
                          ("hlRetry", 36, 54), ("hlAnswer", 62, 88)]:
        d.show(name, on, off)
    d.add('<g class="anim">',
          f'<g class="lagD"><rect x="498" y="188" width="86" height="40" rx="8" fill="{WASH}"/>'
          f'<text x="541" y="213" text-anchor="middle" class="t" style="fill:{FAINT}">Node D</text>'
          f'<text x="541" y="246" text-anchor="middle" class="s">behind chain head</text></g>',
          d.outline("pickA", 192, 188, 86, 40, ACCENT, 8),
          d.outline("failA", 192, 188, 86, 40, CRIT, 8),
          f'<text x="235" y="246" text-anchor="middle" class="s failA" style="fill:{CRIT}">error</text>',
          d.outline("pickB", 294, 188, 86, 40, ACCENT, 8),
          d.outline("okB", 294, 188, 86, 40, OK, 8),
          f'<text x="337" y="246" text-anchor="middle" class="s okB" style="fill:{OK}">answered</text>',
          d.outline("attFail", 624, 40, 232, 64, CRIT), d.badge("attFail", 856, 40, CRIT, "&#x2715;"),
          d.outline("attOk", 624, 40, 232, 64, OK), d.badge("attOk", 856, 40, OK, "&#x2713;"),
          d.outline("appok", 24, 40, 128, 64, OK),
          f'<rect class="hlRetry" x="24" y="319" width="832" height="26" rx="6" fill="{WASH}"/>',
          f'<rect class="hlAnswer" x="24" y="291" width="832" height="26" rx="6" fill="{WASH}"/>',
          '</g>')
    # Legend: the four outcomes of an attempt (always visible).
    d.add('<text x="24" y="278" class="t b">What can happen after an attempt</text>')
    for i, (color, text) in enumerate([
        (OK, "Answer: it goes back to your app."),
        (CRIT, "Retryable error: the request is retried on another node."),
        (BLUE, "No answer in time: a hedge sends the same request to another node, in parallel."),
        (INK, "No nodes left: the circuit breaker ends the request early."),
    ]):
        y = 309 + i * 28
        d.add(f'<circle cx="38" cy="{y - 5}" r="5" fill="{color}"/>', f'<text x="52" y="{y}" class="t">{text}</text>')
    for name, color, pts, t0, t1 in [
        ("req", INK, [(152, 72), (192, 72)], 0, 4),
        ("toSel", INK, [(368, 72), (408, 72)], 12, 16),
        ("toAtt", INK, [(584, 72), (624, 72)], 24, 28),
        ("retry", CRIT, [(740, 104), (740, 122), (496, 122), (496, 104)], 40, 48),
        ("toAtt2", INK, [(584, 72), (624, 72)], 54, 58),
        ("answer", OK, [(740, 40), (740, 22), (88, 22), (88, 40)], 64, 76),
    ]:
        d.move(name, pts, t0, t1)
        d.add(d.dot(name, color))
    d.captions(454, [
        ("c1", 0, 14, "1. Integrity check: Node D is behind the chain head, so it is skipped."),
        ("c2", 14, 36, "2. Selection picks Node A, and the attempt sends the request to it."),
        ("c3", 36, 58, "3. Node A returns a retryable error, so the router goes back and picks Node B."),
        ("c4", 58, 99, "4. Node B answers, and the response goes back to your app."),
    ])
    return d


# --- Hedge: a parallel try when the first is slow -----------------------------

def hedge():
    x0, span = 200, 650                      # timeline from x0 to x0 + span
    tick, win2, end1 = 0.35, 0.60, 0.85      # in fractions of the timeline
    at = lambda f: x0 + span * f
    p = lambda f: f * 90                     # the playhead crosses the timeline in 90% of the loop
    d = Diagram(880, 330, 10,
                "Hedge timeline: attempt 1 goes to Provider 1 and is slow. When the tick passes with no answer, a hedge "
                "sends the same request to Provider 2. Provider 2 answers first and wins; Provider 1's late answer is "
                "thrown away.",
                "When a request is slow, a hedge tries another provider in parallel. The first answer wins.")
    d.add(f'<text x="24" y="40" class="s b">Time &#x2192;</text>')
    for y, title, sub in [(92, "Provider 1", "attempt 1"), (172, "Provider 2", "hedge")]:
        d.add(f'<text x="24" y="{y + 12}" class="t b">{title}</text>', f'<text x="24" y="{y + 30}" class="s">{sub}</text>',
              f'<rect x="{x0}" y="{y}" width="{span}" height="28" rx="6" fill="{WASH}"/>')
    d.add(f'<line x1="{x0}" y1="240" x2="{x0 + span}" y2="240" stroke="{INK}" stroke-opacity="0.2" stroke-width="1.5"/>',
          f'<text x="{x0}" y="262" class="s">0 ms</text>',
          f'<line x1="{at(tick)}" y1="80" x2="{at(tick)}" y2="240" stroke="{INK}" stroke-opacity="0.35" '
          f'stroke-width="1.5" stroke-dasharray="4 4"/>',
          f'<text x="{at(tick)}" y="262" text-anchor="middle" class="s">tick</text>')
    # Bars fill as time passes.
    d.grow("bar1", 0, p(end1))
    d.grow("bar2", p(tick), p(win2))
    d.add(f'<rect class="bar1" x="{x0}" y="92" width="{span * end1}" height="28" rx="6" fill="{INK}" fill-opacity="0.75"/>',
          f'<rect class="bar2" x="{at(tick)}" y="172" width="{span * (win2 - tick)}" height="28" rx="6" fill="{ACCENT}"/>')
    for name, on, off in [("tickLbl", p(tick), 96), ("win", p(win2), 96), ("late", p(end1), 96)]:
        d.show(name, on, off)
    d.add(f'<text x="{at(tick) + 8}" y="76" class="s keep tickLbl">no answer yet: hedge fires</text>',
          f'<g class="keep win">{d.badge("", at(win2), 186, OK, "&#x2713;")}'
          f'<text x="{at(win2) + 18}" y="191" class="s b" style="fill:{OK}">first answer wins, goes to your app</text></g>',
          f'<g class="keep late"><rect x="{x0}" y="92" width="{span * end1}" height="28" rx="6" fill="{PAPER}" fill-opacity="0.6"/>'
          f'<text x="{at(end1)}" y="140" text-anchor="end" class="s">late answer, thrown away</text></g>')
    # Playhead.
    d.move("head", [(x0, 0), (x0 + span, 0)], 0, 90)
    d.add(f'<line class="dot head" x1="0" y1="84" x2="0" y2="240" stroke="{ACCENT}" stroke-width="2"/>')
    d.captions(306, [
        ("c1", 0, p(tick), "1. Attempt 1 goes to Provider 1, and the clock starts."),
        ("c2", p(tick), p(win2), "2. The tick passes with no answer, so a hedge sends the same request to Provider 2."),
        ("c3", p(win2), p(end1), "3. Provider 2 answers first. Attempt 1 is still running, but this answer wins."),
        ("c4", p(end1), 99, "4. Provider 1 answers later. Its answer is thrown away."),
    ])
    return d


if __name__ == "__main__":
    for name, build in [("topology", topology), ("consensus", consensus),
                        ("failsafe-flow", failsafe_flow), ("hedge", hedge)]:
        path = OUT / f"{name}.svg"
        path.write_text(build().svg())
        print(f"wrote {path.relative_to(OUT.parent.parent.parent)} ({path.stat().st_size} bytes)")
