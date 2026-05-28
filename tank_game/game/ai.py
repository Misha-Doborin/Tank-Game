from tank_game.common import *
from tank_game.entities import Ghost, Tank


class AIMixin:
    def update_ai(self, tank, dt):
        if tank.stone_mode or tank.stone_transition > 0:
            return
        if tank.traitor_timer > 0:
            enemies = [
                t
                for t in self.tanks
                if t is not tank and t.team == tank.team and t.alive and not self.is_stone_wall(t)
            ]
        else:
            enemies = [
                t
                for t in self.tanks
                if t.team != tank.team and t.alive and not self.is_stone_wall(t)
            ]
        if not enemies:
            return

        if tank.pos.distance_squared_to(tank.ai_last_pos) < 9:
            tank.ai_stuck_timer += dt
        else:
            tank.ai_stuck_timer = max(0.0, tank.ai_stuck_timer - dt * 2)
        tank.ai_last_pos = tank.pos.copy()
        tank.ai_pressure_timer = max(0.0, tank.ai_pressure_timer - dt)

        target = self.choose_ai_target(tank, enemies)
        to_target = target.pos - tank.pos
        distance = to_target.length()

        threat = self.incoming_bullet_threat(tank)
        aim_direction = self.ai_aim_direction(tank, target)
        if aim_direction is not None and distance < 820:
            tank.direction = aim_direction
            self.try_shoot(tank)
            if tank.monster_timer > 0:
                if distance > 260:
                    self.try_fire_rocket(tank)
                elif distance < 340:
                    self.try_spray_bile(tank)
        if tank.monster_timer > 0 and tank.hp < 70 and distance < 460:
            retreat = self.cardinal_direction(tank.pos - target.pos)
            if retreat.length_squared():
                tank.direction = retreat
                self.try_monster_teleport(tank)

        powerup = self.choose_ai_powerup(tank, target)

        tank.ai_change_timer -= dt
        if threat is not None:
            tank.ai_move = self.dodge_direction(tank, threat, target)
            tank.ai_change_timer = 0.08
            tank.ai_pressure_timer = 0.45
        elif tank.ai_change_timer <= 0 or tank.ai_stuck_timer > 0.22:
            tank.ai_change_timer = random.uniform(0.16, 0.42)
            if powerup is not None:
                tank.ai_move = self.best_ai_direction(tank, pygame.Vector2(powerup.rect.center), preferred_distance=0)
            else:
                preferred_distance = 360 if tank.hp > 1 else 560
                if tank.monster_timer > 0 or target.hp <= tank.bullet_damage:
                    preferred_distance = 230
                tank.ai_move = self.best_ai_direction(tank, target.pos, preferred_distance=preferred_distance)

        moved = self.move_tank(tank, tank.ai_move, dt)
        if not moved:
            tank.ai_move = self.best_escape_direction(tank, target)
            tank.ai_change_timer = 0.06
    def choose_ai_target(self, tank, enemies):
        def score(enemy):
            distance = tank.pos.distance_to(enemy.pos)
            direction = self.cardinal_direction(enemy.pos - tank.pos)
            line_bonus = 230 if self.has_line_of_fire(tank.pos, enemy.pos, direction) else 0
            player_bonus = 110 if enemy.is_player else 0
            weak_bonus = (enemy.max_hp - enemy.hp) * 70
            dangerous_bonus = 90 if enemy.monster_timer > 0 or enemy.rapid_timer > 0 else 0
            return distance - line_bonus - player_bonus - weak_bonus - dangerous_bonus

        return min(enemies, key=score)
    def ai_aim_direction(self, tank, target):
        to_target = target.pos - tank.pos
        if to_target.length_squared() == 0:
            return None

        bullet_speed = 680 if tank.monster_timer > 0 else 560
        travel_time = min(0.7, to_target.length() / bullet_speed)
        predicted = target.pos + target.direction * target.current_speed * travel_time * 0.58

        for point in (predicted, target.pos):
            direction = self.cardinal_direction(point - tank.pos)
            if self.has_line_of_fire(tank.pos, point, direction):
                return direction
        return None
    def choose_ai_powerup(self, tank, target):
        if not self.powerups:
            return None

        best = None
        best_score = 999999
        for powerup in self.powerups:
            distance = tank.pos.distance_to(powerup.rect.center)
            if distance > 900:
                continue
            value = 120
            if powerup.kind == "repair" and tank.hp <= max(2, tank.max_hp // 2):
                value = 420
            elif powerup.kind == "shield" and tank.shield_timer <= 0:
                value = 340
            elif powerup.kind == "rapid" and tank.rapid_timer <= 0:
                value = 300
            elif powerup.kind == "monster" and tank.monster_timer <= 0:
                value = 360
            elif powerup.kind == "turbo" and tank.turbo_timer <= 0:
                value = 260
            elif powerup.kind == "army" and tank.army_timer <= 0:
                value = 330
            elif powerup.kind == "ghost" and tank.ghost_timer <= 0:
                value = 260

            if target.pos.distance_to(powerup.rect.center) < distance:
                value += 90

            score = distance - value
            if score < best_score:
                best = powerup
                best_score = score
        return best if best_score < 430 else None
    def incoming_bullet_threat(self, tank):
        best = None
        best_time = 999
        for bullet in self.bullets:
            if bullet.team == tank.team or bullet.vel.length_squared() == 0:
                continue
            direction = bullet.vel.normalize()
            to_tank = tank.pos - bullet.pos
            closing_distance = to_tank.dot(direction)
            if closing_distance <= 0 or closing_distance > 520:
                continue
            miss_distance = abs(to_tank.x * direction.y - to_tank.y * direction.x)
            danger_radius = tank.size * 0.68 + bullet.radius
            if miss_distance > danger_radius:
                continue
            time_to_hit = closing_distance / bullet.vel.length()
            if time_to_hit < best_time:
                best = bullet
                best_time = time_to_hit
        return best
    def dodge_direction(self, tank, bullet, target):
        bullet_dir = bullet.vel.normalize()
        candidates = []
        if abs(bullet_dir.x) > abs(bullet_dir.y):
            candidates = [pygame.Vector2(0, -1), pygame.Vector2(0, 1)]
        else:
            candidates = [pygame.Vector2(-1, 0), pygame.Vector2(1, 0)]
        candidates += [self.cardinal_direction(tank.pos - target.pos), self.cardinal_direction(target.pos - tank.pos)]
        return self.best_direction_from_candidates(tank, candidates, target.pos, preferred_distance=430)
    def best_ai_direction(self, tank, goal, preferred_distance=0):
        candidates = list(DIRS.values())
        random.shuffle(candidates)
        direct = self.cardinal_direction(goal - tank.pos)
        if direct in candidates:
            candidates.remove(direct)
            candidates.insert(0, direct)
        return self.best_direction_from_candidates(tank, candidates, goal, preferred_distance)
    def best_escape_direction(self, tank, target):
        candidates = list(DIRS.values())
        random.shuffle(candidates)
        return self.best_direction_from_candidates(tank, candidates, target.pos, preferred_distance=520)
    def best_direction_from_candidates(self, tank, candidates, goal, preferred_distance):
        best_direction = candidates[0] if candidates else pygame.Vector2()
        best_score = -999999
        for direction in candidates:
            if direction.length_squared() == 0:
                continue
            lookahead = max(34, tank.current_speed * 0.34)
            if not self.can_tank_step(tank, direction, lookahead):
                continue
            future = tank.pos + direction * lookahead
            distance = future.distance_to(goal)
            if preferred_distance > 0:
                score = -abs(distance - preferred_distance)
            else:
                score = -distance

            line_direction = self.cardinal_direction(goal - future)
            if self.has_line_of_fire(future, goal, line_direction):
                score += 95
            if tank.ai_pressure_timer > 0 and preferred_distance > 0:
                score += min(distance, 700) * 0.08
            score += random.uniform(-8, 8)
            if score > best_score:
                best_score = score
                best_direction = direction
        return best_direction
