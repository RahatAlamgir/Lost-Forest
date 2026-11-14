"""Forest creatures: Snail (armoured), Boar (charger) and Bee (diver)."""
import math
import random

import pygame

from .. import settings as S
from ..core.animation import AnimPlayer
from ..world.tiles import SOLID, SPIKES, WATER
from .base import Body


class Enemy(Body):
    layer = 4
    max_hp = 1
    hitbox = (16, 16)
    death_colors = ((255, 255, 255), (200, 200, 200))

    def __init__(self, x, bottom, anims, start_anim):
        w, h = self.hitbox
        super().__init__(x - w / 2, bottom - h, w, h)
        self.anim = AnimPlayer(anims, start_anim)
        self.hp = self.max_hp
        self.facing = -1
        self.flash = 0.0
        self.state = "idle"
        self.state_time = 0.0
        self.dying = False
        self.fade = 1.0

    # behaviour flags (overridden per state)
    @property
    def hittable(self):
        return not self.dying

    @property
    def harmful(self):
        return not self.dying

    @property
    def stompable(self):
        return not self.dying

    def set_state(self, name):
        self.state = name
        self.state_time = 0.0

    def take_hit(self, damage, direction, push):
        if self.dying:
            return
        self.hp -= damage
        self.flash = 0.15
        self.vx = direction * push * 0.9          # strong enough to knock enemies into hazards
        lvl = self.level
        lvl.audio.play("hit")
        lvl.particles.burst(self.rect.centerx, self.rect.centery, 8, 90, ((255, 255, 255), (255, 230, 160)), 0.3, 150)
        lvl.camera.shake(2, 0.1)
        lvl.hitstop(0.05)
        if self.hp <= 0:
            self.die()

    def stomp(self, player):
        self.take_hit(1, 1 if player.rect.centerx < self.rect.centerx else -1, 60)

    def die(self):
        self.dying = True
        self.set_state("dead")
        self.level.audio.play("enemy_die")
        self.level.stats["enemies"] += 1
        on_kill = getattr(self.level, "on_enemy_killed", None)     # endless mode awards points
        if on_kill:
            on_kill(self)

    def finish_death(self):
        self.alive = False
        self.level.particles.burst(self.rect.centerx, self.rect.centery, 14, 70, self.death_colors, 0.6, 60)

    def draw(self, surface, cam_x, cam_y):
        alpha = int(255 * self.fade)
        self.anim.draw(surface, (self.rect.centerx - cam_x, self.rect.bottom - cam_y),
                       self.facing, self.flash > 0, alpha)

    def player_dir(self):
        p = self.level.player
        return 1 if p.rect.centerx > self.rect.centerx else -1

    # ------------------------------------------------------------------ hazards
    def hazard_ahead(self, direction):
        """Spikes or water just in front of our feet (patrolling enemies turn around)."""
        tm = self.level.tilemap
        x = self.rect.right + 3 if direction > 0 else self.rect.left - 3
        tx = int(x // S.TILE)
        foot = int((self.rect.bottom - 2) // S.TILE)
        below = int((self.rect.bottom + 1) // S.TILE)
        return tm.kind(tx, foot) in (SPIKES, WATER) or tm.kind(tx, below) == WATER

    def check_hazards(self):
        """Spikes, water and bottomless pits kill enemies too (and count as a defeat)."""
        if self.dying or not self.alive:
            return
        tm = self.level.tilemap
        kind = tm.hazard_at(self.rect)
        if kind is not None:
            lvl = self.level
            if kind == WATER:
                lvl.particles.burst(self.rect.centerx, self.rect.bottom - 4, 12, 80,
                                    ((120, 200, 230), (200, 240, 255)), 0.5, 300)
            else:
                lvl.particles.burst(self.rect.centerx, self.rect.bottom - 4, 10, 90,
                                    ((255, 255, 255), (220, 60, 50)), 0.4, 250)
            self.hp = 0
            self.flash = 0.2
            self.die()
        elif self.rect.top > tm.pixel_h + 40:
            self.level.stats["enemies"] += 1
            self.alive = False

    def ally_ahead(self, direction, gap=3):
        """True if another living ground enemy is right in front of us (so walkers don't stack)."""
        probe = pygame.FRect(self.rect.right if direction > 0 else self.rect.left - gap,
                             self.rect.top + 2, gap, self.rect.h - 4)
        for other in self.level.enemies:
            if other is self or other.dying or isinstance(other, Bee):
                continue
            if probe.colliderect(other.rect):
                # only turn if the other one is genuinely ahead of us
                if (other.rect.centerx - self.rect.centerx) * direction > 0:
                    return True
        return False


# =============================================================================
class Snail(Enemy):
    max_hp = S.SNAIL_HP
    hitbox = (20, 14)
    death_colors = ((200, 60, 60), (240, 150, 90), (255, 255, 255))

    def __init__(self, x, bottom, assets):
        super().__init__(x, bottom, assets.snail, "walk")
        self.set_state("walk")
        self.facing = random.choice((-1, 1))

    @property
    def harmful(self):
        return self.state == "walk"

    @property
    def hittable(self):
        return not self.dying

    def take_hit(self, damage, direction, push):
        if self.dying:
            return
        if self.state in ("hide", "shell", "unhide"):
            # armoured shell: the hit bounces off
            self.level.audio.play("clink")
            self.level.particles.sparkle(self.rect.centerx, self.rect.top + 4, (255, 255, 255), 4)
            self.vx = direction * push * 0.6
            self.state_time = min(self.state_time, 0.4)   # stays hidden a bit longer
            return
        super().take_hit(damage, direction, push)
        if not self.dying:
            self.set_state("hide")
            self.anim.play("hide", restart=True)

    def update(self, dt):
        self.anim.update(dt)
        self.state_time += dt
        self.flash = max(0.0, self.flash - dt)
        if self.state == "dead":
            self.vx = 0
            self.anim.play("dead")
            if self.anim.finished:
                self.fade -= dt * 3
                if self.fade <= 0:
                    self.finish_death()
        elif self.state == "walk":
            self.anim.play("walk")
            if (self.wall_ahead(self.facing) or not self.ground_ahead(self.facing)
                    or self.hazard_ahead(self.facing) or self.ally_ahead(self.facing)):
                self.facing *= -1
            self.vx = self.facing * S.SNAIL_SPEED
        elif self.state == "hide":
            self.vx *= max(0.0, 1 - 8 * dt)
            if self.anim.finished:
                self.set_state("shell")
                self.anim.play("shell")
        elif self.state == "shell":
            self.vx *= max(0.0, 1 - 8 * dt)
            if self.state_time > S.SNAIL_HIDE_TIME:
                self.set_state("unhide")
                self.anim.play("unhide", restart=True)
        elif self.state == "unhide":
            self.vx = 0
            if self.anim.finished:
                self.set_state("walk")
        self.apply_gravity(dt)
        self.move(dt)
        self.check_hazards()


# =============================================================================
class Boar(Enemy):
    max_hp = S.BOAR_HP
    hitbox = (28, 18)
    death_colors = ((140, 80, 50), (200, 140, 90), (255, 255, 255))

    def __init__(self, x, bottom, assets):
        super().__init__(x, bottom, assets.boar, "walk")
        self.set_state("patrol")
        self.facing = random.choice((-1, 1))
        self.pause = random.uniform(2.0, 4.0)

    def can_see_player(self):
        p = self.level.player
        if p.is_dead:
            return False
        dx = p.rect.centerx - self.rect.centerx
        if dx * self.facing <= 0 or abs(dx) > S.BOAR_SIGHT_RANGE:
            return False
        if abs(p.rect.bottom - self.rect.bottom) > 30:
            return False
        tm = self.level.tilemap
        ty = int((self.rect.bottom - 8) // S.TILE)
        x0 = int(min(p.rect.centerx, self.rect.centerx) // S.TILE)
        x1 = int(max(p.rect.centerx, self.rect.centerx) // S.TILE)
        return all(tm.kind(tx, ty) != SOLID for tx in range(x0, x1 + 1))

    def take_hit(self, damage, direction, push):
        super().take_hit(damage, direction, push)
        if not self.dying and self.state in ("patrol", "rest"):
            # turn to face the attacker and get angry
            self.facing = -direction
            self.set_state("alert")

    def stomp(self, player):
        super().stomp(player)
        if not self.dying and self.state == "charge":
            self.set_state("stunned")

    def update(self, dt):
        self.anim.update(dt)
        self.state_time += dt
        self.flash = max(0.0, self.flash - dt)
        st = self.state
        if st == "dead":
            self.vx *= max(0.0, 1 - 6 * dt)
            self.anim.play("hit")
            if self.state_time > 0.45:
                self.finish_death()
        elif st == "patrol":
            self.anim.play("walk")
            if (self.wall_ahead(self.facing) or not self.ground_ahead(self.facing)
                    or self.hazard_ahead(self.facing) or self.ally_ahead(self.facing)):
                self.facing *= -1
            self.vx = self.facing * S.BOAR_WALK_SPEED
            self.pause -= dt
            if self.pause <= 0:
                self.set_state("rest")
            if self.can_see_player():
                self.set_state("alert")
        elif st == "rest":
            self.anim.play("idle")
            self.vx = 0
            if self.state_time > 1.0:
                self.pause = random.uniform(2.5, 5.0)
                if random.random() < 0.5:
                    self.facing *= -1
                self.set_state("patrol")
            elif self.can_see_player():
                self.set_state("alert")
        elif st == "alert":
            self.anim.play("idle")
            self.vx = 0
            self.facing = self.player_dir()
            if self.state_time > 0.42:
                self.set_state("charge")
                self.level.audio.play("land")
        elif st == "charge":
            self.anim.play("run")
            self.vx = self.facing * S.BOAR_CHARGE_SPEED
            if int(self.state_time * 12) % 2 == 0:
                self.level.particles.dust(self.rect.centerx - self.facing * 10, self.rect.bottom, 1, 20)
            if self.wall_ahead(self.facing, 2):
                self.set_state("stunned")
                self.vx = -self.facing * 60
                self.vy = -120
                self.level.camera.shake(3, 0.2)
                self.level.audio.play("land")
                self.level.particles.burst(self.rect.centerx + self.facing * 14, self.rect.centery, 8, 60,
                                           ((230, 220, 190),), 0.4, 200)
            elif not self.ground_ahead(self.facing, 4) or self.ally_ahead(self.facing, 4):
                self.set_state("stunned")
                self.vx = 0
            elif self.state_time > 2.2:
                self.set_state("rest")
        elif st == "stunned":
            self.anim.play("idle")
            self.vx *= max(0.0, 1 - 5 * dt)
            if self.state_time > 1.0:
                self.facing = self.player_dir()
                self.pause = random.uniform(2.0, 4.0)
                self.set_state("patrol")
        if self.flash > 0 and st != "dead":
            self.vx *= max(0.0, 1 - 10 * dt)
        self.apply_gravity(dt)
        self.move(dt)
        self.check_hazards()

    def draw(self, surface, cam_x, cam_y):
        super().draw(surface, cam_x, cam_y)
        if self.state == "alert":
            icon = self.level.assets.icons["exclaim"]
            mask = pygame.mask.from_surface(icon).to_surface(setcolor=(255, 220, 90, 255), unsetcolor=(0, 0, 0, 0))
            bob = int(math.sin(self.state_time * 30) * 1)
            surface.blit(mask, (self.rect.centerx - cam_x - 8, self.rect.top - cam_y - 18 + bob))


# =============================================================================
class Bee(Enemy):
    max_hp = S.BEE_HP
    hitbox = (14, 14)
    death_colors = ((250, 200, 60), (40, 30, 20), (255, 255, 255))

    def __init__(self, x, bottom, assets):
        super().__init__(x, bottom - 8, assets.bee, "fly")
        self.home = pygame.Vector2(self.rect.center)
        self.t = random.uniform(0, 10)
        self.cooldown = random.uniform(0.5, 1.5)
        self.target = pygame.Vector2()
        self.dive_dir = pygame.Vector2()
        self.set_state("hover")

    def draw(self, surface, cam_x, cam_y):
        alpha = int(255 * self.fade)
        shake = (random.randint(-1, 1) if self.state == "windup" else 0)
        self.anim.draw(surface, (self.rect.centerx - cam_x + shake, self.rect.centery - cam_y - 4),
                       self.facing, self.flash > 0, alpha)

    def update(self, dt):
        self.anim.update(dt)
        self.state_time += dt
        self.flash = max(0.0, self.flash - dt)
        self.t += dt
        self.cooldown = max(0.0, self.cooldown - dt)
        player = self.level.player
        pos = pygame.Vector2(self.rect.center)
        st = self.state
        if st == "dead":
            self.anim.play("hit")
            self.vy = min(self.vy + 600 * dt, 300)
            self.rect.y += self.vy * dt
            self.fade -= dt * 1.5
            if self.fade <= 0:
                self.finish_death()
            return
        if st == "hover":
            self.anim.play("fly")
            want = self.home + pygame.Vector2(math.sin(self.t * 1.3) * 26, math.sin(self.t * 2.6) * 9)
            pos += (want - pos) * min(1.0, dt * 4)
            self.facing = 1 if (want.x - pos.x) > 0.3 else (-1 if (want.x - pos.x) < -0.3 else self.facing)
            if not player.is_dead and self.cooldown <= 0:
                d = pygame.Vector2(player.rect.center) - pos
                if d.length() < S.BEE_SIGHT_RANGE:
                    self.set_state("windup")
                    self.facing = 1 if d.x > 0 else -1
        elif st == "windup":
            self.anim.play("attack")
            self.facing = self.player_dir()
            pos.y -= 10 * dt
            if self.state_time > 0.5:
                self.target = pygame.Vector2(player.rect.center)
                d = self.target - pos
                self.dive_dir = d.normalize() if d.length() > 1 else pygame.Vector2(self.facing, 0)
                self.set_state("dive")
        elif st == "dive":
            self.anim.play("attack")
            pos += self.dive_dir * S.BEE_DIVE_SPEED * dt
            if self.state_time > 0.85 or self._in_solid(pos):
                self.set_state("return")
        elif st == "return":
            self.anim.play("fly")
            d = self.home - pos
            if d.length() < 3:
                self.set_state("hover")
                self.cooldown = 1.3
            else:
                step = min(d.length(), 75 * dt)
                pos += d.normalize() * step
                self.facing = 1 if d.x > 0 else -1
        if self.flash > 0:
            pos.x += self.vx * dt
            self.vx *= max(0.0, 1 - 9 * dt)
        self.rect.center = (pos.x, pos.y)
        self.check_hazards()

    def _in_solid(self, pos):
        tm = self.level.tilemap
        return tm.kind(int(pos.x // S.TILE), int(pos.y // S.TILE)) == SOLID

    def take_hit(self, damage, direction, push):
        super().take_hit(damage, direction, push)
        if not self.dying and self.state in ("windup", "dive"):
            self.set_state("return")

    def die(self):
        super().die()
        self.vy = -80


ENEMY_TYPES = {"s": Snail, "b": Boar, "z": Bee}
