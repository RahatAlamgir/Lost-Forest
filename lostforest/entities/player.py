"""The hero: movement, jumping, sword combo, damage and death."""
import random

import pygame

from .. import settings as S
from ..core.animation import AnimPlayer, make_silhouette
from ..world.tiles import SOLID, WATER
from .base import Body

# attack definitions: active window (seconds) and hitbox relative to the hero's facing
ATTACKS = {
    "attack1": {"active": (0.05, 0.20), "box": (2, -46, 34, 44), "sound": "swing", "damage": 1, "push": 120},
    "attack2": {"active": (0.00, 0.17), "box": (0, -36, 42, 30), "sound": "swing2", "damage": 1, "push": 200},
}
COMBO_WINDOW = 0.05      # earliest time into attack1 that a second press queues attack2


class Player(Body):
    layer = 5

    def __init__(self, x, y, assets):
        w, h = S.PLAYER_HITBOX
        super().__init__(x - w / 2, y - h, w, h)
        self.anim = AnimPlayer(assets.player, "idle")
        self.facing = 1
        self.health = S.PLAYER_MAX_HEALTH
        self.max_health = S.PLAYER_MAX_HEALTH
        self.state = "normal"         # normal | attack | dash | dead | exit
        self.coyote = 0.0
        self.jump_buffer = 0.0
        self.can_double = True
        self.jump_held = False
        self.invuln = 0.0
        self.hurt_timer = 0.0
        self.land_timer = 0.0
        self.step_timer = 0.0
        self.attack_name = None
        self.attack_time = 0.0
        self.attack_queued = False
        self.attack_hits = set()
        self.dead_time = 0.0
        self.safe_pos = (self.rect.centerx, self.rect.bottom)
        self.safe_timer = 0.0
        self.peak_fall = 0.0
        self.control = True
        # dash
        self.dash_time = 0.0
        self.dash_cooldown = 0.0
        self.dash_dir = 1
        self.air_dash = True          # one dash per time in the air
        self.ghosts = []              # [image, x, y, life] afterimages
        self.ghost_timer = 0.0
        # fast drop
        self.fast_falling = False
        # endless mode: when set, the hero always runs right at this speed (px/s)
        self.auto_run = None

    # ------------------------------------------------------------------ helpers
    @property
    def feet(self):
        return self.rect.centerx, self.rect.bottom

    @property
    def is_dead(self):
        return self.state == "dead"

    def attack_rect(self):
        if self.state != "attack" or self.attack_name is None:
            return None
        spec = ATTACKS[self.attack_name]
        t0, t1 = spec["active"]
        if not (t0 <= self.attack_time <= t1):
            return None
        ox, oy, w, h = spec["box"]
        cx, bottom = self.feet
        if self.facing > 0:
            x = cx + ox
        else:
            x = cx - ox - w
        return pygame.FRect(x, bottom + oy, w, h)

    # ------------------------------------------------------------------ update
    def update(self, dt):
        lvl = self.level
        inp = lvl.input
        self.anim.update(dt)
        self.invuln = max(0.0, self.invuln - dt)
        self.hurt_timer = max(0.0, self.hurt_timer - dt)
        self.land_timer = max(0.0, self.land_timer - dt)
        self.dash_cooldown = max(0.0, self.dash_cooldown - dt)
        self._update_ghosts(dt)

        if self.state == "dead":
            self.dead_time += dt
            self.vx *= max(0.0, 1 - 6 * dt)
            self.apply_gravity(dt)
            self.move(dt)
            return
        if self.state == "exit":
            self.vx = 0
            self.apply_gravity(dt)
            self.move(dt)
            self.anim.play("idle")
            return

        controllable = self.control and self.hurt_timer <= 0
        if self.auto_run is not None:
            move_x = 1                       # endless mode: always running forward
        else:
            move_x = inp.axis_x() if controllable else 0

        # timers
        self.coyote = max(0.0, self.coyote - dt)
        self.jump_buffer = max(0.0, self.jump_buffer - dt)
        if controllable and inp.pressed("jump"):
            self.jump_buffer = S.JUMP_BUFFER_TIME

        # ---- dash (Shift / right mouse): ground or once per jump in the air
        if (controllable and inp.pressed("dash") and self.dash_cooldown <= 0
                and self.state in ("normal", "attack") and (self.on_ground or self.air_dash)):
            self._start_dash(move_x or self.facing)
        if self.state == "dash":
            self._update_dash(dt)
            return

        # ---- horizontal movement
        target = move_x * (self.auto_run if self.auto_run is not None else S.RUN_SPEED)
        attacking = self.state == "attack"
        if attacking and self.on_ground and self.auto_run is None:
            target *= S.ATTACK_MOVE_FACTOR
        if target != 0:
            accel = S.GROUND_ACCEL if self.on_ground else S.AIR_ACCEL
        else:
            accel = S.GROUND_DECEL if self.on_ground else S.AIR_DECEL
        if self.hurt_timer > 0:
            accel = 200
        self.vx = _approach(self.vx, target, accel * dt)
        if move_x and not attacking:
            self.facing = move_x

        # ---- drop through planks: tap DOWN (or DOWN + JUMP) while standing on one
        if (controllable and self.on_ground and inp.pressed("down")
                and self._standing_on_oneway()):
            self._drop_through()

        # ---- jumping
        if self.jump_buffer > 0 and controllable:
            standing_on_oneway = self.on_ground and self._standing_on_oneway()
            if inp.held("down") and standing_on_oneway:
                self._drop_through()
                self.jump_buffer = 0
            elif self.on_ground or self.coyote > 0:
                self._jump(S.JUMP_VELOCITY)
            elif self.can_double:
                self.can_double = False
                self._jump(S.DOUBLE_JUMP_VELOCITY)
                lvl.particles.ring(self.rect.centerx, self.rect.bottom, 10, 60)
                lvl.audio.play("double_jump")
        if self.jump_held and not inp.held("jump") and self.vy < 0:
            self.vy *= S.JUMP_CUT_MULTIPLIER
            self.jump_held = False
        if self.vy >= 0:
            self.jump_held = False

        # ---- attacking
        if controllable and inp.pressed("attack"):
            if self.state == "attack":
                if self.attack_name == "attack1" and self.attack_time >= COMBO_WINDOW:
                    self.attack_queued = True
            else:
                self._start_attack("attack1")
        if self.state == "attack":
            self.attack_time += dt
            dur = self.anim.current.duration
            if self.attack_name == "attack1" and self.attack_queued and self.attack_time >= dur * 0.8:
                self._start_attack("attack2")
            elif self.attack_time >= dur:
                self.state = "normal"
                self.attack_name = None

        # ---- physics (hold DOWN in the air to fast drop)
        fast = controllable and not self.on_ground and inp.held("down")
        if fast and not self.fast_falling:
            self.vy = max(self.vy, 140.0)          # cancel upward motion straight away
            self.jump_held = False
            lvl.audio.play("swing", 0.4)
        self.fast_falling = fast
        if fast:
            self.vy = min(self.vy + S.GRAVITY * S.FAST_FALL_GRAVITY * dt, S.FAST_FALL_SPEED)
            self.ghost_timer -= dt
            if self.ghost_timer <= 0:
                self.ghost_timer = 0.05
                lvl.particles.add(self.rect.centerx + random.uniform(-5, 5), self.rect.top + 4, 0, -40, 0.15,
                                  (220, 230, 255), size=1)
        else:
            self.apply_gravity(dt)
        old_bottom = self.rect.bottom
        if self.vy > 0:
            self.peak_fall = max(self.peak_fall, self.vy)
        was_on_ground = self.move(dt)
        if self.on_ground:
            if not was_on_ground:
                self._on_land()
            self.coyote = S.COYOTE_TIME
            self.can_double = True
            self.air_dash = True
            self.fast_falling = False

        self._update_safe_point(dt)
        self._check_attack_hits()
        self._check_enemy_contacts(old_bottom)
        self._check_hazards()
        self._update_animation(dt, move_x)

    # ------------------------------------------------------------------ actions
    def _jump(self, velocity):
        self.vy = velocity
        self.on_ground = False
        self.coyote = 0
        self.jump_buffer = 0
        self.jump_held = True
        self.peak_fall = 0
        if velocity == S.JUMP_VELOCITY:
            self.level.audio.play("jump")
            self.level.particles.dust(self.rect.centerx, self.rect.bottom, 5, 30)
        self.anim.play("rise", restart=True)

    def _drop_through(self):
        self.drop_through = 0.22
        self.on_ground = False
        self.ground_platform = None
        self.rect.y += 1

    # ------------------------------------------------------------------ dash
    def _start_dash(self, direction):
        lvl = self.level
        if not self.on_ground:
            self.air_dash = False
        self.state = "dash"
        self.attack_name = None
        self.dash_dir = 1 if direction > 0 else -1
        self.facing = self.dash_dir
        self.dash_time = S.DASH_TIME
        self.vy = 0.0
        self.jump_held = False
        self.fast_falling = False
        self.ghost_timer = 0.0
        self.anim.play("dash", restart=True)
        lvl.audio.play("dash")
        if self.on_ground:
            lvl.particles.dust(self.rect.centerx - self.dash_dir * 6, self.rect.bottom, 6, 50)
        else:
            lvl.particles.ring(self.rect.centerx, self.rect.centery, 8, 40, (200, 230, 255))

    def _update_dash(self, dt):
        """Fixed-speed horizontal burst with no gravity. Jumping out of a ground dash keeps its speed."""
        lvl = self.level
        self.dash_time -= dt
        speed = S.DASH_SPEED if self.auto_run is None else max(S.DASH_SPEED, self.auto_run * 1.4)
        self.vx = self.dash_dir * speed
        self.vy = 0.0
        self.ghost_timer -= dt
        if self.ghost_timer <= 0:
            self.ghost_timer = 0.025
            img, ax, ay = self.anim.current.image(self.anim.time, self.facing)
            ghost = make_silhouette(img, (170, 215, 255))
            self.ghosts.append([ghost, self.rect.centerx - ax, self.rect.bottom - ay, 0.22])
        old_bottom = self.rect.bottom
        self.move(dt)
        grounded = self.on_ground or lvl.tilemap.solid_ground_below(self.rect.centerx, self.rect.bottom + 1, 0)
        if self.jump_buffer > 0 and grounded:
            self._end_dash(keep_speed=True)
            self._jump(S.JUMP_VELOCITY)
        elif self.hit_wall or self.dash_time <= 0:
            self._end_dash(keep_speed=not self.hit_wall)
        self._check_enemy_contacts(old_bottom)
        self._check_hazards()

    def _end_dash(self, keep_speed=True):
        self.state = "normal"
        self.dash_cooldown = S.DASH_COOLDOWN
        run = S.RUN_SPEED if self.auto_run is None else self.auto_run
        self.vx = self.dash_dir * run * (1.15 if keep_speed else 0)

    def _update_ghosts(self, dt):
        for g in self.ghosts:
            g[3] -= dt
        self.ghosts = [g for g in self.ghosts if g[3] > 0]

    def _start_attack(self, name):
        self.state = "attack"
        self.attack_name = name
        self.attack_time = 0.0
        self.attack_queued = False
        self.attack_hits = set()
        self.anim.play(name, restart=True)
        self.level.audio.play(ATTACKS[name]["sound"])

    def _standing_on_oneway(self):
        if self.ground_platform is not None:
            return True
        tm = self.level.tilemap
        ty = int((self.rect.bottom + 1) // S.TILE)
        x0 = int(self.rect.left // S.TILE)
        x1 = int((self.rect.right - 0.01) // S.TILE)
        kinds = [tm.kind(tx, ty) for tx in range(x0, x1 + 1)]
        return SOLID not in kinds and any(k != 0 for k in kinds)

    def _on_land(self):
        if self.peak_fall > 500:
            # fast-drop slam
            self.land_timer = 0.16
            self.level.particles.dust(self.rect.centerx, self.rect.bottom, 14, 90)
            self.level.audio.play("land")
            self.level.camera.shake(2, 0.12)
        elif self.peak_fall > 260:
            self.land_timer = 0.12
            self.level.particles.dust(self.rect.centerx, self.rect.bottom, 8, 50)
            self.level.audio.play("land")
        elif self.peak_fall > 120:
            self.level.particles.dust(self.rect.centerx, self.rect.bottom, 4, 30)
            self.level.audio.play("land", 0.5)
        self.peak_fall = 0

    def bounce(self, velocity=S.STOMP_BOUNCE):
        self.vy = velocity
        self.can_double = True
        self.air_dash = True
        self.fast_falling = False
        self.jump_held = self.level.input.held("jump")
        self.anim.play("rise", restart=True)

    # ------------------------------------------------------------------ combat
    def _check_attack_hits(self):
        box = self.attack_rect()
        if box is None:
            return
        spec = ATTACKS[self.attack_name]
        for enemy in self.level.enemies:
            if enemy.alive and enemy.hittable and id(enemy) not in self.attack_hits and box.colliderect(enemy.rect):
                self.attack_hits.add(id(enemy))
                enemy.take_hit(spec["damage"], self.facing, spec["push"])
        for obj in self.level.objects:
            if hasattr(obj, "on_attack") and id(obj) not in self.attack_hits and box.colliderect(obj.rect):
                self.attack_hits.add(id(obj))
                obj.on_attack(self)

    def _check_enemy_contacts(self, old_bottom):
        for enemy in self.level.enemies:
            if not enemy.alive or not self.rect.colliderect(enemy.rect):
                continue
            stomp = (self.vy > 40 and old_bottom <= enemy.rect.top + 8 and enemy.stompable)
            if stomp:
                enemy.stomp(self)
                self.rect.bottom = enemy.rect.top
                self.bounce()
                self.level.audio.play("stomp")
            elif enemy.harmful:
                self.take_damage(1, enemy.rect.centerx)

    def _check_hazards(self):
        tm = self.level.tilemap
        hazard = tm.hazard_at(self.rect)
        if hazard is not None:
            if hazard == WATER:
                self.level.particles.burst(self.rect.centerx, self.rect.bottom - 4, 14, 90,
                                           ((120, 200, 230), (200, 240, 255)), 0.5, 300)
            self.hazard_hit()
        elif self.rect.top > tm.pixel_h + 40:
            self.hazard_hit()

    def hazard_hit(self):
        """Hurt and return to the last safe ground (pits, water, spikes)."""
        if self.state == "dead":
            return
        self.health -= 1
        self.level.audio.play("hurt")
        self.level.camera.shake(4, 0.25)
        if self.health <= 0:
            self.health = 0
            self.die()
            return
        x, bottom = self.safe_pos
        self.rect.centerx = x
        self.rect.bottom = bottom
        self.vx = self.vy = 0
        self.invuln = S.PLAYER_INVULN_TIME
        self.hurt_timer = 0.3          # brief freeze so holding a direction doesn't walk straight back in
        self.state = "normal"
        self.attack_name = None
        self.level.particles.ring(x, bottom - 16, 12, 50)

    def take_damage(self, amount, source_x):
        if self.invuln > 0 or self.state in ("dead", "exit"):
            return
        self.health -= amount
        direction = 1 if self.rect.centerx >= source_x else -1
        kx, ky = S.PLAYER_KNOCKBACK
        self.vx = direction * kx
        self.vy = ky
        self.on_ground = False
        self.hurt_timer = 0.25
        self.invuln = S.PLAYER_INVULN_TIME
        if self.state in ("attack", "dash"):
            if self.state == "dash":
                self.dash_cooldown = S.DASH_COOLDOWN
            self.state = "normal"
            self.attack_name = None
        self.level.audio.play("hurt")
        self.level.camera.shake(3, 0.2)
        self.level.particles.burst(self.rect.centerx, self.rect.centery, 10, 80,
                                   ((220, 60, 50), (255, 140, 120)), 0.4, 250)
        if self.health <= 0:
            self.health = 0
            self.die()

    def heal(self, amount=1):
        if self.health >= self.max_health:
            return False
        self.health = min(self.max_health, self.health + amount)
        return True

    def die(self):
        self.state = "dead"
        self.dead_time = 0.0
        self.anim.play("dead", restart=True)
        self.level.audio.play("death")
        self.level.camera.shake(5, 0.35)

    def respawn(self, pos):
        x, bottom = pos
        self.rect.centerx = x
        self.rect.bottom = bottom
        self.vx = self.vy = 0
        self.health = self.max_health
        self.state = "normal"
        self.attack_name = None
        self.invuln = 1.5
        self.hurt_timer = 0
        self.safe_pos = pos
        self.anim.play("idle", restart=True)

    # ------------------------------------------------------------------ bookkeeping
    def _update_safe_point(self, dt):
        """Remember a solid spot to return to after falling into a hazard."""
        if not self.on_ground or self.ground_platform is not None:
            return
        self.safe_timer -= dt
        if self.safe_timer > 0:
            return
        tm = self.level.tilemap
        ty = int((self.rect.bottom + 1) // S.TILE)
        left = int((self.rect.left - 6) // S.TILE)
        right = int((self.rect.right + 6) // S.TILE)
        # only remember spots with solid ground under both feet and no hazard within 2 tiles
        if (all(tm.kind(tx, ty) == SOLID for tx in range(left, right + 1))
                and tm.hazard_at(self.rect.inflate(64, 8)) is None):
            self.safe_pos = (self.rect.centerx, self.rect.bottom)
            self.safe_timer = 0.2

    def _update_animation(self, dt, move_x):
        if self.state == "attack":
            return
        if not self.on_ground:
            self.anim.play("rise" if self.vy < 0 else "fall")
        elif self.land_timer > 0:
            self.anim.play("land")
        elif abs(self.vx) > 12 and move_x:
            self.anim.play("run")
            self.step_timer -= dt
            if self.step_timer <= 0:
                self.step_timer = 0.28
                self.level.particles.dust(self.rect.centerx - self.facing * 4, self.rect.bottom, 2, 15)
                self.level.audio.play("step", 0.35)
        else:
            self.anim.play("idle")

    # ------------------------------------------------------------------ draw
    def draw(self, surface, cam_x, cam_y):
        for img, gx, gy, life in self.ghosts:
            g = img.copy()
            g.set_alpha(int(150 * life / 0.22))
            surface.blit(g, (round(gx - cam_x), round(gy - cam_y)))
        if self.invuln > 0 and self.state != "dead" and int(self.invuln * 14) % 2 == 0:
            return
        flash = self.hurt_timer > 0.15
        x, bottom = self.feet
        self.anim.draw(surface, (x - cam_x, bottom - cam_y), self.facing, flash)


def _approach(value, target, step):
    if value < target:
        return min(value + step, target)
    return max(value - step, target)
