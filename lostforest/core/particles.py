"""Lightweight pixel particles: dust, sparks, leaves, sparkles, fireflies."""
import math
import random

import pygame


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "size", "gravity", "drag", "kind", "phase")

    def __init__(self, x, y, vx, vy, life, color, size=1, gravity=0.0, drag=0.0, kind="square"):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.life = self.max_life = life
        self.color = color
        self.size = size
        self.gravity = gravity
        self.drag = drag
        self.kind = kind
        self.phase = random.uniform(0, math.tau)


class ParticleSystem:
    MAX = 900

    def __init__(self):
        self.items = []

    def add(self, *args, **kwargs):
        if len(self.items) < self.MAX:
            self.items.append(Particle(*args, **kwargs))

    def update(self, dt):
        alive = []
        for p in self.items:
            p.life -= dt
            if p.life <= 0:
                continue
            p.vy += p.gravity * dt
            if p.drag:
                f = max(0.0, 1.0 - p.drag * dt)
                p.vx *= f
                p.vy *= f
            if p.kind == "leaf":
                p.phase += dt * 3
                p.x += (p.vx + math.sin(p.phase) * 18) * dt
            else:
                p.x += p.vx * dt
            p.y += p.vy * dt
            alive.append(p)
        self.items = alive

    def draw(self, surface, cam_x, cam_y):
        for p in self.items:
            x = int(p.x - cam_x)
            y = int(p.y - cam_y)
            if p.kind == "glow":
                t = p.life / p.max_life
                a = int(160 * (0.5 + 0.5 * math.sin(p.phase + p.life * 6))) * min(1.0, t * 3)
                surface.fill(p.color, (x, y, 1, 1))
                g = pygame.Surface((5, 5), pygame.SRCALPHA)
                pygame.draw.circle(g, (*p.color, int(a * 0.35)), (2, 2), 2)
                surface.blit(g, (x - 2, y - 2))
                continue
            s = p.size
            if p.kind == "shrink":
                s = max(1, int(round(p.size * p.life / p.max_life)))
            surface.fill(p.color, (x, y, s, s))

    # ------------------------------------------------------------------ presets
    def dust(self, x, y, n=6, spread=40, color=(196, 180, 150)):
        for _ in range(n):
            self.add(x + random.uniform(-4, 4), y - random.uniform(0, 2),
                     random.uniform(-spread, spread), random.uniform(-30, -5),
                     random.uniform(0.25, 0.45), color, size=2, drag=4, kind="shrink")

    def burst(self, x, y, n=10, speed=90, colors=((255, 255, 255),), life=0.4, gravity=200, size=2):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            sp = random.uniform(speed * 0.4, speed)
            self.add(x, y, math.cos(a) * sp, math.sin(a) * sp, random.uniform(life * 0.6, life),
                     random.choice(colors), size=size, gravity=gravity, drag=2, kind="shrink")

    def sparkle(self, x, y, color=(255, 236, 140), n=6):
        for _ in range(n):
            self.add(x + random.uniform(-5, 5), y + random.uniform(-5, 5),
                     random.uniform(-15, 15), random.uniform(-45, -15),
                     random.uniform(0.3, 0.6), color, size=1, drag=1)

    def ring(self, x, y, n=12, speed=70, color=(230, 240, 255)):
        for i in range(n):
            a = math.tau * i / n
            self.add(x, y, math.cos(a) * speed, math.sin(a) * speed * 0.5, 0.3, color, size=2, drag=5, kind="shrink")

    def leaf(self, x, y, color):
        self.add(x, y, random.uniform(-25, -8), random.uniform(14, 26), random.uniform(5, 9),
                 color, size=2, kind="leaf")

    def firefly(self, x, y):
        self.add(x, y, random.uniform(-8, 8), random.uniform(-8, 8), random.uniform(3, 6),
                 (220, 255, 140), size=1, kind="glow")
